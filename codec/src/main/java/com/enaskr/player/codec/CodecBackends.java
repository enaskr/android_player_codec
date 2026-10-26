package com.enaskr.player.codec;

/**
 * Optional playback-engine discovery without linking LibVLC into the FFmpeg AAR.
 *
 * Include the official VideoLAN libvlc-all AAR in the consuming Android app
 * to use org.videolan.libvlc.LibVLC, Media and MediaPlayer.
 */
public final class CodecBackends {
    private CodecBackends() { }

    /**
     * Returns true when the companion LibVLC Java API is present in the app.
     * This does not assert that a particular codec/device/runtime will work.
     */
    public static boolean hasLibVlcApi() {
        try {
            ClassLoader loader = CodecBackends.class.getClassLoader();
            Class.forName("org.videolan.libvlc.LibVLC", false, loader);
            Class.forName("org.videolan.libvlc.MediaPlayer", false, loader);
            return true;
        } catch (ClassNotFoundException | LinkageError error) {
            return false;
        }
    }

    /** FFmpeg Java bindings are packaged in the primary codec AAR. */
    public static boolean hasFfmpegApi() {
        return true;
    }
}
