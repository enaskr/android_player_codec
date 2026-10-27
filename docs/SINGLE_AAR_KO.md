# LibVLC 중심 단일 Android Codec Pack AAR

## 구성

**배포물은 단일 AAR 파일 한 개입니다.** 기존처럼 FFmpeg와 LibVLC AAR을 따로 설치하거나 ZIP 안에 중첩하지 않습니다.

- 기본 플레이어: 공식 VideoLAN LibVLC(3.7.7 기준)
- FFmpeg 추가 디코더: VVC(H.266), APV, QOA의 **선별 보완 후보**
- JNI 네이티브 바이너리: Android arm64-v8a, armeabi-v7a, x86, x86_64
- API: 공식 org.videolan.libvlc.* 와 com.enaskr.player.codec.* 를 한 AAR에 포함
- Android Manifest, R.txt, 리소스, LibVLC 네이티브 바이너리는 공식 원본과 바이트 단위 일치하도록 검증
- FFmpeg는 LibVLC 기본 재생에 자동으로 로드되지 않으며, 앱이 보완 디코더를 요청할 때만 로드

## 코덱 차집합 관련 한계

LibVLC 3.7.7은 각 ABI에 단일 libvlc.so에 디코더를 통합합니다. 제공된 AAR에는 실제 지원하는 모든 디코더 목록을 신뢰성 있게 열거할 수 있는 정형 메타데이터가 없습니다. 따라서 VVC, APV, QOA를 LibVLC에 반드시 없는 코덱이라고 단정하거나 FFmpeg의 모든 누락 코덱을 자동 추출했다고 주장하지 않습니다.

이 3종은 FFmpeg 9.0.2 원본에 포함된 희귀·신규 포맷의 **보완 후보**로 명시적으로 지정했습니다. scripts/supplemental-codecs.json에서 후보를 관리하며 FFmpeg의 나머지 수백 개 일반 디코더는 빌드하지 않습니다. 실제 차집합을 검증하려면 LibVLC와 FFmpeg 양쪽으로 동일한 미디어 샘플을 재생하는 실기기 검사가 필요합니다.

FFmpeg 보완 디코더는 LibVLC에서 해당 미디어를 디코딩할 수 없다고 앱이 판단한 경우에만 사용합니다. 하나의 AAR로 묶었다는 이유만으로 엔진이 자동 전환되지는 않습니다.

## 플레이어 연결

배포된 단일 AAR 파일을 Android 프로젝트 app/libs 폴더에 복사합니다.

~~~kotlin
dependencies {
    implementation(files("libs/android-player-codec-pack-0.3.0-ffmpeg9.0.2-libvlc3.7.7.aar"))
}
~~~

LibVLC가 의존하는 AndroidX/Kotlin 라이브러리는 Maven 전이 의존성이 있을 수 있습니다. 로컬 AAR 파일은 전이 의존성을 자동 해결하지 않으므로 배포된 libvlc-all-3.7.7.pom과 사용자 프로젝트의 Gradle 의존성을 확인해야 합니다. **하나의 AAR에 두 엔진이 들어간다는 것과 외부 Java 의존성이 전혀 없다는 것은 다릅니다.**

### 기본 LibVLC 재생

~~~java
LibVlcCodecPack pack = LibVlcCodecPack.create(context);
pack.play(android.net.Uri.parse("https://example.org/video.mp4"));
// Surface 출력: pack.player().getVLCVout() 연결
// 수명 종료: pack.close();
~~~

MediaPlayer는 공식 VideoLAN API를 그대로 제공합니다. 영상 Surface, 자막, 네트워크 스트림, 이벤트, 라이프사이클은 LibVLC 문서를 따릅니다.

### FFmpeg 보완 디코딩

~~~java
// LibVLC로 재생할 수 없는 로컬/seekable 파일에서만 선택
CodecSession session = LibVlcCodecPack.openSupplementalVideo(new java.io.File("/path/file.mp4"));
// CodecSession의 RGBA 프레임 또는 PCM16을 앱 렌더러에 연결
// 반드시 session.close();
~~~

이 API는 독립 FFmpeg 동영상 플레이어가 아닙니다. 기존 CodecSession은 로컬 파일의 PCM16 48kHz stereo 또는 RGBA 프레임을 디코딩하고, 영상·오디오 출력과 동기화는 앱의 책임입니다. FFmpeg 네트워크 스트리밍은 이 보완 모듈에서 비활성화되어 있습니다.

## 빌드 및 배포 자동화

- 매일 한국시간 05:00에 FFmpeg와 LibVLC 안정 버전을 확인
- 버전 조합의 단일 AAR이 정상 배포되어 있으면 빌드 생략
- 업데이트 시 GitHub-hosted Ubuntu 24.04에서 FFmpeg 선택 디코더를 4개 ABI로 컴파일
- 공식 LibVLC AAR을 Maven Central에서 내려받아 공식 체크섬 검증
- VideoLAN 원본 Java 클래스·리소스·native 엔진을 보존하면서 보완 FFmpeg 클래스/JNI를 하나의 AAR에 병합
- FFmpeg 모든 ABI의 16 KiB ELF 정렬과 LibVLC ARM64 16 KiB ELF 정렬 및 JNI/해시 확인 후 GitHub Release 게시
- Synology 및 self-hosted runner에서는 빌드하지 않음

## 라이선스 및 범위

- FFmpeg는 GPL/nonfree 옵션 비활성화, LGPL 동적 라이브러리
- LibVLC는 VideoLAN 공식 LGPL-2.1 바이너리를 보존. 대응 소스는 VideoLAN 공식 저장소 참고
- 소스: https://code.videolan.org/videolan/libvlcjni / https://code.videolan.org/videolan/vlc / https://ffmpeg.org
- 실제 Android 기기 재생·DRM·특허 및 모든 미디어 포맷 호환성은 아직 검증되지 않음
