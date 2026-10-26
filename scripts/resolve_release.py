#!/usr/bin/env python3
"""Select official stable FFmpeg and LibVLC releases; skip complete bundles.

The update check runs entirely inside GitHub Actions and does not install the
Android toolchain or perform remote builds. Networking errors fail closed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

FFMPEG_REMOTE = "https://github.com/FFmpeg/FFmpeg.git"
LIBVLC_METADATA = (
    "https://repo.maven.apache.org/maven2/"
    "org/videolan/android/libvlc-all/maven-metadata.xml"
)
STABLE_REF = re.compile(r"^refs/tags/n([0-9]+\.[0-9]+(?:\.[0-9]+)?)$")
FFMPEG_VERSION = re.compile(r"^n?([0-9]+\.[0-9]+(?:\.[0-9]+)?)$")
LIBVLC_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
BUILD_INPUTS = (
    "codec/",
    "scripts/build_ffmpeg.sh",
    "scripts/verify_shared_libs.py",
    "scripts/verify_aar.py",
    "scripts/verify_libvlc.py",
    "scripts/vendor_libvlc.py",
    "scripts/package_bundle.py",
    "scripts/resolve_release.py",
    "build.gradle.kts",
    "settings.gradle.kts",
    "gradle.properties",
    "gradle/",
)


def version_tuple(version: str) -> tuple[int, int, int]:
    match = FFMPEG_VERSION.fullmatch(version)
    if not match:
        raise ValueError(f"Invalid stable version: {version!r}")
    parts = tuple(map(int, match.group(1).split(".")))
    return parts + (0,) * (3 - len(parts))


def stable_tags(remote_output: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for line in remote_output.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        sha, ref = parts
        match = STABLE_REF.fullmatch(ref)
        if match and re.fullmatch(r"[0-9a-f]{40}", sha):
            tags[match.group(1)] = sha
    return tags


def newest_tag(tags: dict[str, str]) -> str:
    if not tags:
        raise RuntimeError("No stable FFmpeg release tags found; cannot build")
    return max(tags, key=version_tuple)


def libvlc_versions(metadata_xml: bytes | str) -> list[str]:
    root = ET.fromstring(metadata_xml)
    versions = []
    for entry in root.findall("./versioning/versions/version"):
        text = (entry.text or "").strip()
        if LIBVLC_VERSION.fullmatch(text):
            versions.append(text)
    return sorted(set(versions), key=version_tuple)


def latest_libvlc(metadata_xml: bytes | str) -> str:
    versions = libvlc_versions(metadata_xml)
    if not versions:
        raise RuntimeError("No stable LibVLC 3-part releases in Maven Central metadata")
    return versions[-1]


def get_libvlc_metadata() -> bytes:
    request = urllib.request.Request(
        LIBVLC_METADATA, headers={"User-Agent": "android-player-codec"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read(4 * 1024 * 1024)


def release_tag(codec_version: str, ffmpeg: str, libvlc: str) -> str:
    return f"codec-v{codec_version}-ffmpeg{ffmpeg}-libvlc{libvlc}"


def required_assets(codec_version: str, ffmpeg: str, libvlc: str) -> set[str]:
    return {
        f"android-player-codec-{codec_version}-ffmpeg{ffmpeg}.aar",
        f"libvlc-all-{libvlc}.aar",
        f"libvlc-all-{libvlc}.pom",
        f"android-player-codec-bundle-{codec_version}-ffmpeg{ffmpeg}-libvlc{libvlc}.zip",
        f"FFmpeg-source-{ffmpeg}.tar.gz",
        "LIBVLC_PROVENANCE.json",
        "README-BUNDLE.md",
        "SHA256SUMS",
        "BUILD_INFO.txt",
        "VERIFICATION.json",
    }


def get_release_status(repo: str, tag: str, token: str) -> dict | None:
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "android-player-codec",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=30
        ) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError(f"GitHub Release API returned HTTP {error.code}") from error
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise RuntimeError("Invalid GitHub Release API response")
    return data


def is_build_input(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in BUILD_INPUTS)


def changed_build_inputs(before: str, after: str) -> list[str]:
    if not before or set(before) == {"0"}:
        return ["(initial push)"]
    if not after:
        raise ValueError("GITHUB_SHA missing from push event")
    names = subprocess.check_output(
        ["git", "diff", "--name-only", before, after], text=True, timeout=30
    ).splitlines()
    return [name for name in names if is_build_input(name)]


def decide_build(
    event: str, published: bool, force: bool, changed: list[str]
) -> tuple[bool, str]:
    if force:
        return True, "manual force=true"
    if not published:
        return True, "FFmpeg/LibVLC bundle Release missing or incomplete"
    if event == "push" and changed:
        return True, f"codec builder changed: {', '.join(changed[:5])}"
    return False, "all expected FFmpeg and LibVLC bundle assets already published"


def run() -> int:
    event = os.environ.get("GITHUB_EVENT_NAME", "schedule")
    if event not in ("schedule", "workflow_dispatch", "push"):
        raise ValueError(f"Unexpected event: {event}")
    repo = os.environ["GITHUB_REPOSITORY"]
    codec_version = os.environ.get("CODEC_VERSION", "0.2.0")
    ffmpeg_baseline = os.environ.get("FFMPEG_BASELINE_VERSION", "9.0.2")
    libvlc_baseline = os.environ.get("LIBVLC_BASELINE_VERSION", "3.7.7")
    requested_ffmpeg = os.environ.get("INPUT_RELEASE_TAG", "").strip()
    requested_libvlc = os.environ.get("INPUT_LIBVLC_VERSION", "").strip()
    force = os.environ.get("FORCE_BUILD", "false").lower() == "true"
    if event != "workflow_dispatch" and (requested_ffmpeg or requested_libvlc or force):
        raise ValueError("manual version/force overrides are permitted only with workflow_dispatch")

    upstream = subprocess.check_output(
        ["git", "ls-remote", "--tags", "--refs", FFMPEG_REMOTE],
        text=True,
        timeout=120,
    )
    tags = stable_tags(upstream)
    if requested_ffmpeg:
        match = FFMPEG_VERSION.fullmatch(requested_ffmpeg)
        if not match or match.group(1) not in tags:
            raise ValueError(f"Not a published stable FFmpeg tag: {requested_ffmpeg}")
        ffmpeg = match.group(1)
    else:
        ffmpeg = newest_tag(tags)
        if version_tuple(ffmpeg) < version_tuple(ffmpeg_baseline):
            raise RuntimeError(f"FFmpeg latest {ffmpeg} older than baseline {ffmpeg_baseline}")

    metadata = get_libvlc_metadata()
    versions = libvlc_versions(metadata)
    if requested_libvlc:
        if requested_libvlc not in versions:
            raise ValueError(f"Not a published stable LibVLC version: {requested_libvlc}")
        libvlc = requested_libvlc
    else:
        libvlc = latest_libvlc(metadata)
        if version_tuple(libvlc) < version_tuple(libvlc_baseline):
            raise RuntimeError(f"LibVLC latest {libvlc} older than baseline {libvlc_baseline}")

    tag = release_tag(codec_version, ffmpeg, libvlc)
    release = get_release_status(repo, tag, os.environ.get("GITHUB_TOKEN", ""))
    assets = {
        asset.get("name") for asset in release["assets"]
        if asset.get("size", 0) > 0 and asset.get("state", "uploaded") == "uploaded"
    } if release else set()
    published = release is not None and required_assets(codec_version, ffmpeg, libvlc).issubset(assets)
    changed = []
    if event == "push" and published:
        changed = changed_build_inputs(
            os.environ.get("GITHUB_EVENT_BEFORE", ""), os.environ.get("GITHUB_SHA", "")
        )
    build, reason = decide_build(event, published, force, changed)

    outputs = {
        "build": "true" if build else "false",
        "ffmpeg_version": ffmpeg,
        "libvlc_version": libvlc,
        "release_tag": tag,
        "ffmpeg_ref_sha": tags[ffmpeg],
        "reason": reason,
    }
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            for name, value in outputs.items():
                out.write(f"{name}={value}\n")
    summary = (
        "## FFmpeg / LibVLC update check\n\n"
        f"- Event: {event}\n"
        f"- FFmpeg stable version: n{ffmpeg}\n"
        f"- LibVLC stable version: {libvlc}\n"
        f"- Target Release: {tag}\n"
        f"- Complete Release already present: {str(published).lower()}\n"
        f"- Decision: {'BUILD' if build else 'SKIP'}\n"
        f"- Reason: {reason}\n\n"
        "Schedule: daily 05:00 Asia/Seoul (20:00 UTC previous day).\n"
    )
    print(summary, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(summary)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (
        OSError, ValueError, RuntimeError, subprocess.SubprocessError,
        ET.ParseError, urllib.error.URLError
    ) as error:
        print(f"::error::FFmpeg/LibVLC update check failed: {error}", file=sys.stderr)
        sys.exit(1)
