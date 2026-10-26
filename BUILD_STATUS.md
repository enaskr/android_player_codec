# Build verification (2026-10-26)

- FFmpeg: 9.0.2, LGPL decoder/demuxer build; GPL/nonfree modules excluded.
- ARM64 configuration: 477 enabled software decoders and 355 enabled demuxers.
- Target: arm64-v8a, minSdk 23, NDK 28.2.13676358, Gradle 8.9, AGP 8.7.3.
- Java classes, JNI exports, FFmpeg native libraries, and 16 KiB PT_LOAD ELF checks: PASS for arm64-v8a.
- Output: releases/android-player-codec-v0.1.0-ffmpeg9.0.2-arm64-v8a.aar
- SHA-256: 74e714f24374c648fa207f9a7f8fe007fc4dd05c8ce0778a614ccb4ec8462b25
- Device playback test: NOT RUN.
- Other ABIs: GitHub Actions is configured; not locally compiled or verified.
- GitHub repository: enaskr/android_player_codec (repository exists). CI and multi-ABI Release verification pending GitHub Actions run.
