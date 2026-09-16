import zipfile

from base import TempCase, unittest
from qingjian.core import appdirs, config, logsetup, platform_
from qingjian.core.safestore import VERIFY_FAST


class ConfigTests(TempCase):
    def test_defaults_are_sane(self):
        settings = config.Settings()
        settings.ensure_profile()
        self.assertEqual(10, len(settings.bindings))
        self.assertEqual("full", settings.verification)
        self.assertTrue(settings.fast_path)
        self.assertTrue(settings.sidecar.enabled)

    def test_round_trip(self):
        settings = config.load()
        settings.language = "en"
        settings.bindings[0].folder = "/tmp/keep"
        settings.bindings[0].path_template = "{YYYY}"
        settings.verification = VERIFY_FAST
        settings.quota = settings.quota.__class__(max_operations=7)
        config.save(settings)
        again = config.load()
        self.assertEqual("en", again.language)
        self.assertEqual("/tmp/keep", again.bindings[0].folder)
        self.assertEqual(VERIFY_FAST, again.verification)
        self.assertEqual(7, again.quota.max_operations)

    def test_a_corrupt_file_is_preserved_and_defaults_are_used(self):
        appdirs.settings_path().write_text("{ nope", encoding="utf-8")
        settings = config.load()
        self.assertEqual("system", settings.language)
        self.assertTrue((self.data / "settings.broken.json").exists())

    def test_unknown_values_fall_back(self):
        settings = config.Settings.from_dict({"density": "enormous", "verification": "magic",
                                              "workers": "many", "similar_threshold": 5})
        self.assertEqual("standard", settings.density)
        self.assertEqual("full", settings.verification)
        self.assertEqual(4, settings.workers)
        self.assertLessEqual(settings.similar_threshold, 1.0)

    def test_a_short_profile_is_padded_to_ten_keys(self):
        settings = config.Settings.from_dict(
            {"profiles": {"P": [{"key": "1", "action": "move"}]}, "current_profile": "P"})
        self.assertEqual(10, len(settings.bindings))

    def test_duplicate_key_detection(self):
        settings = config.Settings()
        settings.ensure_profile()
        settings.bindings[1].key = settings.bindings[0].key
        self.assertEqual([settings.bindings[0].key], settings.duplicate_keys())

    def test_a_key_the_window_already_uses_is_reported(self):
        """Two shortcuts on one key cancel each other out, so neither fires."""
        bindings = [config.Binding(key="1"), config.Binding(key="G"),
                    config.Binding(key="space"), config.Binding(key="")]
        self.assertEqual(["G", "space"],
                         config.reserved_conflicts(bindings, ["g", "Space", "Ctrl+Z"]))

    def test_target_folders_span_every_preset(self):
        settings = config.Settings()
        settings.ensure_profile()
        settings.bindings[0].folder = str(self.tmp / "A")
        settings.profiles["Other"] = config.default_bindings()
        settings.profiles["Other"][0].folder = str(self.tmp / "B")
        folders = {p.name for p in settings.target_folders()}
        self.assertEqual({"A", "B"}, folders)

    def test_actions_that_need_a_folder(self):
        self.assertTrue(config.Binding("1", "move").needs_folder())
        self.assertFalse(config.Binding("1", "skip").needs_folder())
        self.assertTrue(config.Binding("1", "skip").is_configured())
        self.assertFalse(config.Binding("1", "move").is_configured())


class AppDirsTests(TempCase):
    def test_the_environment_override_wins(self):
        self.assertEqual(self.data, appdirs.data_dir())

    def test_subdirectories_are_created(self):
        for maker in (appdirs.store_dir, appdirs.state_dir, appdirs.cache_dir, appdirs.log_dir):
            self.assertTrue(maker().is_dir())


class LoggingTests(TempCase):
    def test_a_log_file_is_written(self):
        path = logsetup.configure(True, 3, directory=self.data / "logs")
        logsetup.get_logger("t").warning("hello %s", "world")
        self.assertIn("hello world", path.read_text(encoding="utf-8"))

    def test_logging_can_be_switched_off(self):
        self.assertIsNone(logsetup.configure(False, directory=self.data / "logs"))
        logsetup.get_logger("t").warning("nothing should be written")

    def test_the_bundle_carries_logs_and_environment_only(self):
        logsetup.configure(True, 3, directory=self.data / "logs")
        logsetup.get_logger("t").info("something")
        (self.data / "store").mkdir(exist_ok=True)
        (self.data / "store" / "journal.json").write_text("{}", encoding="utf-8")
        media = self.data / "holiday.JPG"
        media.write_bytes(b"a photograph")
        bundle = logsetup.diagnostic_bundle(self.tmp / "bundle.zip", self.data)
        names = zipfile.ZipFile(bundle).namelist()
        self.assertIn("environment.json", names)
        self.assertIn("store/journal.json", names)
        self.assertFalse(any(name.endswith(".JPG") for name in names))

    def test_the_environment_report_names_the_optional_modules(self):
        report = logsetup.environment_report()
        self.assertIn("PySide6", report["modules"])
        self.assertIn("app_version", report)


class PlatformTests(TempCase):
    def test_reserved_names(self):
        self.assertTrue(platform_.is_reserved_name("CON"))
        self.assertTrue(platform_.is_reserved_name("com1.txt"))
        self.assertFalse(platform_.is_reserved_name("common.txt"))

    def test_volume_identity(self):
        self.assertIsNotNone(platform_.volume_id(self.tmp))
        self.assertTrue(platform_.same_volume(self.tmp, self.tmp / "does" / "not" / "exist"))

    def test_free_space_is_reported(self):
        self.assertIsInstance(platform_.free_space(self.tmp), int)

    def test_nearest_existing_walks_up(self):
        self.assertEqual(self.tmp.resolve(),
                         platform_.nearest_existing(self.tmp / "a" / "b" / "c").resolve())

    def test_trash_reports_absence_instead_of_failing_quietly(self):
        if platform_.trash_available():
            self.skipTest("send2trash present")
        with self.assertRaises(platform_.TrashUnavailable):
            platform_.move_to_trash(self.write(self.tmp / "x.bin"))

    SHELL = r"Software\Classes\Directory\shell\Qingjian"
    BACKGROUND = r"Software\Classes\Directory\Background\shell\Qingjian"

    def test_the_folder_menu_opens_the_folder_that_was_clicked(self):
        registry = FakeRegistry()
        platform_.set_folder_menu(True, "Open with Qingjian", [r"C:\Apps\MediaSorter.exe"],
                                  registry=registry)
        self.assertEqual("Open with Qingjian", registry.keys[self.SHELL][""])
        self.assertEqual('"C:\\Apps\\MediaSorter.exe" "%1"',
                         registry.keys[self.SHELL + r"\command"][""])
        self.assertEqual('"C:\\Apps\\MediaSorter.exe" "%V"',
                         registry.keys[self.BACKGROUND + r"\command"][""])
        self.assertTrue(platform_.folder_menu_installed(registry=registry))

    def test_removing_the_folder_menu_leaves_nothing_behind(self):
        registry = FakeRegistry()
        platform_.set_folder_menu(True, "Open with Qingjian", [r"C:\Apps\MediaSorter.exe"],
                                  registry=registry)
        platform_.set_folder_menu(False, registry=registry)
        self.assertEqual({}, registry.keys)
        self.assertFalse(platform_.folder_menu_installed(registry=registry))
        platform_.set_folder_menu(False, registry=registry)     # a second removal is harmless

    def test_a_source_checkout_launches_without_a_console_window(self):
        folder = self.tmp / "python"
        self.write(folder / "python.exe", b"")
        self.write(folder / "pythonw.exe", b"")
        script = str(self.tmp / "main.py")
        self.assertEqual([str(folder / "pythonw.exe"), script],
                         platform_.launch_command(False, str(folder / "python.exe"), script))
        self.assertEqual([r"C:\Apps\MediaSorter.exe"],
                         platform_.launch_command(True, r"C:\Apps\MediaSorter.exe", script))


class FakeRegistry:
    """The part of winreg the folder menu touches.

    Includes the rule that matters: a key that still has subkeys cannot be
    deleted, so removal has to go leaf first.
    """

    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1

    def __init__(self) -> None:
        self.keys: dict[str, dict[str, str]] = {}

    def CreateKey(self, root, path):            # noqa: N802 - winreg naming
        self.keys.setdefault(path, {})
        return path

    def OpenKey(self, root, path):              # noqa: N802 - winreg naming
        if path not in self.keys:
            raise FileNotFoundError(path)
        return path

    def SetValueEx(self, key, name, reserved, kind, value):  # noqa: N802 - winreg naming
        self.keys[key][name] = value

    def CloseKey(self, key):                    # noqa: N802 - winreg naming
        pass

    def DeleteKey(self, root, path):            # noqa: N802 - winreg naming
        if path not in self.keys:
            raise FileNotFoundError(path)
        if any(other.startswith(path + "\\") for other in self.keys):
            raise PermissionError("a key with subkeys cannot be deleted")
        del self.keys[path]


if __name__ == "__main__":
    unittest.main()
