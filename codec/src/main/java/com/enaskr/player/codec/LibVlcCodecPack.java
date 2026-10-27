package com.enaskr.player.codec;

import android.content.Context;
import android.net.Uri;

import org.videolan.libvlc.LibVLC;
import org.videolan.libvlc.Media;
import org.videolan.libvlc.MediaPlayer;

import java.io.Closeable;
import java.io.File;
import java.io.IOException;
import java.util.Objects;

/**
 * LibVLC-first Codec Pack API.
 *
 * Primary playback uses the bundled VideoLAN engine, including its native
 * codecs, networking and Surface support. FFmpeg is a separate, lazy-loaded,
 * SELECTIVE decoder supplement: it is not loaded for normal LibVLC playback.
 *
 * Applications retain responsibility for rendering a fallback CodecSession
 * (PCM16 stereo 48 kHz or RGBA frames). An error from LibVLC is not definitive
 * proof that a particular codec is absent, and automatic visual handoff is
 * not implied by this API.
 */
public final class LibVlcCodecPack implements Closeable {
    public static final String PRIMARY_ENGINE = "libvlc";
    public static final String FALLBACK_ENGINE = "ffmpeg-selective";

    private final LibVLC engine;
    private final MediaPlayer player;
    private boolean closed;

    private LibVlcCodecPack(Context application) {
        engine = new LibVLC(application);
        player = new MediaPlayer(engine);
    }

    /** Creates a LibVLC-backed player without loading FFmpeg. */
    public static LibVlcCodecPack create(Context context) {
        Objects.requireNonNull(context, "context");
        return new LibVlcCodecPack(context.getApplicationContext());
    }

    /** Returns the underlying official VideoLAN player for Surface attachment. */
    public MediaPlayer player() {
        ensureOpen();
        return player;
    }

    /** Starts the primary LibVLC playback path. */
    public void play(Uri uri) {
        Objects.requireNonNull(uri, "uri");
        ensureOpen();
        Media media = new Media(engine, uri);
        try {
            player.setMedia(media);
        } finally {
            media.release();
        }
        player.play();
    }

    /** Stops LibVLC playback, without loading the supplemental decoder. */
    public void stop() {
        ensureOpen();
        player.stop();
    }

    /**
     * Optional FFmpeg PCM decoder, to be used only after the app determines
     * that LibVLC cannot play this local/seekable media. Caller must close
     * the returned CodecSession and handle AudioTrack output.
     */
    public static CodecSession openSupplementalAudio(File file) throws IOException {
        return CodecPack.openAudio(Objects.requireNonNull(file, "file"));
    }

    /**
     * Optional FFmpeg RGBA decoder. Caller must render frames to a Surface
     * and close the returned CodecSession. This is NOT a full FFmpeg player.
     */
    public static CodecSession openSupplementalVideo(File file) throws IOException {
        return CodecPack.openVideo(Objects.requireNonNull(file, "file"));
    }

    /** Decoder inventory in the selective, not the LibVLC native engine. */
    public static String supplementalDecoderNamesJson() {
        return CodecPack.installedFfmpegDecodersJson();
    }

    private void ensureOpen() {
        if (closed) throw new IllegalStateException("LibVlcCodecPack was closed");
    }

    @Override
    public void close() {
        if (closed) return;
        closed = true;
        player.stop();
        player.release();
        engine.release();
    }
}
