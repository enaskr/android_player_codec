package com.enaskr.player.codec;

import org.json.JSONException;
import org.json.JSONObject;

/** Parsed stream metadata; the JSON form remains available for forward compatibility. */
public final class CodecInfo {
    public final String codec;
    public final String type;
    public final int width;
    public final int height;
    public final int sourceSampleRate;
    public final int sourceChannels;
    public final long durationUs;
    public final String rawJson;

    private CodecInfo(JSONObject j) {
        codec = j.optString("codec", "unknown");
        type = j.optString("type", "unknown");
        width = j.optInt("width");
        height = j.optInt("height");
        sourceSampleRate = j.optInt("sampleRate");
        sourceChannels = j.optInt("channels");
        durationUs = j.optLong("durationUs", -1);
        rawJson = j.toString();
    }

    public static CodecInfo parse(String infoJson) throws JSONException {
        return new CodecInfo(new JSONObject(infoJson));
    }
}
