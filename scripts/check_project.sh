#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py
bash -n scripts/*.sh
for file in \
  codec/src/main/java/com/enaskr/player/codec/CodecPack.java \
  codec/src/main/java/com/enaskr/player/codec/CodecSession.java \
  codec/src/main/java/com/enaskr/player/codec/CodecCatalog.java \
  codec/src/main/cpp/codec_jni.c \
  .github/workflows/build-aar.yml; do test -s "$file"; done
printf 'Source validation passed\n'
