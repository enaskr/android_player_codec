#!/usr/bin/env python3
"""Assemble one Android AAR using the official VideoLAN LibVLC AAR as its base.

This is not a nested-AAR dependency: we explicitly merge Java classes and
non-conflicting FFmpeg JNI libraries while preserving VideoLAN's manifest,
resources, R metadata, assets and its original native binaries unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

ABIS = ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
JAVA_ENTRYPOINTS = (
    "org/videolan/libvlc/LibVLC.class",
    "org/videolan/libvlc/MediaPlayer.class",
    "com/enaskr/player/codec/CodecPack.class",
    "com/enaskr/player/codec/CodecSession.class",
    "com/enaskr/player/codec/LibVlcCodecPack.class",
)


def entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    items = archive.infolist()
    seen: set[str] = set()
    result = {}
    for item in items:
        name = item.filename
        path = PurePosixPath(name)
        if (
            name.startswith("/") or "\\" in name or
            ".." in path.parts or
            (name in seen and not name.endswith("/"))
        ):
            raise ValueError(f"Unsafe or duplicate archive entry: {name}")
        seen.add(name)
        result[name] = item
    if archive.testzip() is not None:
        raise ValueError("AAR ZIP checksum corruption")
    return result


def merged_classes(vlc: bytes, extension: bytes) -> tuple[bytes, dict]:
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(vlc)) as base, \
         zipfile.ZipFile(io.BytesIO(extension)) as addon, \
         zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as jar:
        base_items = entries(base)
        addon_items = entries(addon)
        copied: set[str] = set()
        for source, listing in ((base, base_items), (addon, addon_items)):
            for name in listing:
                if name.endswith("/"):
                    continue
                if name in copied:
                    # Java class collisions are never safe to replace.
                    if name.endswith(".class"):
                        raise ValueError(f"Duplicate Java class: {name}")
                    # Keep VideoLAN's original JAR metadata. Never allow
                    # conflicting Android classpath service descriptors.
                    if name.startswith("META-INF/") and base.read(name) == addon.read(name):
                        continue
                    raise ValueError(f"JAR entry collision: {name}")
                jar.writestr(name, source.read(name))
                copied.add(name)
        missing = sorted(set(JAVA_ENTRYPOINTS) - copied)
        if missing:
            raise ValueError(f"Merged classes.jar is missing entrypoints: {missing}")
        report = {
            "videolan_jar_entries": len(base_items),
            "addon_jar_entries": len(addon_items),
            "merged_jar_entries": len(copied),
        }
    # Flush ZIP central directory before collecting the bytes.
    return out.getvalue(), report


def merge(vlc: Path, addon: Path, output: Path, metadata: dict | None = None) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(vlc) as base, zipfile.ZipFile(addon) as extension:
        base_names = entries(base)
        addon_names = entries(extension)
        for required in ("classes.jar", "AndroidManifest.xml", "R.txt"):
            if required not in base_names:
                raise ValueError(f"LibVLC base missing {required}")
        if "classes.jar" not in addon_names:
            raise ValueError("FFmpeg extension missing classes.jar")
        jar, java_report = merged_classes(
            base.read("classes.jar"), extension.read("classes.jar")
        )
        ffmpeg_native: list[str] = []
        for abi in ABIS:
            vlc_names = {
                PurePosixPath(n).name for n in base_names
                if n.startswith(f"jni/{abi}/") and n.endswith(".so")
            }
            addon_names_for_abi = [
                n for n in addon_names
                if n.startswith(f"jni/{abi}/") and n.endswith(".so")
            ]
            if not {"libvlc.so", "libvlcjni.so"}.issubset(vlc_names):
                raise ValueError(f"VideoLAN native engine missing for {abi}")
            if not any(PurePosixPath(n).name == "libandroid_player_codec.so"
                       for n in addon_names_for_abi):
                raise ValueError(f"Supplement JNI library missing for {abi}")
            for name in addon_names_for_abi:
                if PurePosixPath(name).name in vlc_names:
                    raise ValueError(f"Native library collision in {abi}: {name}")
                ffmpeg_native.append(name)
        # Supplement AAR must be self-contained except for its Java and native
        # files. An arbitrary Android resource merge without aapt2 is unsafe.
        allowed = {"classes.jar", "AndroidManifest.xml", "R.txt", "proguard.txt"}
        supplement_metadata = []
        for name in addon_names:
            if name.endswith("/") or name in allowed or name.startswith("jni/"):
                continue
            if name == "public.txt" and not extension.read(name).strip():
                continue
            if name == "META-INF/com/android/build/gradle/aar-metadata.properties":
                supplement_metadata.append(name)
                continue
            raise ValueError(f"Unexpected supplement AAR entry: {name}")
        # Both AARs were built with different AGP versions; the generated
        # aar-metadata.properties is not user code and need not be identical.
        # Preserve the original VideoLAN base metadata in the unified AAR.
        # Record the difference for audit instead of shipping two conflicting
        # copies with the same ZIP path.
        addon_metadata_differences = []
        for name in supplement_metadata:
            if name in base_names and base.read(name) != extension.read(name):
                addon_metadata_differences.append(name)
                print(f"INFO: retaining VideoLAN Gradle AAR metadata: {name}")
        report = {
            "format": "single-physical-aar",
            "primary_engine": "VideoLAN LibVLC",
            "supplemental_engine": "FFmpeg restricted fallback decoders",
            "libvlc_source_sha256": hashlib.sha256(vlc.read_bytes()).hexdigest(),
            "ffmpeg_addon_sha256": hashlib.sha256(addon.read_bytes()).hexdigest(),
            "verified_abis": list(ABIS),
            "libvlc_manifest_preserved": True,
            "libvlc_resources_preserved": True,
            "separate_nested_aars": False,
            "supplemental_jni_entries": ffmpeg_native,
            "videoLAN_aar_metadata_retained": True,
            "supplemental_agp_metadata_differences": addon_metadata_differences,
            **java_report,
            **(metadata or {}),
        }
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5,
                             allowZip64=True) as target:
            for name in base_names:
                if name.endswith("/"):
                    continue
                target.writestr(name, jar if name == "classes.jar" else base.read(name))
            for name in addon_names:
                if name.startswith("jni/") and name.endswith(".so"):
                    target.writestr(name, extension.read(name), compress_type=zipfile.ZIP_STORED)
            for name in supplement_metadata:
                if name not in base_names:
                    target.writestr(name, extension.read(name))
            proguard = extension.read("proguard.txt") if "proguard.txt" in addon_names else b""
            if proguard:
                if "proguard.txt" in base_names:
                    text = base.read("proguard.txt").rstrip(b"\n") + b"\n" + proguard
                    # Rewrite the existing rules only after writing the AAR:
                    # this branch is forbidden to avoid duplicate zip entries.
                    raise ValueError("Both AARs contain ProGuard rules; explicit merge required")
                target.writestr("proguard.txt", proguard)
            target.writestr("codec-pack.json",
                            json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    with zipfile.ZipFile(output) as final:
        names = entries(final)
        if len([x for x in names if x.endswith(".aar")]) > 0:
            raise ValueError("Unexpected nested AAR")
        with zipfile.ZipFile(io.BytesIO(final.read("classes.jar"))) as classes:
            if not set(JAVA_ENTRYPOINTS).issubset(set(classes.namelist())):
                raise ValueError("Java entrypoints disappeared")
    print(f"Created LibVLC-primary single AAR: {output} ({output.stat().st_size} bytes)")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--libvlc", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text()) if args.metadata else {}
    report = merge(args.libvlc, args.ffmpeg, args.output, metadata=metadata)
    args.output.with_suffix(".merge.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
