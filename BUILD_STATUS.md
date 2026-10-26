# Build verification (2026-10-26)

- FFmpeg: 9.0.2, LGPL decoder/demuxer build; GPL/nonfree modules excluded.
- ARM64 configuration: 477 enabled software decoders and 355 enabled demuxers.
- Target: arm64-v8a, minSdk 23, NDK 28.2.13676358, Gradle 8.9, AGP 8.7.3.
- Java classes, JNI exports, FFmpeg native libraries, and 16 KiB PT_LOAD ELF checks: PASS for arm64-v8a.
- Output: releases/android-player-codec-v0.1.0-ffmpeg9.0.2-arm64-v8a.aar
- SHA-256: 74e714f24374c648fa207f9a7f8fe007fc4dd05c8ce0778a614ccb4ec8462b25
- Device playback test: NOT RUN.
- Four-ABI GitHub Actions build: PASS (arm64-v8a, armeabi-v7a, x86, x86_64), including packaged AAR JNI/Java/16 KiB ELF checks.
- GitHub Release: https://github.com/enaskr/android_player_codec/releases/tag/codec-v0.1.0-ffmpeg9.0.2 (published 2026-10-26).
- AAR artifact: android-player-codec-0.1.0-ffmpeg9.0.2.aar (29,412,803 bytes), SHA-256 check passed after downloading to Synology.
- CI build: https://github.com/enaskr/android_player_codec/actions/runs/40293648515 (success).
- Synology verified copy: releases/codec-v0.1.0-ffmpeg9.0.2/ (all 4 ABIs pass standalone verifier).
