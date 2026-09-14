"""Running the same job over many files without blocking on each one.

Reading a file header, hashing it and decoding it all spend most of their time
inside the C library or waiting on the disk, and both release the interpreter
lock, so a thread pool is worth having here even though the work is CPU-bound
in the usual sense.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Sequence

from .safestore import Cancelled

Progress = Callable[[str, int], None]
Cancel = Callable[[], bool]

#: More than this gains nothing: the disk, not the processor, sets the pace.
WORKERS = max(2, min(8, (os.cpu_count() or 4)))


def _noop(message: str, percent: int) -> None:
    """Progress sink for callers that do not report."""


def _never() -> bool:
    return False


def mapped(work: Callable, items: Sequence, progress: Progress = _noop,
           cancel: Cancel = _never, workers: int = 0, first: int = 0,
           span: int = 100) -> list[tuple]:
    """Run *work* over *items*, reporting progress as results arrive.

    Results come back paired with their input, so the caller never depends on
    completion order. ``first`` and ``span`` place this pass inside a longer
    job's nought to a hundred. A raised OSError is reported as a None result
    rather than losing the whole pass for one unreadable file.
    """
    items = list(items)
    total = len(items)
    if not total:
        return []
    count = min(max(1, workers or WORKERS), total)
    out: list[tuple] = []

    # Reporting every file means the caller's progress hook -- which repaints a
    # dialog and pumps the event loop -- runs twenty thousand times on a large
    # folder. Once per step of the bar is all anyone can see.
    step = max(1, total // 100)

    def tick(item) -> None:
        done = len(out)
        if done % step and done != total:
            return
        progress(getattr(item, "name", str(item)), first + int(done * span / total))

    if count == 1:
        for item in items:
            if cancel():
                raise Cancelled("cancelled")
            try:
                out.append((item, work(item)))
            except OSError:
                out.append((item, None))
            tick(item)
        return out

    with ThreadPoolExecutor(max_workers=count, thread_name_prefix="qingjian-work") as pool:
        futures = {pool.submit(work, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            if cancel():
                for pending in futures:
                    pending.cancel()
                raise Cancelled("cancelled")
            try:
                out.append((item, future.result()))
            except OSError:
                out.append((item, None))
            tick(item)
    return out
