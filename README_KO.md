# Android Codec Pack — LibVLC 중심 단일 AAR

[통합 연동 가이드](docs/SINGLE_AAR_KO.md) · [GitHub Actions](https://github.com/enaskr/android_player_codec/actions) · [Releases](https://github.com/enaskr/android_player_codec/releases)

이 프로젝트는 **LibVLC를 기본 재생 엔진**으로 사용하면서 FFmpeg의 선별 보완 디코더를 하나의 Android AAR 파일에 포함합니다. 공식 LibVLC의 Java 클래스·Android 리소스·네이티브 바이너리는 원본 그대로 유지하고, 충돌하지 않는 FFmpeg Java/JNI를 동일 AAR에 병합합니다.

| 구성 | 내용 |
|---|---|
| 기본 재생 엔진 | 공식 VideoLAN LibVLC 3.7.7 |
| FFmpeg 보완 디코더 | VVC(H.266), APV, QOA 후보 |
| Android ABI | arm64-v8a, armeabi-v7a, x86, x86_64 |
| Android 최소 버전 | API 23 |
| GitHub 자동 확인 | 매일 05:00 KST |
| 빌드 실행 | GitHub-hosted Ubuntu 24.04 |

**중요:** LibVLC의 전체 디코더 목록은 공식 AAR에서 확정할 수 없습니다. 위 후보들이 모두 LibVLC에 없다는 사실이나 FFmpeg의 모든 차집합을 추출했다는 사실은 **확인되지 않았습니다.** 일반 FFmpeg 디코더 수백 개를 중복 탑재하지 않도록 우선 세 가지 희귀·신규 후보만 선택했습니다.

## 단일 AAR 설치

GitHub Actions가 검증·배포한 후 Android 앱의 app/libs에 다음 파일 하나만 복사합니다.

~~~kotlin
dependencies {
    implementation(files("libs/android-player-codec-pack-0.3.0-ffmpeg9.0.2-libvlc3.7.7.aar"))
}
~~~

추가로 별도의 LibVLC AAR을 설치하면 클래스가 중복됩니다. 단, LibVLC의 AndroidX/Kotlin 전이 의존성은 프로젝트에서 확인해야 합니다. 로컬 AAR 파일만으로 Maven 전이 의존성이 설치되지는 않습니다.

## 재생 API

기본 재생은 LibVlcCodecPack.create(context).play(uri)로 실행합니다. 재생 Surface 출력에는 공식 VideoLAN MediaPlayer의 VLCVout을 연결해야 합니다.

앱에서 LibVLC가 특정 로컬 파일을 디코딩할 수 없다고 판단하면 openSupplementalVideo/openSupplementalAudio로 FFmpeg 보완 디코딩을 요청할 수 있습니다. 기존 CodecSession은 원시 RGBA 프레임 또는 PCM16을 반환하므로 렌더링과 오디오 출력은 앱이 구현해야 합니다. 자동으로 두 재생 엔진이 완벽히 전환되는 것은 아닙니다.

## 자동화 및 검증

매일 05:00 KST에 LibVLC와 FFmpeg의 최신 정식 버전을 조회합니다. 동일 버전 조합의 단일 AAR이 이미 성공 배포되어 있으면 빌드 작업을 생략합니다. 업데이트 시 모든 컴파일·검증·배포를 GitHub Actions의 표준 runner에서 수행합니다.

FFmpeg 4개 ABI는 JNI/16 KiB ELF 정렬을 확인하고, LibVLC는 ARM64 16 KiB 정렬을 검사합니다. 공식 LibVLC 3.7.7의 ARM32 및 x86 바이너리에는 4 KiB ELF 세그먼트가 존재하므로 16 KiB 페이지 크기 호환성은 보장하지 않습니다.

라이선스: VideoLAN LibVLC LGPL-2.1, FFmpeg LGPL(GPL/nonfree 비활성화). 실제 재생·DRM·특허 및 모든 미디어 포맷 호환성은 별도 검증이 필요합니다.
