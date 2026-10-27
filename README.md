# Android Codec Pack — LibVLC-first Single AAR

[한국어](README_KO.md) · [Integration guide](docs/SINGLE_AAR_KO.md) · [Actions](https://github.com/enaskr/android_player_codec/actions)

This repository builds ONE physical Android AAR, keeping the official VideoLAN LibVLC engine as the primary player and adding a small FFmpeg decoder supplement. LibVLC Java classes, Android manifest/resources and native libraries are preserved byte-for-byte. FFmpeg supplement Java classes and non-colliding native JNI libraries are merged into the same AAR, not nested as another AAR.

## Decoder architecture

- Primary engine: VideoLAN LibVLC 3.7.7 stable baseline — media playback, streaming, Surface and subtitles.
- FFmpeg supplement: VVC/H.266, APV and QOA decoder candidates from FFmpeg 9.0.2. All other stock FFmpeg decoders are explicitly disabled to reduce duplication and size.
- Primary API: com.enaskr.player.codec.LibVlcCodecPack. Normal LibVLC playback never loads the supplemental FFmpeg libraries.
- Secondary API: CodecPack and CodecSession, which expose raw PCM16/RGBA decoding for local seekable media when the application determines LibVLC cannot play it. Applications must implement supplemental rendering; this is not a full automatic fallback video player.
- ABI: arm64-v8a, armeabi-v7a, x86, x86_64; Android minSdk 23.

**Support statement:** LibVLC provides a monolithic native binary without an authoritative inventory of its enabled decoders. VVC, APV and QOA are curated additional candidates, not proven to be universally absent from LibVLC. This build does not claim a complete, independently verified difference between the two engines. Verify each format against real Android devices and media samples.

## Install one AAR

After the v0.3.0 Release passes CI, place the following one file in your app/libs directory:

~~~kotlin
dependencies {
    implementation(files("libs/android-player-codec-pack-0.3.0-ffmpeg9.0.2-libvlc3.7.7.aar"))
}
~~~

Do NOT also declare the separate official LibVLC AAR, or it would duplicate classes/native libraries. The AAR may need Java/AndroidX transitive dependencies from the official LibVLC Maven POM; local AAR files do not automatically resolve them. The Release supplies that POM for reference.

## GitHub Actions only

Check latest stable FFmpeg Git tags and LibVLC Maven Central versions daily at **05:00 Asia/Seoul** (UTC cron: 0 20 * * *). If a complete release for this version combination already exists, skip all expensive builds.

Otherwise build only the selected FFmpeg supplement on GitHub-hosted Ubuntu 24.04 for four Android ABIs; validate its JNI and 16 KiB ELF alignment; retrieve and checksum-check the original official LibVLC AAR; merge and independently verify the final one AAR; then publish it with SHA-256, FFmpeg matching source, LibVLC provenance, POM and verification report. VideoLAN's own LibVLC binary is an upstream prebuilt, not recompiled here. No Synology, self-hosted runner or external build server is used for this project.

LibVLC ARM64 is checked for 16 KiB ELF alignment. Official 3.7.7 ARM32 and x86 binaries contain 4 KiB load segments and their 16 KiB compatibility is not guaranteed. Android device playback, DRM and codec patent compliance require separate validation.

Licensing: LibVLC LGPL-2.1; LGPL-configured FFmpeg with GPL/nonfree disabled. See [integration/redistribution guidance](docs/SINGLE_AAR_KO.md).
