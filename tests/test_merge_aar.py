"""Synthetic tests for the LibVLC-primary, physically merged Android AAR."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.merge_aar import merge, ABIS


def jar(names):
    with io.BytesIO() as tmp:
        with zipfile.ZipFile(tmp, "w") as z:
            for name in names:
                z.writestr(name, b"bytecode:" + name.encode())
        return tmp.getvalue()


VLC_CLASSES = (
    "org/videolan/libvlc/LibVLC.class",
    "org/videolan/libvlc/Media.class",
    "org/videolan/libvlc/MediaPlayer.class",
)
FF_CLASSES = (
    "com/enaskr/player/codec/CodecPack.class",
    "com/enaskr/player/codec/CodecSession.class",
    "com/enaskr/player/codec/LibVlcCodecPack.class",
)


def create_aar(path, vlc=False, class_collision=False, native_collision=False, omit_abi=None):
    with zipfile.ZipFile(path, "w") as z:
        if vlc:
            z.writestr("AndroidManifest.xml", "<manifest package='org.videolan'/>")
            z.writestr("R.txt", "int string libvlc hello")
            z.writestr("res/values/strings.xml", "<resources/>")
            z.writestr("classes.jar", jar(VLC_CLASSES))
        else:
            classes = FF_CLASSES + (("org/videolan/libvlc/Media.class",) if class_collision else ())
            z.writestr("classes.jar", jar(classes))
            z.writestr("proguard.txt", "-keep class com.enaskr.player.codec.** { *; }")
        for abi in ABIS:
            if abi == omit_abi:
                continue
            if vlc:
                for lib in ("libvlc.so", "libvlcjni.so", "libc++_shared.so"):
                    z.writestr(f"jni/{abi}/{lib}", ("upstream-"+abi+lib).encode())
            else:
                z.writestr(f"jni/{abi}/libandroid_player_codec.so", b"addon")
                if native_collision:
                    z.writestr(f"jni/{abi}/libvlc.so", b"collision")
    return path


class UnifiedMergeTests(unittest.TestCase):
    def test_single_aar_keeps_vlc_files_and_adds_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            base = create_aar(folder / "libvlc.aar", vlc=True)
            addon = create_aar(folder / "supplement.aar")
            out = folder / "single.aar"
            report = merge(base, addon, out, metadata={"fallback_candidates":["vvc","qoa"]})
            with zipfile.ZipFile(out) as combined, zipfile.ZipFile(base) as original:
                names = combined.namelist()
                self.assertEqual(len(names), len(set(names)))
                self.assertEqual(combined.read("AndroidManifest.xml"),
                                 original.read("AndroidManifest.xml"))
                self.assertEqual(combined.read("res/values/strings.xml"),
                                 original.read("res/values/strings.xml"))
                for abi in ABIS:
                    self.assertEqual(combined.read(f"jni/{abi}/libvlc.so"),
                                     original.read(f"jni/{abi}/libvlc.so"))
                    self.assertIn(f"jni/{abi}/libandroid_player_codec.so", names)
                with zipfile.ZipFile(io.BytesIO(combined.read("classes.jar"))) as classes:
                    self.assertTrue(set(VLC_CLASSES+FF_CLASSES).issubset(classes.namelist()))
                meta = json.loads(combined.read("codec-pack.json"))
                self.assertEqual(meta["fallback_candidates"], ["vvc","qoa"])
                self.assertFalse(meta["separate_nested_aars"])
            self.assertEqual(report["primary_engine"], "VideoLAN LibVLC")

    def test_duplicate_java_class_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            base=create_aar(folder/"vlc.aar",vlc=True)
            addon=create_aar(folder/"addon.aar",class_collision=True)
            with self.assertRaisesRegex(ValueError, "Duplicate Java class"):
                merge(base,addon,folder/"out.aar")

    def test_native_library_collision_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            base=create_aar(folder/"vlc.aar",vlc=True)
            addon=create_aar(folder/"addon.aar",native_collision=True)
            with self.assertRaisesRegex(ValueError, "Native library collision"):
                merge(base,addon,folder/"out.aar")

    def test_missing_abi_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            base=create_aar(folder/"vlc.aar",vlc=True)
            addon=create_aar(folder/"addon.aar",omit_abi="x86")
            with self.assertRaisesRegex(ValueError, "Supplement JNI library missing"):
                merge(base,addon,folder/"out.aar")


if __name__ == "__main__":
    unittest.main()
