#!/usr/bin/env python3
"""Verify the single LibVLC-primary Codec Pack AAR before Release publication."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from verify_aar import verify as verify_ffmpeg
from verify_libvlc import verify as verify_original_libvlc

ABIS = ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
JNI = ("libvlc.so", "libvlcjni.so", "libc++_shared.so")
REQUIRED_CLASSES = (
    "org/videolan/libvlc/LibVLC.class",
    "org/videolan/libvlc/MediaPlayer.class",
    "org/videolan/libvlc/Media.class",
    "com/enaskr/player/codec/LibVlcCodecPack.class",
    "com/enaskr/player/codec/CodecPack.class",
    "com/enaskr/player/codec/CodecSession.class",
)


def verify(unified: Path, vlc_original: Path, ffmpeg_addon: Path) -> dict:
    # This gate checks FFmpeg's Java native symbols and all 4 ABIs' 16 KiB ELF
    # alignment, and separately checks all VideoLAN ABIs with strict ARM64.
    ffmpeg = verify_ffmpeg(unified)
    original_vlc = verify_original_libvlc(vlc_original)

    with zipfile.ZipFile(unified) as pack, \
         zipfile.ZipFile(vlc_original) as upstream, \
         zipfile.ZipFile(ffmpeg_addon) as addon:
        names = pack.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate entries inside the combined AAR")
        if any(n.endswith(".aar") for n in names):
            raise ValueError("A nested AAR is not a valid single-AAR Codec Pack")
        if not {"classes.jar", "AndroidManifest.xml", "R.txt", "codec-pack.json"}.issubset(names):
            raise ValueError("LibVLC base metadata or unified provenance is missing")

        metadata = json.loads(pack.read("codec-pack.json"))
        if metadata["primary_engine"] != "VideoLAN LibVLC":
            raise ValueError("Primary engine was changed from LibVLC")
        if metadata.get("separate_nested_aars") is not False:
            raise ValueError("Invalid nested AAR metadata")
        if metadata["libvlc_source_sha256"] != hashlib.sha256(vlc_original.read_bytes()).hexdigest():
            raise ValueError("LibVLC original SHA-256 mismatch")
        if metadata["ffmpeg_addon_sha256"] != hashlib.sha256(ffmpeg_addon.read_bytes()).hexdigest():
            raise ValueError("FFmpeg extension SHA-256 mismatch")

        # Keep all original resources, assets, manifest, native libraries,
        # external jars and raw R metadata. Only classes.jar is combined.
        preserved = []
        for name in upstream.namelist():
            if name.endswith("/") or name == "classes.jar":
                continue
            if name not in names or pack.read(name) != upstream.read(name):
                raise ValueError(f"Original LibVLC file changed: {name}")
            preserved.append(name)

        with zipfile.ZipFile(io.BytesIO(pack.read("classes.jar"))) as merged_jar, \
             zipfile.ZipFile(io.BytesIO(upstream.read("classes.jar"))) as vlc_jar, \
             zipfile.ZipFile(io.BytesIO(addon.read("classes.jar"))) as addon_jar:
            merged = set(merged_jar.namelist())
            if not set(REQUIRED_CLASSES).issubset(merged):
                raise ValueError(f"Required Codec Pack classes missing: {set(REQUIRED_CLASSES) - merged}")
            for source in (vlc_jar, addon_jar):
                for name in source.namelist():
                    if name.endswith("/"):
                        continue
                    if name not in merged or merged_jar.read(name) != source.read(name):
                        raise ValueError(f"Java class or JAR metadata changed: {name}")

        for abi in ABIS:
            for lib in JNI:
                native = f"jni/{abi}/{lib}"
                if native not in names:
                    raise ValueError(f"Missing original LibVLC native library {native}")
            if f"jni/{abi}/libandroid_player_codec.so" not in names:
                raise ValueError(f"Missing FFmpeg fallback JNI in {abi}")
            for entry in addon.namelist():
                if not entry.startswith(f"jni/{abi}/") or not entry.endswith(".so"):
                    continue
                if entry not in names or pack.read(entry) != addon.read(entry):
                    raise ValueError(f"FFmpeg fallback native lib changed: {entry}")

    result = {
        "single_aar": unified.name,
        "primary": "LibVLC",
        "supplemental": "Selective FFmpeg candidate decoders (lazy loaded)",
        "verified_abis": list(ABIS),
        "preserved_videolan_entries": len(preserved),
        "libvlc": original_vlc,
        "ffmpeg": ffmpeg,
        "native_alignment_note": "LibVLC arm64-v8a 16 KiB required; upstream 32-bit may be 4 KiB",
        "actual_android_device_playback": "not tested",
        "availability_note": "No proof that every listed supplemental candidate is absent in LibVLC",
    }
    print(f"PASS single AAR: LibVLC unchanged, selective FFmpeg native and merged Java for {len(ABIS)} ABIs")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aar", required=True, type=Path)
    parser.add_argument("--libvlc", required=True, type=Path)
    parser.add_argument("--ffmpeg", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = verify(args.aar, args.libvlc, args.ffmpeg)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
