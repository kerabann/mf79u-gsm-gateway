#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
python3 - <<'PY'
import hashlib
from pathlib import Path
p=Path('work/zte/voice/opencore-amr-0.1.6.tar.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='483eb4061088e2b34b358e47540b5d495a96cd468e361050fae615b1809dc4a1'
p=Path('work/zte/voice/vo-amrwbenc-0.1.3.tar.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='5652b391e0f0e296417b841b02987d3fd33e6c0af342c69542cbb016a71d9d4e'
PY
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
  mkdir -p firmware/mf79u/build/amr-pic
  cd firmware/mf79u/build/amr-pic
  if ! test -f Makefile; then
    ../../../../work/zte/voice/opencore-amr-0.1.6/configure \
      --host=arm-linux-gnueabi --disable-shared --enable-static --enable-compile-c \
      --disable-gcc-armv5 --disable-examples \
      CFLAGS="-O2 -fPIC -march=armv7-a -marm -mfloat-abi=soft" \
      CXXFLAGS="-O2 -fPIC -march=armv7-a -marm -mfloat-abi=soft" > configure.log
  fi
  make -j4 -C amrnb > make.log
  make -j4 -C amrwb > make-wb.log
  mkdir -p /work/firmware/mf79u/build/amrwb-enc-pic
  cd /work/firmware/mf79u/build/amrwb-enc-pic
  if ! test -f Makefile; then
    ../../../../work/zte/voice/vo-amrwbenc-0.1.3/configure \
      --host=arm-linux-gnueabi --disable-shared --enable-static \
      CFLAGS="-O2 -fPIC -march=armv7-a -marm -mfloat-abi=soft" > configure.log
  fi
  make -j4 > make.log
'
