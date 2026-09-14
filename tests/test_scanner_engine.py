from datetime import datetime

from base import TempCase, unittest
from fixtures import build_library
from qingjian.core import config, dedupe, mediatypes, scanner
from qingjian.core.engine import Engine, human_size
from qingjian.core.opqueue import Job, OperationQueue
from qingjian.core.safestore import Cancelled
from qingjian.core.sidecar import SidecarRules
from qingjian.core.state import StateStore


class ScannerTests(TempCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "lib"
        build_library(self.root)
        self.deep = scanner.scan(self.root, recursive=True)
        self.state = StateStore(self.data / "state.db")

    def tearDown(self):
        self.state.close()
        super().tearDown()

    def test_recursive_and_flat_scans_differ(self):
        self.assertEqual(0, len(scanner.scan(self.root, recursive=False)))
        self.assertGreater(len(self.deep), 10)

    def test_target_folders_are_skipped(self):
        excluded = scanner.scan(self.root, True, excluded=[self.root / "Backup"])
        self.assertNotIn("Backup", {p.parent.name for p in excluded})

    def test_non_media_is_ignored(self):
        self.assertNotIn("notes.txt", {p.name for p in self.deep})

    def test_partial_files_are_ignored(self):
        self.write(self.root / "Day3" / ".qingjian-abc-x.JPG.part", b"junk")
        self.assertNotIn(".qingjian-abc-x.JPG.part",
                         {p.name for p in scanner.scan(self.root, True)})

    def test_scanning_can_be_cancelled(self):
        with self.assertRaises(Cancelled):
            scanner.scan(self.root, True, cancel=lambda: True)

    def test_filters(self):
        expectations = {
            "images": lambda p: mediatypes.is_image(p),
            "videos": lambda p: mediatypes.is_video(p),
            "raw": lambda p: mediatypes.is_raw(p),
        }
        for mode, predicate in expectations.items():
            got = scanner.apply_filter(self.deep, scanner.FilterSpec(mode=mode))
            self.assertTrue(all(predicate(p) for p in got), mode)
            self.assertTrue(got, mode)

    def test_orientation_filters(self):
        portrait = scanner.apply_filter(self.deep, scanner.FilterSpec(mode="portrait"))
        self.assertEqual(["tall.JPG"], [p.name for p in portrait])

    def test_short_video_filter(self):
        short = scanner.apply_filter(self.deep, scanner.FilterSpec(mode="short",
                                                                   short_video_seconds=60))
        self.assertEqual(["MOV_001.MP4"], [p.name for p in short])

    def test_rating_filters(self):
        target = str(self.root / "Day4" / "solo_01.JPG")
        self.state.apply({"tags_set": [[target, 5, "green"]]})
        ratings = self.state.tags_for([str(p) for p in self.deep])
        rated = scanner.apply_filter(self.deep, scanner.FilterSpec(mode="rated", ratings=ratings))
        self.assertEqual(["solo_01.JPG"], [p.name for p in rated])
        unrated = scanner.apply_filter(self.deep,
                                       scanner.FilterSpec(mode="unrated", ratings=ratings))
        self.assertNotIn("solo_01.JPG", [p.name for p in unrated])

    def test_name_pattern(self):
        got = scanner.apply_filter(self.deep, scanner.FilterSpec(name_pattern="burst"))
        self.assertEqual(4, len(got))

    def test_an_unfinished_regex_does_not_raise(self):
        scanner.apply_filter(self.deep, scanner.FilterSpec(name_pattern="burst("))

    def test_date_range(self):
        got = scanner.apply_filter(self.deep, scanner.FilterSpec(
            date_from=datetime(2026, 8, 14, 19, 0), date_to=datetime(2026, 8, 14, 19, 50)))
        self.assertIn("IMG_5511.JPG", [p.name for p in got])
        self.assertNotIn("solo_01.JPG", [p.name for p in got])

    def test_excluded_paths_are_dropped(self):
        first = self.deep[0]
        spec = scanner.FilterSpec(exclude={str(first)})
        self.assertNotIn(first, scanner.apply_filter(self.deep, spec))

    def test_natural_sort(self):
        names = ["a10.jpg", "a2.jpg", "a1.jpg"]
        paths = [self.root / n for n in names]
        self.assertEqual(["a1.jpg", "a2.jpg", "a10.jpg"],
                         [p.name for p in scanner.sort_paths(paths, "name")])

    def test_sorting_modes_do_not_raise(self):
        for mode in scanner.SORTS:
            scanner.sort_paths(self.deep, mode, ratings={})

    def test_reverse(self):
        forward = scanner.sort_paths(self.deep, "name")
        backward = scanner.sort_paths(self.deep, "name", reverse=True)
        self.assertEqual(forward, list(reversed(backward)))

    def test_random_is_reproducible_with_a_seed(self):
        first = scanner.sort_paths(self.deep, "random", seed=5)
        second = scanner.sort_paths(self.deep, "random", seed=5)
        self.assertEqual(first, second)

    def test_build_queue_collapses_companions(self):
        queue = scanner.build_queue(self.deep, scanner.FilterSpec(), SidecarRules())
        self.assertLess(len(queue), len(self.deep))
        self.assertNotIn("IMG_5511.CR2", [p.name for p in queue])


class QueueTests(TempCase):
    def test_jobs_run_in_order(self):
        order = []
        queue = OperationQueue()
        for index in range(5):
            queue.submit(Job(run=lambda p, c, i=index: order.append(i), label=str(index)))
        self.assertTrue(queue.wait_idle(10))
        queue.stop()
        self.assertEqual([0, 1, 2, 3, 4], order)

    def test_a_failure_is_kept_and_can_be_retried(self):
        attempts = []

        def flaky(progress, cancel):
            attempts.append(1)
            if len(attempts) < 2:
                raise OSError("first attempt fails")

        queue = OperationQueue()
        queue.submit(Job(run=flaky, label="flaky"))
        queue.wait_idle(10)
        self.assertEqual(1, len(queue.failures()))
        queue.retry_failures()
        queue.wait_idle(10)
        queue.stop()
        self.assertEqual([], queue.failures())

    def test_one_failure_does_not_stop_the_rest(self):
        done = []
        queue = OperationQueue()
        queue.submit(Job(run=lambda p, c: (_ for _ in ()).throw(OSError("x"))))
        for index in range(3):
            queue.submit(Job(run=lambda p, c, i=index: done.append(i)))
        queue.wait_idle(10)
        queue.stop()
        self.assertEqual([0, 1, 2], done)

    def test_events_are_reported(self):
        seen = []
        queue = OperationQueue(on_event=lambda event, job: seen.append(event))
        queue.submit(Job(run=lambda p, c: None))
        queue.wait_idle(10)
        queue.stop()
        self.assertIn("queued", seen)
        self.assertIn("finished", seen)


class EngineTests(TempCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "lib"
        build_library(self.root)
        settings = config.Settings()
        settings.recursive = True
        self.keep = self.tmp / "Keepers"
        settings.bindings[0].folder = str(self.keep)
        settings.bindings[0].name_template = "{name}"
        settings.bindings[1].action = "copy"
        settings.bindings[1].folder = str(self.tmp / "Deliver")
        settings.bindings[1].name_template = "{name}"
        self.engine = Engine(self.data, settings)
        self.engine.open_folder(self.root)

    def tearDown(self):
        self.engine.close()
        super().tearDown()

    def test_opening_builds_a_queue(self):
        self.assertGreater(len(self.engine.all_files), 10)
        self.assertGreater(len(self.engine.queue_paths), 0)
        self.assertLess(len(self.engine.queue_paths), len(self.engine.all_files))

    def test_opening_a_missing_folder_raises(self):
        with self.assertRaises(Exception):
            self.engine.open_folder(self.tmp / "nope")

    def test_classify_move_and_undo(self):
        self.engine.go_to(self.root / "Day3" / "IMG_5511.JPG")
        outcome = self.engine.classify(self.engine.settings.bindings[0])
        self.assertEqual(4, len(outcome.record.paths))
        self.assertEqual(4, len(self.tree(self.keep)))
        self.engine.undo()
        self.assertEqual([], self.tree(self.keep))

    def test_copy_marks_the_original_handled_and_hides_it(self):
        source = self.root / "Day4" / "solo_01.JPG"
        self.engine.go_to(source)
        self.engine.classify(self.engine.settings.bindings[1])
        self.engine.rebuild_queue()
        self.assertNotIn(source, self.engine.queue_paths)

    def test_the_cursor_survives_a_rebuild(self):
        self.engine.go_to(self.root / "Day4" / "solo_02.JPG")
        current = self.engine.current_path()
        self.engine.rebuild_queue()
        self.assertEqual(current, self.engine.current_path())

    def test_stepping_wraps_around(self):
        self.engine.index = len(self.engine.queue_paths) - 1
        self.engine.step(1)
        self.assertEqual(0, self.engine.index)

    def test_review_mode(self):
        source = self.root / "Day4" / "solo_03.JPG"
        self.engine.go_to(source)
        self.engine.skip()
        self.engine.rebuild_queue()
        self.assertNotIn(source, self.engine.queue_paths)
        self.engine.set_review_mode(True)
        self.assertEqual([source], self.engine.queue_paths)
        self.engine.set_review_mode(False)

    def test_filters_change_the_queue(self):
        self.engine.settings.filter_mode = "videos"
        self.engine.rebuild_queue()
        self.assertTrue(all(mediatypes.is_video(p) for p in self.engine.queue_paths))
        self.engine.settings.filter_mode = "all"
        self.engine.rebuild_queue()

    def test_tagging(self):
        target = self.engine.current_path()
        self.engine.tag([target], rating=4, label="green")
        self.assertEqual((4, "green"), self.engine.state.tag(str(target)))

    def test_a_tag_follows_a_rename(self):
        target = self.root / "Day4" / "solo_01.JPG"
        self.engine.tag([target], rating=5)
        self.engine.rename("renamed.JPG", target)
        self.assertEqual((5, ""), self.engine.state.tag(str(target.with_name("renamed.JPG"))))

    def test_duplicate_modes(self):
        for mode in (dedupe.MODE_EXACT, dedupe.MODE_SIMILAR, dedupe.MODE_BURST):
            groups = self.engine.find_duplicates(mode)
            self.assertIsInstance(groups, list)
        self.assertEqual(1, len(self.engine.find_duplicates(dedupe.MODE_EXACT)))

    def test_ignoring_and_restoring_duplicates(self):
        groups = self.engine.find_duplicates(dedupe.MODE_EXACT)
        self.engine.ignore_duplicates(groups[0].extras)
        self.assertEqual([], self.engine.find_duplicates(dedupe.MODE_EXACT))
        self.engine.restore_ignored()
        self.assertEqual(1, len(self.engine.find_duplicates(dedupe.MODE_EXACT)))

    def test_ignoring_never_touches_a_file(self):
        groups = self.engine.find_duplicates(dedupe.MODE_EXACT)
        extra = groups[0].extras[0]
        before = extra.path.read_bytes()
        self.engine.ignore_duplicates([extra])
        self.assertEqual(before, extra.path.read_bytes())

    def test_reclaim_retires_the_oldest_records(self):
        self.engine.settings.quota = self.engine.settings.quota.__class__(
            max_operations=0, max_bytes=1, max_days=0, automatic=False)
        self.engine.go_to(self.root / "Day3" / "IMG_5511.JPG")
        self.engine.trash()
        self.assertGreater(self.engine.backup_usage(), 0)
        freed, retired = self.engine.reclaim(force=True)
        self.assertGreater(freed, 0)
        self.assertEqual(1, retired)
        self.assertFalse(self.engine.can_undo())

    def test_clearing_backups(self):
        self.engine.go_to(self.root / "Day3" / "IMG_5511.JPG")
        self.engine.trash()
        self.engine.clear_backups()
        self.assertEqual(0, self.engine.backup_usage())
        self.assertFalse(self.engine.can_undo())

    def test_statistics_and_export(self):
        self.engine.go_to(self.root / "Day4" / "solo_01.JPG")
        self.engine.classify(self.engine.settings.bindings[0])
        rows = self.engine.statistics()
        self.assertTrue(any(row[0] for row in rows))
        out = self.engine.export_csv(self.tmp / "records.csv")
        text = out.read_text(encoding="utf-8-sig")
        self.assertIn("solo_01.JPG", text)

    def test_csv_export_defuses_formula_injection(self):
        tricky = self.root / "Day4" / "=cmd.JPG"
        (self.root / "Day4" / "solo_01.JPG").rename(tricky)
        self.engine.rescan()
        self.engine.go_to(tricky)
        self.engine.classify(self.engine.settings.bindings[0])
        text = self.engine.export_csv(self.tmp / "r.csv").read_text(encoding="utf-8-sig")
        self.assertNotIn(",=", text.replace(",='", ",X"))

    def test_info_rows(self):
        rows = self.engine.info_rows(self.root / "Day3" / "IMG_5511.JPG")
        labels = [row[0] for row in rows]
        self.assertTrue(any("Sony" in row[1] for row in rows))
        self.assertEqual(len(labels), len(rows))

    def test_diagnostic_bundle_has_no_media(self):
        import zipfile
        bundle = self.engine.diagnostic_bundle(self.tmp / "b.zip")
        names = zipfile.ZipFile(bundle).namelist()
        self.assertIn("environment.json", names)
        self.assertFalse(any(name.endswith(".JPG") for name in names))

    def test_recover_is_a_no_op_when_nothing_is_pending(self):
        self.assertFalse(self.engine.has_pending())
        self.assertFalse(self.engine.recover())

    def test_settings_changes_reach_the_store(self):
        settings = self.engine.settings
        settings.fast_path = False
        settings.verification = "fast"
        self.engine.apply_settings(settings)
        self.assertFalse(self.engine.store.fast_path)
        self.assertEqual("fast", self.engine.store.verify)

    def test_human_size(self):
        self.assertEqual("512 B", human_size(512))
        self.assertEqual("1.0 KB", human_size(1024))
        self.assertEqual("1.0 GB", human_size(1024 ** 3))


if __name__ == "__main__":
    unittest.main()
