#!/bin/sh
set -eu
cd "$(dirname "$0")"
task_root=$(cd ../.. && pwd)
python3 - <<'PY'
import hashlib
from pathlib import Path
p=Path('../../work/zte/voice/opencore-amr-0.1.6.tar.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest() == '483eb4061088e2b34b358e47540b5d495a96cd468e361050fae615b1809dc4a1'
PY
docker run --rm -v "$task_root:/work" -w /work mf79u-build-tools:local sh -eu -c '
  mkdir -p firmware/mf79u/build/amr-build
  cd firmware/mf79u/build/amr-build
  ../../../../work/zte/voice/opencore-amr-0.1.6/configure \
    --host=arm-linux-gnueabi --disable-shared --enable-static --enable-compile-c \
    --disable-gcc-armv5 --disable-examples \
    CFLAGS="-O2 -march=armv7-a -marm -mfloat-abi=soft" \
    CXXFLAGS="-O2 -march=armv7-a -marm -mfloat-abi=soft"
  make -j4 -C amrnb
  cd /work
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -march=armv7-a -marm -mfloat-abi=soft \
    -static -Iwork/zte/voice/opencore-amr-0.1.6/amrnb \
    firmware/mf79u/src/amr-tool.c firmware/mf79u/build/amr-build/amrnb/.libs/libopencore-amrnb.a \
    -lm -o firmware/mf79u/build/amr-tool
  arm-linux-gnueabi-strip firmware/mf79u/build/amr-tool
  arm-linux-gnueabi-readelf -h firmware/mf79u/build/amr-tool > firmware/mf79u/build/amr-tool.elf.txt
'
