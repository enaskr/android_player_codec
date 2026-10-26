#define _FILE_OFFSET_BITS 64
#include <jni.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libavutil/bprint.h>
#include <libavutil/channel_layout.h>
#include <libavutil/error.h>
#include <libavutil/opt.h>
#include <libavutil/samplefmt.h>
#include <libswresample/swresample.h>
#include <libswscale/swscale.h>

#define KIND_AUDIO 1
#define KIND_VIDEO 2
#define PCM_RATE 48000
#define PCM_CHANNELS 2
#define MAX_VIDEO_BYTES (256 * 1024 * 1024)

/* Decoder state is confined to one Java CodecSession. Its public methods are synchronized. */
typedef struct CodecSessionNative {
    int fd;
    int64_t file_start;
    int64_t file_length;  /* -1 when unknown. */
    int64_t logical_pos;
    AVIOContext *io;
    AVFormatContext *format;
    AVCodecContext *decoder;
    AVFrame *frame;
    AVPacket *packet;
    SwrContext *swr;
    struct SwsContext *sws;
    AVChannelLayout cached_layout;
    enum AVSampleFormat cached_format;
    int cached_rate;
    int stream_index;
    int kind;
    int eof_sent;
    uint8_t *audio_cache;
    size_t audio_cache_cap;
    size_t audio_cache_size;
    size_t audio_cache_pos;
} CodecSessionNative;

static void throw_java(JNIEnv *env, const char *type, const char *message) {
    jclass klass = (*env)->FindClass(env, type);
    if (klass != NULL) (*env)->ThrowNew(env, klass, message);
}

static void throw_ffmpeg(JNIEnv *env, const char *action, int err) {
    char detail[AV_ERROR_MAX_STRING_SIZE] = {0};
    char message[512];
    av_strerror(err, detail, sizeof(detail));
    snprintf(message, sizeof(message), "%s: %s (%d)", action, detail, err);
    throw_java(env, "java/io/IOException", message);
}

static int io_read(void *opaque, uint8_t *buf, int len) {
    CodecSessionNative *s = (CodecSessionNative *)opaque;
    if (len <= 0) return AVERROR(EINVAL);
    if (s->file_length >= 0) {
        int64_t remaining = s->file_length - s->logical_pos;
        if (remaining <= 0) return AVERROR_EOF;
        if ((int64_t)len > remaining) len = (int)remaining;
    }
    ssize_t n;
    do {
        n = pread(s->fd, buf, (size_t)len, (off_t)(s->file_start + s->logical_pos));
    } while (n < 0 && errno == EINTR);
    if (n < 0) return AVERROR(errno);
    if (n == 0) return AVERROR_EOF;
    s->logical_pos += n;
    return (int)n;
}

static int64_t io_seek(void *opaque, int64_t off, int whence) {
    CodecSessionNative *s = (CodecSessionNative *)opaque;
    if ((whence & ~AVSEEK_FORCE) == AVSEEK_SIZE)
        return s->file_length >= 0 ? s->file_length : AVERROR(ENOSYS);
    int64_t pos = 0;
    switch (whence & ~AVSEEK_FORCE) {
        case SEEK_SET: pos = off; break;
        case SEEK_CUR:
            if (__builtin_add_overflow(s->logical_pos, off, &pos)) return AVERROR(EINVAL);
            break;
        case SEEK_END:
            if (s->file_length < 0 || __builtin_add_overflow(s->file_length, off, &pos))
                return AVERROR(ENOSYS);
            break;
        default: return AVERROR(EINVAL);
    }
    if (pos < 0 || (s->file_length >= 0 && pos > s->file_length)) return AVERROR(EINVAL);
    s->logical_pos = pos;
    return pos;
}

static void free_session(CodecSessionNative *s) {
    if (!s) return;
    swr_free(&s->swr);
    if (s->sws) sws_freeContext(s->sws);
    av_channel_layout_uninit(&s->cached_layout);
    avcodec_free_context(&s->decoder);
    av_packet_free(&s->packet);
    av_frame_free(&s->frame);
    if (s->format) avformat_close_input(&s->format);
    if (s->io) avio_context_free(&s->io);
    if (s->fd >= 0) close(s->fd);
    av_freep(&s->audio_cache);
    free(s);
}

JNIEXPORT jstring JNICALL
Java_com_enaskr_player_codec_CodecPack_nativeVersion(JNIEnv *env, jclass clazz) {
    (void)clazz;
    return (*env)->NewStringUTF(env, av_version_info());
}

JNIEXPORT jstring JNICALL
Java_com_enaskr_player_codec_CodecPack_nativeDecoders(JNIEnv *env, jclass clazz) {
    (void)clazz;
    AVBPrint out;
    av_bprint_init(&out, 2048, AV_BPRINT_SIZE_UNLIMITED);
    av_bprintf(&out, "[");
    void *iterator = NULL;
    const AVCodec *codec;
    int first = 1;
    while ((codec = av_codec_iterate(&iterator)) != NULL) {
        if (!av_codec_is_decoder(codec)) continue;
        if (!first) av_bprintf(&out, ",");
        first = 0;
        /* FFmpeg codec names contain only safe characters for JSON string values. */
        av_bprintf(&out, "{\"name\":\"%s\",\"type\":\"%s\"}", codec->name,
                   av_get_media_type_string(codec->type) ?: "unknown");
    }
    av_bprintf(&out, "]");
    if (!av_bprint_is_complete(&out)) {
        av_bprint_finalize(&out, NULL);
        throw_java(env, "java/lang/OutOfMemoryError", "FFmpeg codec inventory allocation failed");
        return NULL;
    }
    jstring result = (*env)->NewStringUTF(env, out.str);
    av_bprint_finalize(&out, NULL);
    return result;
}

JNIEXPORT jlong JNICALL
Java_com_enaskr_player_codec_CodecSession_nativeOpen(JNIEnv *env, jclass clazz,
                                                     jint fd, jlong start, jlong length, jint kind) {
    (void)clazz;
    if (fd < 0 || start < 0 || length < -1 || (kind != KIND_AUDIO && kind != KIND_VIDEO)) {
        throw_java(env, "java/lang/IllegalArgumentException", "Invalid descriptor, offset, length or stream type");
        return 0;
    }
    CodecSessionNative *s = (CodecSessionNative *)calloc(1, sizeof(*s));
    if (!s) { throw_java(env, "java/lang/OutOfMemoryError", "Unable to allocate decoder"); return 0; }
    s->fd = -1;
    s->stream_index = -1;
    s->cached_format = AV_SAMPLE_FMT_NONE;
    s->kind = kind;
    s->file_start = (int64_t)start;
    s->file_length = (int64_t)length;
    s->fd = dup(fd);
    if (s->fd < 0) { throw_java(env, "java/io/IOException", "dup(fd) failed"); goto fail; }
    if (s->file_length < 0) {
        struct stat st;
        if (fstat(s->fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_size >= s->file_start)
            s->file_length = st.st_size - s->file_start;
    }
    uint8_t *buffer = (uint8_t *)av_malloc(64 * 1024);
    if (!buffer) { throw_java(env, "java/lang/OutOfMemoryError", "AVIO buffer allocation failed"); goto fail; }
    s->io = avio_alloc_context(buffer, 64 * 1024, 0, s, io_read, NULL, io_seek);
    if (!s->io) {
        av_free(buffer);
        throw_java(env, "java/lang/OutOfMemoryError", "AVIO context allocation failed");
        goto fail;
    }
    s->format = avformat_alloc_context();
    if (!s->format) { throw_java(env, "java/lang/OutOfMemoryError", "Demuxer allocation failed"); goto fail; }
    s->format->pb = s->io;
    s->format->flags |= AVFMT_FLAG_CUSTOM_IO;
    int err = avformat_open_input(&s->format, NULL, NULL, NULL);
    if (err < 0) { throw_ffmpeg(env, "avformat_open_input", err); goto fail; }
    err = avformat_find_stream_info(s->format, NULL);
    if (err < 0) { throw_ffmpeg(env, "avformat_find_stream_info", err); goto fail; }
    enum AVMediaType media = kind == KIND_AUDIO ? AVMEDIA_TYPE_AUDIO : AVMEDIA_TYPE_VIDEO;
    const AVCodec *codec = NULL;
    int stream_id = av_find_best_stream(s->format, media, -1, -1, &codec, 0);
    if (stream_id < 0 || !codec) { throw_ffmpeg(env, "No supported decoder for selected stream", stream_id); goto fail; }
    s->stream_index = stream_id;
    s->decoder = avcodec_alloc_context3(codec);
    if (!s->decoder) { throw_java(env, "java/lang/OutOfMemoryError", "Codec context allocation failed"); goto fail; }
    err = avcodec_parameters_to_context(s->decoder, s->format->streams[stream_id]->codecpar);
    if (err >= 0) err = avcodec_open2(s->decoder, codec, NULL);
    if (err < 0) { throw_ffmpeg(env, "avcodec_open2", err); goto fail; }
    s->frame = av_frame_alloc();
    s->packet = av_packet_alloc();
    if (!s->frame || !s->packet) { throw_java(env, "java/lang/OutOfMemoryError", "Frame/packet allocation failed"); goto fail; }
    if (kind == KIND_VIDEO) {
        int64_t video_bytes = (int64_t)s->decoder->width * s->decoder->height * 4;
        if (video_bytes <= 0 || video_bytes > MAX_VIDEO_BYTES) {
            throw_java(env, "java/io/IOException", "Unsupported/oversized video dimensions"); goto fail;
        }
    }
    return (jlong)(uintptr_t)s;
fail:
    free_session(s);
    return 0;
}

static CodecSessionNative *get_session(JNIEnv *env, jlong handle) {
    if (!handle) {
        throw_java(env, "java/lang/IllegalStateException", "Codec session closed");
        return NULL;
    }
    return (CodecSessionNative *)(uintptr_t)handle;
}

JNIEXPORT jstring JNICALL
Java_com_enaskr_player_codec_CodecSession_nativeInfo(JNIEnv *env, jclass clazz, jlong handle) {
    (void)clazz;
    CodecSessionNative *s = get_session(env, handle);
    if (!s) return NULL;
    char info[1024];
    int64_t duration = s->format->duration == AV_NOPTS_VALUE ? -1 : s->format->duration;
    const char *codec = avcodec_get_name(s->decoder->codec_id);
    int channels = s->decoder->ch_layout.nb_channels;
    snprintf(info, sizeof(info),
             "{\"type\":\"%s\",\"codec\":\"%s\",\"durationUs\":%" PRId64
             ",\"width\":%d,\"height\":%d,\"sampleRate\":%d,\"channels\":%d}",
             s->kind == KIND_AUDIO ? "audio" : "video", codec, duration,
             s->decoder->width, s->decoder->height, s->decoder->sample_rate, channels);
    return (*env)->NewStringUTF(env, info);
}

static int decoder_read_next(CodecSessionNative *s) {
    for (;;) {
        int r = avcodec_receive_frame(s->decoder, s->frame);
        if (r == 0) return 1;
        if (r == AVERROR_EOF) return 0;
        if (r != AVERROR(EAGAIN)) return r;
        r = av_read_frame(s->format, s->packet);
        if (r < 0) {
            if (!s->eof_sent) {
                s->eof_sent = 1;
                r = avcodec_send_packet(s->decoder, NULL);
                if (r < 0 && r != AVERROR_EOF) return r;
                continue;
            }
            return 0;
        }
        if (s->packet->stream_index != s->stream_index) { av_packet_unref(s->packet); continue; }
        r = avcodec_send_packet(s->decoder, s->packet);
        av_packet_unref(s->packet);
        if (r < 0) return r;
    }
}

static int resample_frame(CodecSessionNative *s) {
    AVChannelLayout in_layout;
    memset(&in_layout, 0, sizeof(in_layout));
    if (s->frame->ch_layout.nb_channels) {
        int e = av_channel_layout_copy(&in_layout, &s->frame->ch_layout);
        if (e < 0) return e;
    } else {
        av_channel_layout_default(&in_layout, PCM_CHANNELS);
    }
    const int rate = s->frame->sample_rate;
    if (rate <= 0) { av_channel_layout_uninit(&in_layout); return AVERROR(EINVAL); }
    int changed = !s->swr || s->cached_rate != rate || s->cached_format != s->frame->format ||
                  av_channel_layout_compare(&s->cached_layout, &in_layout);
    if (changed) {
        swr_free(&s->swr);
        av_channel_layout_uninit(&s->cached_layout);
        AVChannelLayout out_layout;
        av_channel_layout_default(&out_layout, PCM_CHANNELS);
        int err = swr_alloc_set_opts2(&s->swr, &out_layout, AV_SAMPLE_FMT_S16, PCM_RATE,
                                      &in_layout, (enum AVSampleFormat)s->frame->format,
                                      rate, 0, NULL);
        av_channel_layout_uninit(&out_layout);
        if (err >= 0) err = swr_init(s->swr);
        if (err < 0) { av_channel_layout_uninit(&in_layout); return err; }
        av_channel_layout_copy(&s->cached_layout, &in_layout);
        s->cached_rate = rate;
        s->cached_format = (enum AVSampleFormat)s->frame->format;
    }
    av_channel_layout_uninit(&in_layout);
    int64_t samples = av_rescale_rnd(swr_get_delay(s->swr, rate) + s->frame->nb_samples,
                                     PCM_RATE, rate, AV_ROUND_UP);
    if (samples <= 0 || samples > 5000000) return AVERROR(EINVAL);
    size_t max_bytes = (size_t)samples * PCM_CHANNELS * sizeof(int16_t);
    if (max_bytes > s->audio_cache_cap) {
        uint8_t *next = (uint8_t *)av_realloc(s->audio_cache, max_bytes);
        if (!next) return AVERROR(ENOMEM);
        s->audio_cache = next;
        s->audio_cache_cap = max_bytes;
    }
    uint8_t *out_planes[] = {s->audio_cache};
    int count = swr_convert(s->swr, out_planes, (int)samples,
                             (const uint8_t **)s->frame->extended_data, s->frame->nb_samples);
    if (count < 0) return count;
    s->audio_cache_size = (size_t)count * PCM_CHANNELS * sizeof(int16_t);
    s->audio_cache_pos = 0;
    return 0;
}

JNIEXPORT jint JNICALL
Java_com_enaskr_player_codec_CodecSession_nativeAudioRead(JNIEnv *env, jclass clazz,
                                                     jlong handle, jobject dest, jint offset, jint capacity) {
    (void)clazz;
    CodecSessionNative *s = get_session(env, handle);
    if (!s) return -1;
    if (s->kind != KIND_AUDIO) { throw_java(env, "java/lang/IllegalStateException", "Audio decoder required"); return -1; }
    uint8_t *buffer = (*env)->GetDirectBufferAddress(env, dest);
    jlong available = (*env)->GetDirectBufferCapacity(env, dest);
    if (!buffer || offset < 0 || capacity <= 0 || available < (jlong)offset + capacity) {
        throw_java(env, "java/lang/IllegalArgumentException", "Writable direct buffer with free space required"); return -1;
    }
    if (s->audio_cache_pos >= s->audio_cache_size) {
        int r;
        do {
            r = decoder_read_next(s);
            if (r == 0) return -1;
            if (r < 0) { throw_ffmpeg(env, "Audio decode failed", r); return -1; }
            r = resample_frame(s);
            av_frame_unref(s->frame);
            if (r < 0) { throw_ffmpeg(env, "Audio resample failed", r); return -1; }
        } while (s->audio_cache_size == 0);
    }
    size_t left = s->audio_cache_size - s->audio_cache_pos;
    size_t n = left < (size_t)capacity ? left : (size_t)capacity;
    n &= ~(size_t)3;  /* stereo s16 frames are four bytes */
    if (!n) { throw_java(env, "java/lang/IllegalArgumentException", "Buffer needs at least four free bytes"); return -1; }
    memcpy(buffer + offset, s->audio_cache + s->audio_cache_pos, n);
    s->audio_cache_pos += n;
    return (jint)n;
}

JNIEXPORT jint JNICALL
Java_com_enaskr_player_codec_CodecSession_nativeVideoFrameBytes(JNIEnv *env, jclass clazz, jlong handle) {
    (void)clazz;
    CodecSessionNative *s = get_session(env, handle);
    return s ? s->decoder->width * s->decoder->height * 4 : -1;
}

JNIEXPORT jlong JNICALL
Java_com_enaskr_player_codec_CodecSession_nativeVideoRead(JNIEnv *env, jclass clazz,
                                                     jlong handle, jobject dest, jint offset, jint capacity) {
    (void)clazz;
    CodecSessionNative *s = get_session(env, handle);
    if (!s) return -1;
    if (s->kind != KIND_VIDEO) { throw_java(env, "java/lang/IllegalStateException", "Video decoder required"); return -1; }
    uint8_t *buffer = (*env)->GetDirectBufferAddress(env, dest);
    jlong available = (*env)->GetDirectBufferCapacity(env, dest);
    int width = s->decoder->width, height = s->decoder->height;
    int64_t bytes = (int64_t)width * height * 4;
    if (!buffer || bytes <= 0 || bytes > capacity || offset < 0 || available < offset + bytes) {
        throw_java(env, "java/lang/IllegalArgumentException", "Direct RGBA buffer smaller than frame width*height*4"); return -1;
    }
    int r = decoder_read_next(s);
    if (r == 0) return -1;
    if (r < 0) { throw_ffmpeg(env, "Video decode failed", r); return -1; }
    s->sws = sws_getCachedContext(s->sws, s->frame->width, s->frame->height,
                                   (enum AVPixelFormat)s->frame->format,
                                   width, height, AV_PIX_FMT_RGBA,
                                   SWS_BILINEAR, NULL, NULL, NULL);
    if (!s->sws) { av_frame_unref(s->frame); throw_java(env, "java/io/IOException", "RGBA converter setup failed"); return -1; }
    uint8_t *dst[] = {buffer + offset, NULL, NULL, NULL};
    int strides[] = {width * 4, 0, 0, 0};
    r = sws_scale(s->sws, (const uint8_t *const *)s->frame->data, s->frame->linesize,
                  0, s->frame->height, dst, strides);
    int64_t pts = s->frame->best_effort_timestamp;
    int64_t time_us = pts == AV_NOPTS_VALUE ? 0 :
        av_rescale_q(pts, s->format->streams[s->stream_index]->time_base, AV_TIME_BASE_Q);
    av_frame_unref(s->frame);
    if (r <= 0) { throw_java(env, "java/io/IOException", "RGBA swscale conversion failed"); return -1; }
    return time_us < 0 ? 0 : (jlong)time_us;
}

JNIEXPORT void JNICALL
Java_com_enaskr_player_codec_CodecSession_nativeSeek(JNIEnv *env, jclass clazz,
                                                jlong handle, jlong position_us) {
    (void)clazz;
    CodecSessionNative *s = get_session(env, handle);
    if (!s) return;
    if (position_us < 0) { throw_java(env, "java/lang/IllegalArgumentException", "Negative position"); return; }
    int r = av_seek_frame(s->format, -1, position_us, AVSEEK_FLAG_BACKWARD);
    if (r < 0) { throw_ffmpeg(env, "Seek failed", r); return; }
    avcodec_flush_buffers(s->decoder);
    s->audio_cache_size = s->audio_cache_pos = 0;
    s->eof_sent = 0;
    av_frame_unref(s->frame);
    av_packet_unref(s->packet);
}

JNIEXPORT void JNICALL
Java_com_enaskr_player_codec_CodecSession_nativeClose(JNIEnv *env, jclass clazz, jlong handle) {
    (void)env; (void)clazz;
    if (handle) free_session((CodecSessionNative *)(uintptr_t)handle);
}
