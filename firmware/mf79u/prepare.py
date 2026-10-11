#!/usr/bin/env python3
"""Local B03 rootfs overlay. Never connects to or flashes the modem."""
import hashlib
import json
from pathlib import Path
import shutil
import importlib.util
from adb_boot import patch_rc

HERE = Path(__file__).resolve().parent
WORK = HERE.parent.parent
ROOT = HERE / 'build' / 'rootfs'
EXPECTED = '544766bfc6317ba3a1c820c9c9d82b73e14174a2bc4f03fd6962471d5dea564b'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    policy_spec = importlib.util.spec_from_file_location('native_installer', HERE / 'install-native.py')
    policy_module = importlib.util.module_from_spec(policy_spec)
    policy_spec.loader.exec_module(policy_module)
    policy_module.policy()
    backup = WORK / 'outputs/zte-backup/rootfs.mtd5.bin'
    if digest(backup) != EXPECTED:
        raise SystemExit('Unexpected base rootfs: refusing to build')
    if ROOT.exists():
        shutil.rmtree(ROOT)
    shutil.copytree(HERE / 'build/stock-rootfs', ROOT, symlinks=True)
    # Only use already-reviewed local changes. No saved passwords or SMS database.
    overlays = {
        'outputs/zte-config-sms-enabled.bin': 'usr/zte/zte_conf/config/config',
        'firmware/mf79u/build/amr-tool': 'usr/bin/mf79u-amr-tool',
        'firmware/mf79u/build/mf79u-net-led': 'usr/bin/mf79u-net-led',
        'firmware/mf79u/build/ims-userspace-ipsec.so': 'lib/mf79u-ims-userspace-ipsec.so',
        'firmware/mf79u/build/volte-ipc-probe': 'usr/bin/mf79u-ims-probe',
        'firmware/mf79u/build/volte-private-ipc': 'usr/bin/mf79u-ims-private',
        'firmware/mf79u/build/modem-sip-gateway': 'usr/bin/mf79u-sip-gateway',
        'firmware/mf79u/build/mf79u-control': 'usr/bin/mf79u-control',
        'firmware/mf79u/build/cp-ipc-probe': 'usr/bin/mf79u-cp-probe',
        'firmware/mf79u/build/cp-ipc-selftest': 'usr/bin/mf79u-cp-selftest',
        'firmware/mf79u/build/mf79u-native-gateway': 'usr/bin/mf79u-native-gateway',
        'firmware/mf79u/start-control.sh': 'usr/zte/mf79u/start-control.sh',
        'firmware/mf79u/start-native.sh': 'usr/zte/mf79u/start-native.sh',
        'firmware/mf79u/build/mf79u-adb-boot': 'usr/zte/mf79u/adb-boot',
        'firmware/mf79u/build/zte_topsw_daemon.custom.conf': 'usr/zte/zte_conf/config/zte_topsw_daemon.conf',
        'firmware/mf79u/build/zte_debug.custom.sh': 'usr/zte/zte_conf/scripts/zte_debug.sh',
        'firmware/mf79u/control/web/index.html': 'usr/zte_web/web/index.html',
        'firmware/mf79u/control/web/app.js': 'usr/zte_web/web/app.js',
        'firmware/mf79u/control/web/style.css': 'usr/zte_web/web/style.css',
        'work/zte/voice/sip-deps/ca-bundle.pem': 'usr/zte/mf79u/ca-bundle.pem',
        'work/zte/voice/sip-deps/opus-1.6.1/COPYING': 'usr/zte/mf79u/opus-LICENSE',
        'work/zte/voice/sip-deps/bcg729-1.1.2/LICENSE.txt': 'usr/zte/mf79u/bcg729-LICENSE',
        'work/zte/voice/sip-deps/openssl-3.5.9/LICENSE.txt': 'usr/zte/mf79u/openssl-LICENSE',
        'work/zte/voice/pjproject/pjproject-2.17/COPYING': 'usr/zte/pjproject-LICENSE',
        'work/zte/voice/opencore-amr-0.1.6/LICENSE': 'usr/zte/opencore-amr-LICENSE',
        'work/zte/voice/vo-amrwbenc-0.1.3/COPYING': 'usr/zte/vo-amrwbenc-LICENSE',
    }
    stockcfg = WORK / 'outputs/zte-config-stock.bin'
    modified = WORK / 'outputs/zte-config-sms-enabled.bin'
    a, b = stockcfg.read_bytes(), modified.read_bytes()
    if len(a) != len(b) or [i for i in range(len(a)) if a[i] != b[i]] != [14796]:
        raise SystemExit('SMS config patch differs from reviewed one-byte change')
    if (ROOT / 'usr/zte/zte_conf/config/config').read_bytes() != a:
        raise SystemExit('Backup configuration differs from expected stock B03')
    changes = []
    removed = []
    web=ROOT/'usr/zte_web/web'
    # Keep vendor backend configuration and runtime templates.
    for entry in list(web.iterdir()):
        if entry.name in ('copy','config.json','index.html'):continue
        for file in ([entry] if entry.is_file() else sorted(entry.rglob('*'),key=lambda p:len(p.parts),reverse=True)):
            removed.append('/'+str(file.relative_to(ROOT)))
        removed.append('/'+str(entry.relative_to(ROOT)))
        if entry.is_dir():shutil.rmtree(entry)
        else:entry.unlink()
    removed=sorted(set(removed))

    for source, dest in overlays.items():
        target = ROOT / dest
        old = digest(target) if target.is_file() else None
        mode=target.stat().st_mode & 0o777 if target.exists() else (0o755 if dest.startswith('usr/bin/') or dest.endswith('.sh') or dest.endswith('/adb-boot') else 0o644)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORK / source, target)
        target.chmod(mode)
        changes.append({'path': '/' + dest, 'before_sha256': old, 'sha256': digest(target)})
    startup = ROOT / 'etc/rc'
    before_startup = digest(startup)
    startup.write_bytes(patch_rc(startup.read_bytes()))
    with startup.open('a') as out:
        out.write('\n# MF79U native voice, exclusive LEDs and WebUI.\n'
                  '/usr/zte/mf79u/start-control.sh >/dev/null 2>&1 &\n')
    changes.append({'path': '/etc/rc', 'before_sha256': before_startup, 'sha256': digest(startup)})
    table=HERE/'build/device-table.txt'
    lines=[line for line in table.read_text().splitlines() if line.split() and line.split()[0] not in removed]
    known={line.split()[0] for line in lines}
    for change in changes:
        path=change['path'];target=ROOT/path.lstrip('/')
        if path not in known:lines.append(f"{path} f {target.stat().st_mode & 0o777:o} 0 0 - - - - -")
    lines.append('/usr/zte/mf79u d 755 0 0 - - - - -')
    table.write_text('\n'.join(lines)+'\n')
    manifest = {
        'version': 'mf79u-custom-0.9-experimental',
        'base': 'BD_XCBZHKMF79UV1.0.0B03', 'base_rootfs_sha256': EXPECTED,
        'geometry': {'erase_size': 131072, 'nand_write_size': 2048,
                     'linux_page_size': 4096, 'partition_size': 50331648},
        'voice_enabled': True, 'boot_tested': False, 'flash_authorized_by_this_script': False,
        'adb': {'normal_boot_autostart': True, 'usb_profile': 'debug',
                'helper': '/usr/zte/mf79u/adb-boot', 'resident_watcher': False,
                'reserved_factory_amt_modes_preserved': True},
        'autonomy': {
            'ready': False,
            'controller_packaged': True,
            'controller_autostart': True,
            'local_cp_queries_device_tested': False,  # verify.py binds live evidence to artifact hashes.
            'local_sim_aka_device_tested': False,
            'local_ims_registration_device_tested': False,
            'blocker': 'Full replacement rootfs boot and flash recovery have not been tested',
            'next_gate': 'Bind standalone boot/call evidence to these artifact hashes, then verify image recovery before flashing',
        },
        'network_led': {'no_registration': 'red', 'idle': 'blue', 'outgoing_or_connected': 'green',
                        'incoming_unanswered': 'red+blue', 'wifi_policy': 'native interface UP status; stock LED service disabled',
                        'registration_source': 'local AT_CTL CEREG/CGREG/CREG',
                        'call_source': 'native IMS IPC URCs via control probe',
                        'ims_event_adapter_packaged': True, 'ims_runtime_autostart': True},
        'disabled_stock_services': ['zte_topsw_led', 'zte_topsw_self_regist', 'zte_dm', 'zte_topsw_dua (prestartdua FOTA)'],
        'software_codec': {'AMR-NB': {'implementation':'OpenCORE 0.1.6','modes':list(range(8)),'maximum_bps':12200},
                           'AMR-WB': {'decoder':'OpenCORE 0.1.6','encoder':'VisualOn 0.1.3','modes':list(range(9)),'maximum_bps':23850},
                           'G722': {'implementation':'PJPROJECT 2.17','pcm_rate':16000,'rtp_clock':8000,'bitrate':64000},
                           'standalone_modem_tested': True,'integrated_with_vendor_ims': True,
                           'runtime_enable':'MF79U_OPERATOR_CODECS=1 in private RAM executable',
                           'selection':'AMR-WB / AMR-NB fallback',
                           'verification':json.loads((HERE/'build/operator-codecs-verification.json').read_text())},
        'sip_gateway': {'stack': 'PJSIP 2.17', 'transports': ['UDP','TCP','TLS'],
                        'modem_endpoint': '192.168.0.1:5080', 'pbx_endpoint': '192.168.0.169:5060',
                        'codecs': ['OPUS','G722','PCMA','PCMU','G729'], 'pcm_rate':16000,
                        'roles': {'TRUNK': {'peer_or_registration': True, 'transports': ['UDP','TCP','TLS']},
                                  'SERVER': {'single_account': True, 'single_binding': True, 'transport': 'UDP'}},
                        'host_cp_relay_required': False, 'runtime_autostart': True,
                        'local_registrar_physical_modem_tested': False,
                        'outbound_call_and_pbx_audio_modem_tested': True,
                        'reverse_pcm_activity_confirmed': True,
                        'incoming_sim_call_tested': True, 'reverse_speech_quality_tested': True,
                        'clarity_goal_achieved':False},
        'webui': {'native':True,'bootstrap_seconds':60,'boot_tested':False,
                  'device_component_tested':True,'managed_b03_boot_tested':True,
                  'settings_file':'/mnt/userdata/mf79u/settings.json'},
        'changes': changes,'removed_paths':removed,
    }
    (HERE / 'build/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Prepared reviewed rootfs overlay; no device writes')

if __name__ == '__main__':
    main()
