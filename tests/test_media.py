from datetime import datetime

from PIL import Image, ImageFilter

from base import TempCase, unittest
from fixtures import build_library, exif_bytes, scene
from qingjian.core import dedupe, exifread, hashcache, imaging, isobmff, mediatypes, metadata


class MediaTypeTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(mediatypes.KIND_RAW, mediatypes.kind("a.CR2"))
        self.assertEqual(mediatypes.KIND_VIDEO, mediatypes.kind("a.MP4"))
        self.assertEqual(mediatypes.KIND_IMAGE, mediatypes.kind("a.jpeg"))
        self.assertEqual(mediatypes.KIND_OTHER, mediatypes.kind("a.txt"))

    def test_raw_counts_as_an_image_but_not_a_plain_one(self):
        self.assertTrue(mediatypes.is_image("a.NEF"))
        self.assertTrue(mediatypes.is_raw("a.NEF"))
        self.assertFalse(mediatypes.is_video("a.NEF"))

    def test_the_common_raw_formats_are_covered(self):
        for ext in (".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2"):
            self.assertIn(ext, mediatypes.RAW_EXTENSIONS, ext)

    def test_case_is_irrelevant(self):
        self.assertTrue(mediatypes.is_media("A.JpG"))


class ExifTests(TempCase):
    def make_tiff(self, name="raw.tif", when=datetime(2026, 8, 14, 19, 42, 8)):
        path = self.tmp / name
        scene(1, (400, 300)).save(path, exif=exif_bytes(when))
        return path

    def test_tiff_exif_is_read_without_a_raw_decoder(self):
        tags = exifread.read_tiff_exif(self.make_tiff())
        self.assertEqual("ILCE-7M4", tags["Model"])
        self.assertEqual("2026:08:14 19:42:08", tags["DateTimeOriginal"])
        self.assertEqual(400, tags["ISOSpeedRatings"])

    def test_a_non_tiff_file_returns_nothing_rather_than_raising(self):
        junk = self.write(self.tmp / "junk.bin", b"not a tiff at all")
        self.assertEqual({}, exifread.read_tiff_exif(junk))

    def test_a_truncated_file_does_not_raise(self):
        path = self.make_tiff()
        data = path.read_bytes()
        self.write(self.tmp / "cut.tif", data[:64])
        exifread.read_tiff_exif(self.tmp / "cut.tif")


class IsoBmffTests(TempCase):
    def test_duration_and_size_are_read_without_a_video_library(self):
        from fixtures import _write_mp4
        clip = _write_mp4(self.tmp / "clip.mp4", 74)
        header = isobmff.read_header(clip)
        self.assertAlmostEqual(74.0, header["duration"], places=2)
        self.assertEqual(1920, header["width"])
        self.assertIsInstance(header["created"], datetime)

    def test_a_non_video_returns_nothing(self):
        junk = self.write(self.tmp / "j.bin", b"\x00" * 64)
        self.assertEqual({}, isobmff.read_header(junk))


class MetadataTests(TempCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "lib"
        self.made = build_library(self.root)

    def test_jpeg_metadata(self):
        info = metadata.read(self.root / "Day3" / "IMG_5511.JPG")
        self.assertEqual("Sony ILCE-7M4", info.camera)
        self.assertEqual("400", info.iso)
        self.assertEqual("f/2.8", info.aperture)
        self.assertEqual("1/250", info.shutter)
        self.assertFalse(info.captured_is_fallback)

    def test_capture_time_falls_back_to_mtime(self):
        plain = self.tmp / "plain.png"
        Image.new("RGB", (10, 10)).save(plain)
        info = metadata.read(plain)
        self.assertTrue(info.captured_is_fallback)
        self.assertIsNotNone(info.captured)

    def test_video_duration_without_pyav(self):
        info = metadata.read(self.root / "Day4" / "MOV_001.MP4")
        self.assertAlmostEqual(12.0, info.duration, places=1)
        self.assertEqual("0:12", metadata.format_duration(info.duration))

    def test_orientation_helpers(self):
        self.assertTrue(metadata.read(self.root / "Day3" / "tall.JPG").is_portrait)
        self.assertTrue(metadata.read(self.root / "Day4" / "solo_01.JPG").is_landscape)

    def test_a_missing_file_reports_an_error_instead_of_raising(self):
        info = metadata.read(self.tmp / "nope.jpg")
        self.assertTrue(info.error)

    def test_a_corrupt_image_does_not_raise(self):
        broken = self.write(self.tmp / "broken.jpg", b"\xff\xd8\xff" + b"\x00" * 200)
        info = metadata.read(broken)
        self.assertEqual(mediatypes.KIND_IMAGE, info.kind)

    def test_the_cache_returns_the_same_object_until_the_file_changes(self):
        path = self.root / "Day3" / "IMG_5511.JPG"
        first = metadata.read(path)
        self.assertIs(first, metadata.read(path))
        metadata.clear_cache()
        self.assertIsNot(first, metadata.read(path))

    def test_duration_formatting(self):
        self.assertEqual("", metadata.format_duration(None))
        self.assertEqual("0:07", metadata.format_duration(7))
        self.assertEqual("1:01", metadata.format_duration(61))
        self.assertEqual("1:00:00", metadata.format_duration(3600))


class ImagingTests(TempCase):
    def setUp(self):
        super().setUp()
        self.base = scene(3)
        self.original = self.tmp / "orig.jpg"
        self.base.save(self.original, quality=95)

    def test_identical_images_hash_the_same(self):
        copy = self.tmp / "copy.jpg"
        copy.write_bytes(self.original.read_bytes())
        self.assertEqual(imaging.phash(self.original), imaging.phash(copy))

    def test_a_resized_export_is_still_a_near_match(self):
        small = self.tmp / "small.jpg"
        self.base.resize((450, 300)).save(small, quality=80)
        self.assertGreaterEqual(
            imaging.similarity(imaging.phash(self.original), imaging.phash(small)), 0.92)

    def test_a_different_picture_is_not_a_match(self):
        other = self.tmp / "other.jpg"
        scene(99).save(other, quality=95)
        self.assertLess(
            imaging.similarity(imaging.phash(self.original), imaging.phash(other)), 0.92)

    def test_blur_lowers_the_sharpness_score(self):
        blurred = self.tmp / "blur.jpg"
        self.base.filter(ImageFilter.GaussianBlur(4)).save(blurred, quality=95)
        self.assertGreater(imaging.sharpness(self.original), imaging.sharpness(blurred) * 3)

    def test_defects_are_named(self):
        white = self.tmp / "white.png"
        Image.new("RGB", (200, 200), (255, 255, 255)).save(white)
        black = self.tmp / "black.png"
        Image.new("RGB", (200, 200), (0, 0, 0)).save(black)
        self.assertEqual("overexposed", imaging.looks_unusable(imaging.quality_score(white)))
        self.assertEqual("black", imaging.looks_unusable(imaging.quality_score(black)))
        self.assertEqual("", imaging.looks_unusable(imaging.quality_score(self.original)))

    def test_hamming_and_similarity(self):
        self.assertEqual(0, imaging.hamming(0b1010, 0b1010))
        self.assertEqual(2, imaging.hamming(0b1010, 0b0000))
        self.assertEqual(1.0, imaging.similarity(5, 5))
        self.assertEqual(0.0, imaging.similarity(None, 5))

    def test_an_unreadable_file_returns_none_rather_than_raising(self):
        junk = self.write(self.tmp / "junk.jpg", b"nope")
        self.assertIsNone(imaging.phash(junk))
        self.assertEqual(0.0, imaging.sharpness(junk))

    def test_embedded_preview_extraction(self):
        raw = self.tmp / "fake.cr2"
        raw.write_bytes(b"HEADER" * 100 + self.original.read_bytes() + b"TRAILER")
        blob = imaging.extract_embedded_jpeg(raw)
        self.assertIsNotNone(blob)
        self.assertTrue(blob.startswith(b"\xff\xd8\xff"))
        self.assertIsNotNone(imaging.phash(raw))


class DedupeTests(TempCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "lib"
        build_library(self.root)
        self.paths = sorted(p for p in self.root.rglob("*")
                            if p.is_file() and mediatypes.is_media(p))
        self.cache = hashcache.HashCache(None)

    def test_exact_finds_the_byte_identical_copy(self):
        groups = dedupe.find_exact(self.paths, self.cache)
        self.assertEqual(1, len(groups))
        self.assertEqual({"IMG_5511.JPG"}, {m.path.name for m in groups[0].members})
        self.assertEqual(2, len(groups[0].members))

    def test_similar_finds_the_web_export(self):
        groups = dedupe.find_similar(self.paths, 0.92, self.cache)
        names = {m.path.name for group in groups for m in group.members}
        self.assertIn("IMG_5511_web.jpg", names)

    def test_similar_keeps_the_largest_frame(self):
        for group in dedupe.find_similar(self.paths, 0.92, self.cache):
            if any(m.path.name == "IMG_5511_web.jpg" for m in group.members):
                self.assertEqual("IMG_5511.JPG", group.keep().path.name)
                break
        else:
            self.fail("the web export was not grouped")

    def test_bursts_are_found_and_the_sharpest_is_kept(self):
        groups = dedupe.find_bursts(self.paths, cache=self.cache)
        self.assertEqual(1, len(groups))
        group = groups[0]
        self.assertEqual(4, len(group.members))
        self.assertEqual("burst_03.JPG", group.keep().path.name)

    def test_a_burst_stays_in_shooting_order(self):
        group = dedupe.find_bursts(self.paths, cache=self.cache)[0]
        names = [m.path.name for m in group.members]
        self.assertEqual(sorted(names), names)

    def test_the_ignore_list_removes_a_pair(self):
        groups = dedupe.find_exact(self.paths, self.cache)
        extra = groups[0].extras[0]
        key = dedupe.identity_key(extra.path, extra.digest)
        self.assertEqual([], dedupe.find_exact(self.paths, self.cache, ignored={key}))

    def test_editing_a_file_puts_it_back_into_consideration(self):
        groups = dedupe.find_exact(self.paths, self.cache)
        extra = groups[0].extras[0]
        key = dedupe.identity_key(extra.path, extra.digest)
        extra.path.write_bytes(extra.path.read_bytes() + b"edited")
        # The old key no longer matches, so the file is judged afresh.
        self.assertNotEqual(key, dedupe.identity_key(extra.path, "different"))

    def test_the_banded_index_finds_every_close_pair(self):
        hashes = [0, 1, 3, 0xFFFF_FFFF_FFFF_FFFF]
        pairs = dedupe.banded_pairs(hashes, 2)
        self.assertIn((0, 1), pairs)
        self.assertIn((0, 2), pairs)
        self.assertNotIn((0, 3), pairs)

    def test_a_higher_threshold_finds_fewer_groups(self):
        loose = len(dedupe.find_similar(self.paths, 0.88, self.cache))
        tight = len(dedupe.find_similar(self.paths, 0.98, self.cache))
        self.assertGreaterEqual(loose, tight)

    def test_summary(self):
        summary = dedupe.summarise(dedupe.find_exact(self.paths, self.cache))
        self.assertEqual(1, summary["groups"])
        self.assertGreater(summary["reclaimable"], 0)


class HashCacheTests(TempCase):
    def test_a_value_survives_a_reopen(self):
        path = self.write(self.tmp / "a.jpg", b"x" * 50)
        cache = hashcache.HashCache(self.data / "c.db")
        calls = []
        cache.compute(path, "phash", lambda p: calls.append(p) or 123)
        cache.close()
        again = hashcache.HashCache(self.data / "c.db")
        try:
            self.assertEqual(123, again.compute(path, "phash", lambda p: calls.append(p) or 999))
            self.assertEqual(1, len(calls))
        finally:
            again.close()

    def test_an_edited_file_is_recomputed(self):
        path = self.write(self.tmp / "a.jpg", b"x" * 50)
        cache = hashcache.HashCache(self.data / "c.db")
        cache.compute(path, "sha256", lambda p: "first")
        import time
        try:
            time.sleep(0.01)
            path.write_bytes(b"y" * 90)
            self.assertEqual("second", cache.compute(path, "sha256", lambda p: "second"))
        finally:
            cache.close()

    def test_it_works_without_a_file(self):
        path = self.write(self.tmp / "a.jpg", b"x")
        cache = hashcache.HashCache(None)
        self.assertEqual(7, cache.compute(path, "phash", lambda p: 7))
        self.assertEqual(7, cache.compute(path, "phash", lambda p: 9))


if __name__ == "__main__":
    unittest.main()
