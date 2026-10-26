"""Bundle artifact integrity tests; no Android tools or internet required."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("package_bundle", SCRIPTS / "package_bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def dummy_aar(path: Path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("classes.jar", b"stub")


class BundleTests(unittest.TestCase):
    def test_bundle_contains_two_original_aars(self):
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp)
            codec = dist / "android-player-codec-0.2.0-ffmpeg9.0.2.aar"
            vlc = dist / "libvlc-all-3.7.7.aar"
            dummy_aar(codec)
            dummy_aar(vlc)
            for name in ("libvlc-all-3.7.7.pom", "LIBVLC_PROVENANCE.json",
                         "BUILD_INFO.txt", "VERIFICATION.json"):
                (dist / name).write_text("test", encoding="utf-8")
            result = bundle.create_bundle(dist, "0.2.0", "9.0.2", "3.7.7")
            with zipfile.ZipFile(result) as z:
                self.assertEqual(z.read(codec.name), codec.read_bytes())
                self.assertEqual(z.read(vlc.name), vlc.read_bytes())
                self.assertIn("README-BUNDLE.md", z.namelist())

    def test_missing_libvlc_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp)
            with self.assertRaises(ValueError):
                bundle.create_bundle(dist, "0.2.0", "9.0.2", "3.7.7")


if __name__ == "__main__":
    unittest.main()
