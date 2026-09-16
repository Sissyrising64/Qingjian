"""Shared test scaffolding."""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))


class TempCase(unittest.TestCase):
    """A test with its own data directory, so nothing touches a real library."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.data = self.tmp / "data"
        self.data.mkdir()
        self._previous = os.environ.get("QINGJIAN_DATA_DIR")
        os.environ["QINGJIAN_DATA_DIR"] = str(self.data)
        from qingjian.core import metadata
        metadata.clear_cache()
        # Fault-injection tests deliberately provoke warnings; keep them out of
        # the test output so a real failure is easy to see.
        logging.getLogger("qingjian").setLevel(logging.CRITICAL)

    def tearDown(self) -> None:
        # unittest normally runs registered cleanups after tearDown. On
        # Windows that is too late for TemporaryDirectory: SQLite connections
        # registered with addCleanup still hold their files open here.
        self.doCleanups()
        if self._previous is None:
            os.environ.pop("QINGJIAN_DATA_DIR", None)
        else:
            os.environ["QINGJIAN_DATA_DIR"] = self._previous
        self._tmp.cleanup()

    def count_hashes(self) -> list[str]:
        """Record the name of every file hashed in full, until the test ends."""
        from qingjian.core import safestore
        seen: list[str] = []
        real = safestore.fingerprint

        def counting(path, *args, **kwargs):
            seen.append(Path(path).name)
            return real(path, *args, **kwargs)

        safestore.fingerprint = counting
        self.addCleanup(setattr, safestore, "fingerprint", real)
        return seen

    def write(self, path: Path, content: bytes = b"data") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def tree(self, root: Path) -> list[str]:
        if not root.exists():
            return []
        return sorted(str(p.relative_to(root)).replace("\\", "/")
                      for p in root.rglob("*") if p.is_file())
