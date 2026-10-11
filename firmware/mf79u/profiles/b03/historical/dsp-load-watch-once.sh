#!/bin/sh
# Consumed before every other operation; never retries on the next boot.
set -u
rm -f /mnt/userdata/mf79u/dsp-load-watch.once
if [ "$(md5sum /mnt/userdata/mf79u/rc.before-dsp-load-watch | cut -d ' ' -f 1)" != "b98c87a5d44b5c8b847ca5ad3125b5d7" ]; then
    echo MF79U_DSP_BOOT_BACKUP_REJECTED
    exit 0
fi
if [ "$(md5sum /etc/rc | cut -d ' ' -f 1)" != "16a69cfcd2131dc5dfb3e2d84f2ef89b" ]; then
    echo MF79U_DSP_BOOT_CURRENT_RC_REJECTED
    exit 0
fi
if ! mount -o remount,rw /; then exit 0; fi
if ! cp /mnt/userdata/mf79u/rc.before-dsp-load-watch /etc/.mf79u-rc.new; then mount -o remount,ro /; exit 0; fi
chmod 744 /etc/.mf79u-rc.new
if ! mv /etc/.mf79u-rc.new /etc/rc; then mount -o remount,ro /; exit 0; fi
sync
mount -o remount,ro /
if [ "$(md5sum /etc/rc | cut -d ' ' -f 1)" != "b98c87a5d44b5c8b847ca5ad3125b5d7" ]; then exit 0; fi
echo MF79U_DSP_BOOT_RC_RESTORED
if [ "$(md5sum /lib/cpko/cpko.ko | cut -d ' ' -f 1)" != "8138d03644b0417ec3fba9d7175200bc" ]; then exit 0; fi
if [ "$(md5sum /mnt/userdata/mf79u/dsp-load-watch.once.ko | cut -d ' ' -f 1)" != "53d2b834a424f2462a0257eef032263f" ]; then exit 0; fi
insmod /mnt/userdata/mf79u/dsp-load-watch.once.ko || true
