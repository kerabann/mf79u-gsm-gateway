#!/bin/sh
set -eu
cd -P "$(dirname "$0")"
../../work/jffs2-venv/bin/python inspect-rootfs.py ../../outputs/zte-backup/rootfs.mtd5.bin \
  build/stock-rootfs --device-table build/device-table.txt --inventory build/stock-inventory.json
if ! docker image inspect mf79u-build-tools:local >/dev/null 2>&1; then
  docker build -t mf79u-build-tools:local .
fi
sh build-codec.sh
sh build-ims-diagnostics.sh
sh build-sip-deps.sh
sh build-sip-gateway.sh
sh build-control.sh
sh build-native-cp.sh
sh build-net-led.sh
../../work/jffs2-venv/bin/python isolate-volte.py
python3 prepare.py
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
  arm-linux-gnueabi-gcc -Os -march=armv7-a -marm -mfloat-abi=soft -fomit-frame-pointer \
    -ffreestanding -fno-builtin -fno-stack-protector -nostdlib -static -no-pie \
    -Wl,--build-id=none -Wl,-e,_start -o build/voice-probe src/voice-probe.c
  install -m 755 build/voice-probe build/rootfs/usr/bin/mf79u-voice-probe
  # Linux filesystem restores 0777 symlink modes hidden by macOS bind mounts.
  cp -a build/rootfs /tmp/rootfs
  mkfs.jffs2 --root=/tmp/rootfs --output=build/rootfs.experimental.jffs2 \
    --little-endian --eraseblock=131072 --pagesize=4096 --no-cleanmarkers \
    --compression-mode=none --faketime --devtable=build/device-table.txt
  test "$(stat -c %s build/rootfs.experimental.jffs2)" -le 50331648
  arm-linux-gnueabi-readelf -h build/voice-probe > build/voice-probe.elf.txt
  sha256sum build/rootfs.experimental.jffs2 build/voice-probe build/mf79u-net-led \
    build/mf79u-control build/amr-tool build/modem-sip-gateway build/ims-userspace-ipsec.so build/volte-ipc-probe \
    build/volte-private-ipc build/cp-ipc-probe build/mf79u-native-gateway \
    build/cp-ipc-selftest > build/SHA256SUMS
'
../../work/jffs2-venv/bin/python verify.py
echo 'Experimental rootfs assembled. Not a signed updater or verified boot image.'
