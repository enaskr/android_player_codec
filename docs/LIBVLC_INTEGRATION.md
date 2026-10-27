# LibVLC integration update

The current Android Codec Pack v0.3 uses LibVLC as its primary engine and
ships **one physical AAR** instead of the older two-AAR ZIP.

See [단일 Codec Pack 연동 가이드](SINGLE_AAR_KO.md) for Gradle setup, LibVLC
playback, the selective FFmpeg API, ABI validation and redistribution terms.

Existing v0.2.x two-AAR Releases remain available for backward compatibility.
Do not simultaneously declare the old separate LibVLC AAR and the new Codec Pack.
