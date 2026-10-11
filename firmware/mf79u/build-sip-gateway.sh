#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
python3 - <<'PY'
from pathlib import Path
import hashlib
p=Path('work/zte/voice/pjproject/pjproject-2.17.tar.gz')
tree=Path('work/zte/voice/sip-deps/pjproject-2.17')
if not tree.is_dir():
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='065fe06c06788d97c35f563796d59f00ce52fe9558a52d7b490a042a966facce'
PY
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
  prefix=/work/work/zte/voice/sip-deps/arm
  test -f $prefix/lib/libopus.a && test -f $prefix/lib/libbcg729.a && test -f $prefix/lib/libssl.a
  if [ ! -d work/zte/voice/sip-deps/pjproject-2.17 ]; then tar -xzf work/zte/voice/pjproject/pjproject-2.17.tar.gz -C work/zte/voice/sip-deps; fi
  cd work/zte/voice/sip-deps/pjproject-2.17
  if [ ! -f .mf79u-full-sip-build ]; then
    printf "%s\n" "#define PJMEDIA_HAS_VIDEO 0" \
      "#define PJ_HAS_SSL_SOCK 1" "#define PJ_LOG_MAX_LEVEL 2" \
      "#define PJSUA_MAX_CALLS 2" > pjlib/include/pj/config_site.h
    ./configure --host=arm-linux-gnueabi --disable-video --with-ssl=$prefix --with-opus=$prefix --with-bcg729=$prefix \
      --disable-sound --disable-opencore-amr --disable-silk \
      --disable-speex-aec --disable-speex-codec --disable-gsm-codec \
      --disable-ilbc-codec --disable-g7221-codec \
      --disable-libsrtp --disable-libwebrtc --disable-sdl --disable-ffmpeg \
      --disable-v4l2 --disable-openh264 \
      CFLAGS="-Os -march=armv7-a -mfloat-abi=soft -ffunction-sections -fdata-sections" LDFLAGS="-L$prefix/lib"
    make dep
    make clean
    touch .mf79u-full-sip-build
  fi
  make -j4 lib
  cd /work
  pj=work/zte/voice/sip-deps/pjproject-2.17
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a -mfloat-abi=soft \
    firmware/mf79u/src/sip-settings-selftest.c -o firmware/mf79u/build/sip-settings-selftest
  qemu-arm firmware/mf79u/build/sip-settings-selftest
  for name in modem-sip-gateway sip-codec-selftest; do
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -Wl,--gc-sections -s \
    -march=armv7-a -mfloat-abi=soft -DPJ_AUTOCONF=1 \
    -DPJ_IS_BIG_ENDIAN=0 -DPJ_IS_LITTLE_ENDIAN=1 -DPJMEDIA_HAS_SRTP=0 \
    -I$pj/pjlib/include -I$pj/pjlib-util/include -I$pj/pjnath/include \
    -I$pj/pjmedia/include -I$pj/pjsip/include \
    firmware/mf79u/src/$name.c firmware/mf79u/src/sip-clock-policy.c \
    -Wl,--wrap=pjmedia_master_port_create \
    -Wl,--start-group $pj/pjsip/lib/*.a $pj/pjmedia/lib/*.a $pj/third_party/lib/*.a \
      $pj/pjnath/lib/*.a $pj/pjlib-util/lib/*.a $pj/pjlib/lib/*.a \
      -Wl,--end-group $prefix/lib/libopus.a $prefix/lib/libbcg729.a $prefix/lib/libssl.a $prefix/lib/libcrypto.a -lm -lpthread -ldl \
    -o firmware/mf79u/build/$name
  done
'
