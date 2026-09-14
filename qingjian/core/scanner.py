"""Finding, filtering and ordering the files to sort."""
from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from . import mediatypes, metadata, sidecar as sidecar_mod
from .safestore import Cancelled

Progress = Callable[[str, int], None]
Cancel = Callable[[], bool]


def _noop(message: str, percent: int) -> None:
    """Progress sink for callers that do not report."""


def _never() -> bool:
    return False


FILTERS = ("all", "images", "videos", "raw", "landscape", "portrait", "square",
           "short", "animated", "rated", "unrated", "labelled")
SORTS = ("name", "date", "modified", "size", "rating", "random")

_NUMBER = re.compile(r"(\d+)")


def natural_key(path: Path) -> list:
    return [int(part) if part.isdigit() else part.casefold()
            for part in _NUMBER.split(path.name)]


def scan(root: str | Path, recursive: bool = False, excluded: Sequence[Path] = (),
         progress: Progress = _noop, cancel: Cancel = _never) -> list[Path]:
    """Every media file under *root*, skipping target trees and symlinks."""
    root = Path(root)
    blocked = []
    for item in excluded:
        try:
            blocked.append(Path(item).resolve())
        except (OSError, RuntimeError):
            continue
    found: list[Path] = []

    def is_blocked(folder: Path) -> bool:
        try:
            resolved = folder.resolve()
        except (OSError, RuntimeError):
            return True
        return any(resolved == item or resolved.is_relative_to(item) for item in blocked)

    for current, directories, names in os.walk(root, followlinks=False):
        here = Path(current)
        if recursive:
            directories[:] = [
                name for name in directories
                if not (here / name).is_symlink()
                and not name.startswith(".qingjian")
                and not is_blocked(here / name)
            ]
        else:
            directories[:] = []
        for name in names:
            if cancel():
                raise Cancelled("cancelled")
            if name.startswith(".qingjian-") and name.endswith(".part"):
                continue
            path = here / name
            if path.suffix.lower() not in mediatypes.MEDIA_EXTENSIONS:
                continue
            try:
                if path.is_symlink() or not path.is_file():
                    continue
            except OSError:
                continue
            found.append(path)
        progress(str(here), 0)
    return found


@dataclass
class FilterSpec:
    """Everything the queue can be narrowed by."""

    mode: str = "all"
    short_video_seconds: int = 60
    min_rating: int = 0
    label: str = ""
    name_pattern: str = ""
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_pixels: int = 0
    max_pixels: int = 0
    #: Paths already handled (copied, tagged) that should not reappear.
    exclude: set[str] = field(default_factory=set)
    ratings: dict[str, tuple[int, str]] = field(default_factory=dict)

    def narrows_nothing(self) -> bool:
        """True when this filter would keep every file it is shown.

        The common case by far. Recognising it lets the queue rebuild skip the
        per-file checks entirely and look only at the exclusion set.
        """
        return (self.mode == "all" and not self.name_pattern and not self.min_rating
                and not self.label and self.date_from is None and self.date_to is None
                and not self.min_pixels and not self.max_pixels)

    def compiled_pattern(self):
        if not self.name_pattern:
            return None
        try:
            return re.compile(self.name_pattern, re.IGNORECASE)
        except re.error:
            # An unfinished regex typed into a search box must not raise.
            return re.compile(re.escape(self.name_pattern), re.IGNORECASE)


def _matches(path: Path, spec: FilterSpec, pattern) -> bool:
    # One conversion, not three: this runs once per file on every rebuild.
    text = str(path)
    if text in spec.exclude:
        return False
    if pattern and not pattern.search(path.name):
        return False

    rating, label = spec.ratings.get(text, (0, ""))
    mode = spec.mode

    if mode == "rated" and rating <= 0:
        return False
    if mode == "unrated" and rating > 0:
        return False
    if mode == "labelled" and not label:
        return False
    if spec.min_rating and rating < spec.min_rating:
        return False
    if spec.label and label != spec.label:
        return False

    is_video = mediatypes.is_video(path)
    if mode == "images" and is_video:
        return False
    if mode == "videos" and not is_video:
        return False
    if mode == "raw" and not mediatypes.is_raw(path):
        return False
    if mode == "animated" and not mediatypes.may_animate(path):
        return False

    needs_info = (
        mode in ("landscape", "portrait", "square", "short")
        or spec.date_from or spec.date_to or spec.min_pixels or spec.max_pixels
    )
    if not needs_info:
        return True

    # Reading the header is enough for dimensions and dates. The previous
    # version fully decoded every image just to compare width with height.
    info = metadata.read(path)
    if mode == "landscape" and not info.is_landscape:
        return False
    if mode == "portrait" and not info.is_portrait:
        return False
    if mode == "square" and not info.is_square:
        return False
    if mode == "short":
        if not is_video or info.duration is None or info.duration > spec.short_video_seconds:
            return False
    if spec.min_pixels and info.width * info.height < spec.min_pixels:
        return False
    if spec.max_pixels and info.width * info.height > spec.max_pixels:
        return False
    if spec.date_from or spec.date_to:
        when = info.when()
        if spec.date_from and when < spec.date_from:
            return False
        if spec.date_to and when > spec.date_to:
            return False
    return True


def apply_filter(paths: Sequence[Path], spec: FilterSpec, progress: Progress = _noop,
                 cancel: Cancel = _never) -> list[Path]:
    total = max(1, len(paths))
    out: list[Path] = []
    if spec.narrows_nothing():
        # Nothing to test but "is it still there" and "has it been handled".
        exclude = spec.exclude
        for index, path in enumerate(paths):
            if cancel():
                raise Cancelled("cancelled")
            if index % 256 == 0:
                progress(path.name, int(index * 100 / total))
            if str(path) in exclude:
                continue
            try:
                if path.is_file():
                    out.append(path)
            except OSError:
                continue
        return out

    pattern = spec.compiled_pattern()
    for index, path in enumerate(paths):
        if cancel():
            raise Cancelled("cancelled")
        if index % 64 == 0:
            progress(path.name, int(index * 100 / total))
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        if _matches(path, spec, pattern):
            out.append(path)
    return out


def sort_key(mode: str = "name", ratings: dict[str, tuple[int, str]] | None = None,
             capture_time: Callable[[Path], float] | None = None):
    """The key `sort_paths` orders by, or None when the order has no key.

    Exposed so a caller that has to place one restored file can bisect into the
    list it already holds instead of sorting the whole library again.
    """
    ratings = ratings or {}
    if mode == "name":
        return natural_key
    if mode == "date":
        return capture_time or metadata.capture_time
    if mode == "modified":
        return lambda p: p.stat().st_mtime if p.exists() else 0
    if mode == "size":
        return lambda p: p.stat().st_size if p.exists() else 0
    if mode == "rating":
        return lambda p: (-ratings.get(str(p), (0, ""))[0], natural_key(p))
    return None


def sort_paths(paths: Sequence[Path], mode: str = "name", reverse: bool = False,
               ratings: dict[str, tuple[int, str]] | None = None,
               seed: int | None = None,
               capture_time: Callable[[Path], float] | None = None) -> list[Path]:
    """Order *paths*.

    ``capture_time`` lets the caller supply a cached reader. Sorting by date
    otherwise opens and parses every file in the folder, which on a library of
    twenty thousand photographs is seconds of work repeated on every change of
    filter.
    """
    items = list(paths)
    ratings = ratings or {}
    if mode == "random":
        random.Random(seed).shuffle(items)
        return items
    if mode == "name":
        items.sort(key=natural_key)
    elif mode == "date":
        items.sort(key=capture_time or metadata.capture_time)
    elif mode == "modified":
        items.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)
    elif mode == "size":
        items.sort(key=lambda p: p.stat().st_size if p.exists() else 0)
    elif mode == "rating":
        items.sort(key=lambda p: (-ratings.get(str(p), (0, ""))[0], natural_key(p)))
    if reverse:
        items.reverse()
    return items


def build_queue(paths: Sequence[Path], spec: FilterSpec, rules: sidecar_mod.SidecarRules,
                sort_mode: str = "name", reverse: bool = False,
                ratings: dict[str, tuple[int, str]] | None = None,
                progress: Progress = _noop, cancel: Cancel = _never,
                capture_time: Callable[[Path], float] | None = None) -> list[Path]:
    """Filter, collapse sidecar groups to one row each, then order."""
    kept = apply_filter(paths, spec, progress, cancel)
    collapsed = sidecar_mod.collapse_groups(kept, rules)
    return sort_paths(collapsed, sort_mode, reverse, ratings, capture_time=capture_time)
