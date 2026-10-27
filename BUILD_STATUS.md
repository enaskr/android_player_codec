# Current single-AAR Release v0.3.0 (2026-10-27)

- Architecture: **LibVLC 3.7.7 primary engine + selective FFmpeg 9.0.2 decoder candidates (VVC, APV, QOA)**.
- **One single Android AAR:** android-player-codec-pack-0.3.0-ffmpeg9.0.2-libvlc3.7.7.aar (115,587,624 bytes).
- Release: https://github.com/enaskr/android_player_codec/releases/tag/codec-v0.3.0-ffmpeg9.0.2-libvlc3.7.7
- GitHub-hosted-only Action run: https://github.com/enaskr/android_player_codec/actions/runs/40428226719 — **success**.
- Official LibVLC 3.7.7 Java classes, Android manifest/resources and native libraries preserved in the unified AAR and checked against original bytes.
- All four selective FFmpeg ABIs (arm64-v8a, armeabi-v7a, x86, x86_64): build, Java/JNI symbol checks and 16 KiB PT_LOAD ELF validation passed.
- Official LibVLC ABI files validated, with strict 16 KiB ELF required for arm64-v8a; x86_64 upstream also aligned. VideoLAN's arm32/x86 include 4 KiB PT_LOAD segments and are not claimed 16 KiB-compatible.
- GitHub Actions Release includes SHA256SUMS, MERGE_INFO.json, VERIFICATION.json, LIBVLC_PROVENANCE.json, official POM, selected codec policy, matching FFmpeg source and integration guide.
- These FFmpeg codec names are **curated candidates**, not a verified complete set of decoders missing from LibVLC's monolithic libvlc.so.
- Android physical-device playback, seamless FFmpeg renderer handoff, DRM compatibility and full third-party legal compliance: **not verified**.
- Daily 05:00 Asia/Seoul conditional update check is retained.

## Historical releases

### Original FFmpeg AAR (2026-10-26)

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

## LibVLC companion Release 0.2.0 (2026-10-26)

- GitHub Actions: https://github.com/enaskr/android_player_codec/actions/runs/40298585803 (success)
- Release: https://github.com/enaskr/android_player_codec/releases/tag/codec-v0.2.0-ffmpeg9.0.2-libvlc3.7.7
- Official VideoLAN LibVLC 3.7.7 downloaded unchanged from Maven Central; checked Maven upstream SHA-1 and separately recorded SHA-256.
- Four ABI native files and Java LibVLC API validated; arm64-v8a and x86_64 pass 16 KiB ELF alignment. Upstream armeabi-v7a and x86 include 4 KiB load segments; 16 KiB support for these ABIs is NOT guaranteed.
- FFmpeg 9.0.2 compiled from source for all four Android ABIs on GitHub-hosted runners; 16 KiB checks passed.
- AAR: android-player-codec-0.2.0-ffmpeg9.0.2.aar (29,413,386 bytes).
- LibVLC AAR: libvlc-all-3.7.7.aar (92,576,688 bytes).
- ZIP bundle: android-player-codec-bundle-0.2.0-ffmpeg9.0.2-libvlc3.7.7.zip (122,004,493 bytes).
- Downloaded Release checksum verified in GitHub Actions; device playback/DRM compatibility NOT tested.
- No Synology or self-hosted runner used for this Release build.
