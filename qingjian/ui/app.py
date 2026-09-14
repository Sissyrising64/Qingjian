"""Application bootstrap: one instance, one style, one window."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox

from .. import __app_name__, __display_name__, __organization__, __version__
from ..core import appdirs, config
from ..core.engine import Engine
from ..core.i18n import set_language, tr
from ..core.logsetup import get_logger
from . import icons, theme

log = get_logger("app")


def create_app(argv: list[str] | None = None) -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__display_name__)
    app.setOrganizationName(__organization__)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setWindowIcon(icons.app_icon())
    _load_fonts(app)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setStyleSheet(theme.stylesheet())
    return app


def _load_fonts(app: QApplication) -> None:
    """Offscreen Qt has no system font discovery, and some Windows installs
    lack the interface font, so register a CJK-capable face explicitly."""
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    ]
    # Register when Qt cannot discover fonts itself (offscreen) or when the
    # interface font may simply be absent (Windows installs vary).
    if app.platformName() != "offscreen" and sys.platform != "win32":
        return
    for path in candidates:
        try:
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
        except OSError:
            continue


def _parse(argv: list[str]) -> dict:
    options = {"data_dir": None, "language": "", "folder": "", "selfcheck": False,
               "version": False}
    rest = list(argv[1:])
    while rest:
        item = rest.pop(0)
        if item in ("--version", "-V"):
            options["version"] = True
        elif item == "--selfcheck":
            options["selfcheck"] = True
        elif item == "--data-dir" and rest:
            options["data_dir"] = Path(rest.pop(0))
        elif item == "--lang" and rest:
            options["language"] = rest.pop(0)
        elif not item.startswith("-"):
            options["folder"] = item
    return options


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    options = _parse(argv)
    if options["version"]:
        print(f"{__display_name__} (Qingjian) {__version__}")
        return 0
    if options["selfcheck"]:
        from ..selfcheck import run as run_selfcheck
        return run_selfcheck(argv[argv.index("--selfcheck") + 1:])

    if options["data_dir"]:
        os.environ[appdirs.ENV_VAR] = str(options["data_dir"])

    app = create_app(argv)

    # One instance per data directory: two copies sorting the same library
    # would race on the journal.
    lock = QLockFile(str(appdirs.lock_path()))
    lock.setStaleLockTime(0)
    if not lock.tryLock(50):
        QMessageBox.warning(None, __display_name__, tr("error.single_instance"))
        return 1

    settings = config.load()
    if options["language"]:
        settings.language = options["language"]
    set_language(settings.language)
    app.setStyleSheet(theme.stylesheet(settings.density))

    try:
        engine = Engine(appdirs.data_dir(), settings)
    except Exception as error:                      # pragma: no cover - startup failure
        log.exception("engine failed to start")
        QMessageBox.critical(None, __display_name__, str(error))
        lock.unlock()
        return 1

    from .mainwindow import MainWindow
    window = MainWindow(engine)
    if options["folder"] and Path(options["folder"]).is_dir():
        # Handed to the window rather than opened here: opening now would run a
        # scan (which pumps events) before exec(), letting the queued start-up
        # timer fire re-entrantly in the middle of it.
        window.startup_folder = Path(options["folder"])
    window.show()
    try:
        return app.exec()
    finally:
        lock.unlock()
