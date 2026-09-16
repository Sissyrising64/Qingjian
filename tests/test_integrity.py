"""History must survive being used quickly.

Every case here is a failure that reached a real folder: the redo button stayed
lit after the branch it belonged to was gone, and sorting on the queue thread
raced undo on the interface thread over a single journal file.
"""
from __future__ import annotations

import ast
import hashlib
import json
import threading
from pathlib import Path

from base import ROOT, TempCase, unittest
from qingjian.core import config, ops, safestore
from qingjian.core.engine import Engine
from qingjian.core.safestore import TransactionError

PACKAGE = ROOT / "qingjian"


def digests(root: Path) -> dict[str, list[str]]:
    """Content -> where it lives, so a doubled file is impossible to miss."""
    out: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "app" in path.parts:
            continue
        key = hashlib.sha256(path.read_bytes()).hexdigest()
        out.setdefault(key, []).append(str(path.relative_to(root)))
    return out


class HistoryBranchTests(TempCase):
    """A new operation ends the branch that undo created."""

    def build(self, files: int = 3) -> tuple[Engine, Path, config.Binding]:
        source = self.tmp / "src"
        source.mkdir()
        for index in range(files):
            self.write(source / f"img{index}.jpg", bytes([65 + index]) * (400 + index))
        settings = config.Settings()
        settings.source_folder = str(source)
        engine = Engine(data_dir=self.tmp / "app", settings=settings)
        engine.open_folder(source)
        self.addCleanup(engine.close)
        return engine, source, config.Binding(key="1", action="move",
                                              folder=str(self.tmp / "f1"))

    def test_a_new_operation_clears_the_redo_branch(self):
        """Sort, undo, sort the same file again: there is nothing left to redo.

        Leaving the record there kept the button live, and pressing it replayed
        a move whose source had already gone somewhere else.
        """
        engine, source, binding = self.build()
        engine.classify(binding, source / "img0.jpg")
        engine.undo()
        self.assertTrue(engine.can_redo())
        engine.classify(binding, source / "img0.jpg")
        self.assertFalse(engine.can_redo())
        self.assertEqual(engine.state.counts()["redo"], 0)

    def test_the_file_is_never_in_two_places_after_that_sequence(self):
        engine, source, binding = self.build()
        engine.classify(binding, source / "img0.jpg")
        engine.undo()
        engine.classify(binding, source / "img0.jpg")
        engine.redo()
        engine.redo()
        for places in digests(self.tmp).values():
            self.assertEqual(len(places), 1, f"the same content is in {places}")

    def test_undo_then_redo_still_works_when_nothing_intervenes(self):
        """Truncating the branch must not break the ordinary case."""
        engine, source, binding = self.build()
        engine.classify(binding, source / "img0.jpg")
        engine.undo()
        self.assertTrue((source / "img0.jpg").exists())
        engine.redo()
        self.assertTrue((self.tmp / "f1" / "img0.jpg").exists())
        self.assertFalse((source / "img0.jpg").exists())

    def test_tagging_does_not_end_the_redo_branch(self):
        """Only operations that push history should truncate it."""
        engine, source, binding = self.build()
        engine.classify(binding, source / "img0.jpg")
        engine.undo()
        engine.tag([source / "img1.jpg"], rating=3)
        self.assertTrue(engine.can_redo())

    def test_dropping_the_branch_releases_its_restore_copies(self):
        """A truncated record's snapshots are deleted, not orphaned on disk.

        Replacing a file is what keeps a restore copy after undo: redo needs it
        to replace that file again.
        """
        engine, source, binding = self.build()
        self.write(self.tmp / "f1" / "img2.jpg", b"the file that gets replaced")
        engine.classify(binding, source / "img2.jpg",
                        resolver=lambda _source, _target: ops.CONFLICT_REPLACE)
        engine.undo()
        before = engine.store.usage(refresh=True)
        engine.classify(binding, source / "img0.jpg")
        after = engine.store.usage(refresh=True)
        self.assertLess(after, before)
        self.assertEqual(engine.state.counts()["redo"], 0)


class ExclusionTests(TempCase):
    """Two mutations must never be in flight at once."""

    def build(self) -> tuple[Engine, Path, config.Binding]:
        source = self.tmp / "src"
        source.mkdir()
        for index in range(8):
            self.write(source / f"img{index}.jpg", bytes([65 + index]) * 20000)
        settings = config.Settings()
        settings.source_folder = str(source)
        settings.background_queue = True
        engine = Engine(data_dir=self.tmp / "app", settings=settings)
        engine.open_folder(source)
        self.addCleanup(engine.close)
        return engine, source, config.Binding(key="1", action="move",
                                              folder=str(self.tmp / "f1"))

    def test_a_second_transaction_waits_for_the_first(self):
        """Hold one transaction open and start another; they must not overlap.

        There is one journal file. Two transactions in flight meant one thread
        renaming the temporary the other was still writing, which left a
        transaction running with nothing on disk to recover it.
        """
        engine, source, binding = self.build()
        engine.classify(binding, source / "img0.jpg")   # something to undo

        guard = threading.Lock()
        active = 0
        overlapped: list[str] = []
        inside = threading.Event()
        proceed = threading.Event()
        original = engine.store._apply

        def spy(payload, progress, save_state):
            nonlocal active
            with guard:
                active += 1
                if active > 1:
                    overlapped.append(str(payload.get("label")))
            inside.set()
            proceed.wait(3.0)
            try:
                return original(payload, progress, save_state)
            finally:
                with guard:
                    active -= 1

        engine.store._apply = spy
        self.addCleanup(setattr, engine.store, "_apply", original)

        errors: list[BaseException] = []

        def sort_one():
            try:
                engine.classify(binding, source / "img1.jpg")
            except BaseException as error:      # noqa: BLE001 - recorded
                errors.append(error)

        def undo_one():
            try:
                engine.undo()
            except BaseException as error:      # noqa: BLE001 - recorded
                errors.append(error)

        first = threading.Thread(target=sort_one)
        first.start()
        self.assertTrue(inside.wait(3.0), "the first transaction never started")
        second = threading.Thread(target=undo_one)
        second.start()
        second.join(0.4)
        self.assertTrue(second.is_alive(), "the second transaction did not wait")
        proceed.set()
        first.join(5)
        second.join(5)
        self.assertEqual(overlapped, [], "two transactions were in flight at once")
        self.assertEqual([type(e).__name__ for e in errors], [])

    def test_sorting_in_the_background_while_undoing_stays_consistent(self):
        """The queue thread and the interface thread sharing one journal.

        Before the store took a lock this raised `pending_block_write`, and the
        two threads' atomic writes clobbered each other's temporary file.
        """
        engine, source, binding = self.build()
        for path in sorted(source.iterdir()):
            engine.enqueue("sort", lambda progress, cancel, path=path:
                           engine.classify(binding, path, progress=progress, cancel=cancel),
                           {"path": str(path)})
        errors: list[str] = []
        for _ in range(20):
            try:
                if engine.can_undo():
                    engine.undo()
            except TransactionError as error:
                errors.append(str(error))
        engine.queue.wait_idle(30)
        failures = [str(job.error) for job in engine.queue.failures()]
        self.assertEqual(failures, [], "a queued operation failed")
        self.assertEqual(errors, [], "an interactive operation was refused")
        self.assertFalse(engine.store.has_pending(), "a journal was left behind")
        for places in digests(self.tmp).values():
            self.assertEqual(len(places), 1, f"the same content is in {places}")

    def test_a_mutation_started_inside_another_is_refused(self):
        """`processEvents` can dispatch a key press mid-transaction.

        A reentrant lock would wave that second operation through, because it
        arrives on the same thread as the first.
        """
        engine, source, binding = self.build()
        seen: list[str] = []

        def meddle(_message, _percent):
            if seen:
                return
            seen.append("tried")
            with self.assertRaises(TransactionError):
                engine.classify(binding, source / "img1.jpg")

        engine.classify(binding, source / "img0.jpg", progress=meddle)
        self.assertEqual(seen, ["tried"], "the progress hook never ran")
        self.assertTrue((source / "img1.jpg").exists(), "the nested move went through")


class AtomicWriteTests(TempCase):
    """The journal is one file; writing it from two threads must still work."""

    def test_concurrent_writers_do_not_destroy_each_other(self):
        target = self.tmp / "journal.json"
        errors: list[BaseException] = []

        def write(index: int) -> None:
            try:
                for round_ in range(40):
                    safestore.atomic_json(target, {"who": index, "round": round_})
            except BaseException as error:      # noqa: BLE001 - recorded, not raised
                errors.append(error)

        threads = [threading.Thread(target=write, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual([type(e).__name__ for e in errors], [])
        # Whatever landed last must still be a whole, readable document.
        self.assertIn("who", json.loads(target.read_text(encoding="utf-8")))
        leftovers = [p.name for p in self.tmp.iterdir() if p.name.endswith(".writing")]
        self.assertEqual(leftovers, [])


class TransitionCostTests(unittest.TestCase):
    """Undo must not pay the price of opening the folder again."""

    @staticmethod
    def _method(path: Path, klass: str, method: str):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == klass:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == method:
                        return item
        raise AssertionError(f"{klass}.{method} not found in {path.name}")

    @staticmethod
    def _calls(node: ast.AST) -> set[str]:
        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                owner = child.func.value
                if isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name) \
                        and owner.value.id == "self":
                    names.add(f"{owner.attr}.{child.func.attr}")
        return names

    def test_undo_and_redo_do_not_walk_the_folder(self):
        """`rescan` re-lists every file and drops every parsed header."""
        source = PACKAGE / "ui" / "mainwindow.py"
        calls = self._calls(self._method(source, "MainWindow", "_transition"))
        self.assertNotIn("engine.rescan", calls,
                         "undo re-scans the whole source folder")
        self.assertIn("engine.absorb", calls,
                      "undo no longer patches the lists from the record")

    def test_undo_waits_for_queued_sorting(self):
        tree = ast.parse((PACKAGE / "ui" / "mainwindow.py").read_text(encoding="utf-8"))
        body = ast.dump(self._method(PACKAGE / "ui" / "mainwindow.py",
                                     "MainWindow", "_transition"))
        self.assertIn("_drain_queue", body,
                      "undo can start while a queued move is still running")
        self.assertTrue(tree)


if __name__ == "__main__":
    unittest.main()


class AbsorbTests(TempCase):
    """Undo patches the lists instead of re-reading the folder."""

    _runs = 0

    def build(self, sort_mode: str = "name", count: int = 12):
        # A subTest loop builds several libraries in one test; keep them apart.
        AbsorbTests._runs += 1
        home = self.tmp / f"run{AbsorbTests._runs}"
        source = home / "src"
        source.mkdir(parents=True)
        for index in range(count):
            self.write(source / f"img{index:02d}.jpg", bytes([65 + index]) * (400 + index))
        settings = config.Settings()
        settings.source_folder = str(source)
        settings.sort_mode = sort_mode
        engine = Engine(data_dir=home / "app", settings=settings)
        engine.open_folder(source)
        self.addCleanup(engine.close)
        return engine, source, config.Binding(key="1", action="move",
                                              folder=str(home / "f1"))

    @staticmethod
    def sort_one(engine, binding, target):
        """What pressing a binding key does: drop the row, then move the file.

        Doing it any other way makes these tests pass for the wrong reason --
        the row is still in the queue, so "it came back" proves nothing.
        """
        engine.queue_paths.remove(target)
        return engine.classify(binding, target)

    def test_a_restored_file_lands_where_a_full_sort_would_put_it(self):
        engine, source, binding = self.build()
        expected = list(engine.queue_paths)
        target = source / "img05.jpg"
        self.sort_one(engine, binding, target)
        self.assertNotIn(target, engine.queue_paths)
        outcome = engine.undo()
        change = engine.absorb(outcome.record)
        self.assertIsNotNone(change)
        self.assertEqual([path for _where, path in change["added"]], [target])
        self.assertEqual(engine.queue_paths, expected)
        self.assertIn(target, engine.all_files)

    def test_the_same_holds_with_the_order_reversed(self):
        engine, source, binding = self.build()
        engine.settings.sort_reverse = True
        engine.rebuild_queue()
        expected = list(engine.queue_paths)
        target = source / "img07.jpg"
        self.sort_one(engine, binding, target)
        outcome = engine.undo()
        self.assertIsNotNone(engine.absorb(outcome.record))
        self.assertEqual(engine.queue_paths, expected)

    def test_every_sort_order_agrees_with_a_full_rebuild(self):
        """A bisect into a list sorted by another key lands anywhere.

        Sorting by rating reads the tag table, so a key built from only the
        touched file's rating scored every existing row as unrated.
        """
        for mode in ("name", "date", "modified", "size", "rating"):
            with self.subTest(mode=mode):
                engine, source, binding = self.build(sort_mode=mode)
                for index, path in enumerate(sorted(source.iterdir())):
                    engine.tag([path], rating=(index % 5) + 1)
                engine.rebuild_queue()
                expected = list(engine.queue_paths)
                target = expected[len(expected) // 2]
                self.sort_one(engine, binding, target)
                outcome = engine.undo()
                self.assertIsNotNone(engine.absorb(outcome.record))
                self.assertEqual(engine.queue_paths, expected,
                                 f"{mode} order disagrees with a full sort")

    def test_undoing_a_skip_brings_the_row_back(self):
        """The file never moved; only its place in the done list changed."""
        engine, source, _binding = self.build()
        target = source / "img02.jpg"
        engine.queue_paths.remove(target)
        engine.skip(target)
        outcome = engine.undo()
        change = engine.absorb(outcome.record)
        self.assertIsNotNone(change)
        self.assertIn(target, engine.queue_paths)

    def test_undoing_a_copy_brings_the_row_back(self):
        engine, source, _binding = self.build()
        copy = config.Binding(key="3", action="copy",
                                     folder=str(source.parent / "f3"))
        target = source / "img03.jpg"
        engine.queue_paths.remove(target)
        engine.classify(copy, target)
        outcome = engine.undo()
        self.assertIsNotNone(engine.absorb(outcome.record))
        self.assertIn(target, engine.queue_paths)
        self.assertFalse((source.parent / "f3" / "img03.jpg").exists())

    def test_an_action_that_leaves_the_file_alone_still_takes_the_row_out(self):
        """Copy, favourite and skip do not move anything; they change the list.

        Synchronous mode no longer rebuilds the queue, so absorb has to notice.
        It did not, and holding the key down copied the same photograph over
        and over while the queue never moved on.
        """
        for action in ("copy", "favorite", "skip"):
            with self.subTest(action=action):
                engine, source, _binding = self.build()
                binding = config.Binding(key="1", action=action,
                                         folder=str(source.parent / "out"))
                target = engine.queue_paths[2]
                outcome = engine.classify(binding, target)
                change = engine.absorb(outcome.record)
                self.assertIsNotNone(change, "absorb gave up and forced a rebuild")
                self.assertIn(target, [p for p in change["removed"]])
                self.assertNotIn(target, engine.queue_paths)
                self.assertTrue(target.exists(), "the original was moved, not marked")

    def test_it_agrees_with_a_full_rebuild_for_those_actions(self):
        for action in ("copy", "favorite", "skip"):
            with self.subTest(action=action):
                engine, source, _binding = self.build()
                binding = config.Binding(key="1", action=action,
                                         folder=str(source.parent / "out"))
                outcome = engine.classify(binding, engine.queue_paths[2])
                engine.absorb(outcome.record)
                patched = list(engine.queue_paths)
                engine.rebuild_queue()
                self.assertEqual(patched, engine.queue_paths)

    def test_a_file_the_filter_excludes_is_not_forced_back(self):
        """Undo restores the file, not a row the current filter rejects."""
        engine, source, binding = self.build()
        target = source / "img04.jpg"
        self.sort_one(engine, binding, target)
        engine.settings.filter_mode = "videos"
        outcome = engine.undo()
        change = engine.absorb(outcome.record)
        self.assertIsNotNone(change)
        self.assertEqual(change["added"], [])
        self.assertTrue(target.exists())

    def test_absorbing_does_not_list_the_folder(self):
        """The record already names the files; walking the tree is the cost."""
        engine, source, binding = self.build()
        engine.classify(binding, source / "img03.jpg")
        outcome = engine.undo()
        listings = []
        real = Path.iterdir

        def counted(self):
            listings.append(str(self))
            return real(self)

        Path.iterdir = counted
        try:
            self.assertIsNotNone(engine.absorb(outcome.record))
        finally:
            Path.iterdir = real
        self.assertEqual(listings, [], f"the folder was listed: {listings}")

    def test_a_sort_it_cannot_reproduce_falls_back(self):
        """Random order has no insert point, so the caller must rebuild."""
        engine, source, binding = self.build(sort_mode="random")
        engine.classify(binding, source / "img02.jpg")
        outcome = engine.undo()
        self.assertIsNone(engine.absorb(outcome.record))

    def test_review_mode_falls_back(self):
        engine, source, binding = self.build()
        engine.classify(binding, source / "img02.jpg")
        outcome = engine.undo()
        engine.set_review_mode(True)
        self.assertIsNone(engine.absorb(outcome.record))

    def test_redo_takes_the_file_back_out(self):
        engine, source, binding = self.build()
        target = source / "img04.jpg"
        self.sort_one(engine, binding, target)
        outcome = engine.undo()
        engine.absorb(outcome.record)
        self.assertIn(target, engine.queue_paths)
        outcome = engine.redo()
        change = engine.absorb(outcome.record)
        self.assertIsNotNone(change)
        self.assertNotIn(target, engine.queue_paths)
        self.assertNotIn(target, engine.all_files)

    def test_a_sidecar_does_not_add_a_second_row(self):
        """A restored raw joins the jpeg already in the queue, not beside it."""
        engine, source, binding = self.build()
        self.write(source / "img06.arw", b"raw payload")
        engine.rescan()
        before = len(engine.queue_paths)
        self.sort_one(engine, binding, source / "img06.jpg")
        outcome = engine.undo()
        engine.absorb(outcome.record)
        self.assertEqual(len(engine.queue_paths), before)


class ReentrancyGuardTests(unittest.TestCase):
    """Everything a shortcut can reach has to refuse to run mid-operation."""

    #: Handlers bound to keys that mutate the queue or the two list views.
    GUARDED = ("classify_index", "skip_current", "rename_current", "trash_current",
               "_rate_current", "_label_current", "toggle_review", "_run_operation",
               "_transition", "recover_pending", "open_folder", "rescan",
               "_rebuild_queue", "_recursive_changed", "choose_binding_folder",
               "open_bindings")

    def test_every_mutating_handler_checks_the_busy_flag(self):
        """`processEvents` dispatches buffered key presses mid-transaction.

        Hold a binding key, then press undo: the buffered presses used to reach
        straight into the queue and both views while a move was in flight.
        """
        tree = ast.parse((PACKAGE / "ui" / "mainwindow.py").read_text(encoding="utf-8"))
        unguarded = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and node.name == "MainWindow"):
                continue
            for item in node.body:
                if not isinstance(item, ast.FunctionDef) or item.name not in self.GUARDED:
                    continue
                body = ast.dump(item)
                if "_busy" not in body and "_blocked" not in body:
                    unguarded.append(item.name)
        self.assertEqual(unguarded, [], f"unguarded handlers: {unguarded}")

    def test_the_grid_stays_dirty_until_its_build_finishes(self):
        """A row inserted into a half-built grid puts it out of step for good."""
        text = (PACKAGE / "ui" / "mainwindow.py").read_text(encoding="utf-8")
        start = text.index("def _fill_grid(self)")
        body = text[start:text.index("def _decorations(self")]
        self.assertIn("_grid_building", body)
        self.assertNotIn("self._grid_dirty = False\n        paths", body,
                         "the dirty flag is cleared before the build runs")

    def test_the_strip_is_never_redrawn_with_a_partial_decoration_map(self):
        """set_paths replaces what the strip holds, so a short map wipes badges."""
        text = (PACKAGE / "ui" / "mainwindow.py").read_text(encoding="utf-8")
        for line, content in enumerate(text.splitlines(), 1):
            if "filmstrip.set_queue" in content:
                window = "\n".join(text.splitlines()[line - 1:line + 2])
                self.assertNotIn("self._decorations([path])", window,
                                 f"line {line} passes a one-file decoration map")
