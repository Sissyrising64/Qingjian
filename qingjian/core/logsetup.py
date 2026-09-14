"""Rotating run log plus a diagnostic bundle.

The previous version had no log at all: when something failed the only record
was a message box the user had already dismissed.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import platform
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from .. import __version__
from . import appdirs

LOGGER_NAME = "qingjian"
_configured = False


class _ClosingTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Flush and release the Windows file handle after every record.

    Keeping the handle open prevents temporary data directories, portable
    installs and application-data migrations from being removed on Windows.
    ``delay=True`` makes the next record reopen the same file transparently.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        finally:
            self.close()


def get_logger(name: str = "") -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def configure(enabled: bool = True, keep_days: int = 7, level: int = logging.INFO,
              directory: Path | None = None) -> Path | None:
    """Attach a rotating file handler. Safe to call more than once."""
    global _configured
    root = get_logger()
    root.setLevel(level)
    root.propagate = False
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover
            pass
    _configured = False
    if not enabled:
        root.addHandler(logging.NullHandler())
        return None

    folder = directory or appdirs.log_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "qingjian.log"
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    try:
        handler = _ClosingTimedRotatingFileHandler(
            path, when="midnight", backupCount=max(1, keep_days), encoding="utf-8", delay=True
        )
    except OSError:
        return None
    handler.setFormatter(formatter)
    root.addHandler(handler)
    if sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setLevel(logging.WARNING)
        stream.setFormatter(formatter)
        root.addHandler(stream)
    _configured = True
    root.info("logging started · version %s · %s", __version__, platform.platform())
    return path


def is_configured() -> bool:
    return _configured


def environment_report() -> dict:
    modules = {}
    for name in ("PySide6", "PIL", "numpy", "cv2", "av", "send2trash", "hachoir"):
        try:
            module = __import__(name)
            modules[name] = str(getattr(module, "__version__", "present"))
        except Exception:
            modules[name] = "missing"
    return {
        "app_version": __version__,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "data_dir": str(appdirs.data_dir(create=False)),
        "modules": modules,
    }


#: Files copied into a bundle, relative to the data directory. Media never is.
BUNDLE_INCLUDE = ("logs", "store/journal.json", "store/quota.json", "state", "settings.json")


def diagnostic_bundle(destination: str | Path, data_root: Path | None = None) -> Path:
    """Write a zip with logs, transaction metadata and environment info.

    Media files are never included; only the application's own records, which
    do contain the paths of the files that were sorted.
    """
    root = data_root or appdirs.data_dir(create=False)
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("environment.json", json.dumps(environment_report(), indent=2, ensure_ascii=False))
        for entry in BUNDLE_INCLUDE:
            source = root / entry
            if source.is_dir():
                for item in sorted(source.rglob("*")):
                    if item.is_file() and item.stat().st_size < 32 * 1024 * 1024:
                        bundle.write(item, str(Path(entry) / item.relative_to(source)))
            elif source.is_file():
                bundle.write(source, entry)
        snapshots = root / "store" / "snapshots"
        if snapshots.is_dir():
            listing = []
            for item in sorted(snapshots.iterdir()):
                try:
                    listing.append({"name": item.name, "bytes": item.stat().st_size})
                except OSError:
                    continue
            bundle.writestr("snapshots-index.json", json.dumps(listing, indent=2))
    return out
