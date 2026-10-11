#!/usr/bin/env python3
"""Verify offline image contents, modes and protected vendor code."""
import hashlib
import importlib.util
import json
from pathlib import Path
from adb_boot import patch_rc

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inspector', HERE / 'inspect-rootfs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
build = HERE / 'build'
image = build / 'rootfs.experimental.jffs2'
_, actual = module.inspect(image, build / 'rootfs')
original = json.loads((build / 'stock-inventory.json').read_text())
manifest = json.loads((build / 'manifest.json').read_text())
patches = {r['path']: r for r in manifest['changes']}
removed=set(manifest.get('removed_paths',[]))
actual = {r['path']: r for r in actual}
protected = 0
for before in original:
    if before['path'] in removed:
        if not before['path'].startswith('/usr/zte_web/web/') or before['path'] in actual:raise SystemExit('Invalid removal: '+before['path'])
        continue
    after = actual.get(before['path'])
    if after is None or before['kind'] != after['kind'] or before['mode'] != after['mode']:
        raise SystemExit('Mode or type changed unexpectedly: ' + before['path'])
    if before['path'] not in patches and before['sha256'] != after['sha256']:
        raise SystemExit('Unplanned content change: ' + before['path'])
    if before['path'].startswith(('/bin/', '/lib/', '/sbin/')):
        protected += 1
for path, patch in patches.items():
    if actual[path]['sha256'] != patch['sha256']:
        raise SystemExit('Overlay checksum mismatch: ' + path)
startup = (build / 'rootfs/etc/rc').read_bytes()
if patch_rc(startup) != startup or b'# MF79U automatic ADB boot policy v1\n' not in startup:
    raise SystemExit('Automatic ADB boot policy missing')
adb_helper = build / 'rootfs/usr/zte/mf79u/adb-boot'
if adb_helper.read_bytes() != (build / 'mf79u-adb-boot').read_bytes() or adb_helper.stat().st_mode & 0o111 != 0o111:
    raise SystemExit('ADB boot helper missing, changed or not executable')
probe = build / 'voice-probe'
probe_sha = hashlib.sha256(probe.read_bytes()).hexdigest()
if actual['/usr/bin/mf79u-voice-probe']['sha256'] != probe_sha:
    raise SystemExit('Native probe differs in rootfs')
allowed_new = set(patches) | {'/usr/bin/mf79u-voice-probe', '/usr/zte/mf79u'}
new = set(actual) - {r['path'] for r in original}
if new - allowed_new:
    raise SystemExit('Unexpected new paths: ' + repr(new - allowed_new))
size = image.stat().st_size
if size > manifest['geometry']['partition_size']:
    raise SystemExit('Image does not fit rootfs partition')
manifest['native_component'] = {'path': '/usr/bin/mf79u-voice-probe', 'sha256': probe_sha}
manifest['image'] = {'size': size, 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
manifest['verification'] = {'paths': len(actual), 'unchanged_vendor_binary_paths': protected,
                            'contents_and_modes_checked': True, 'crc_checked': True}
native_report = build / 'native-cp-verification.json'
if native_report.exists():
    proof = json.loads(native_report.read_text())
    binaries = ('cp-ipc-probe', 'cp-ipc-selftest', 'mf79u-native-gateway')
    verified = all(proof.get('artifact_sha256', {}).get(name) ==
                   hashlib.sha256((build / name).read_bytes()).hexdigest() for name in binaries)
    if verified and proof.get('queue_inventory_preserved') is True:
        manifest['autonomy']['local_cp_queries_device_tested'] = True
        manifest['autonomy']['native_cp_verification'] = proof
standalone_report = build / 'standalone-verification.json'
if standalone_report.exists():
    proof = json.loads(standalone_report.read_text())
    binaries = ('mf79u-native-gateway', 'mf79u-net-led', 'volte-private-ipc', 'ims-userspace-ipsec.so', 'modem-sip-gateway')
    verified = all(proof.get('artifact_sha256', {}).get(name) ==
                   hashlib.sha256((build / name).read_bytes()).hexdigest() for name in binaries)
    scripts = {'start-native.sh': 'start-native.sh', 'start-control-userdata.sh': 'start-control-userdata.sh'}
    verified &= all(proof.get('artifact_sha256', {}).get(name) == hashlib.sha256((HERE / source).read_bytes()).hexdigest()
                    for name, source in scripts.items())
    if verified and proof.get('boot_autostart_confirmed') and not proof.get('mac_relay_or_watcher_running'):
        for field in ('local_sim_aka_device_tested', 'local_ims_registration_device_tested'):
            manifest['autonomy'][field] = proof.get(field) is True
        manifest['autonomy']['runtime_control_ready'] = True
        manifest['autonomy']['ready'] = proof.get('voice_audio_without_relay_verified') is True
        manifest['autonomy']['standalone_verification'] = proof
registrar_report = build / 'sip-registrar-live.json'
if registrar_report.exists():
    proof = json.loads(registrar_report.read_text())
    verified = proof.get('artifactSha256') == hashlib.sha256((build / 'modem-sip-gateway').read_bytes()).hexdigest()
    verified &= all(proof.get(field) is True for field in (
        'authenticatedRegister', 'bindingVisible', 'configurationRestored',
        'physicalModem', 'safeDestinationRejected',
    ))
    verified &= proof.get('simCalls') is False
    if verified:
        manifest['sip_gateway']['local_registrar_physical_modem_tested'] = True
        manifest['sip_gateway']['local_registrar_verification'] = proof
(build / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'PASS: {len(actual)} paths; {protected} vendor binary paths unchanged; image {size} bytes')
