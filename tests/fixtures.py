"""Builds a small but realistic photo library on disk for the tests."""
from __future__ import annotations

import struct
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def exif_bytes(when: datetime, camera=("Sony", "ILCE-7M4"), lens="FE 24mm F2.8 G",
               iso=400) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = camera[0]
    exif[0x0110] = camera[1]
    exif[0x0132] = when.strftime("%Y:%m:%d %H:%M:%S")
    exif[0x8769] = {
        0x9003: when.strftime("%Y:%m:%d %H:%M:%S"),
        0x8827: iso,
        0x829D: (28, 10),
        0x829A: (1, 250),
        0x920A: (24, 1),
        0xA434: lens,
    }
    return exif.tobytes()


def scene(seed: int, size=(900, 600)) -> Image.Image:
    """A deterministic picture with real structure, not noise."""
    rng = np.random.default_rng(seed)
    width, height = size
    y = np.linspace(0, 1, height)[:, None]
    x = np.linspace(0, 1, width)[None, :]
    ones = np.ones((height, width))
    sky = np.stack([
        40 + 180 * y * ones + 30 * np.sin(6 * x + seed) * ones,
        60 + 120 * y * ones + 20 * np.cos(4 * x + seed) * ones,
        110 + 60 * y * ones,
    ], axis=-1)
    image = Image.fromarray(np.clip(sky, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    for index in range(5):
        base = height * (0.55 + 0.06 * index)
        peak = base - height * (0.18 + 0.05 * ((seed + index) % 4))
        left = width * (index / 5.0) - 60
        draw.polygon([(left, base), (left + width * 0.16, peak),
                      (left + width * 0.32, base)], fill=(30 + 12 * index, 34 + 10 * index, 60))
    for _ in range(28):
        cx, cy = rng.integers(0, width), rng.integers(0, height)
        draw.ellipse([cx, cy, cx + 7, cy + 7], fill=(240, 230, 200))
    return image


def build_library(root: Path) -> dict:
    """Create the fixture tree and return a map of what is where."""
    root = Path(root)
    day3 = root / "Day3"
    day4 = root / "Day4"
    backup = root / "Backup"
    for folder in (day3, day4, backup):
        folder.mkdir(parents=True, exist_ok=True)

    start = datetime(2026, 8, 14, 19, 42, 8)
    made: dict[str, list[Path]] = {"exact": [], "similar": [], "burst": [],
                                   "unique": [], "sidecar": [], "video": [], "junk": []}

    # A photo with a raw and metadata sidecars beside it.
    master = scene(1)
    master.save(day3 / "IMG_5511.JPG", exif=exif_bytes(start), quality=95)
    (day3 / "IMG_5511.CR2").write_bytes(b"CR2-placeholder" * 800)
    (day3 / "IMG_5511.XMP").write_text("<x:xmpmeta/>", encoding="utf-8")
    (day3 / "IMG_5511.JPG.xmp").write_text("<x:xmpmeta/>", encoding="utf-8")
    made["sidecar"] = [day3 / "IMG_5511.JPG", day3 / "IMG_5511.CR2",
                       day3 / "IMG_5511.XMP", day3 / "IMG_5511.JPG.xmp"]

    # Byte-identical copy in another folder.
    (backup / "IMG_5511.JPG").write_bytes((day3 / "IMG_5511.JPG").read_bytes())
    made["exact"] = [day3 / "IMG_5511.JPG", backup / "IMG_5511.JPG"]

    # Same frame exported small: near, not exact.
    master.resize((450, 300)).save(day3 / "IMG_5511_web.jpg", quality=80)
    made["similar"] = [day3 / "IMG_5511.JPG", day3 / "IMG_5511_web.jpg"]

    # A burst: four frames one second apart, slightly different, one sharpest.
    burst_base = scene(2)
    for index in range(4):
        when = start + timedelta(minutes=5, seconds=index)
        frame = burst_base.rotate(0.25 * index, resample=Image.Resampling.BICUBIC)
        if index != 2:
            frame = frame.filter(ImageFilter.GaussianBlur(0.6 + 0.5 * index))
        name = day4 / f"burst_{index + 1:02d}.JPG"
        frame.save(name, exif=exif_bytes(when), quality=95)
        made["burst"].append(name)

    # Plain unrelated photographs.
    for index in range(3):
        when = start + timedelta(hours=1, minutes=index * 7)
        name = day4 / f"solo_{index + 1:02d}.JPG"
        scene(10 + index).save(name, exif=exif_bytes(when), quality=95)
        made["unique"].append(name)

    # A portrait-orientation frame, for the orientation filter.
    scene(20, size=(600, 900)).save(day3 / "tall.JPG", exif=exif_bytes(start), quality=92)
    made["unique"].append(day3 / "tall.JPG")

    # Two short videos with real ISO base-media headers.
    for index, seconds in enumerate((12, 95)):
        made["video"].append(_write_mp4(day4 / f"MOV_00{index + 1}.MP4", seconds))

    # Files a media sorter must ignore.
    (root / "notes.txt").write_text("not media", encoding="utf-8")
    (day3 / "IMG_5511.txt").write_text("same stem, not a sidecar kind", encoding="utf-8")
    made["junk"] = [root / "notes.txt", day3 / "IMG_5511.txt"]
    return made


def _write_mp4(path: Path, seconds: int) -> Path:
    def box(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I4s", 8 + len(payload), kind) + payload

    timescale = 600
    created = 3_870_000_000
    mvhd = box(b"mvhd", b"\x00\x00\x00\x00"
               + struct.pack(">IIII", created, created, timescale, timescale * seconds)
               + b"\x00" * 80)
    tkhd_payload = (b"\x00\x00\x00\x00" + struct.pack(">II", created, created)
                    + struct.pack(">I", 1) + b"\x00" * 4
                    + struct.pack(">I", timescale * seconds) + b"\x00" * (8 + 2 + 2 + 2 + 2 + 36)
                    + struct.pack(">II", 1920 << 16, 1080 << 16))
    data = (box(b"ftyp", b"isom" + b"\x00" * 8)
            + box(b"moov", mvhd + box(b"trak", box(b"tkhd", tkhd_payload)))
            + box(b"mdat", b"\x00" * 256))
    path.write_bytes(data)
    return path
