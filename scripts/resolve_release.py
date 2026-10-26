#!/usr/bin/env python3
"""Check FFmpeg stable tags and gate heavy Android codec builds."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

FFMPEG_REMOTE = "https://github.com/FFmpeg/FFmpeg.git"
STABLE_REF = re.compile(r"^refs/tags/n([0-9]+\.[0-9]+(?:\.[0-9]+)?)$")
VERSION = re.compile(r"^n?([0-9]+\.[0-9]+(?:\.[0-9]+)?)$")
BUILD_INPUTS = (
    "codec/",
    "scripts/build_ffmpeg.sh",
    "scripts/verify_shared_libs.py",
    "scripts/verify_aar.py",
    "build.gradle.kts",
    "settings.gradle.kts",
    "gradle.properties",
    "gradle/",
)


def version_tuple(version: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(version)
    if not match:
        raise ValueError(f"Invalid stable FFmpeg version: {version!r}")
    fields = tuple(map(int, match.group(1).split(".")))
    return fields + (0,) * (3 - len(fields))


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


def required_assets(codec_version: str, ffmpeg_version: str) -> set[str]:
    return {
        f"android-player-codec-{codec_version}-ffmpeg{ffmpeg_version}.aar",
        f"FFmpeg-source-{ffmpeg_version}.tar.gz",
        "SHA256SUMS",
        "BUILD_INFO.txt",
        "VERIFICATION.json",
    }


def get_release_status(repo: str, tag: str, token: str) -> dict | None:
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "android-player-codec"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
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
    return [p for p in names if is_build_input(p)]


def decide_build(event: str, published: bool, force: bool, changed: list[str]) -> tuple[bool, str]:
    if force:
        return True, "manual force=true"
    if not published:
        return True, "FFmpeg AAR Release missing or incomplete"
    if event == "push" and changed:
        return True, f"builder source changed: {', '.join(changed[:5])}"
    return False, "all expected assets are already published"


def run() -> int:
    event = os.environ.get("GITHUB_EVENT_NAME", "schedule")
    if event not in ("schedule", "workflow_dispatch", "push"):
        raise ValueError(f"Unexpected event: {event}")
    repo = os.environ["GITHUB_REPOSITORY"]
    codec_version = os.environ.get("CODEC_VERSION", "0.1.0")
    baseline = os.environ.get("FFMPEG_BASELINE_VERSION", "9.0.2")
    requested = os.environ.get("INPUT_RELEASE_TAG", "").strip()
    force = os.environ.get("FORCE_BUILD", "false").lower() == "true"
    if event != "workflow_dispatch" and (requested or force):
        raise ValueError("release_tag and force may only be set manually")

    upstream = subprocess.check_output(
        ["git", "ls-remote", "--tags", "--refs", FFMPEG_REMOTE],
        text=True, timeout=120,
    )
    tags = stable_tags(upstream)
    if requested:
        match = VERSION.fullmatch(requested)
        if not match or match.group(1) not in tags:
            raise ValueError(f"Not a published stable FFmpeg tag: {requested}")
        version = match.group(1)
    else:
        version = newest_tag(tags)
        if version_tuple(version) < version_tuple(baseline):
            raise RuntimeError(f"Upstream latest {version} is older than baseline {baseline}")

    release_tag = f"codec-v{codec_version}-ffmpeg{version}"
    release = get_release_status(repo, release_tag, os.environ.get("GITHUB_TOKEN", ""))
    assets = {asset.get("name") for asset in release["assets"]} if release else set()
    published = release is not None and required_assets(codec_version, version).issubset(assets)
    changed = []
    if event == "push" and published:
        changed = changed_build_inputs(
            os.environ.get("GITHUB_EVENT_BEFORE", ""),
            os.environ.get("GITHUB_SHA", ""),
        )
    build, reason = decide_build(event, published, force, changed)

    outputs = {
        "build": "true" if build else "false",
        "ffmpeg_version": version,
        "release_tag": release_tag,
        "upstream_ref_sha": tags[version],
        "reason": reason,
    }
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            for name, value in outputs.items():
                out.write(f"{name}={value}\n")
    summary = (
        "## FFmpeg update check\n\n"
        f"- Event: {event}\n"
        f"- Latest selected stable FFmpeg tag: n{version}\n"
        f"- Target Release: {release_tag}\n"
        f"- Required release assets already present: {str(published).lower()}\n"
        f"- Decision: {'BUILD' if build else 'SKIP'}\n"
        f"- Reason: {reason}\n\n"
        "Scheduled check: daily 05:00 Asia/Seoul (20:00 UTC previous day).\n"
    )
    print(summary, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(summary)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"::error::FFmpeg update check failed: {error}", file=sys.stderr)
        sys.exit(1)
