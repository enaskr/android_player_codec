# Android Player Codec AAR

Android 플레이어에 Gradle 의존성으로 포함하는 **코덱 확장 AAR** 프로젝트입니다. APK를 설치하는 방식은 아닙니다.

## 제공 기능

- Android `MediaCodecList`를 통해 기기에 설치된 하드웨어·소프트웨어 디코더와 MIME 지원 목록 조회
- LGPL 구성으로 빌드한 **FFmpeg 9.0.2**의 기본 소프트웨어 디코더 및 디먹서 제공
- FFmpeg에 실제 포함된 디코더 목록을 조회하는 API 제공
- 로컬 파일 또는 `content://` URI의 파일 디스크립터 기반 디코딩
- 오디오: PCM16, 48 kHz, 스테레오 출력 및 구간 이동
- 비디오: RGBA8888 프레임과 마이크로초 단위 타임스탬프 출력 및 구간 이동
- Android의 `arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64`를 대상으로 빌드 및 16 KiB ELF 정렬 검증
- GitHub Actions에서 FFmpeg 소스 컴파일 → AAR 빌드 → JNI/ABI 검증 → 산출물 업로드 → 수동 실행 시 Release 게시

**주의:** 모든 코덱이 모든 기기에서 실행된다고 보증할 수 없습니다. 하드웨어 코덱은 기기에 따라 달라지고, FFmpeg 기본 구성에서 지원되지 않는 외부 상용 라이브러리·코덱은 포함하지 않습니다. DRM 복호화 기능은 제공하지 않습니다.

## 설치 및 연동

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

본 프로젝트는 FFmpeg 기반 소프트웨어 디코딩 기능과 Android 코덱 탐색 기능을 제공하며, **상업용 코덱에 필요한 특허 라이선스, DRM 또는 모든 기기에 대한 호환성을 보장하지 않습니다.** 실제 AAR 빌드 및 기기에서의 디코딩·메모리·성능 검증 후 운영에 적용해야 합니다.
