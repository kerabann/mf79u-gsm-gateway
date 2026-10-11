#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
sh firmware/mf79u/build-media-codec.sh
sh firmware/mf79u/build-net-led.sh
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
  pj=work/zte/voice/sip-deps/pjproject-2.17
  for name in enc dec; do
    arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -fPIC -DNDEBUG -DPJ_DEBUG=1 \
      -march=armv7-a -mfloat-abi=soft -DPJ_AUTOCONF=1 \
      -DPJ_IS_BIG_ENDIAN=0 -DPJ_IS_LITTLE_ENDIAN=1 \
      -I$pj/pjlib/include -I$pj/pjmedia/include \
      -c $pj/pjmedia/src/pjmedia-codec/g722/g722_$name.c \
      -o firmware/mf79u/build/g722-$name-pic.o
  done
  for name in kernel-summary socket-health ims-packet-summary volte-signal-watch udp-injection-selftest ipc-cleanup pcm-queue-selftest; do
    arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -static -march=armv7-a \
      -mfloat-abi=soft firmware/mf79u/src/$name.c -o firmware/mf79u/build/$name
  done
  for name in volte-ipc-probe net-led-ipc-selftest; do
    arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -static -march=armv7-a \
      -mfloat-abi=soft firmware/mf79u/src/$name.c firmware/mf79u/src/net-led-policy.c \
      -o firmware/mf79u/build/$name
  done
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -static -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/esp-fragment-selftest.c \
    firmware/mf79u/src/ipv4-fragments.c -o firmware/mf79u/build/esp-fragment-selftest
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -static -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/amr-rate-selftest.c \
    firmware/mf79u/src/amr-rate-policy.c firmware/mf79u/src/caller-id.c -o firmware/mf79u/build/amr-rate-selftest
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -static -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/pcm-resample-selftest.c \
    -lm -o firmware/mf79u/build/pcm-resample-selftest
  # Vendor uClibc uses SysV symbol hashing and libc.so.0. Do not link GNU libc.
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -static -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/pcm-network-selftest.c \
    firmware/mf79u/src/ims-software-media.c -Iwork/zte/voice/opencore-amr-0.1.6/amrnb \
    -Iwork/zte/voice/opencore-amr-0.1.6/amrwb -Iwork/zte/voice/vo-amrwbenc-0.1.3 \
    firmware/mf79u/build/amr-pic/amrnb/.libs/libopencore-amrnb.a \
    firmware/mf79u/build/amr-pic/amrwb/.libs/libopencore-amrwb.a \
    firmware/mf79u/build/amrwb-enc-pic/.libs/libvo-amrwbenc.a \
    -o firmware/mf79u/build/pcm-network-selftest
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -shared -nostdlib -fPIC \
    -march=armv7-a -mfloat-abi=soft -Wl,--hash-style=sysv \
    -Lfirmware/mf79u/build/link-sdk/lib firmware/mf79u/src/ims-sip-observer.c \
    -l:libdl-0.9.33.2.so -o firmware/mf79u/build/ims-sip-observer.so
  arm-linux-gnueabi-readelf -d firmware/mf79u/build/ims-sip-observer.so
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -shared -nostdlib -fPIC \
    -march=armv7-a -mfloat-abi=soft -Wl,--hash-style=sysv \
    -Lfirmware/mf79u/build/link-sdk/lib firmware/mf79u/src/ims-userspace-ipsec.c \
    firmware/mf79u/src/amr-rate-policy.c firmware/mf79u/src/caller-id.c \
    firmware/mf79u/src/esp-null.c firmware/mf79u/src/ipv4-fragments.c \
    firmware/mf79u/src/vendor-codecs.c \
    firmware/mf79u/build/g722-enc-pic.o firmware/mf79u/build/g722-dec-pic.o \
    -DPJ_AUTOCONF=1 -DPJ_IS_BIG_ENDIAN=0 -DPJ_IS_LITTLE_ENDIAN=1 \
    -I$pj/pjlib/include -I$pj/pjmedia/include -I$pj/pjmedia/src/pjmedia-codec/g722 \
    firmware/mf79u/src/ims-software-media.c -Iwork/zte/voice/opencore-amr-0.1.6/amrnb \
    -Iwork/zte/voice/opencore-amr-0.1.6/amrwb -Iwork/zte/voice/vo-amrwbenc-0.1.3 \
    firmware/mf79u/build/amr-pic/amrnb/.libs/libopencore-amrnb.a \
    firmware/mf79u/build/amr-pic/amrwb/.libs/libopencore-amrwb.a \
    firmware/mf79u/build/amrwb-enc-pic/.libs/libvo-amrwbenc.a \
    -l:libdl-0.9.33.2.so -l:libcrypto.so.1.0.0 \
    -l:libpthread-0.9.33.2.so -lgcc -o firmware/mf79u/build/ims-userspace-ipsec.so
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -nostdlib -no-pie -marm \
    -march=armv7-a -mfloat-abi=soft -Wl,-e,_start -Wl,--hash-style=sysv \
    -Wl,--dynamic-linker=/lib/ld-uClibc.so.0 -Lfirmware/mf79u/build/link-sdk/lib \
    firmware/mf79u/src/ims-crypto-selftest.c -l:libdl-0.9.33.2.so \
    -l:libuClibc-0.9.33.2.so -l:ld-uClibc-0.9.33.2.so \
    -o firmware/mf79u/build/ims-crypto-selftest
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror -nostdlib -no-pie -marm \
    -march=armv7-a -mfloat-abi=soft -Wl,-e,_start -Wl,--hash-style=sysv \
    -Wl,--dynamic-linker=/lib/ld-uClibc.so.0 -Lfirmware/mf79u/build/link-sdk/lib \
    firmware/mf79u/src/ims-media-selftest.c -l:libdl-0.9.33.2.so \
    -l:libuClibc-0.9.33.2.so -l:ld-uClibc-0.9.33.2.so \
    -o firmware/mf79u/build/ims-media-selftest
'
