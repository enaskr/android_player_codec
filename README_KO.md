# Android Player Codec AAR

## LibVLC 공식 AAR 함께 제공

Android Player Codec 0.2.0부터 FFmpeg AAR과 함께 **VideoLAN 공식 LibVLC AAR**을 배포하는 구조를 추가했습니다. LibVLC 3.7.7(안정 버전)을 Maven Central에서 가져와 Maven 공식 SHA-1을 대조하고 SHA-256을 별도 기록하며, 네이티브 4개 ABI를 확인하되 ARM64만 16 KiB ELF 정렬을 필수 검사하고, **FFmpeg AAR + LibVLC AAR을 하나의 ZIP 번들**로 제공합니다.

LibVLC 자체를 이 프로젝트에서 소스 컴파일하지는 않습니다. VideoLAN의 공식 사전 빌드 AAR을 검증한 뒤 변경하지 않고 배포합니다. 대신 FFmpeg 소스 빌드, LibVLC 검증, AAR 생성, ZIP 패키징과 Release 게시 등 **이 프로젝트의 모든 빌드 작업은 GitHub-hosted Actions에서만 실행**합니다. Synology, 개인 서버 또는 self-hosted runner를 사용하지 않습니다.

[LibVLC 연동 가이드](docs/LIBVLC_INTEGRATION.md). 권장 Gradle 사용법은 FFmpeg 로컬 AAR과 implementation("org.videolan.android:libvlc-all:3.7.7")을 선언하는 방식입니다. 오프라인용 LibVLC AAR도 ZIP에 함께 제공하지만, AndroidX 등의 전이 의존성은 동봉 POM을 참고해 직접 추가해야 합니다.


Android 플레이어에 Gradle 의존성으로 포함하는 **코덱 확장 AAR** 프로젝트입니다. APK를 설치하는 방식은 아닙니다.

## 제공 기능

- Android `MediaCodecList`를 통해 기기에 설치된 하드웨어·소프트웨어 디코더와 MIME 지원 목록 조회
- LGPL 구성으로 빌드한 **FFmpeg 9.0.2**의 기본 소프트웨어 디코더 및 디먹서 제공
- FFmpeg에 실제 포함된 디코더 목록을 조회하는 API 제공
- 로컬 파일 또는 `content://` URI의 파일 디스크립터 기반 디코딩
- 오디오: PCM16, 48 kHz, 스테레오 출력 및 구간 이동
- 비디오: RGBA8888 프레임과 마이크로초 단위 타임스탬프 출력 및 구간 이동
- Android의 `arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64`를 대상으로 빌드 및 16 KiB ELF 정렬 검증
- GitHub Actions에서 FFmpeg 소스 컴파일 → AAR 빌드 → JNI/ABI 검증 → 산출물 업로드 → 검증 성공 시 Release 게시

**주의:** 모든 코덱이 모든 기기에서 실행된다고 보증할 수 없습니다. 하드웨어 코덱은 기기에 따라 달라지고, FFmpeg 기본 구성에서 지원되지 않는 외부 상용 라이브러리·코덱은 포함하지 않습니다. DRM 복호화 기능은 제공하지 않습니다.

## 매일 05:00 자동 업데이트 확인

GitHub Actions에서 **매일 한국시간(KST) 오전 05:00**에 FFmpeg와 LibVLC의 최신 안정 버전을 함께 확인합니다. GitHub Actions cron 설정은 전날 UTC 20:00인 0 20 * * *입니다. GitHub 서버 사정에 따라 실제 실행 시각은 지연될 수 있습니다.

1. FFmpeg 공식 Git 태그 및 LibVLC Maven Central 메타데이터에서 각각 최신 정식 버전을 찾습니다. FFmpeg RC·베타와 LibVLC EAP·RC 등 시험 버전은 제외합니다.
2. 두 버전 조합에 해당하는 Release에 FFmpeg AAR, LibVLC 공식 AAR/POM, 통합 ZIP, SHA-256, 검증 보고서, 소스 정보가 모두 존재하는지 검사합니다.
3. 동일한 FFmpeg·LibVLC 조합이 정상 배포됐으면 **코덱 컴파일·AAR 빌드·Release 배포를 모두 생략**하고 확인 단계만 성공 처리합니다.
4. 새로운 정식 버전이거나 필수 배포 파일이 없으면 4개 ABI를 컴파일하고 JNI/16 KiB ELF 검증에 성공한 경우에만 Release를 게시합니다. 실패한 경우 다음 실행에서 재시도합니다.

플레이어 및 네이티브 빌드 소스가 변경된 Push는 해당 FFmpeg 버전을 다시 빌드합니다. README 또는 일정 설정만 변경된 경우에는 기존 배포본을 재빌드하지 않습니다. Actions의 Run workflow 메뉴에서는 release_tag(FFmpeg), libvlc_version(LibVLC), force=true로 특정 버전 조합을 강제 재빌드할 수 있습니다.

원본 태그 또는 GitHub Release 정보를 조회하지 못하면 빌드를 시작하지 않고 오류를 기록합니다. 생성된 AAR을 사용하려면 Android 플레이어를 다시 빌드해야 합니다.

## 설치 및 연동

[검증된 4개 ABI 통합 AAR 다운로드](https://github.com/enaskr/android_player_codec/releases/download/codec-v0.1.0-ffmpeg9.0.2/android-player-codec-0.1.0-ffmpeg9.0.2.aar) · [SHA-256](https://github.com/enaskr/android_player_codec/releases/download/codec-v0.1.0-ffmpeg9.0.2/SHA256SUMS) · [검증 결과](https://github.com/enaskr/android_player_codec/releases/download/codec-v0.1.0-ffmpeg9.0.2/VERIFICATION.json)


플레이어 모듈의 `app/libs/` 폴더에 빌드된 AAR을 넣고 다음을 Gradle에 선언합니다.

```kotlin
dependencies {
    implementation(files("libs/android-player-codec-0.1.0-ffmpeg9.0.2.aar"))
}
```

**AAR은 별도로 설치하는 APK가 아닙니다.** 기존 앱에 동적으로 코덱을 추가하려면 플레이어를 이 AAR로 다시 빌드해야 합니다. 사용자가 추가 APK를 설치하는 플러그인 방식을 원한다면 별도 Android Service/AIDL 인터페이스가 필요합니다.

## Java 연동 예제

```java
import com.enaskr.player.codec.CodecCatalog;
import com.enaskr.player.codec.CodecPack;
import com.enaskr.player.codec.CodecSession;
import java.nio.ByteBuffer;

String platformDecoders = CodecCatalog.deviceDecodersJson();
String ffmpegDecoders = CodecCatalog.ffmpegDecodersJson();
String ffmpegVersion = CodecPack.version();

try (CodecSession audio = CodecPack.openAudio(getContentResolver(), mediaUri)) {
    ByteBuffer pcm = ByteBuffer.allocateDirect(19200);
    while (true) {
        pcm.clear();
        int length = audio.readAudioPcm(pcm);
        if (length == -1) break;
        pcm.flip();
        // PCM16 48 kHz 스테레오 데이터를 AudioTrack에 전달
    }
}
```

비디오는 `CodecPack.openVideo()`로 열고 `CodecSession.readVideoFrameRgba()`로 RGBA8888 프레임을 가져옵니다. 프레임 버퍼 크기는 `CodecInfo.parse(session.streamInfoJson())`의 너비×높이×4입니다. 타임스탬프를 이용한 화면 출력 동기화는 플레이어 측에서 구현해야 합니다.

파일 디스크립터는 읽기 및 임의 위치 접근이 가능해야 합니다. HTTP·HLS·DASH 스트리밍, DRM, A/V 동기화 및 UI는 본 라이브러리에서 처리하지 않습니다. 디코딩 작업은 UI 스레드가 아닌 백그라운드 스레드에서 실행해야 합니다.

## 빌드 환경

JDK 17, Gradle 8.9, Android Gradle Plugin 8.7.3, Android SDK 35, NDK 28.2.13676358, CMake 3.22.1, `patchelf` 및 FFmpeg 컴파일에 필요한 개발 도구가 필요합니다.

```bash
mkdir -p work
git clone --branch n9.0.2 --depth 1 https://github.com/FFmpeg/FFmpeg.git work/ffmpeg-9.0.2
export ANDROID_NDK_HOME="$HOME/Android/Sdk/ndk/28.2.13676358"
for abi in arm64-v8a armeabi-v7a x86 x86_64; do
    bash scripts/build_ffmpeg.sh "$abi"
done
gradle :codec:assembleRelease
python3 scripts/verify_aar.py codec/build/outputs/aar/codec-release.aar
```

`.github/workflows/build-aar.yml`에 동일한 과정을 GitHub Actions로 자동화했습니다. FFmpeg `.so`가 없는 상태에서 AAR 패키징을 시도하면 실패하도록 구성했습니다.

## 라이선스 및 사용 범위

프로젝트의 Java/JNI 코드는 Apache-2.0, FFmpeg는 자체 LGPL 라이선스를 적용합니다. 빌드 시 `--disable-gpl --disable-nonfree` 옵션을 지정하고 FFmpeg와 동적 링크하여 GPL·비자유 옵션을 제외합니다. 배포 시 저작권·소스 제공·수정 라이브러리 교체 가능성과 관련한 LGPL 의무를 준수해야 합니다. Release에는 FFmpeg 해당 버전의 소스 아카이브를 포함하도록 설계했습니다.

공식 라이선스 문서: https://ffmpeg.org/legal.html

본 프로젝트는 FFmpeg 기반 소프트웨어 디코딩 기능과 Android 코덱 탐색 기능을 제공하며, **상업용 코덱에 필요한 특허 라이선스, DRM 또는 모든 기기에 대한 호환성을 보장하지 않습니다.** **4개 ABI 통합 AAR의 GitHub Actions 빌드와 JNI·16 KiB ELF 정렬 검증이 모두 성공했습니다.** 다만 실제 Android 기기의 디코딩 동작, 메모리 사용량과 재생 성능은 아직 검증되지 않았습니다.
