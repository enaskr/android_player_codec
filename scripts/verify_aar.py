#!/usr/bin/env python3
"""Fail CI unless AAR has required JNI, Java API and LGPL FFmpeg native libs."""
from __future__ import annotations
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import zipfile
from verify_shared_libs import MACHINES, REQUIRED, verify_elf


def verify(path: pathlib.Path, abis: tuple[str, ...] | None = None) -> dict:
    with zipfile.ZipFile(path) as aar:
        bad = aar.testzip()
        if bad:
            raise ValueError(f"AAR corruption: {bad}")
        names = set(aar.namelist())
        with zipfile.ZipFile(io.BytesIO(aar.read("classes.jar"))) as classes:
            for klass in ("CodecPack", "CodecSession", "CodecCatalog", "CodecInfo"):
                name = f"com/enaskr/player/codec/{klass}.class"
                if name not in classes.namelist():
                    raise ValueError(f"AAR missing {name}")
        target_abis = tuple(abis) if abis is not None else tuple(MACHINES)
        if not target_abis or any(abi not in MACHINES for abi in target_abis):
            raise ValueError(f"Invalid ABI list: {target_abis}")
        report = {"aar": path.name, "abis": {}, "verified_abis": list(target_abis), "required_java_api": [
            "CodecPack", "CodecSession", "CodecCatalog", "CodecInfo"]}
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for abi in target_abis:
                report["abis"][abi] = {}
                for lib in REQUIRED + ["android_player_codec"]:
                    file = f"jni/{abi}/lib{lib}.so"
                    if file not in names:
                        raise ValueError(f"AAR missing {file}")
                    data = aar.read(file)
                    aligns = verify_elf(data, abi)
                    report["abis"][abi][lib] = {"bytes": len(data), "pt_load_alignment": aligns}
                    if lib == "android_player_codec":
                        dest = root / f"{abi}.so"
                        dest.write_bytes(data)
                        dynamic = subprocess.run(["readelf", "-W", "--dyn-syms", str(dest)],
                                                 text=True, capture_output=True,
                                                 errors="replace", check=True).stdout
                        expected = (
                            "Java_com_enaskr_player_codec_CodecSession_nativeOpen",
                            "Java_com_enaskr_player_codec_CodecSession_nativeAudioRead",
                            "Java_com_enaskr_player_codec_CodecSession_nativeVideoRead",
                            "Java_com_enaskr_player_codec_CodecSession_nativeClose",
                            "Java_com_enaskr_player_codec_CodecPack_nativeDecoders",
                        )
                        for method in expected:
                            if method not in dynamic:
                                raise ValueError(f"{abi}: missing native JNI method {method}")
    return report


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3, 4):
        sys.exit("Usage: verify_aar.py <codec.aar> [report.json] [arm64-v8a|armeabi-v7a|x86|x86_64]")
    target_abis = (sys.argv[3],) if len(sys.argv) == 4 else None
    report = verify(pathlib.Path(sys.argv[1]), target_abis)
    if len(sys.argv) >= 3:
        pathlib.Path(sys.argv[2]).write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: {', '.join(report['verified_abis'])}, native JNI exports, native 16 KiB ELF, Java API")
