#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
python3 - <<'PY'
from pathlib import Path
import hashlib,tarfile
p=Path('work/zte/voice/vowifi/strongswan-6.1.0.tar.bz2')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='fe6c97481298767213cfc2e9a1da29fdd8018d481ff4cb9cf0283099654f20d4'
s=Path('work/zte/voice/vowifi/strongswan-6.1.0/src/libcharon/plugins/eap_simaka_reauth')
(s/'eap_simaka_reauth_plugin.c').write_bytes(Path('firmware/mf79u/src/vowifi-sim-plugin.c').read_bytes())
for name in ['cp-ipc.c','cp-ipc.h']:(s/name).write_bytes(Path('firmware/mf79u/src',name).read_bytes())
p=s/'Makefile.am';v=p.read_text()
if 'cp-ipc.c' not in v:v+='\nlibstrongswan_eap_simaka_reauth_la_SOURCES += cp-ipc.c cp-ipc.h\n'
p.write_text(v)
root=Path('work/zte/voice/vowifi/strongswan-6.1.0')
(root/'src/libstrongswan/networking/tun_device.c').write_bytes(Path('firmware/mf79u/src/vowifi-packet-device.c').read_bytes())
(root/'src/libstrongswan/networking/vowifi-ipv4-checksum.h').write_bytes(Path('firmware/mf79u/src/vowifi-ipv4-checksum.h').read_bytes())
for name in ['charon','swanctl']:
 p=root/'src'/name/'Makefile.am';v=p.read_text()
 if name+'_LDFLAGS = -all-static' not in v:v+='\n'+name+'_LDFLAGS = -all-static\n'
 p.write_text(v)
p=root/'src/libcharon/plugins/kernel_libipsec/kernel_libipsec_ipsec.c';v=p.read_text()
needle='if (policy->direction != POLICY_OUT)'
if 'install_routes' not in v:v=v.replace(needle,'if (!lib->settings->get_bool(lib->settings, "%s.install_routes", TRUE, lib->ns) || policy->direction != POLICY_OUT)')
p.write_text(v)
p=root/'src/libcharon/plugins/p_cscf/p_cscf_handler.c'
with tarfile.open('work/zte/voice/vowifi/strongswan-6.1.0.tar.bz2') as archive:v=archive.extractfile('strongswan-6.1.0/src/libcharon/plugins/p_cscf/p_cscf_handler.c').read().decode()
needle='server->destroy(server);'
if 'mf79u-pcscf' not in v:
 v=v.replace('#include <networking/host.h>', '#include <stdio.h>\n#include <fcntl.h>\n#include <unistd.h>\n#include <networking/host.h>')
 v=v.replace(needle, 'if (family == AF_INET) { char ip[64]; chunk_t raw = server->get_address(server); if (inet_ntop(AF_INET, raw.ptr, ip, sizeof(ip))) { int fd = open("/dev/mf79u/vowifi/mf79u-pcscf", O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW, 0600); if (fd >= 0) { dprintf(fd, "%s\\n", ip); close(fd); } int list = open("/dev/mf79u/vowifi/pcscf-list", O_WRONLY|O_CREAT|O_APPEND|O_NOFOLLOW, 0600); if (list >= 0) { dprintf(list, "%s\\n", ip); close(list); } } }\n\t\t\t'+needle)
 p.write_text(v)
PY
python3 firmware/mf79u/patch-vowifi-idr.py
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
 dpkg --add-architecture armel
 apt-get -qq update && apt-get -qq install -y autoconf automake libtool pkg-config libgmp-dev:armel > /dev/null
 cd work/zte/voice/vowifi/strongswan-6.1.0
 autoreconf -fi >/work/firmware/mf79u/build/vowifi-autoreconf.log 2>&1
 prefix=/work/work/zte/voice/vowifi/arm
 crypto=/work/work/zte/voice/sip-deps/arm
 ./configure --host=arm-linux-gnueabi --prefix="$prefix" --sysconfdir=/dev/mf79u/vowifi --with-piddir=/dev/mf79u/vowifi --disable-defaults --disable-shared --enable-static --enable-monolithic --enable-charon --enable-ikev2 --enable-vici --enable-swanctl --disable-openssl --enable-aes --enable-sha2 --enable-gmp --enable-pem --enable-pkcs1 --enable-x509 --enable-random --enable-nonce --enable-kdf --enable-hmac --enable-fips-prf --enable-sha1 --enable-eap-identity --enable-eap-aka --enable-eap-simaka-reauth --enable-kernel-netlink --enable-kernel-libipsec --enable-libipsec --enable-socket-default --enable-p-cscf --enable-updown --enable-resolve --enable-attr CFLAGS="-Os -march=armv7-a -mfloat-abi=soft -ffunction-sections -fdata-sections" CPPFLAGS="-I$crypto/include" LDFLAGS="-L$crypto/lib -static -Wl,--gc-sections" > /work/firmware/mf79u/build/vowifi-configure.log 2>&1
 rm -f src/libstrongswan/plugin_constructors.c src/libcharon/plugin_constructors.c
 make -j4 > /work/firmware/mf79u/build/vowifi-build.log 2>&1
 make install > /work/firmware/mf79u/build/vowifi-install.log 2>&1
 arm-linux-gnueabi-strip "$prefix/libexec/ipsec/charon" "$prefix/sbin/swanctl"
 arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a -mfloat-abi=soft /work/firmware/mf79u/src/cp-ipc.c /work/firmware/mf79u/src/vowifi-prepare.c -o /work/firmware/mf79u/build/mf79u-vowifi-prepare
 cp "$prefix/libexec/ipsec/charon" /work/firmware/mf79u/build/mf79u-vowifi-charon
 cp "$prefix/sbin/swanctl" /work/firmware/mf79u/build/mf79u-vowifi-swanctl
'
