"""The window itself, driven offscreen.

test_static stands in for these on a machine without Qt. Where PySide6 is
installed they run the real widgets, because the failures they guard -- a
double-click that filed two photographs, a key that silently did nothing --
only exist once events are flowing.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from base import ROOT, TempCase, unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QContextMenuEvent, QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
    HAVE_QT = True
except ImportError:                                     # pragma: no cover - depends on the install
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class QtCase(TempCase):
    def setUp(self):
        super().setUp()
        from qingjian.ui.app import create_app
        self.app = create_app(["qingjian-tests"])

    def patch(self, owner, name, value) -> None:
        original = getattr(owner, name)
        setattr(owner, name, value)
        self.addCleanup(setattr, owner, name, original)

    def wait_until(self, predicate, timeout: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(20)
        return bool(predicate())


class WindowCase(QtCase):
    """A real window over eight photographs, sorting synchronously."""

    def setUp(self):
        super().setUp()
        from PIL import Image
        from qingjian.core import config
        from qingjian.core.engine import Engine
        from qingjian.ui.mainwindow import MainWindow
        self.source = self.tmp / "src"
        self.source.mkdir()
        for index in range(8):
            Image.new("RGB", (320, 240), (index * 30, 90, 140)).save(
                self.source / f"IMG_{index:04d}.JPG")
        self.keep = self.tmp / "keep"
        settings = config.Settings()
        settings.background_queue = False
        settings.restore_position = False
        settings.logging_enabled = False
        settings.bindings[0].folder = str(self.keep)
        self.settings = settings
        self.engine = Engine(self.data, settings)
        self.window = MainWindow(self.engine)
        self.addCleanup(self.close_window)
        self.window.show()
        self.app.processEvents()
        self.window.open_folder(self.source)
        self.app.processEvents()

    def close_window(self) -> None:
        self.window.close()
        self.app.processEvents()

    def activate(self) -> None:
        self.window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(self.window, 2000))


class RecycleTests(WindowCase):
    def refuse_questions(self) -> list:
        asked = []

        def question(*args, **kwargs):
            asked.append(args)
            return QMessageBox.StandardButton.No

        self.patch(QMessageBox, "question", question)
        return asked

    def test_delete_recycles_at_once_and_undo_brings_it_back(self):
        asked = self.refuse_questions()
        current = self.engine.current_path()
        self.window.trash_current()
        self.app.processEvents()
        self.assertEqual([], asked)
        self.assertFalse(current.exists())
        self.window.undo()
        self.app.processEvents()
        self.assertTrue(current.exists())

    def test_recycling_a_grid_selection_asks_nothing(self):
        from qingjian.core import config
        asked = self.refuse_questions()
        self.settings.bindings[2].action = "trash"
        self.window._set_view(config.VIEW_GRID)
        self.app.processEvents()
        chosen = list(self.engine.queue_paths[:3])
        self.window.grid.select_all_paths(chosen)
        self.window.classify_index(2)
        self.app.processEvents()
        self.assertEqual([], asked)
        self.assertEqual([False, False, False], [path.exists() for path in chosen])


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class BindingCardTests(QtCase):
    def setUp(self):
        super().setUp()
        from qingjian.ui.widgets import BindingCard
        self.card = BindingCard(3)
        self.addCleanup(self.card.deleteLater)
        self.acted: list[int] = []
        self.asked: list[int] = []
        self.card.activated.connect(self.acted.append)
        self.card.folder_requested.connect(self.asked.append)

    def mouse(self, kind, buttons) -> None:
        point = QPointF(10, 10)
        QApplication.sendEvent(self.card, QMouseEvent(kind, point, point,
                                                      Qt.MouseButton.LeftButton, buttons,
                                                      Qt.KeyboardModifier.NoModifier))

    def test_a_double_click_acts_once_and_never_opens_the_folder_picker(self):
        """Qt delivers press, release, press, double-click, release.

        Both releases used to classify, so double-clicking a card to change its
        folder filed two photographs before the folder picker even opened.
        """
        self.mouse(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton)
        self.mouse(QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)
        self.mouse(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton)
        self.mouse(QEvent.Type.MouseButtonDblClick, Qt.MouseButton.LeftButton)
        self.mouse(QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)
        self.assertEqual([3], self.acted)
        self.assertEqual([], self.asked)

    def test_a_right_click_asks_for_a_folder_and_files_nothing(self):
        QApplication.sendEvent(self.card, QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                                                            QPoint(10, 10)))
        self.assertEqual([], self.acted)
        self.assertEqual([3], self.asked)


class ReservedKeyTests(WindowCase):
    def test_the_key_editor_refuses_a_key_the_window_already_uses(self):
        from qingjian.core import config
        from qingjian.ui.editors import BindingsDialog
        warned = []
        self.patch(QMessageBox, "warning", lambda *args, **kwargs: warned.append(args[2]))
        bindings = [config.Binding(key=key) for key in config.DEFAULT_KEYS]
        bindings[1].key = "G"
        dialog = BindingsDialog(bindings, [], self.window, reserved=self.window.reserved_keys())
        self.addCleanup(dialog.deleteLater)
        dialog._accept()
        self.assertNotEqual(QDialog.DialogCode.Accepted, dialog.result())
        self.assertEqual(1, len(warned))
        self.assertIn("G", warned[0])

    def test_a_saved_clash_warns_and_the_window_key_keeps_working(self):
        from qingjian.core import config
        self.settings.bindings[1].key = "G"
        self.settings.bindings[1].folder = str(self.tmp / "other")
        self.window._install_binding_shortcuts()
        self.assertIn("G", self.window.status_label.text())
        self.activate()
        QTest.keyClick(self.window, Qt.Key.Key_G)
        self.app.processEvents()
        self.assertEqual(config.VIEW_GRID, self.window.view_mode)
        self.assertEqual([], list((self.tmp / "other").glob("*")))


class SidecarPromptTests(WindowCase):
    def record_prompt(self, prompt: str) -> list[bool]:
        from qingjian.ui import mainwindow
        from qingjian.ui.dialogs import SidecarDialog
        seen: list[bool] = []

        class Recording(SidecarDialog):
            def exec(self):
                seen.append(self.remembered())
                return QDialog.DialogCode.Rejected

        self.patch(mainwindow, "SidecarDialog", Recording)
        self.settings.sidecar = self.settings.sidecar.with_prompt(prompt)
        current = self.engine.current_path()
        self.write(current.with_suffix(".CR2"), b"raw")
        self.window.classify_index(0)
        self.assertTrue(current.exists())
        return seen

    def test_ask_each_time_leaves_remember_unticked(self):
        """Ticked by default, the first answer quietly switched asking off."""
        from qingjian.core.sidecar import PROMPT_EACH
        self.assertEqual([False], self.record_prompt(PROMPT_EACH))

    def test_ask_once_still_offers_to_remember(self):
        from qingjian.core.sidecar import PROMPT_ONCE
        self.assertEqual([True], self.record_prompt(PROMPT_ONCE))


class HandledFilesTests(WindowCase):
    def test_copied_files_can_be_brought_back_from_the_status_bar(self):
        from qingjian.core import config
        self.settings.bindings[1] = config.Binding(key="2", action="copy",
                                                   folder=str(self.tmp / "copies"))
        self.window._install_binding_shortcuts()
        current = self.engine.current_path()
        self.window.classify_index(1)
        self.app.processEvents()
        self.assertNotIn(current, self.engine.queue_paths)
        self.assertTrue(self.window.handled_button.isVisible())
        self.window.handled_button.click()
        self.app.processEvents()
        self.assertIn(current, self.engine.queue_paths)
        self.assertFalse(self.window.handled_button.isVisible())


class GridSliderTests(WindowCase):
    def test_dragging_the_size_slider_rebuilds_the_grid_once(self):
        """Every tick rebuilt every row: 69 ms a tick with five thousand items."""
        edges: list[int] = []
        self.patch(self.window.grid, "set_edge", edges.append)
        for value in range(170, 230, 5):
            self.window.grid_size.setValue(value)
        self.assertEqual([], edges, "the grid was rebuilt while the slider was still moving")
        self.assertTrue(self.wait_until(lambda: edges))
        QTest.qWait(100)
        self.assertEqual([225], edges)


class HoldArrowTests(WindowCase):
    def setUp(self):
        super().setUp()
        self.activate()
        self.rendered: list[str] = []
        real = self.window.preview.show_path

        def counting(path, cached=None):
            self.rendered.append(Path(path).name)
            return real(path, cached)

        self.patch(self.window.preview, "show_path", counting)

    def right(self, press: bool = True, repeat: bool = False) -> None:
        QTest.simulateEvent(self.window, press, int(Qt.Key.Key_Right),
                            Qt.KeyboardModifier.NoModifier, "", repeat, -1)

    def test_holding_right_flips_through_without_decoding_each_picture(self):
        start = self.engine.index
        self.right()
        for _ in range(4):
            self.right(repeat=True)
        self.assertEqual(start + 5, self.engine.index)
        self.assertEqual(1, len(self.rendered), self.rendered)

    def test_letting_go_renders_the_picture_it_stopped_on(self):
        start = self.engine.index
        self.right()
        for _ in range(3):
            self.right(repeat=True)
        self.right(press=False)
        self.app.processEvents()
        self.assertEqual(start + 4, self.engine.index)
        self.assertEqual(self.engine.current_path().name, self.rendered[-1])

    def test_holding_in_the_grid_does_not_run_the_cursor_away(self):
        """The grid shows no cursor, so a held key would file a photo nobody saw."""
        from qingjian.core import config
        self.window._set_view(config.VIEW_GRID)
        start = self.engine.index
        self.right()
        for _ in range(4):
            self.right(repeat=True)
        self.right(press=False)
        self.assertEqual(start + 1, self.engine.index)


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class PreviewAudioTests(QtCase):
    """Opening the audio device costs one and a half seconds on some machines."""

    def setUp(self):
        super().setUp()
        from qingjian.ui import preview
        self.opened: list[int] = []
        real = preview.QAudioOutput

        def counting(*args):
            self.opened.append(1)
            return real(*args)

        self.patch(preview, "QAudioOutput", counting)
        self.pane = preview.MediaPreview()
        self.addCleanup(self.pane.deleteLater)

    def let_go(self, clip: Path) -> None:
        """The player closes its file asynchronously; wait so the folder can be removed."""
        self.pane.release()

        def removed() -> bool:
            try:
                clip.unlink(missing_ok=True)
            except PermissionError:
                return False
            return True

        self.wait_until(removed)

    def test_photos_never_open_the_audio_device(self):
        from PIL import Image
        photo = self.tmp / "a.jpg"
        Image.new("RGB", (64, 48)).save(photo)
        self.pane.show_path(photo)
        self.pane.toggle_mute()
        self.assertEqual([], self.opened)

    def test_the_first_video_opens_it_once_and_keeps_the_mute_setting(self):
        try:
            import av
            import numpy as np
        except ImportError:
            self.skipTest("PyAV is not installed")
        clip = self.tmp / "clip.mp4"
        container = av.open(str(clip), "w")
        stream = container.add_stream("mpeg4", rate=24)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for index in range(12):
            frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), index * 20, np.uint8),
                                               format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
        container.close()
        self.pane.toggle_mute()
        self.pane.show_path(clip)
        self.pane.show_path(clip)
        self.addCleanup(self.let_go, clip)
        self.assertEqual([1], self.opened)
        self.assertTrue(self.pane.audio.isMuted())


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class SecondLaunchTests(QtCase):
    def test_a_second_launch_hands_its_folder_to_the_running_window(self):
        """The second launch is a separate process, as it is from Explorer.

        A thread cannot stand in for it: Qt's Windows pipes finish their reads
        through the owning thread's event dispatcher, which a bare thread lacks.
        """
        from qingjian.ui import app as app_module
        name = f"qingjian-test-{uuid.uuid4().hex}"
        received: list[str] = []
        bell = app_module.Doorbell(name)
        self.addCleanup(bell.close)
        bell.arrived.connect(received.append)
        script = self.write(self.tmp / "second_launch.py", (
            "import sys\n"
            "from PySide6.QtCore import QCoreApplication\n"
            "app = QCoreApplication([])\n"
            "from qingjian.ui.app import hand_over\n"
            "print(hand_over(sys.argv[1], sys.argv[2]))\n").encode("utf-8"))
        child = subprocess.Popen([sys.executable, str(script), name, r"D:\Photos\Trip"],
                                 stdout=subprocess.PIPE, text=True,
                                 env=dict(os.environ, PYTHONPATH=str(ROOT)))
        self.addCleanup(child.kill)
        self.assertTrue(self.wait_until(lambda: child.poll() is not None, timeout=30))
        self.assertEqual("True", child.stdout.read().strip())
        self.assertEqual([r"D:\Photos\Trip"], received)

    def test_with_nobody_listening_the_hand_over_fails(self):
        from qingjian.ui import app as app_module
        self.assertFalse(app_module.hand_over(f"qingjian-test-{uuid.uuid4().hex}", "",
                                              timeout_ms=200))


@unittest.skipUnless(sys.platform == "win32", "the folder menu is a Windows feature")
class FolderMenuSettingTests(WindowCase):
    def test_turning_the_switch_on_installs_the_folder_menu(self):
        from qingjian.core import platform_
        from qingjian.ui.editors import SettingsDialog
        calls = []
        self.patch(platform_, "folder_menu_installed", lambda registry=None: False)
        self.patch(platform_, "set_folder_menu",
                   lambda enabled, *args, **kwargs: calls.append(enabled))
        dialog = SettingsDialog(self.settings, self.engine, self.window)
        self.addCleanup(dialog.deleteLater)
        dialog._controls["folder_menu"].setChecked(True)
        dialog._save()
        self.assertEqual([True], calls)

    def test_saving_without_touching_the_switch_leaves_the_registry_alone(self):
        from qingjian.core import platform_
        from qingjian.ui.editors import SettingsDialog
        calls = []
        self.patch(platform_, "folder_menu_installed", lambda registry=None: True)
        self.patch(platform_, "set_folder_menu",
                   lambda enabled, *args, **kwargs: calls.append(enabled))
        dialog = SettingsDialog(self.settings, self.engine, self.window)
        self.addCleanup(dialog.deleteLater)
        dialog._save()
        self.assertEqual([], calls)


class BaggingTests(WindowCase):
    """The copy that drops into an envelope must never cover the next print."""

    def setUp(self):
        super().setUp()
        self.window._motion = True          # the machine's own setting must not decide this

    def test_a_later_filing_never_shows_the_last_print_at_full_size(self):
        """Setting a drop's end points on the stopped animation reported a final
        frame, and the copy appeared over the next print. It takes a different
        envelope from the last drop: moving the end point is what reports it."""
        from PySide6.QtCore import QAbstractAnimation
        self.window._drop(self.window._binding_cards[1], self.window._take_off())
        self.window._fall.setCurrentTime(self.window._fall.duration())
        self.assertEqual(QAbstractAnimation.State.Stopped, self.window._fall.state())

        self.window._drop(self.window._binding_cards[2], self.window._take_off())
        self.assertFalse(self.window._flyer.isVisible())

    def test_the_copy_appears_only_once_it_is_under_half_size(self):
        flight = self.window._take_off()
        self.window._drop(self.window._binding_cards[1], flight)
        fall = self.window._fall
        fall.pause()
        fall.setCurrentTime(1)
        self.assertFalse(self.window._flyer.isVisible())
        fall.setCurrentTime(fall.duration() // 3)
        self.assertTrue(self.window._flyer.isVisible())
        self.assertLess(self.window._flyer.width(), flight[1].width() / 2)


class NoAnimationTests(WindowCase):
    """With Windows' "show animations" turned off, nothing on the counter animates."""

    def setUp(self):
        from qingjian.core import platform_
        self.patch(platform_, "animations_enabled", lambda: False)
        super().setUp()

    def test_filing_stamps_the_envelope_without_animating(self):
        from PySide6.QtCore import QAbstractAnimation
        card = self.window._binding_cards[0]
        self.window.classify_index(0)
        self.app.processEvents()
        self.assertIsNone(self.window._flyer)
        self.assertEqual(QAbstractAnimation.State.Stopped, card._stamp_animation.state())
        self.assertGreater(card._stamp, 0)

    def test_hovering_an_envelope_lifts_it_without_animating(self):
        from PySide6.QtCore import QAbstractAnimation
        from PySide6.QtGui import QEnterEvent
        card = self.window._binding_cards[0]
        point = QPointF(5, 5)
        QApplication.sendEvent(card, QEnterEvent(point, point, point))
        self.assertEqual(QAbstractAnimation.State.Stopped, card._lift_animation.state())
        self.assertEqual(1.0, card._lift)


class NarrowWindowTests(WindowCase):
    """The smallest window keeps the words that matter; a wide one gives up nothing."""

    def setUp(self):
        super().setUp()
        from qingjian.core.i18n import get_language, set_language
        self.addCleanup(set_language, get_language())
        self.window._change_language("en")          # the longer language is the harder case

    def show_at(self, width: int, height: int) -> None:
        self.window.resize(width, height)
        QTest.qWait(50)

    def test_no_row_is_squeezed_below_its_own_minimum_in_the_smallest_window(self):
        """An explicit window minimum lets Qt overlap widgets instead of growing."""
        for language in ("en", "zh"):
            with self.subTest(language=language):
                self.window._change_language(language)
                self.show_at(1180, 740)
                central = self.window.centralWidget()
                self.assertLessEqual(central.layout().minimumSize().width(), central.width())

    def test_the_last_filing_stays_readable_in_the_smallest_window(self):
        """With the long "show hidden files again" button competing for the same row."""
        from qingjian.core.i18n import tr
        self.window.handled_button.setText(tr("status.hidden_handled", count=12))
        self.window.handled_button.setVisible(True)
        self.show_at(1180, 740)
        message = tr("status.done_action", action=tr("action.move"), name="IMG_0007.JPG")
        self.window.status(message, "success")
        QTest.qWait(20)
        label = self.window.status_label
        self.assertGreaterEqual(label.width(), label.fontMetrics().horizontalAdvance(message))

    def test_the_snapshot_bar_never_shows_without_its_figures(self):
        for width in (1180, 1540, 1920):
            with self.subTest(width=width):
                self.show_at(width, 900)
                self.assertEqual(self.window.quota_label.isVisible(),
                                 self.window.quota_bar.isVisible())

    def test_a_wide_window_gives_up_nothing(self):
        from qingjian.core.i18n import tr
        self.show_at(1920, 1030)
        window = self.window
        self.assertTrue(window.preset_label.isVisible())
        self.assertTrue(window.quota_label.isVisible())
        self.assertEqual(tr("side.search_targets"), window.search_edit.placeholderText())
        self.assertEqual(tr("header.choose_folder"), window.choose_button.text())
        self.assertEqual(tr("scan.recursive"), window.recursive_check.text())


class StampsFollowTheViewTests(WindowCase):
    def test_the_rating_stars_are_on_screen_in_either_view(self):
        from qingjian.core import config
        for mode in (config.VIEW_GRID, config.VIEW_SINGLE, config.VIEW_GRID):
            with self.subTest(view=mode):
                self.window._set_view(mode)
                self.app.processEvents()
                self.assertTrue(self.window.rating.isVisible())


if __name__ == "__main__":
    unittest.main()
