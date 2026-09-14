"""Where the application keeps its own data.

Resolution order, highest first:

1. ``QINGJIAN_DATA_DIR`` — used by the tests and by the diagnostic runner so a
   run can never touch a real library's history.
2. A ``qingjian-portable`` marker directory beside the executable, which makes
   a USB-stick install keep its state with it.
3. The platform's per-user application data directory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .. import __app_name__, __organization__

ENV_VAR = "QINGJIAN_DATA_DIR"
PORTABLE_MARKER = "qingjian-portable"


def _platform_data_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
        return root / __organization__ / __app_name__
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / __organization__ / __app_name__
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / __organization__.lower() / __app_name__.lower()


def executable_dir() -> Path:
    """Directory holding the running program (the bundle dir when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else Path.cwd()


def portable_dir() -> Path | None:
    try:
        candidate = executable_dir() / PORTABLE_MARKER
    except OSError:
        return None
    return candidate if candidate.is_dir() else None


def data_dir(create: bool = True) -> Path:
    override = os.environ.get(ENV_VAR)
    if override:
        root = Path(override).expanduser()
    else:
        root = portable_dir() or _platform_data_root()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def subdir(name: str, create: bool = True) -> Path:
    path = data_dir(create=create) / name
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def store_dir(create: bool = True) -> Path:
    """Transactions, snapshots and journal."""
    return subdir("store", create)


def state_dir(create: bool = True) -> Path:
    """History shards, review queues, tags, ignore lists."""
    return subdir("state", create)


def cache_dir(create: bool = True) -> Path:
    """Thumbnails and content-hash caches. Safe to delete at any time."""
    return subdir("cache", create)


def log_dir(create: bool = True) -> Path:
    return subdir("logs", create)


def settings_path() -> Path:
    return data_dir() / "settings.json"


def lock_path() -> Path:
    return data_dir() / "qingjian.lock"
