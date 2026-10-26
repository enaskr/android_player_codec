package com.enaskr.player.codec;

import android.content.ContentResolver;
import android.content.res.AssetFileDescriptor;
import android.net.Uri;
import java.io.File;
import java.io.IOException;
import java.util.Objects;

/** FFmpeg software-decoder extension API for Android video and audio players. */
public final class CodecPack {
    private static volatile boolean loaded;
    private CodecPack() {}

    public static synchronized void ensureLoaded() {
        if (loaded) return;
        for (String name : new String[] {
                "avutil", "swresample", "swscale", "avcodec", "avformat", "android_player_codec"
        }) System.loadLibrary(name);
        loaded = true;
    }

    /** Installed FFmpeg version. Can be called only when this AAR includes native libs. */
    public static String version() {
        ensureLoaded();
        return nativeVersion();
    }

    /** JSON array of decoders actually compiled into this library. */
    public static String installedFfmpegDecodersJson() {
        ensureLoaded();
        return nativeDecoders();
    }

    /** Open a file/content URI as a software audio decoder with 48kHz, stereo, PCM16 output. */
    public static CodecSession openAudio(ContentResolver resolver, Uri uri) throws IOException {
        return open(resolver, uri, CodecSession.KIND_AUDIO);
    }

    /** Open a file/content URI as a software video decoder with RGBA8888 frame output. */
    public static CodecSession openVideo(ContentResolver resolver, Uri uri) throws IOException {
        return open(resolver, uri, CodecSession.KIND_VIDEO);
    }

    public static CodecSession openAudio(File file) throws IOException {
        return openFile(file, CodecSession.KIND_AUDIO);
    }

    public static CodecSession openVideo(File file) throws IOException {
        return openFile(file, CodecSession.KIND_VIDEO);
    }

    private static CodecSession openFile(File file, int kind) throws IOException {
        Objects.requireNonNull(file, "file");
        android.os.ParcelFileDescriptor fd =
                android.os.ParcelFileDescriptor.open(file, android.os.ParcelFileDescriptor.MODE_READ_ONLY);
        try {
            return CodecSession.open(fd.getFd(), 0, fd.getStatSize(), kind);
        } finally { fd.close(); }
    }

    private static CodecSession open(ContentResolver resolver, Uri uri, int kind) throws IOException {
        Objects.requireNonNull(resolver, "resolver");
        Objects.requireNonNull(uri, "uri");
        try (AssetFileDescriptor afd = resolver.openAssetFileDescriptor(uri, "r")) {
            if (afd == null) throw new IOException("Unable to open URI: " + uri);
            return CodecSession.open(afd.getParcelFileDescriptor().getFd(),
                    afd.getStartOffset(), afd.getLength(), kind);
        }
    }

    private static native String nativeVersion();
    private static native String nativeDecoders();
}
