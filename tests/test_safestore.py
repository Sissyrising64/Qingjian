import json
import time
from pathlib import Path

from base import TempCase, unittest
from qingjian.core import safestore as ss
from qingjian.core.safestore import (Cancelled, Plan, QuotaPolicy, SafeStore, TransactionError,
                                     VERIFY_FAST, VERIFY_FULL, identity, reclaim_candidates,
                                     step_copy, step_move, step_unlink)


class StoreCase(TempCase):
    def setUp(self):
        super().setUp()
        self.src = self.tmp / "src"
        self.dst = self.tmp / "dst"
        self.src.mkdir()
        self.dst.mkdir()
        self.store = SafeStore(self.data / "store")

    def file(self, name, content=b"payload" * 100):
        return self.write(self.src / name, content)

    def move_plan(self, path, target):
        plan = Plan(forward=[step_move(path, target, identity(path))])
        plan.inverse = SafeStore.invert(plan.forward)
        return plan


class MoveTests(StoreCase):
    def test_same_volume_move_writes_no_snapshot(self):
        source = self.file("a.bin")
        plan = self.move_plan(source, self.dst / "2026" / "a.bin")
        self.assertEqual(0, plan.bytes_written())
        self.store.run(plan)
        self.assertTrue((self.dst / "2026" / "a.bin").is_file())
        self.assertFalse(source.exists())
        self.assertEqual(0, self.store.usage())

    def test_move_is_reversible_byte_for_byte(self):
        content = b"exact bytes" * 500
        source = self.file("a.bin", content)
        plan = self.move_plan(source, self.dst / "a.bin")
        self.store.run(plan)
        self.store.run(Plan(forward=plan.inverse))
        self.assertEqual(content, source.read_bytes())
        self.assertFalse((self.dst / "a.bin").exists())

    def test_cross_volume_move_copies_verifies_then_unlinks(self):
        source = self.file("a.bin")
        original = ss.same_volume
        ss.same_volume = lambda a, b: False
        try:
            plan = self.move_plan(source, self.dst / "a.bin")
            self.assertGreater(plan.bytes_written(), 0)
            self.store.run(plan)
        finally:
            ss.same_volume = original
        self.assertTrue((self.dst / "a.bin").is_file())
        self.assertFalse(source.exists())
        self.assertEqual([], [p for p in self.dst.iterdir() if p.name.startswith(".qingjian-")])

    def test_a_target_that_already_exists_is_refused(self):
        source = self.file("a.bin")
        self.write(self.dst / "a.bin", b"someone else")
        with self.assertRaises(TransactionError):
            self.store.run(self.move_plan(source, self.dst / "a.bin"))
        self.assertEqual(b"someone else", (self.dst / "a.bin").read_bytes())


class GuardTests(StoreCase):
    def test_a_file_edited_behind_our_back_stops_the_transaction(self):
        source = self.file("a.bin")
        plan = self.move_plan(source, self.dst / "a.bin")
        source.write_bytes(b"changed by another program")
        with self.assertRaises(TransactionError) as caught:
            self.store.run(plan)
        self.assertEqual("error.external_change", caught.exception.key)
        self.assertTrue(source.exists())

    def test_a_refusal_before_any_change_leaves_no_journal(self):
        """Otherwise one rejected key press blocks every later operation."""
        source = self.file("a.bin")
        plan = self.move_plan(source, self.dst / "a.bin")
        source.write_bytes(b"changed")
        with self.assertRaises(TransactionError):
            self.store.run(plan)
        self.assertFalse(self.store.has_pending())
        # And the store still works afterwards.
        self.store.run(self.move_plan(source, self.dst / "a.bin"))
        self.assertTrue((self.dst / "a.bin").is_file())

    def test_a_partial_failure_keeps_the_journal(self):
        first = self.file("a.bin")
        second = self.file("b.bin")
        stale = identity(second)
        second.write_bytes(b"changed after planning")
        plan = Plan(forward=[step_move(first, self.dst / "a.bin", identity(first)),
                             step_move(second, self.dst / "b.bin", stale)])
        with self.assertRaises(TransactionError) as caught:
            self.store.run(plan)
        self.assertEqual("error.unfinished", caught.exception.key)
        self.assertTrue(self.store.has_pending())
        self.assertTrue((self.dst / "a.bin").is_file())

    def test_symlinks_are_refused(self):
        source = self.file("a.bin")
        link = self.src / "link.bin"
        try:
            link.symlink_to(source)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(TransactionError):
            identity(link)

    def test_disk_full_is_caught_before_anything_is_written(self):
        source = self.file("a.bin", b"x" * 200000)
        original = ss.free_space
        ss.free_space = lambda path: 1024
        try:
            with self.assertRaises(TransactionError) as caught:
                self.store.run(Plan(forward=[step_copy(source, self.dst / "a.bin",
                                                       identity(source))]))
            self.assertEqual("error.disk_full", caught.exception.key)
        finally:
            ss.free_space = original
        self.assertTrue(source.exists())
        self.assertFalse((self.dst / "a.bin").exists())
        self.assertFalse(self.store.has_pending())

    def test_an_interrupted_copy_leaves_no_partial_file(self):
        source = self.file("a.bin")
        original = ss.copy_verified

        def explode(src, target, *args, **kwargs):
            Path(target).write_bytes(b"half")
            raise OSError("simulated write failure")

        ss.copy_verified = explode
        try:
            with self.assertRaises(OSError):
                self.store.run(Plan(forward=[step_copy(source, self.dst / "a.bin",
                                                       identity(source))]))
        finally:
            ss.copy_verified = original
        leftovers = [p.name for p in self.dst.iterdir()]
        self.assertEqual([], leftovers)

    def test_cancelling_before_a_write_changes_nothing(self):
        source = self.file("a.bin")
        with self.assertRaises(Cancelled):
            self.store.run(self.move_plan(source, self.dst / "a.bin"), cancel=lambda: True)
        self.assertTrue(source.exists())
        self.assertFalse(self.store.has_pending())


class RecoveryTests(StoreCase):
    def test_a_crash_between_steps_is_finished_on_restart(self):
        first = self.file("a.bin")
        second = self.file("b.bin")
        plan = Plan(forward=[step_move(first, self.dst / "a.bin", identity(first)),
                             step_move(second, self.dst / "b.bin", identity(second))])
        payload = plan.to_dict()
        payload["stage_id"] = "stage"
        ss.atomic_json(self.store.journal_path, payload)
        self.store._run_step(payload["forward"][0], VERIFY_FULL, "stage", lambda *a: None)

        restarted = SafeStore(self.data / "store")
        self.assertTrue(restarted.has_pending())
        restarted.recover()
        self.assertTrue((self.dst / "a.bin").is_file())
        self.assertTrue((self.dst / "b.bin").is_file())
        self.assertFalse(restarted.has_pending())

    def test_recovery_is_idempotent(self):
        source = self.file("a.bin")
        plan = self.move_plan(source, self.dst / "a.bin")
        self.store.run(plan)
        payload = plan.to_dict()
        payload["stage_id"] = "stage"
        ss.atomic_json(self.store.journal_path, payload)
        self.store.recover()                     # replaying a finished plan
        self.assertTrue((self.dst / "a.bin").is_file())

    def test_a_copy_that_finished_before_the_crash_is_recognised(self):
        source = self.file("a.bin")
        step = step_copy(source, self.dst / "a.bin", identity(source))
        plan = Plan(forward=[step])
        payload = plan.to_dict()
        payload["stage_id"] = "stage"
        ss.atomic_json(self.store.journal_path, payload)
        self.store._run_step(payload["forward"][0], VERIFY_FULL, "stage", lambda *a: None)
        # The journal on disk still has result=None, as it would after a crash.
        restarted = SafeStore(self.data / "store")
        restarted.recover()
        self.assertTrue((self.dst / "a.bin").is_file())
        self.assertTrue(source.exists())

    def test_state_is_committed_only_after_the_files(self):
        source = self.file("a.bin")
        committed = []
        plan = self.move_plan(source, self.dst / "a.bin")
        plan.state = {"marker": True}
        self.store.run(plan, save_state=committed.append)
        self.assertEqual([{"marker": True}], committed)

    def test_a_damaged_journal_is_not_silently_dropped(self):
        self.store.journal_path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            self.store.recover()


class DeleteAndReplaceTests(StoreCase):
    def test_delete_keeps_a_restore_copy_and_undo_puts_it_back(self):
        content = b"precious" * 200
        source = self.file("a.bin", content)
        snapshot = self.store.snapshot(source)
        step = step_unlink(source, identity(source))
        step["snapshot"] = snapshot
        plan = Plan(forward=[step])
        plan.inverse = SafeStore.invert(plan.forward)
        self.store.run(plan)
        self.assertFalse(source.exists())
        self.store.run(Plan(forward=plan.inverse))
        self.assertEqual(content, source.read_bytes())

    def test_a_damaged_restore_copy_is_refused(self):
        source = self.file("a.bin")
        snapshot = self.store.snapshot(source)
        Path(snapshot["file"]).write_bytes(b"corrupted")
        step = step_unlink(source, identity(source))
        step["snapshot"] = snapshot
        plan = Plan(forward=[step])
        plan.inverse = SafeStore.invert(plan.forward)
        self.store.run(plan)
        with self.assertRaises(TransactionError) as caught:
            self.store.run(Plan(forward=plan.inverse))
        self.assertIn(caught.exception.key, ("error.snapshot_missing", "error.unfinished"))

    def test_replacing_preserves_the_old_file_for_undo(self):
        source = self.file("a.bin", b"new content")
        target = self.write(self.dst / "a.bin", b"old content")
        snapshot = self.store.snapshot(target)
        unlink = step_unlink(target, identity(target))
        unlink["snapshot"] = snapshot
        plan = Plan(forward=[unlink, step_move(source, target, identity(source))])
        plan.inverse = SafeStore.invert(plan.forward)
        self.store.run(plan)
        self.assertEqual(b"new content", target.read_bytes())
        self.store.run(Plan(forward=plan.inverse))
        self.assertEqual(b"old content", target.read_bytes())
        self.assertEqual(b"new content", source.read_bytes())


class VerificationTests(StoreCase):
    def test_fast_mode_uses_size_and_mtime(self):
        source = self.file("a.bin")
        record = identity(source, VERIFY_FAST)
        self.assertNotIn("hash", record)
        self.assertIn("mtime_ns", record)

    def test_full_mode_records_a_hash(self):
        source = self.file("a.bin")
        self.assertIn("hash", identity(source, VERIFY_FULL))

    def test_copy_verification_detects_a_changing_source(self):
        source = self.file("a.bin", b"x" * (2 * 1024 * 1024))
        target = self.dst / "a.bin"
        real_stat = Path.stat
        calls = {"n": 0}

        class Fake:
            def __init__(self, real, bump):
                self.__dict__.update({k: getattr(real, k) for k in
                                      ("st_size", "st_mtime_ns", "st_atime_ns")})
                self.st_mtime_ns = real.st_mtime_ns + bump

        def patched(self, *args, **kwargs):
            real = real_stat(self, *args, **kwargs)
            if self == source:
                calls["n"] += 1
                if calls["n"] > 1:
                    return Fake(real, 1000)
            return real

        Path.stat = patched
        try:
            with self.assertRaises(TransactionError) as caught:
                ss.copy_verified(source, target)
            self.assertEqual("error.source_changed", caught.exception.key)
        finally:
            Path.stat = real_stat


class QuotaTests(StoreCase):
    def rows(self, ages_days, sizes=None):
        now = time.time()
        sizes = sizes or [0] * len(ages_days)
        out = []
        for age, size in zip(ages_days, sizes):
            snapshots = []
            if size:
                path = self.store.snapshot_root / f"snap{len(out)}"
                path.write_bytes(b"x" * size)
                snapshots.append(str(path))
            out.append({"time_epoch": now - age * 86400, "snapshots": snapshots})
        return out, now

    def test_age_limit(self):
        rows, now = self.rows([40, 10, 0])
        policy = QuotaPolicy(max_operations=0, max_bytes=0, max_days=30)
        self.assertEqual([0], reclaim_candidates(rows, policy, now))

    def test_count_limit_drops_the_oldest(self):
        rows, now = self.rows([5, 4, 3, 2, 1])
        policy = QuotaPolicy(max_operations=2, max_bytes=0, max_days=0)
        self.assertEqual([0, 1, 2], reclaim_candidates(rows, policy, now))

    def test_byte_limit(self):
        rows, now = self.rows([3, 2, 1], sizes=[1000, 1000, 1000])
        policy = QuotaPolicy(max_operations=0, max_bytes=1500, max_days=0)
        self.assertEqual([0, 1], reclaim_candidates(rows, policy, now))

    def test_nothing_is_dropped_inside_every_limit(self):
        rows, now = self.rows([1, 1], sizes=[10, 10])
        self.assertEqual([], reclaim_candidates(rows, QuotaPolicy(), now))

    def test_discarding_snapshots_reports_the_bytes_freed(self):
        source = self.file("a.bin", b"y" * 5000)
        snapshot = self.store.snapshot(source)
        self.assertEqual(5000, self.store.usage())
        self.assertEqual(5000, self.store.discard_snapshots([snapshot["file"]]))
        self.assertEqual(0, self.store.usage())

    def test_sweeping_partials(self):
        (self.dst / ".qingjian-abc-a.bin.part").write_bytes(b"junk")
        (self.dst / "keep.bin").write_bytes(b"keep")
        self.assertEqual(1, self.store.sweep_partials([self.dst]))
        self.assertEqual(["keep.bin"], [p.name for p in self.dst.iterdir()])


if __name__ == "__main__":
    unittest.main()
