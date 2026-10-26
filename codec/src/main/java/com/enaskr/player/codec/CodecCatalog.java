package com.enaskr.player.codec;

import android.media.MediaCodecInfo;
import android.media.MediaCodecList;
import android.os.Build;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Query hardware/software codecs installed by Android and FFmpeg in one consistent format. */
public final class CodecCatalog {
    private CodecCatalog() {}

    /** All Android platform decoders, including secure/tunneled-only codecs. */
    public static String deviceDecodersJson() {
        JSONArray result = new JSONArray();
        MediaCodecInfo[] all = new MediaCodecList(MediaCodecList.ALL_CODECS).getCodecInfos();
        for (MediaCodecInfo info : all) {
            if (info.isEncoder()) continue;
            for (String mime : info.getSupportedTypes()) {
                JSONObject row = new JSONObject();
                try {
                    row.put("name", info.getName());
                    row.put("mime", mime);
                    row.put("source", "android_mediacodec");
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        row.put("hardwareAccelerated", info.isHardwareAccelerated());
                        row.put("softwareOnly", info.isSoftwareOnly());
                    }
                    result.put(row);
                } catch (JSONException e) { throw new IllegalStateException(e); }
            }
        }
        return result.toString();
    }

    /** true indicates the device advertises a decoder for the MIME type; profile/level varies. */
    public static boolean deviceDecoderAvailable(String mime) {
        for (MediaCodecInfo info : new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos()) {
            if (info.isEncoder()) continue;
            for (String type : info.getSupportedTypes()) if (type.equalsIgnoreCase(mime)) return true;
        }
        return false;
    }

    public static String ffmpegDecodersJson() { return CodecPack.installedFfmpegDecodersJson(); }
}
