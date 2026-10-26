# Android Player Codec AAR

[한국어 설명서](README_KO.md) · [FFmpeg](https://ffmpeg.org/) · [Android MediaCodecList](https://developer.android.com/reference/android/media/MediaCodecList)

Android playback SDK packaged as an **AAR** (not a standalone APK). It exposes:

- The installed Android device hardware/software media decoder inventory (`MediaCodecList`), including decoder names and MIME types.
- FFmpeg **9.0.2** software decoders and demuxers bundled inside the AAR as separately linkable LGPL shared native libraries (`libavcodec`, `libavformat`, `libavutil`, `libswresample`, `libswscale`). External and patent-encumbered libraries are **not** enabled.
- An Android Java API to inspect the actual compiled FFmpeg decoders, open a local `File` or `content://` URI via file descriptor, read **PCM16 48 kHz stereo audio** in bounded chunks, and decode **RGBA8888 video frames** with presentation timestamps.
- ABI build scripts for `arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64`, and 16 KiB native `PT_LOAD` alignment checks.
- GitHub Actions which builds the native libraries from pinned FFmpeg source, assembles the AAR, verifies its Java/JNI symbols and native libraries, uploads artifacts, and on successful push or manual runs publishes a versioned GitHub Release including FFmpeg sources.

**Important:** This project does **not** guarantee every possible media codec or format will work on every device. Capabilities depend on the Android device, the actual FFmpeg build configuration and codec licensing. Hardware/secure codecs are not implemented by FFmpeg and DRM-protected playback is out of scope. Video in RGBA output is CPU-intensive; the app should prefer Android `MediaCodec` for supported hardware formats.

## AAR integration

[Download verified 4-ABI AAR](https://github.com/enaskr/android_player_codec/releases/download/codec-v0.1.0-ffmpeg9.0.2/android-player-codec-0.1.0-ffmpeg9.0.2.aar) · [SHA-256](https://github.com/enaskr/android_player_codec/releases/download/codec-v0.1.0-ffmpeg9.0.2/SHA256SUMS) · [Verification report](https://github.com/enaskr/android_player_codec/releases/download/codec-v0.1.0-ffmpeg9.0.2/VERIFICATION.json)


Download the verified `.aar` from GitHub Actions or Releases and place it in your Android player module under `app/libs/`:

```kotlin
dependencies {
    implementation(files("libs/android-player-codec-0.1.0-ffmpeg9.0.2.aar"))
}
```

The host player **must be rebuilt** with this AAR. Unlike an Android APK, an AAR cannot be independently installed on the phone to add codecs to an existing app. If independently installed plugins are needed, build a separate APK exposing these APIs over an Android bound service (AIDL); an AAR and an APK are different deployment models.

### Java API

```java
import android.net.Uri;
import android.content.ContentResolver;
import java.nio.ByteBuffer;
import com.enaskr.player.codec.CodecPack;
import com.enaskr.player.codec.CodecCatalog;
import com.enaskr.player.codec.CodecInfo;
import com.enaskr.player.codec.CodecSession;

String androidDecoders = CodecCatalog.deviceDecodersJson();
String ffmpegDecoders = CodecCatalog.ffmpegDecodersJson();
String ffmpegVersion = CodecPack.version();

ContentResolver resolver = context.getContentResolver();
Uri uri = /* local or provider-backed, seekable content URI */ null;
try (CodecSession session = CodecPack.openAudio(resolver, uri)) {
    CodecInfo meta = CodecInfo.parse(session.streamInfoJson());
    ByteBuffer pcm = ByteBuffer.allocateDirect(19200);  // 100 ms at 48kHz * 2ch * 2 bytes
    for (;;) {
        pcm.clear();
        int n = session.readAudioPcm(pcm);
        if (n == -1) break;
        pcm.flip();
        // Read n bytes from pcm and submit them to an AudioTrack (PCM 16-bit, stereo, 48000Hz).
    }
}

try (CodecSession video = CodecPack.openVideo(resolver, uri)) {
    CodecInfo meta = CodecInfo.parse(video.streamInfoJson());
    ByteBuffer rgba = ByteBuffer.allocateDirect(meta.width * meta.height * 4);
    long ptsUs = video.readVideoFrameRgba(rgba);
    // ptsUs == -1: EOF, otherwise schedule RGBA display at microsecond timestamp.
}
```

`CodecSession` is sequential, blocking and should be called from a worker thread, not the UI thread. `CodecPack` duplicates the supplied file descriptor; the caller may close its descriptor after opening. For cloud files, the provider needs a seekable file descriptor; this AAR does not include HTTP streaming, adaptive streaming, audio/video synchronization or playback UI. Access to DRM-protected content is not supported.

For the codec list, query the runtime using `CodecCatalog.ffmpegDecodersJson()` rather than guessing support from file extensions. `MediaCodecList` may advertise secure/tunneled hardware decoders unsuitable for a generic RGBA/PCM buffer. A MIME advertisement is not a profile/level or throughput guarantee.

## Building

Requirements: JDK 17, Gradle 8.9, Android Gradle Plugin 8.7.3, Android SDK 35, Android NDK **28.2.13676358**, CMake 3.22.1, `patchelf`, `git`, `make`, `python3`, and build prerequisites listed by FFmpeg. For Linux x86_64:

```bash
mkdir -p work
git clone --branch n9.0.2 --depth 1 https://github.com/FFmpeg/FFmpeg.git work/ffmpeg-9.0.2
export ANDROID_NDK_HOME="$HOME/Android/Sdk/ndk/28.2.13676358"
for abi in arm64-v8a armeabi-v7a x86 x86_64; do
    bash scripts/build_ffmpeg.sh "$abi"
done
gradle :codec:assembleRelease
python3 scripts/verify_aar.py codec/build/outputs/aar/codec-release.aar
```

The project intentionally **fails** if the required FFmpeg `.so` files are missing. CI builds FFmpeg from source and does not bundle unverified, closed-source or GPL-only codec libraries.

## Source tree

```
codec/src/main/java/com/enaskr/player/codec/   Java SDK
codec/src/main/cpp/                        JNI bridge, FFmpeg demux/decode, CMake
scripts/build_ffmpeg.sh                    LGPL native cross compiler
scripts/verify_shared_libs.py              ELF verification
scripts/verify_aar.py                      AAR verification
.github/workflows/build-aar.yml           GitHub Actions build/release
```

## Licensing, limitations and source obligations

The Java/JNI glue in this repository is Apache-2.0; FFmpeg retains its own LGPL licensing. The native build uses `--disable-gpl --disable-nonfree` and dynamic linking. **LGPL obligations remain**: preserve attribution and notices, make corresponding FFmpeg source available, permit reverse engineering for debugging modifications, and use a legally compliant redistribution process. The GitHub Actions Release includes the exact tagged FFmpeg source archive used to build the AAR.

FFmpeg's own guidance: https://ffmpeg.org/legal.html . Dolby, DTS, HEVC, AV1 and other formats may have patent, trademark, hardware, or distribution terms separate from FFmpeg's LGPL. This is not legal advice. Codec availability is not a guarantee of licensing clearance. FFmpeg releases should be tracked and rebuilt for security updates.

**Release status:** The [FFmpeg 9.0.2 / Codec SDK 0.1.0](https://github.com/enaskr/android_player_codec/releases/tag/codec-v0.1.0-ffmpeg9.0.2) AAR was built and independently verified for all four Android ABIs, including Java/JNI symbols and 16 KiB ELF load-segment alignment. Runtime decoding on representative Android devices is **not yet verified**. Native crashes, non-seekable streams, unusual frame layouts, codecs requiring external libraries, and DRM are explicit gaps to test before production.
