#!/usr/bin/env python3
"""Verify Android library ABI, SONAME/NEEDED names and ELF 16 KiB page alignment."""
from __future__ import annotations
import pathlib
import re
import struct
import subprocess
import sys

MACHINES = {"arm64-v8a": (2, 183), "armeabi-v7a": (1, 40),
            "x86": (1, 3), "x86_64": (2, 62)}
PAGE = 16 * 1024
REQUIRED = ["avutil", "swresample", "swscale", "avcodec", "avformat"]


def verify_elf(raw: bytes, abi: str) -> list[int]:
    if len(raw) < 64 or raw[:4] != b"\x7fELF" or raw[5] != 1:
        raise ValueError(f"{abi}: invalid ELF")
    arch, machine = MACHINES[abi]
    if raw[4] != arch or struct.unpack_from("<H", raw, 18)[0] != machine:
        raise ValueError(f"{abi}: wrong ELF machine/class")
    if arch == 2:
        phoff, = struct.unpack_from("<Q", raw, 32)
        phentsize, count = struct.unpack_from("<HH", raw, 54)
        min_header, offs = 56, (8, 16, 48)
        fmt = "<Q"
    else:
        phoff, = struct.unpack_from("<I", raw, 28)
        phentsize, count = struct.unpack_from("<HH", raw, 42)
        min_header, offs = 32, (4, 8, 28)
        fmt = "<I"
    if phentsize < min_header or count < 1 or phoff + phentsize * count > len(raw):
        raise ValueError(f"{abi}: corrupt ELF program header table")
    aligns = []
    for i in range(count):
        p = phoff + i * phentsize
        if struct.unpack_from("<I", raw, p)[0] != 1:
            continue
        o, v, align = (struct.unpack_from(fmt, raw, p + x)[0] for x in offs)
        if align < PAGE or align % PAGE or o % PAGE != v % PAGE:
            raise ValueError(f"{abi}: non-16KiB PT_LOAD segment: {align}")
        aligns.append(align)
    if not aligns:
        raise ValueError(f"{abi}: missing PT_LOAD")
    return aligns


def check_native_folder(folder: pathlib.Path, abi: str) -> dict:
    report = {}
    for name in REQUIRED + ["android_player_codec"]:
        path = folder / f"lib{name}.so"
        if name == "android_player_codec" and not path.exists():
            continue  # JNI library is created later by Gradle/CMake.
        if not path.exists():
            raise ValueError(f"Missing {path}")
        aligns = verify_elf(path.read_bytes(), abi)
        proc = subprocess.run(["readelf", "-dW", str(path)], capture_output=True,
                              text=True, errors="replace", check=True)
        needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", proc.stdout)
        name_line = re.findall(r"\(SONAME\).*?\[(.*?)\]", proc.stdout)
        if name_line and name_line[0] != path.name:
            raise ValueError(f"{path}: wrong SONAME {name_line[0]}")
        bad = [lib for lib in needed if re.match(r"libav\w+\.so\.\d", lib)]
        if bad:
            raise ValueError(f"{path}: versioned DT_NEEDED dependencies {bad}")
        report[name] = {"bytes": path.stat().st_size, "pt_load_alignment": aligns,
                        "needed": needed}
    return report


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in MACHINES:
        sys.exit("Usage: verify_shared_libs.py <lib-folder> <abi>")
    result = check_native_folder(pathlib.Path(sys.argv[1]), sys.argv[2])
    print(f"PASS {sys.argv[2]}: {len(result)} native libraries, 16 KiB ELF alignment")
