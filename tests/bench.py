"""Measures the changes that were made for speed, so the claims are checkable."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def timed(label, function, *args, **kwargs):
    start = time.perf_counter()
    result = function(*args, **kwargs)
    return label, time.perf_counter() - start, result


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="qingjian-bench-"))
    os.environ["QINGJIAN_DATA_DIR"] = str(work / "data")
    from PIL import Image
    from qingjian.core import config, metadata, scanner
    from qingjian.core.engine import Engine
    from qingjian.core.safestore import (Plan, SafeStore, identity, step_move)
    from qingjian.core.state import Record, StateStore, empty_delta

    print("=" * 74)
    print("scan and filter, 1200 images")
    library = work / "library"
    library.mkdir(parents=True)
    for index in range(1200):
        folder = library / f"day{index % 12:02d}"
        folder.mkdir(exist_ok=True)
        landscape = index % 3 != 0
        size = (160, 120) if landscape else (120, 160)
        Image.new("RGB", size, (index % 255, 90, 140)).save(folder / f"IMG_{index:05d}.JPG",
                                                            quality=70)
    for label, seconds, value in [
        timed("  scan (recursive)", scanner.scan, library, True),
    ]:
        print(f"{label:38} {seconds * 1000:8.1f} ms   {len(value)} files")
    files = scanner.scan(library, True)

    metadata.clear_cache()
    label, seconds, kept = timed("  filter: landscape (header only)",
                                 scanner.apply_filter, files,
                                 scanner.FilterSpec(mode="landscape"))
    print(f"{label:38} {seconds * 1000:8.1f} ms   {len(kept)} kept")

    def full_decode_filter(paths):
        out = []
        for path in paths:
            with Image.open(path) as image:
                image.load()                      # what the old build did
                if image.width >= image.height:
                    out.append(path)
        return out

    label, seconds, kept = timed("  filter: landscape (full decode)", full_decode_filter, files)
    print(f"{label:38} {seconds * 1000:8.1f} ms   {len(kept)} kept   <- previous behaviour")

    print()
    print("  the same test at a real camera's resolution (40 files, 6000 x 4000):")
    big_folder = work / "big-library"
    big_folder.mkdir()
    for index in range(40):
        size = (6000, 4000) if index % 3 else (4000, 6000)
        Image.new("RGB", size, (index * 6 % 255, 90, 140)).save(
            big_folder / f"BIG_{index:03d}.JPG", quality=60)
    big_files = scanner.scan(big_folder, False)
    metadata.clear_cache()
    label, seconds, kept = timed("  filter: landscape (header only)",
                                 scanner.apply_filter, big_files,
                                 scanner.FilterSpec(mode="landscape"))
    print(f"{label:38} {seconds * 1000:8.1f} ms   {len(kept)} kept")
    label, seconds, kept = timed("  filter: landscape (full decode)",
                                 full_decode_filter, big_files)
    print(f"{label:38} {seconds * 1000:8.1f} ms   {len(kept)} kept   <- previous behaviour")

    print()
    print("=" * 74)
    print("moving a large file")
    big = work / "big.bin"
    payload = os.urandom(1024 * 1024) * 64          # 64 MB
    big.write_bytes(payload)
    store = SafeStore(work / "store-fast")
    target = work / "moved" / "big.bin"
    plan = Plan(forward=[step_move(big, target, identity(big))])
    label, seconds, _ = timed("  fast path (same volume)", store.run, plan)
    print(f"{label:38} {seconds * 1000:8.1f} ms   snapshots {store.usage() / 1e6:.1f} MB")

    target.rename(big)
    import qingjian.core.safestore as ss
    real = ss.same_volume
    ss.same_volume = lambda a, b: False
    store2 = SafeStore(work / "store-slow")
    store2.snapshot(big)                            # what the old build always did
    plan2 = Plan(forward=[step_move(big, target, identity(big))])
    label, seconds, _ = timed("  copy+verify+snapshot (old way)", store2.run, plan2)
    print(f"{label:38} {seconds * 1000:8.1f} ms   snapshots {store2.usage() / 1e6:.1f} MB")
    ss.same_volume = real

    print()
    print("=" * 74)
    print("history growth")
    state = StateStore(work / "data" / "bench.db")
    for batch in (0, 5000, 20000):
        if batch:
            state.apply({"records_add": [
                Record(id=f"b{batch}-{i}", action="move", original=f"/a/{i}.jpg").to_dict()
                for i in range(batch)]})
        delta = empty_delta()
        delta["records_add"].append(
            Record(id=f"one-{batch}", action="move", original="/a/z.jpg").to_dict())
        label, seconds, _ = timed(f"  one record with {state.counts()['history']:>6} present",
                                  state.apply, delta)
        print(f"{label:38} {seconds * 1000:8.2f} ms")

    print()
    print("=" * 74)
    print("duplicate scanning, cold and warm")
    settings = config.Settings()
    settings.recursive = True
    engine = Engine(work / "data", settings)
    engine.open_folder(library)
    for pass_name in ("cold", "warm"):
        label, seconds, groups = timed(f"  exact ({pass_name})", engine.find_duplicates, "exact")
        print(f"{label:38} {seconds * 1000:8.1f} ms   {len(groups)} groups")
    for pass_name in ("cold", "warm"):
        label, seconds, groups = timed(f"  similar ({pass_name})", engine.find_duplicates,
                                       "similar")
        print(f"{label:38} {seconds * 1000:8.1f} ms   {len(groups)} groups")
    engine.close()

    print()
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
