#!/usr/bin/env python3
"""Create one downloadable bundle containing two independently consumable AARs.

Do not merge AAR classes/resources/native libraries: Android Gradle does not
support a nested AAR as a transitive dependency. Both AARs remain byte-identical.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import zipfile


def bundle_readme(codec: str, ffmpeg: str, libvlc: str) -> str:
    ffmpeg_name = f"android-player-codec-{codec}-ffmpeg{ffmpeg}.aar"
    vlc_name = f"libvlc-all-{libvlc}.aar"
    return f"""# Android Player Codec + Official VideoLAN LibVLC

Versions: Codec SDK {codec}; LGPL FFmpeg {ffmpeg}; VideoLAN LibVLC {libvlc}.

This is a DISTRIBUTION BUNDLE containing TWO AARs, not a single merged AAR.
The codec SDK is compiled from FFmpeg sources on GitHub Actions runners;
the official VideoLAN LibVLC AAR is downloaded unchanged from Maven Central
and verified against Maven's published checksum (SHA-1 for 3.7.7);\na separate SHA-256 is recorded inside GitHub Actions.

## Recommended player Gradle configuration

Place {ffmpeg_name} into app/libs/; then use:

repositories {{
    google()
    mavenCentral()
}}
dependencies {{
    implementation(files("libs/{ffmpeg_name}"))
    implementation("org.videolan.android:libvlc-all:{libvlc}")
}}

Gradle Maven integration for LibVLC is preferred: it also resolves VideoLAN's
POM-declared transitive AndroidX/Kotlin dependencies. Do not add both the local
LibVLC AAR and the Maven dependency at once: that would duplicate classes.

## Offline alternative

Put BOTH {ffmpeg_name} and {vlc_name} into app/libs/ and add:

dependencies {{
    implementation(files("libs/{ffmpeg_name}"))
    implementation(files("libs/{vlc_name}"))
}}

In that mode you must also declare the dependencies from {vlc_name[:-4]}.pom
manually. A local .aar does NOT automatically install transitive dependencies.

See docs/LIBVLC_INTEGRATION.md in the source repository for playback and Surface
examples. AARs are app compile-time dependencies, NOT independently installable
Android packages. DRM is not provided. Real-device playback remains untested.

## Sources / licenses

FFmpeg source (matching release) is a separate Release asset. FFmpeg is built
with --disable-gpl --disable-nonfree. Official LibVLC is licensed as stated
in its POM (LGPL-2.1); upstream source: 
https://code.videolan.org/videolan/libvlcjni and
https://code.videolan.org/videolan/vlc

Redistributors must satisfy the relevant copyright, source-offer, LGPL
relinkability, and third-party codec/patent obligations.
"""


def create_bundle(dist: Path, codec: str, ffmpeg: str, libvlc: str) -> Path:
    codec_name = f"android-player-codec-{codec}-ffmpeg{ffmpeg}.aar"
    vlc_name = f"libvlc-all-{libvlc}.aar"
    pom_name = f"libvlc-all-{libvlc}.pom"
    bundle_name = f"android-player-codec-bundle-{codec}-ffmpeg{ffmpeg}-libvlc{libvlc}.zip"
    files = [
        codec_name, vlc_name, pom_name, "LIBVLC_PROVENANCE.json",
        "README-BUNDLE.md", "BUILD_INFO.txt", "VERIFICATION.json",
    ]
    readme = bundle_readme(codec, ffmpeg, libvlc)
    (dist / "README-BUNDLE.md").write_text(readme, encoding="utf-8")
    for name in files:
        path = dist / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing bundle input: {path}")
    # Check required AARs before distributing files to other applications.
    for name in (codec_name, vlc_name):
        with zipfile.ZipFile(dist / name) as aar:
            if "classes.jar" not in aar.namelist():
                raise ValueError(f"{name}: classes.jar missing")
    output = dist / bundle_name
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in files:
            archive.write(dist / name, arcname=name)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError("Distribution bundle ZIP corruption")
        if sorted(archive.namelist()) != sorted(files):
            raise ValueError("Unexpected distribution ZIP file set")
    print(f"Built {output} containing {codec_name} and {vlc_name}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--codec", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--libvlc", required=True)
    args = parser.parse_args()
    create_bundle(args.dist, args.codec, args.ffmpeg, args.libvlc)


if __name__ == "__main__":
    main()
