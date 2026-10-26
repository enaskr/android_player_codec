#!/usr/bin/env python3
"""Validate official LibVLC AAR before it is included in a codec bundle.

All four supported ABIs, Java entrypoints, native ELF architectures, and
16 KiB PT_LOAD alignment are mandatory. Does not claim runtime playback tests.
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import zipfile

from verify_shared_libs import MACHINES, verify_elf

REQUIRED_CLASSES = (
    "org/videolan/libvlc/LibVLC.class",
    "org/videolan/libvlc/Media.class",
    "org/videolan/libvlc/MediaPlayer.class",
)
FFMPEG_JNI_BASENAMES = frozenset({
    "libavutil.so", "libavcodec.so", "libavformat.so",
    "libswscale.so", "libswresample.so", "libandroid_player_codec.so",
})


def verify(path: pathlib.Path) -> dict:
    if not path.exists() or path.stat().st_size < 1024:
        raise ValueError(f"Missing/empty LibVLC AAR: {path}")
    report = {
        "artifact": path.name,
        "abi_validation": "ELF machine and PT_LOAD 16 KiB alignment",
        "required_java_api": list(REQUIRED_CLASSES),
        "abis": {},
        "runtime_device_playback": "not tested",
    }
    with zipfile.ZipFile(path) as aar:
        bad_entry = aar.testzip()
        if bad_entry:
            raise ValueError(f"Corrupted LibVLC AAR entry: {bad_entry}")
        entries = set(aar.namelist())
        with zipfile.ZipFile(io.BytesIO(aar.read("classes.jar"))) as java:
            class_names = set(java.namelist())
            missing_classes = set(REQUIRED_CLASSES) - class_names
            if missing_classes:
                raise ValueError(f"LibVLC Java API missing: {sorted(missing_classes)}")
        for abi in MACHINES:
            prefix = f"jni/{abi}/"
            so_files = sorted(
                name for name in entries
                if name.startswith(prefix) and name.endswith(".so")
                and len(name[len(prefix):].split("/")) == 1
            )
            if not so_files:
                raise ValueError(f"LibVLC native libraries missing for {abi}")
            names = {pathlib.PurePosixPath(n).name for n in so_files}
            conflict = names & FFMPEG_JNI_BASENAMES
            if conflict:
                raise ValueError(
                    f"LibVLC/FFmpeg JNI packaging collision in {abi}: {sorted(conflict)}"
                )
            if not any("vlc" in name.lower() for name in names):
                raise ValueError(f"{abi}: no recognizable LibVLC native loader")
            native = []
            for entry in so_files:
                data = aar.read(entry)
                align = verify_elf(data, abi)
                native.append({
                    "library": pathlib.PurePosixPath(entry).name,
                    "bytes": len(data),
                    "pt_load_alignment": align,
                })
            report["abis"][abi] = {"native_libraries": native}
            print(f"PASS {abi}: {len(native)} LibVLC native libs, all PT_LOAD aligned >= 16 KiB")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("aar", type=pathlib.Path)
    parser.add_argument("report", type=pathlib.Path)
    args = parser.parse_args()
    result = verify(args.aar)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Verified all 4 LibVLC ABIs: {args.aar}")


if __name__ == "__main__":
    main()
