#!/usr/bin/env bash
# Cross-build stock LGPL FFmpeg decoding/demuxing libraries for one Android ABI.
set -euo pipefail
ABI="${1:?Usage: scripts/build_ffmpeg.sh <arm64-v8a|armeabi-v7a|x86|x86_64>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="${FFMPEG_SOURCE_DIR:-$ROOT/work/ffmpeg-9.0.2}"
NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
API="${ANDROID_API:-23}"
JOBS="${BUILD_JOBS:-2}"
if [[ -z "$NDK" || ! -x "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar" ]]; then
  echo 'Android NDK r28+ not configured; set ANDROID_NDK_HOME' >&2; exit 1
fi
if [[ ! -x "$SOURCE/configure" ]]; then
  echo "FFmpeg source not found: $SOURCE" >&2; exit 1
fi
if ! command -v patchelf >/dev/null; then
  echo 'patchelf is required to normalize Android .so SONAMEs' >&2; exit 1
fi
TOOL="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
case "$ABI" in
  arm64-v8a) ARCH=aarch64; CPU=armv8-a; TARGET="aarch64-linux-android" ;;
  armeabi-v7a) ARCH=arm; CPU=armv7-a; TARGET="armv7a-linux-androideabi" ;;
  x86) ARCH=x86; CPU=i686; TARGET="i686-linux-android" ;;
  x86_64) ARCH=x86_64; CPU=x86-64; TARGET="x86_64-linux-android" ;;
  *) echo "Unsupported ABI: $ABI" >&2; exit 1 ;;
esac
WORK="$ROOT/work/build-$ABI"
PREFIX="$ROOT/work/install-$ABI"
mkdir -p "$WORK" "$PREFIX"
cd "$WORK"
"$SOURCE/configure" \
  --prefix="$PREFIX" \
  --target-os=android --arch="$ARCH" --cpu="$CPU" \
  --enable-cross-compile \
  --cc="$TOOL/${TARGET}${API}-clang" \
  --cxx="$TOOL/${TARGET}${API}-clang++" \
  --ld="$TOOL/${TARGET}${API}-clang" \
  --ar="$TOOL/llvm-ar" --nm="$TOOL/llvm-nm" \
  --ranlib="$TOOL/llvm-ranlib" --strip="$TOOL/llvm-strip" \
  --sysroot="$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot" \
  --enable-shared --disable-static --enable-pic \
  --disable-programs --disable-doc --disable-debug \
  --disable-encoders --disable-muxers --disable-avdevice --disable-avfilter \
  --disable-network --disable-autodetect \
  --disable-vulkan --disable-gpl --disable-nonfree \
  --enable-pthreads --disable-symver \
  --extra-cflags='-fPIC' \
  --extra-ldflags='-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384' \
  ${FFMPEG_EXTRA_CONFIGURE:-}
make -j"$JOBS"
make install
DEST="$ROOT/codec/src/main/jniLibs/$ABI"
mkdir -p "$DEST"
for lib in avutil swresample swscale avcodec avformat; do
  src="$PREFIX/lib/lib${lib}.so"
  [[ -f "$src" ]] || { echo "Missing FFmpeg library $src" >&2; exit 1; }
  cp -L "$src" "$DEST/lib${lib}.so"
done
# Android packaged JNI libraries must have unversioned .so basenames.
# Rewrite DT_SONAME and DT_NEEDED only, without modifying the ABI/codec logic.
for lib in avutil swresample swscale avcodec avformat; do
  libfile="$DEST/lib${lib}.so"
  patchelf --set-soname "lib${lib}.so" "$libfile"
  for dep in avutil swresample swscale avcodec avformat; do
    old="$(patchelf --print-needed "$libfile" | grep -E "^lib${dep}\.so\.[0-9]+" | head -1 || true)"
    if [[ -n "$old" ]]; then
      patchelf --replace-needed "$old" "lib${dep}.so" "$libfile"
    fi
  done
done
# Header ABI is consistent across the four NDK targets; overwrite same version only.
mkdir -p "$ROOT/codec/src/main/ffmpeg-include"
cp -a "$PREFIX/include/." "$ROOT/codec/src/main/ffmpeg-include/"
python3 "$ROOT/scripts/verify_shared_libs.py" "$DEST" "$ABI"
printf 'Completed LGPL FFmpeg Android ABI %s\n' "$ABI"
