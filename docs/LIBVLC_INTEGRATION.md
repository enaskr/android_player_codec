# FFmpeg + LibVLC Android 플레이어 연동

## 배포 구조

GitHub Release의 ZIP 번들에는 다음 두 AAR이 포함됩니다.

- Android Player Codec AAR: FFmpeg + Java/JNI. GitHub-hosted Actions에서 FFmpeg 소스 컴파일
- VideoLAN 공식 LibVLC AAR: Maven Central의 안정 버전을 GitHub Actions에서 다운로드하고 SHA-256, Java API, ABI, 16 KiB ELF 정렬을 검사한 변경 없는 원본

AAR 내부에 다른 AAR을 넣는 것만으로 Gradle 의존성이 생기지 않습니다. 따라서 두 AAR을 단일 AAR로 물리적으로 병합하지 않고, 하나의 배포 ZIP으로 묶습니다.

## 권장 Gradle 연동

FFmpeg AAR을 플레이어의 app/libs 폴더에 복사하고 공식 LibVLC는 Maven Central에서 받으세요. Maven 방식은 LibVLC의 AndroidX/Kotlin 전이 의존성도 해결합니다.

~~~kotlin
// app/build.gradle.kts
dependencies {
    implementation(files("libs/android-player-codec-0.2.0-ffmpeg9.0.2.aar"))
    implementation("org.videolan.android:libvlc-all:3.7.7")
}
~~~

CodecBackends.hasLibVlcApi()를 호출하면 LibVLC Java API 클래스가 앱의 클래스패스에 있는지 확인할 수 있습니다. 실제 디코딩 호환성 검사는 아닙니다.

## 완전 오프라인 AAR 연동

배포 ZIP의 두 AAR을 app/libs 폴더에 복사합니다.

~~~kotlin
dependencies {
    implementation(files("libs/android-player-codec-0.2.0-ffmpeg9.0.2.aar"))
    implementation(files("libs/libvlc-all-3.7.7.aar"))
}
~~~

로컬 AAR은 Maven 전이 의존성을 자동으로 설치하지 않습니다. ZIP에 동봉된 libvlc-all-3.7.7.pom의 의존성(AndroidX 등)을 별도로 추가해야 합니다. 공식 Maven LibVLC와 로컬 AAR을 동시에 선언하면 중복 클래스 오류가 발생합니다.

## Java 예제: LibVLC

~~~java
import org.videolan.libvlc.LibVLC;
import org.videolan.libvlc.Media;
import org.videolan.libvlc.MediaPlayer;

LibVLC engine = new LibVLC(context);
MediaPlayer player = new MediaPlayer(engine);
Media media = new Media(engine, android.net.Uri.parse("https://example.org/video.mp4"));
player.setMedia(media);
media.release();
player.play();

// 비디오 Surface를 사용할 때는 getVLCVout()에 SurfaceView를 연결한
// 뒤 attachViews()를 호출합니다.
// 종료: player.stop(); player.release(); engine.release();
~~~

실제 기기에서 라이프사이클, 네트워크 권한, 하드웨어 가속, 백그라운드 재생, 비디오 Surface 연결을 검증해야 합니다.

## 재생 엔진 선택

| 엔진 | 핵심 기능 |
|---|---|
| Android MediaCodec | 기기에 설치된 하드웨어·소프트웨어 디코더 |
| FFmpeg AAR | 로컬/seekable 파일의 PCM 오디오·RGBA 비디오 디코딩 |
| LibVLC AAR | 플레이어 재생 제어, 미디어 출력 및 네트워크 스트림 처리 |

FFmpeg API는 현재 HTTP/HLS/DASH를 직접 처리하지 않습니다. LibVLC는 더 많은 재생 기능을 제공하지만 DRM, 모든 코덱, 모든 기기의 호환성을 보장하지 않습니다. 앱이 실제 재생 엔진을 선택하고 자원을 관리해야 합니다.

## GitHub Actions 전용 빌드 및 자동화

- 매일 한국시간 05:00에 FFmpeg Git 정식 태그 및 LibVLC Maven Central 정식 버전을 조회
- 같은 버전의 양쪽 AAR·ZIP·체크섬·검증 리포트가 이미 있으면 무거운 빌드 생략
- 업데이트 시 GitHub-hosted Ubuntu 러너에서 FFmpeg 4개 ABI 컴파일
- 같은 러너에서 공식 LibVLC AAR과 POM을 Maven Central에서 내려받아 상위 SHA-256 및 16 KiB ELF를 검사
- Gradle AAR 컴파일·두 AAR 배포 ZIP·GitHub Release 게시까지 모두 GitHub Actions 내부에서 실행

Synology나 자체 호스팅 러너는 사용하지 않습니다. 단, LibVLC 자체를 소스에서 다시 컴파일하는 작업은 포함하지 않습니다. VideoLAN에서 사전 컴파일한 공식 바이너리를 검증해 제공하는 방식입니다.

## 라이선스와 소스

FFmpeg는 GPL/nonfree 옵션을 비활성화하고 동적 LGPL 구성으로 빌드하며 해당 FFmpeg 소스 아카이브를 제공합니다. VideoLAN LibVLC 공식 AAR의 Maven POM은 LGPL-2.1을 명시합니다. 소스: https://code.videolan.org/videolan/libvlcjni 및 https://code.videolan.org/videolan/vlc

LibVLC 내부의 일부 플러그인 등에는 추가 라이선스 제약이 있을 수 있으므로 재배포 전 라이선스 및 대응 소스 제공 요건을 검토해야 합니다. 실제 기기 재생·성능·DRM 호환성은 자동 검증 대상이 아닙니다.
