#!/bin/sh
export PATH=/mnt/userdata/mf79u/tools/bin:/usr/bin:/bin:/usr/sbin:/sbin
export HOME=/mnt/userdata/mf79u/ssh-home
cd "$HOME" || exit 1
umask 077
exec /mnt/userdata/mf79u/tools/busybox ash "$@"
