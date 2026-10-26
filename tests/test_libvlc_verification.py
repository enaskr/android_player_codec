"""Local synthetic-AAR validation; no network, SDK, or device required."""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("verify_libvlc", SCRIPTS / "verify_libvlc.py")
libvlc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(libvlc)


def stub_elf(abi, alignment=16384):
    from verify_shared_libs import MACHINES
    kind, machine = MACHINES[abi]
    data = bytearray(256)
    data[:6] = bytes([127, 69, 76, 70, kind, 1])
    struct.pack_into("<H", data, 18, machine)
    if kind == 2:
        struct.pack_into("<Q", data, 32, 64)
        struct.pack_into("<HH", data, 54, 56, 1)
        struct.pack_into("<I", data, 64, 1)
        struct.pack_into("<Q", data, 64 + 48, alignment)
    else:
        struct.pack_into("<I", data, 28, 52)
        struct.pack_into("<HH", data, 42, 32, 1)
        struct.pack_into("<I", data, 52, 1)
        struct.pack_into("<I", data, 52 + 28, alignment)
    return bytes(data)


def java_jar():
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as z:
        for name in libvlc.REQUIRED_CLASSES:
            z.writestr(name, b"fake bytecode for file-set tests")
    return result.getvalue()


def aar_file(folder: Path, abis, bad_abi=None, conflict=False) -> Path:
    out = folder / "libvlc.aar"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("classes.jar", java_jar())
        for abi in abis:
            z.writestr(
                f"jni/{abi}/libvlc.so",
                stub_elf(abi, 4096 if abi == bad_abi else 16384)
            )
            if conflict:
                z.writestr(f"jni/{abi}/libavcodec.so", stub_elf(abi))
    return out


class LibVlcVerifierTests(unittest.TestCase):
    def test_all_four_abis_pass_synthetic_input(self):
        from verify_shared_libs import MACHINES
        with tempfile.TemporaryDirectory() as folder:
            report = libvlc.verify(aar_file(Path(folder), MACHINES))
        self.assertEqual(set(report["abis"]), set(MACHINES))

    def test_missing_abi_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = aar_file(Path(folder), ["arm64-v8a"])
            with self.assertRaisesRegex(ValueError, "missing for"):
                libvlc.verify(path)

    def test_four_kib_alignment_is_rejected(self):
        from verify_shared_libs import MACHINES
        with tempfile.TemporaryDirectory() as folder:
            path = aar_file(Path(folder), MACHINES, bad_abi="arm64-v8a")
            with self.assertRaisesRegex(ValueError, "non-16KiB"):
                libvlc.verify(path)

    def test_native_name_collision_is_rejected(self):
        from verify_shared_libs import MACHINES
        with tempfile.TemporaryDirectory() as folder:
            path = aar_file(Path(folder), MACHINES, conflict=True)
            with self.assertRaisesRegex(ValueError, "collision"):
                libvlc.verify(path)


if __name__ == "__main__":
    unittest.main()
