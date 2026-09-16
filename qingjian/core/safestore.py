"""Durable, content-checked file transactions.

Model
-----
A :class:`Plan` is an ordered list of steps plus the ready-made inverse list
that undoes them. The journal is written, fsynced and closed *before* the first
user file is touched, so an interrupted run always leaves enough on disk to
finish or to reverse.

Every step is idempotent: it first asks "is this already the case?" and returns
if so. That is what makes crash recovery a simple replay rather than a guess.

Why there is a fast path
------------------------
The previous engine expressed a move as "snapshot both ends, copy the content
to the target, verify it, delete the source". Moving a 5 GB video therefore
read and wrote roughly 15 GB and left a 5 GB restore copy behind. When source
and target sit on one volume a move is a directory-entry change: ``os.replace``
is atomic, needs no copy, and is undone by replacing back. Hashing exists to
prove a *copy* is faithful; a rename has no copy to prove, so the fast path
verifies identity by size and mtime and is still safe.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .logsetup import get_logger
from .platform_ import free_space, hide, same_volume

log = get_logger("safestore")

Progress = Callable[[str, int], None]
Cancel = Callable[[], bool]

BLOCK = 1024 * 1024

#: Where a recycled file waits: a hidden folder beside the one it came from.
#: Getting there is a rename on the same disk -- instant, undone by renaming
#: back -- where a restore copy in the application's own folder meant copying
#: every recycled video onto the system drive.
TRASH_DIR = ".qingjian-trash"

# ``os.replace`` is atomic for readers, but Windows can briefly reject two
# concurrent replacements of the same destination with ``PermissionError``.
# Journal writes are tiny; serialize them in-process while retaining unique
# temporary names so a failed writer can only clean up its own file.
_ATOMIC_JSON_LOCK = threading.RLock()

VERIFY_FULL = "full"
VERIFY_FAST = "fast"

# step kinds
MOVE = "move"
COPY = "copy"
WRITE = "write"
UNLINK = "unlink"

def _NOOP_PROGRESS(message: str, percent: int) -> None:
    """Progress sink used when a caller does not care."""


def _NEVER() -> bool:
    """Cancellation probe that never cancels."""
    return False


class Cancelled(Exception):
    """The user stopped the operation before any file was changed."""


class TransactionError(OSError):
    """Carries an i18n key in :attr:`key` alongside the plain message."""

    def __init__(self, key: str, message: str = "", **fields: object) -> None:
        super().__init__(message or key)
        self.key = key
        self.fields = fields


# ---------------------------------------------------------------- utilities


def atomic_json(path: str | Path, value: object) -> None:
    """Write JSON so that a crash leaves either the old file or the new one.

    The temporary carries a unique suffix. A shared one meant two threads
    writing the same journal raced: the first ``os.replace`` moved the file the
    second was still writing, and that second write then failed with
    FileNotFoundError, leaving a transaction running with no journal at all.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}-{uuid.uuid4().hex}.writing")
    with _ATOMIC_JSON_LOCK:
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise


def read_json(path: str | Path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    # A damaged file is never silently replaced with an empty one; the caller
    # decides, because throwing history away is worse than refusing to start.
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(path: str | Path, progress: Progress = _NOOP_PROGRESS,
                cancel: Cancel = _NEVER) -> str | None:
    """SHA-256 of *path*, or None when it does not exist."""
    path = Path(path)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise TransactionError("error.not_regular_file", str(path), path=str(path))
    digest = hashlib.sha256()
    size = path.stat().st_size
    done = 0
    with path.open("rb") as stream:
        while block := stream.read(BLOCK):
            if cancel():
                raise Cancelled("cancelled")
            digest.update(block)
            done += len(block)
            progress(f"{path.name}", int(done * 100 / max(1, size)))
    return digest.hexdigest()


#: How much of each end of a file the cheap prefilter reads.
SAMPLE = 64 * 1024


def sample_digest(path: str | Path) -> str | None:
    """A digest of the size plus the first and last :data:`SAMPLE` bytes.

    Two byte-identical files always agree on this, so it never hides a
    duplicate; files that merely share a size almost never agree, so the
    duplicate scan can skip reading them in full. On a library of raw files or
    video that is the difference between reading a few megabytes and reading
    every byte on the disk.
    """
    path = Path(path)
    try:
        size = path.stat().st_size
        digest = hashlib.sha256(str(size).encode("ascii"))
        with path.open("rb") as stream:
            digest.update(stream.read(SAMPLE))
            if size > 2 * SAMPLE:
                stream.seek(-SAMPLE, os.SEEK_END)
                digest.update(stream.read(SAMPLE))
    except OSError:
        return None
    return digest.hexdigest()


def identity(path: str | Path, verify: str = VERIFY_FULL,
             progress: Progress = _NOOP_PROGRESS, cancel: Cancel = _NEVER) -> dict | None:
    """Describe the current content of *path*, or None when absent."""
    path = Path(path)
    try:
        stat = path.stat()
    except (OSError, ValueError):
        return None
    if path.is_symlink() or not path.is_file():
        raise TransactionError("error.symlink" if path.is_symlink() else "error.not_regular_file",
                               str(path), path=str(path))
    record = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if verify == VERIFY_FULL:
        record["hash"] = fingerprint(path, progress, cancel)
    return record


def identity_matches(path: str | Path, expected: dict | None, verify: str = VERIFY_FULL,
                     progress: Progress = _NOOP_PROGRESS, cancel: Cancel = _NEVER) -> bool:
    """Does *path* currently hold the content described by *expected*?"""
    path = Path(path)
    exists = path.exists()
    if expected is None:
        return not exists
    if not exists:
        return False
    try:
        stat = path.stat()
    except OSError:
        return False
    if expected.get("size") is not None and stat.st_size != expected["size"]:
        return False
    want_hash = expected.get("hash")
    if want_hash and verify == VERIFY_FULL:
        return fingerprint(path, progress, cancel) == want_hash
    want_mtime = expected.get("mtime_ns")
    if want_mtime is not None:
        return stat.st_mtime_ns == want_mtime
    return True


def copy_verified(source: str | Path, target: str | Path, progress: Progress = _NOOP_PROGRESS,
                  cancel: Cancel = _NEVER, verify: str = VERIFY_FULL) -> dict:
    """Copy *source* to a fresh *target* and prove the copy is faithful."""
    source, target = Path(source), Path(target)
    before = source.stat()
    total = before.st_size
    digest = hashlib.sha256()
    done = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as inp, target.open("xb") as out:
        while block := inp.read(BLOCK):
            if cancel():
                raise Cancelled("cancelled")
            out.write(block)
            digest.update(block)
            done += len(block)
            progress(source.name, int(done * 100 / max(1, total)))
        out.flush()
        os.fsync(out.fileno())
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise TransactionError("error.source_changed", str(source), path=str(source))
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    value = digest.hexdigest()
    if verify == VERIFY_FULL and fingerprint(target, progress, cancel) != value:
        raise TransactionError("error.copy_verify", str(target), path=str(target))
    stat = target.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "hash": value}


# ------------------------------------------------------------------- plans


def step_move(src: str | Path, dst: str | Path, src_id: dict, result: dict | None = None) -> dict:
    return {"kind": MOVE, "src": str(src), "dst": str(dst), "src_id": src_id,
            "result": result or dict(src_id)}


def step_copy(src: str | Path, dst: str | Path, src_id: dict) -> dict:
    return {"kind": COPY, "src": str(src), "dst": str(dst), "src_id": src_id, "result": None}


def step_write(dst: str | Path, snapshot: dict, expect: dict | None) -> dict:
    return {"kind": WRITE, "dst": str(dst), "snapshot": snapshot, "expect": expect,
            "result": {"size": snapshot.get("size"), "hash": snapshot.get("hash")}}


def step_unlink(path: str | Path, expect: dict | None) -> dict:
    return {"kind": UNLINK, "dst": str(path), "expect": expect, "result": None}


@dataclass
class Plan:
    """A forward step list, its inverse, and the app state to commit with it."""

    forward: list[dict] = field(default_factory=list)
    inverse: list[dict] = field(default_factory=list)
    state: dict | None = None
    verify: str = VERIFY_FULL
    label: str = ""
    #: Snapshots this plan created, so a rollback can delete them again.
    snapshots: list[str] = field(default_factory=list)

    def bytes_written(self) -> int:
        total = 0
        for step in self.forward:
            if step["kind"] == COPY:
                total += int((step.get("src_id") or {}).get("size") or 0)
            elif step["kind"] == WRITE:
                total += int((step.get("snapshot") or {}).get("size") or 0)
            elif step["kind"] == MOVE:
                # Counted only when the two ends sit on different volumes.
                if not same_volume(step["src"], Path(step["dst"]).parent):
                    total += int((step.get("src_id") or {}).get("size") or 0)
        return total

    def targets(self) -> list[str]:
        return [step["dst"] for step in self.forward]

    def to_dict(self) -> dict:
        return {"forward": self.forward, "inverse": self.inverse, "state": self.state,
                "verify": self.verify, "label": self.label, "snapshots": self.snapshots}

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        return cls(forward=list(data.get("forward") or []),
                   inverse=list(data.get("inverse") or []),
                   state=data.get("state"),
                   verify=str(data.get("verify") or VERIFY_FULL),
                   label=str(data.get("label") or ""),
                   snapshots=list(data.get("snapshots") or []))


@dataclass(frozen=True)
class QuotaPolicy:
    """Limits past which the oldest restore copies are reclaimed."""

    max_operations: int = 200
    max_bytes: int = 20 * 1024 ** 3
    max_days: int = 30
    #: Reclaim without asking once a limit is passed.
    automatic: bool = True

    def to_dict(self) -> dict:
        return {"max_operations": self.max_operations, "max_bytes": self.max_bytes,
                "max_days": self.max_days, "automatic": self.automatic}

    @classmethod
    def from_dict(cls, data: dict | None) -> "QuotaPolicy":
        if not isinstance(data, dict):
            return cls()
        def positive(key: str, default: int) -> int:
            try:
                value = int(data.get(key, default))
            except (TypeError, ValueError):
                return default
            return max(0, value)
        return cls(positive("max_operations", 200),
                   positive("max_bytes", 20 * 1024 ** 3),
                   positive("max_days", 30),
                   bool(data.get("automatic", True)))


# ------------------------------------------------------------------- store


class SafeStore:
    """Owns the journal, the snapshot area and the transaction executor."""

    def __init__(self, root: str | Path, quota: QuotaPolicy | None = None,
                 verify: str = VERIFY_FULL, fast_path: bool = True) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.root / "journal.json"
        self.snapshot_root = self.root / "snapshots"
        self.snapshot_root.mkdir(exist_ok=True)
        self.quota = quota or QuotaPolicy()
        self.verify = verify
        self.fast_path = fast_path
        # Walking the restore area is a stat per snapshot; the status bar asks
        # for it after every operation, so the answer is remembered until a
        # snapshot is actually written or reclaimed.
        self._usage: int | None = None
        # There is one journal file, so there can be one transaction. Sorting
        # runs on the queue thread while undo and redo ran straight off the
        # interface thread, and the two then fought over that file: whoever
        # renamed it first left the other writing into nothing.
        self._lock = threading.RLock()
        # Recycle folders live beside the user's files, so the usage total can
        # only find them again after a restart if it keeps a list of them.
        self.trash_index = self.root / "trash-folders.json"
        self._trash_lock = threading.Lock()
        try:
            self._trash_folders: set[str] = set(read_json(self.trash_index, []) or [])
        except ValueError:
            self._trash_folders = set()
        self._sweep_writing()

    def _sweep_writing(self) -> None:
        """Drop half-written journals left by a kill during atomic_json."""
        try:
            for item in self.root.iterdir():
                if item.name.endswith(".writing"):
                    item.unlink(missing_ok=True)
        except OSError:
            pass

    # -- pending -------------------------------------------------------
    def has_pending(self) -> bool:
        return self.journal_path.exists()

    def pending_plan(self) -> Plan | None:
        if not self.has_pending():
            return None
        return Plan.from_dict(read_json(self.journal_path, {}) or {})

    # -- snapshots -----------------------------------------------------
    def snapshot(self, path: str | Path, progress: Progress = _NOOP_PROGRESS,
                 cancel: Cancel = _NEVER) -> dict | None:
        """Copy *path* into the restore area. None when the file is absent."""
        path = Path(path)
        if not path.exists():
            return None
        target = self.snapshot_root / uuid.uuid4().hex
        try:
            info = copy_verified(path, target, progress, cancel, self.verify)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        if self._usage is not None:
            self._usage += int(info["size"])
        return {"file": str(target), "hash": info.get("hash"), "size": info["size"]}

    def trash_slot(self, path: str | Path) -> Path | None:
        """A free name for *path* in the hidden recycle folder beside it.

        None when that folder cannot be made there -- a file in the way, no
        rights -- or the name would be too long; the caller then keeps a restore
        copy instead.
        """
        path = Path(path)
        slot = path.parent / TRASH_DIR / (uuid.uuid4().hex + path.suffix)
        if len(str(slot)) > 259:
            return None
        try:
            self._prepare_trash_folder(slot.parent)
        except OSError:
            return None
        return slot

    def _prepare_trash_folder(self, folder: Path) -> None:
        if not folder.is_dir():
            folder.mkdir(parents=True)
            hide(folder)
        with self._trash_lock:
            if str(folder) in self._trash_folders:
                return
            self._trash_folders.add(str(folder))
            atomic_json(self.trash_index, sorted(self._trash_folders))

    def usage(self, refresh: bool = False) -> int:
        if self._usage is not None and not refresh:
            return self._usage
        with self._trash_lock:
            folders = [self.snapshot_root, *map(Path, self._trash_folders)]
        total = 0
        for folder in folders:
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        try:
                            if entry.is_file(follow_symlinks=False):
                                total += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            continue
            except OSError:
                continue
        self._usage = total
        return total

    def discard_snapshots(self, refs: Iterable[str]) -> int:
        freed = 0
        for ref in refs:
            path = Path(ref)
            if not path.is_file():
                continue
            try:
                freed += path.stat().st_size
                path.unlink()
            except OSError:
                continue
            if path.parent.name == TRASH_DIR:
                self._drop_trash_folder_if_empty(path.parent)
        if self._usage is not None:
            self._usage = max(0, self._usage - freed)
        return freed

    def _drop_trash_folder_if_empty(self, folder: Path) -> None:
        try:
            folder.rmdir()                  # refuses while anything is left in it
        except OSError:
            return
        with self._trash_lock:
            self._trash_folders.discard(str(folder))
            atomic_json(self.trash_index, sorted(self._trash_folders))

    def _count_recycled(self, src: Path, dst: Path, identity_: dict | None) -> None:
        """Keep the usage total right as files go into and out of a recycle folder."""
        if self._usage is None:
            return
        size = int((identity_ or {}).get("size") or 0)
        if dst.parent.name == TRASH_DIR:
            self._usage += size
        elif src.parent.name == TRASH_DIR:
            self._usage = max(0, self._usage - size)

    # -- executing -----------------------------------------------------
    def run(self, plan: Plan, progress: Progress = _NOOP_PROGRESS,
            cancel: Cancel = _NEVER, save_state: Callable[[dict], None] | None = None) -> None:
        """Journal *plan*, apply it, then commit its state and clear the journal."""
        with self._lock:
            if self.has_pending():
                raise TransactionError("error.pending_block_write")
            plan.verify = plan.verify or self.verify
            self._precheck(plan)
            if cancel():
                raise Cancelled("cancelled")
            payload = plan.to_dict()
            payload["stage_id"] = uuid.uuid4().hex
            payload["created"] = time.time()
            # Durable before the first user file changes.
            atomic_json(self.journal_path, payload)
            self._apply(payload, progress, save_state)

    def recover(self, progress: Progress = _NOOP_PROGRESS,
                save_state: Callable[[dict], None] | None = None) -> bool:
        """Finish a journalled transaction left behind by a crash."""
        with self._lock:
            if not self.has_pending():
                return False
            payload = read_json(self.journal_path, None)
            if not payload:
                self.journal_path.unlink(missing_ok=True)
                return False
            log.warning("resuming journalled transaction %s", payload.get("stage_id"))
            self._apply(payload, progress, save_state)
            return True

    # -- internals -----------------------------------------------------
    def _precheck(self, plan: Plan) -> None:
        need = plan.bytes_written()
        if need <= 0:
            return
        roots: dict[object, int] = {}
        for step in plan.forward:
            if step["kind"] not in (COPY, WRITE):
                continue
            size = int((step.get("src_id") or step.get("snapshot") or {}).get("size") or 0)
            parent = Path(step["dst"]).parent
            roots[str(parent)] = roots.get(str(parent), 0) + size
        for parent, size in roots.items():
            available = free_space(parent)
            # Leave a small margin: a volume filled to the last byte behaves badly.
            if available is not None and available < size + 16 * 1024 * 1024:
                raise TransactionError("error.disk_full", f"{parent}: need {size}, free {available}")

    def _apply(self, payload: dict, progress: Progress, save_state) -> None:
        verify = str(payload.get("verify") or VERIFY_FULL)
        stage = str(payload.get("stage_id") or uuid.uuid4().hex)
        steps = list(payload.get("forward") or [])
        total = max(1, len(steps))
        mutated = bool(payload.get("mutated"))
        try:
            for index, step in enumerate(steps):
                progress(Path(step.get("dst", "")).name, int(index * 100 / total))
                if self._run_step(step, verify, stage, progress):
                    mutated = True
        except BaseException as error:
            if not mutated:
                # Nothing on disk changed, so there is nothing to recover from.
                # Leaving a journal here would block every later operation for
                # a failure that already rolled itself back.
                self.journal_path.unlink(missing_ok=True)
                log.warning("transaction refused before any change: %s", error)
                raise
            payload["mutated"] = True
            atomic_json(self.journal_path, payload)
            log.exception("transaction stopped part-way")
            if isinstance(error, Cancelled):
                raise
            raise TransactionError("error.unfinished", str(error), error=str(error)) from error
        state = payload.get("state")
        if state is not None and save_state is not None:
            save_state(state)
        self.journal_path.unlink(missing_ok=True)

    def _staged_copy(self, source: Path, dst: Path, stage: str, verify: str,
                     progress: Progress) -> dict:
        """Copy into a hidden sibling, then rename into place.

        The temporary carries this transaction's stage id so it is owned by
        exactly one run and is never matched by a wildcard.
        """
        staged = dst.with_name(f".qingjian-{stage}-{dst.name}.part")
        staged.unlink(missing_ok=True)
        try:
            info = copy_verified(source, staged, progress, _NEVER, verify)
        except BaseException:
            staged.unlink(missing_ok=True)
            raise
        os.replace(staged, dst)
        return info

    def sweep_partials(self, folders: Iterable[str | Path]) -> int:
        """Remove leftover ``.part`` files from a run that died mid-copy."""
        removed = 0
        for folder in folders:
            try:
                for item in Path(folder).iterdir():
                    if item.name.startswith(".qingjian-") and item.name.endswith(".part"):
                        item.unlink(missing_ok=True)
                        removed += 1
            except OSError:
                continue
        return removed

    def _run_step(self, step: dict, verify: str, stage: str, progress: Progress) -> bool:
        """Apply one step. Returns True when the filesystem actually changed."""
        kind = step["kind"]
        dst = Path(step["dst"])
        result = step.get("result")

        if kind == MOVE:
            # Identity here is size and modification time, never content: a
            # rename has no copy to prove, and a cross-volume move proves its
            # copy inside `_staged_copy`. Hashing both ends first read a 300 MB
            # video twice for a rename that takes a millisecond.
            src = Path(step["src"])
            done_at_dst = identity_matches(dst, result, VERIFY_FAST)
            if done_at_dst and not src.exists():
                return False                            # already done
            if done_at_dst and src.exists():
                # Crashed between writing the target and removing the source.
                if identity_matches(src, step.get("src_id"), VERIFY_FAST):
                    src.unlink()
                    return True
                raise TransactionError("error.changed_midway", str(src), path=str(src))
            if not identity_matches(src, step.get("src_id"), VERIFY_FAST):
                raise TransactionError("error.external_change", str(src), path=str(src))
            if dst.exists():
                raise TransactionError("error.changed_midway", str(dst), path=str(dst))
            if dst.parent.name == TRASH_DIR:
                # Redo can land in a recycle folder that reclaiming has removed.
                self._prepare_trash_folder(dst.parent)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
            if self.fast_path and same_volume(src, dst.parent):
                os.replace(src, dst)
            else:
                self._staged_copy(src, dst, stage, verify, progress)
                src.unlink()
            self._count_recycled(src, dst, step.get("src_id"))
            return True

        if kind == COPY:
            src = Path(step["src"])
            # A copy preserves size, mtime and content, so the source identity
            # also describes a finished copy. Checking both is what lets
            # recovery recognise a copy that completed just before the crash,
            # back when `result` had not been written to the journal yet.
            if identity_matches(dst, result or step.get("src_id"), VERIFY_FAST):
                return False
            if dst.exists():
                raise TransactionError("error.changed_midway", str(dst), path=str(dst))
            if not identity_matches(src, step.get("src_id"), VERIFY_FAST):
                raise TransactionError("error.external_change", str(src), path=str(src))
            dst.parent.mkdir(parents=True, exist_ok=True)
            step["result"] = self._staged_copy(src, dst, stage, verify, progress)
            return True

        if kind == WRITE:
            snapshot = step.get("snapshot") or {}
            source = Path(snapshot.get("file", ""))
            if result and identity_matches(dst, result, verify):
                return False
            if not source.is_file():
                raise TransactionError("error.snapshot_missing", str(source), path=str(source))
            if snapshot.get("hash") and fingerprint(source) != snapshot["hash"]:
                raise TransactionError("error.snapshot_missing", str(source), path=str(source))
            if dst.exists() and not identity_matches(dst, step.get("expect"), verify):
                raise TransactionError("error.changed_midway", str(dst), path=str(dst))
            dst.parent.mkdir(parents=True, exist_ok=True)
            self._staged_copy(source, dst, stage, verify, progress)
            return True

        if kind == UNLINK:
            if not dst.exists():
                return False
            if not identity_matches(dst, step.get("expect"), verify):
                raise TransactionError("error.external_change", str(dst), path=str(dst))
            dst.unlink()
            return True

        raise TransactionError("error.name_invalid", f"unknown step kind {kind!r}")

    # -- inverses ------------------------------------------------------
    @staticmethod
    def invert(steps: list[dict]) -> list[dict]:
        """Build the step list that undoes *steps*, in reverse order."""
        out: list[dict] = []
        for step in reversed(steps):
            kind = step["kind"]
            if kind == MOVE:
                identity_at_target = step.get("result") or step.get("src_id")
                out.append({"kind": MOVE, "src": step["dst"], "dst": step["src"],
                            "src_id": identity_at_target,
                            "result": step.get("src_id") or identity_at_target})
            elif kind == COPY:
                # The inverse is built before the copy runs, so `result` is not
                # filled in yet. A verified copy has the source's content and
                # mtime, so the source identity describes the finished copy too.
                out.append({"kind": UNLINK, "dst": step["dst"],
                            "expect": step.get("result") or step.get("src_id"),
                            "result": None})
            elif kind == WRITE:
                previous = step.get("expect")
                if previous is None:
                    out.append({"kind": UNLINK, "dst": step["dst"],
                                "expect": step.get("result") or (step.get("snapshot") or None),
                                "result": None})
                else:
                    out.append({"kind": WRITE, "dst": step["dst"],
                                "snapshot": step.get("previous_snapshot") or {},
                                "expect": step.get("result"),
                                "result": previous})
            elif kind == UNLINK:
                snapshot = step.get("snapshot") or {}
                out.append({"kind": WRITE, "dst": step["dst"], "snapshot": snapshot,
                            "expect": None,
                            "result": {"size": snapshot.get("size"), "hash": snapshot.get("hash")}})
        return out


def snapshot_bytes(record: dict) -> int:
    """Bytes of restore copies a history record is holding open."""
    total = 0
    for ref in record.get("snapshots") or []:
        try:
            total += Path(ref).stat().st_size
        except OSError:
            continue
    return total


def reclaim_candidates(records: list[dict], policy: QuotaPolicy,
                       now: float | None = None) -> list[int]:
    """Indices of the oldest records to retire so *policy* is satisfied.

    Records are assumed oldest-first. Retiring a record means deleting its
    restore copies and marking it non-undoable — never touching a user file.
    """
    now = time.time() if now is None else now
    sizes = [snapshot_bytes(r) for r in records]
    total = sum(sizes)
    live = list(range(len(records)))
    drop: list[int] = []

    def retire(index: int) -> None:
        nonlocal total
        live.remove(index)
        drop.append(index)
        total -= sizes[index]

    if policy.max_days > 0:
        horizon = now - policy.max_days * 86400
        for index in list(live):
            when = records[index].get("time_epoch")
            if isinstance(when, (int, float)) and when < horizon:
                retire(index)
    if policy.max_operations > 0:
        while len(live) > policy.max_operations:
            retire(live[0])
    if policy.max_bytes > 0:
        while live and total > policy.max_bytes:
            retire(live[0])
    return sorted(drop)
