# Player integration design

1. On app start call `CodecCatalog.deviceDecodersJson()`; this API works with the Android platform, without FFmpeg loading.
2. Before software decoding, call `CodecCatalog.ffmpegDecodersJson()` and inspect the real bundled decoders list.
3. Prefer Android `MediaCodec` video hardware decoders when the format, profile, level, resolution and secure mode are supported. This library is a software fallback.
4. For local SAF content use `CodecPack.openAudio(ContentResolver, Uri)` or `openVideo`. The file descriptor must be seekable, and the content must not be DRM-encrypted.
5. For audio create `AudioTrack` with `ENCODING_PCM_16BIT`, `CHANNEL_OUT_STEREO`, `48000`; decode on a worker thread and write PCM with correct buffer bounds.
6. For video allocate a **direct** ByteBuffer of `width*height*4` and call `readVideoFrameRgba`. RGBA conversion runs on the CPU. Schedule display using the returned presentation timestamp and an application-controlled clock.
7. Create separate `CodecSession` instances for audio and video to avoid cross-stream state contention. The SDK does not synchronize A/V clocks or render frames.
8. Close sessions promptly. All decoder handles, FDs and FFmpeg buffers are released by `close()`.
9. The AAR is a **build-time** dependency, not an APK and not a runtime plugin installer. For runtime plugin APKs, define a bound Service/AIDL contract and provide your own process/permission model.
10. Production readiness requires instrumented playback tests: H.264+AAC MP4, HEVC+AAC MKV, AV1/Opus WebM, MP3, FLAC, Vorbis, EAC3/AC3 where legal, seek tests and nonseekable failure handling. Test a 16 KiB page-size device.
