#!/usr/bin/env python3
"""Fetch unmodified official LibVLC Android AAR and POM from Maven Central.

This script runs on GitHub-hosted Actions only. It does NOT claim to compile
LibVLC from source. Maven-provided artifact checksums (SHA-1 or SHA-256) are verified, and
provenance is recorded for LGPL redistribution and supply-chain audits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import urllib.request
import urllib.error

MAVEN_BASE = "https://repo.maven.apache.org/maven2/org/videolan/android/libvlc-all"
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def download(url: str, destination: pathlib.Path) -> dict[str, str]:
    digests = {"sha256": hashlib.sha256(), "sha1": hashlib.sha1()}
    request = urllib.request.Request(url, headers={"User-Agent": "android-player-codec"})
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as stream:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            for digest in digests.values():
                digest.update(chunk)
            stream.write(chunk)
    if destination.stat().st_size == 0:
        raise ValueError(f"Empty download: {url}")
    return {name: digest.hexdigest() for name, digest in digests.items()}


def maven_checksum(url: str) -> tuple[str, str]:
    """Maven Central offers SHA-1 sidecars for this LibVLC version (no SHA-256).
    
    Prefer SHA-256 if published later; otherwise verify Maven's SHA-1 and
    record an independently computed SHA-256 for distribution integrity.
    """
    for algorithm, length in (("sha256", 64), ("sha1", 40)):
        request = urllib.request.Request(
            f"{url}.{algorithm}", headers={"User-Agent": "android-player-codec"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(200).decode("ascii", "strict").strip()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                continue
            raise
        match = re.match(r"^([a-fA-F0-9]{" + str(length) + r"})(?:\s.*)?$", data)
        if not match:
            raise ValueError(f"Malformed Maven Central {algorithm} checksum")
        return algorithm, match.group(1).lower()
    raise ValueError("Maven Central did not publish SHA-256 or SHA-1 checksums")


def vendor(version: str, output: pathlib.Path) -> dict:
    if not VERSION.fullmatch(version):
        raise ValueError(f"Only a stable LibVLC release may be vendored: {version!r}")
    output.mkdir(parents=True, exist_ok=True)
    base = f"{MAVEN_BASE}/{version}"
    result = {}
    for kind in ("aar", "pom"):
        name = f"libvlc-all-{version}.{kind}"
        url = f"{base}/{name}"
        path = output / name
        digests = download(url, path)
        algorithm, expected = maven_checksum(url)
        if digests[algorithm] != expected:
            path.unlink(missing_ok=True)
            raise ValueError(f"Maven Central {algorithm} mismatch for {name}")
        result[name] = {
            "source_url": url,
            "sha256": digests["sha256"],
            "upstream_checksum_algorithm": algorithm,
            "upstream_checksum": expected,
            "size_bytes": path.stat().st_size,
        }
        print(f"Verified Maven Central {algorithm.upper()} for {name}; recorded SHA-256={digests['sha256']}")
    provenance = {
        "library": "VideoLAN official Android LibVLC",
        "maven_coordinates": f"org.videolan.android:libvlc-all:{version}",
        "version": version,
        "binary_origin": "Maven Central; unchanged upstream AAR",
        "license": "LGPL-2.1 (review included native plugins and upstream licensing before redistribution)",
        "project_source": "https://code.videolan.org/videolan/libvlcjni",
        "libvlc_engine_source": "https://code.videolan.org/videolan/vlc",
        "release_artifact_source": base,
        "files": result,
    }
    (output / "LIBVLC_PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return provenance


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        vendor(args.version, args.output)
    except (ValueError, OSError, urllib.error.URLError) as exc:
        parser.exit(1, f"::error::{exc}\n")
