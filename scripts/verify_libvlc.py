#!/usr/bin/env python3
"""Validate official LibVLC AAR before it is included in a codec bundle.

All four supported ABIs, Java entrypoints, and native ELF architectures are
mandatory. 16 KiB PT_LOAD alignment is required for arm64-v8a; VideoLAN's
stable 3.7.7 official 32-bit native binaries can have 4 KiB alignment. Does not claim runtime playback tests.
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import struct
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


def inspect_elf(data: bytes, abi: str, require_16k: bool) -> list[int]:
    """Validate ELF class/machine/table; enforce 16 KiB only for ARM64.

    For other ABIs, keep original upstream alignment and record it without
    falsely claiming compatibility on 16 KiB page-size devices.
    """
    if require_16k:
        return verify_elf(data, abi)
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[5] != 1:
        raise ValueError(f"{abi}: malformed or non-little-endian ELF")
    expected_class, machine = MACHINES[abi]
    if data[4] != expected_class or struct.unpack_from("<H", data, 18)[0] != machine:
        raise ValueError(f"{abi}: invalid ELF architecture")
    if expected_class == 2:
        off, = struct.unpack_from("<Q", data, 32)
        entsize, count = struct.unpack_from("<HH", data, 54)
        fmt, p_offset, p_vaddr, p_align, minsize = "<Q", 8, 16, 48, 56
    else:
        off, = struct.unpack_from("<I", data, 28)
        entsize, count = struct.unpack_from("<HH", data, 42)
        fmt, p_offset, p_vaddr, p_align, minsize = "<I", 4, 8, 28, 32
    if entsize < minsize or count < 1 or off + entsize * count > len(data):
        raise ValueError(f"{abi}: corrupt ELF program header table")
    alignments = []
    for idx in range(count):
        start = off + idx * entsize
        if struct.unpack_from("<I", data, start)[0] != 1:
            continue
        offset = struct.unpack_from(fmt, data, start + p_offset)[0]
        vaddr = struct.unpack_from(fmt, data, start + p_vaddr)[0]
        align = struct.unpack_from(fmt, data, start + p_align)[0]
        if align < 4096 or align & (align - 1) or offset % align != vaddr % align:
            raise ValueError(f"{abi}: invalid PT_LOAD alignment {align}")
        alignments.append(align)
    if not alignments:
        raise ValueError(f"{abi}: no loadable ELF segments")
    return alignments


def verify(path: pathlib.Path) -> dict:
    if not path.exists() or path.stat().st_size < 1024:
        raise ValueError(f"Missing/empty LibVLC AAR: {path}")
    report = {
        "artifact": path.name,
        "abi_validation": "4 ABI ELF architecture; 16 KiB PT_LOAD required for arm64-v8a only",
        "strict_16k_abis": ["arm64-v8a"],
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
                align = inspect_elf(data, abi, require_16k=(abi == "arm64-v8a"))
                native.append({
                    "library": pathlib.PurePosixPath(entry).name,
                    "bytes": len(data),
                    "pt_load_alignment": align,
                    "is_16k_elf_aligned": all(x >= 16384 for x in align),
                })
            aligned = all(n["is_16k_elf_aligned"] for n in native)
            report["abis"][abi] = {"native_libraries": native, "all_elf_16k_aligned": aligned}
            if not aligned:
                print(f"WARNING {abi}: upstream LibVLC includes 4 KiB ELF; 16 KiB page-size compatibility not verified")
            else:
                print(f"PASS {abi}: {len(native)} LibVLC libraries, 16 KiB ELF aligned")
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
    print(f"Verified ELF machines for all four ABIs and strict ARM64 16 KiB: {args.aar}")


if __name__ == "__main__":
    main()
