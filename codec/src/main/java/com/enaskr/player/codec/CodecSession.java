package com.enaskr.player.codec;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.Objects;

/** One sequential audio OR video decoder; methods are synchronized and not designed for real-time sharing. */
public final class CodecSession implements AutoCloseable {
    public static final int KIND_AUDIO = 1;
    public static final int KIND_VIDEO = 2;
    public static final int AUDIO_SAMPLE_RATE = 48000;
    public static final int AUDIO_CHANNELS = 2;
    public static final int AUDIO_BYTES_PER_SAMPLE = 2;
    private long handle;
    private final int kind;
    private final String streamInfoJson;

    private CodecSession(long handle, int kind, String infoJson) {
        this.handle = handle;
        this.kind = kind;
        this.streamInfoJson = infoJson;
    }

    static CodecSession open(int fd, long offset, long length, int kind) throws IOException {
        CodecPack.ensureLoaded();
        if (kind != KIND_AUDIO && kind != KIND_VIDEO) throw new IllegalArgumentException("Invalid kind");
        long handle = nativeOpen(fd, offset, length, kind);
        if (handle == 0) throw new IOException("Native decoder failed to open");
        try {
            return new CodecSession(handle, kind, nativeInfo(handle));
        } catch (RuntimeException | Error ex) {
            nativeClose(handle);
            throw ex;
        }
    }

    /** Metadata JSON: codec name, duration, size and sample rate for the selected stream. */
    public String streamInfoJson() { return streamInfoJson; }

    public int kind() { return kind; }

    /**
     * Writes up to dst.remaining() decoded stereo interleaved PCM16 bytes.
     * @return bytes written, or -1 at end of stream.
     */
    public synchronized int readAudioPcm(ByteBuffer dst) throws IOException {
        checkOpen(KIND_AUDIO);
        checkDirect(dst);
        int result = nativeAudioRead(handle, dst, dst.position(), dst.remaining());
        if (result > 0) dst.position(dst.position() + result);
        return result;
    }

    /**
     * Writes one decoded RGBA8888 frame to dst (direct ByteBuffer).
     * Requires streamInfoJson() width * height * 4 bytes of remaining capacity.
     * @return presentation timestamp in microseconds, or -1 at EOF.
     */
    public synchronized long readVideoFrameRgba(ByteBuffer dst) throws IOException {
        checkOpen(KIND_VIDEO);
        checkDirect(dst);
        long result = nativeVideoRead(handle, dst, dst.position(), dst.remaining());
        if (result >= 0) dst.position(dst.position() + nativeVideoFrameBytes(handle));
        return result;
    }

    /** Seek the selected stream; next audio or video read resumes near positionUs. */
    public synchronized void seekToUs(long positionUs) throws IOException {
        checkOpen(kind);
        if (positionUs < 0) throw new IllegalArgumentException("Negative seek position");
        nativeSeek(handle, positionUs);
    }

    private void checkOpen(int expectedKind) {
        if (handle == 0) throw new IllegalStateException("CodecSession already closed");
        if (expectedKind != kind) throw new IllegalStateException("Wrong stream kind");
    }

    private static void checkDirect(ByteBuffer buffer) {
        Objects.requireNonNull(buffer, "buffer");
        if (!buffer.isDirect() || buffer.isReadOnly())
            throw new IllegalArgumentException("Requires writable direct ByteBuffer");
    }

    @Override public synchronized void close() {
        if (handle != 0) {
            nativeClose(handle);
            handle = 0;
        }
    }

    private static native long nativeOpen(int fd, long offset, long length, int kind) throws IOException;
    private static native String nativeInfo(long handle);
    private static native int nativeAudioRead(long handle, ByteBuffer dst, int offset, int capacity) throws IOException;
    private static native long nativeVideoRead(long handle, ByteBuffer dst, int offset, int capacity) throws IOException;
    private static native int nativeVideoFrameBytes(long handle);
    private static native void nativeSeek(long handle, long positionUs) throws IOException;
    private static native void nativeClose(long handle);
}
