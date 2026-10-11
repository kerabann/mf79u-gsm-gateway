#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
python3 - <<'PY'
import hashlib,json
from pathlib import Path
p=Path('work/zte/voice/sip-deps')
for s in json.loads((p/'sources.json').read_text()):
 assert hashlib.sha256((p/s['file']).read_bytes()).hexdigest()==s['sha256'],s['file']
PY
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
 base=/work/work/zte/voice/sip-deps
 prefix=$base/arm
 if [ ! -f "$prefix/lib/libbcg729.a" ] || [ ! -f "$prefix/.mf79u-rand-devrandom" ]; then apt-get -qq update && apt-get -qq install -y cmake perl > /dev/null; fi
 flags="-Os -march=armv7-a -mfloat-abi=soft -ffunction-sections -fdata-sections"
 if [ ! -f "$prefix/lib/libopus.a" ]; then
  cd "$base/opus-1.6.1"
  ./configure --host=arm-linux-gnueabi --prefix="$prefix" --enable-static --disable-shared --enable-fixed-point --disable-float-api --disable-intrinsics --disable-asm --disable-extra-programs --disable-doc CFLAGS="$flags"
  make -j4 && make install
 fi
 if [ ! -f "$prefix/lib/libbcg729.a" ]; then
  cmake -S "$base/bcg729-1.1.2" -B "$base/bcg729-arm" -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_C_COMPILER=arm-linux-gnueabi-gcc -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_SHARED_LIBS=OFF -DCMAKE_C_FLAGS="$flags"
  cmake --build "$base/bcg729-arm" -j4 && cmake --install "$base/bcg729-arm"
 fi
 if [ ! -f "$prefix/.mf79u-rand-devrandom" ]; then
  cd "$base/openssl-3.5.9"
  ./Configure linux-armv4 --cross-compile-prefix=arm-linux-gnueabi- --prefix="$prefix" --libdir=lib no-shared no-module no-tests no-asm no-dso no-apps no-comp no-legacy no-fips no-ssl3 no-tls1 no-tls1_1 --with-rand-seed=devrandom no-deprecated no-quic $flags
  make -j4 build_libs && make install_dev
  touch "$prefix/.mf79u-rand-devrandom"
 fi
'
