"""Thin wrappers over the few genuinely platform-specific operations.

Keeping these in one place is what lets the rest of the core run (and be
tested) on a machine that is not Windows. Every function degrades to a clear
failure rather than a traceback from three layers down.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

#: Names Windows refuses regardless of extension, in any letter case.
WINDOWS_RESERVED: frozenset[str] = frozenset(
    {"con", "prn", "aux", "nul", "clock$"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
    # Windows 11 also rejects the superscript digit forms.
    | {f"com{c}" for c in "¹²³"}
    | {f"lpt{c}" for c in "¹²³"}
)

#: Characters Windows forbids in a path component.
ILLEGAL_NAME_CHARS = '<>:"/\\|?*'

#: Conservative cap. Long-path support exists but is opt-in per machine.
MAX_PATH_LENGTH = 255


class TrashUnavailable(RuntimeError):
    """The system recycle bin could not be reached."""


def _send2trash():
    try:
        from send2trash import send2trash  # type: ignore
    except Exception:  # pragma: no cover - depends on the install
        return None
    return send2trash


def trash_available() -> bool:
    return _send2trash() is not None


def move_to_trash(path: str | Path) -> None:
    """Send *path* to the platform recycle bin.

    Raises :class:`TrashUnavailable` when no backend is installed, so callers
    can fall back to the application's own restore area instead of silently
    doing nothing (the previous version swallowed this).
    """
    fn = _send2trash()
    if fn is None:
        raise TrashUnavailable("send2trash is not installed")
    fn(str(path))


def reveal(path: str | Path) -> bool:
    """Show *path* in the system file manager. Returns False if it could not."""
    target = Path(path)
    try:
        if IS_WINDOWS:
            # explorer.exe wants the odd "/select," token as one argument and
            # returns a non-zero exit code even on success, so ignore the code.
            subprocess.run(["explorer.exe", f"/select,{target}"], check=False)
            return True
        if IS_MACOS:
            subprocess.run(["open", "-R", str(target)], check=False)
            return True
        opener = shutil.which("xdg-open")
        if not opener:
            return False
        subprocess.run([opener, str(target.parent)], check=False)
        return True
    except (OSError, ValueError):
        return False


def nearest_existing(path: str | Path) -> Path:
    """Walk up from *path* until something exists. Used before a target is made."""
    current = Path(path).absolute()
    seen = 0
    while not current.exists() and current.parent != current and seen < 64:
        current = current.parent
        seen += 1
    return current


def volume_id(path: str | Path):
    """An opaque identifier for the volume holding *path*, or None.

    On Windows ``st_dev`` is the volume serial number, on POSIX the device id;
    either way two paths with the same value can be renamed between.
    """
    try:
        return nearest_existing(path).stat().st_dev
    except OSError:
        return None


def same_volume(a: str | Path, b: str | Path) -> bool:
    left = volume_id(a)
    right = volume_id(b)
    return left is not None and left == right


def free_space(path: str | Path) -> int | None:
    try:
        return shutil.disk_usage(nearest_existing(path)).free
    except OSError:
        return None


def filesystem_is_case_insensitive(path: str | Path) -> bool:
    """Probe rather than assume: a case-sensitive volume can be mounted on
    Windows, and macOS can be formatted either way."""
    base = nearest_existing(path)
    try:
        probe = base / ".qingjian-case-probe"
        alt = base / ".QINGJIAN-CASE-PROBE"
        probe.touch(exist_ok=True)
        try:
            return alt.exists()
        finally:
            probe.unlink(missing_ok=True)
    except OSError:
        return IS_WINDOWS or IS_MACOS


def path_equal(a: str | Path, b: str | Path, case_insensitive: bool | None = None) -> bool:
    if case_insensitive is None:
        case_insensitive = IS_WINDOWS or IS_MACOS
    left, right = str(a), str(b)
    if case_insensitive:
        return os.path.normcase(left).casefold() == os.path.normcase(right).casefold()
    return left == right


def is_reserved_name(name: str) -> bool:
    stem = name.split(".", 1)[0].strip().casefold()
    return stem in WINDOWS_RESERVED
