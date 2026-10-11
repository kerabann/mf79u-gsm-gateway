"""Checked full-overlay install/update/restore. Status and plan are read-only."""
from pathlib import Path
import argparse
import base64
import contextlib
import datetime
import gzip
import hashlib
import http.server
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
from package import ROOT, FW, BUILD, DATA, ARTIFACTS, SCRIPTS, check

ADB = [os.environ.get('ADB', 'adb')]
REPORTS = ROOT / 'reports'
REPORTS.mkdir(exist_ok=True)
ABI = json.loads((FW / 'profiles/b03/link-abi.json').read_text())
KERNEL = json.loads((FW / 'profiles/b03/kernel-abi.json').read_text())
ROOT_TARGETS = ['/etc/rc', '/usr/zte/mf79u/adb-boot', '/usr/zte/zte_conf/config/zte_topsw_daemon.conf',
                '/usr/zte/zte_conf/scripts/zte_debug.sh', '/usr/zte_web/web/index.html', '/lib/libatext.so']


def shell(command, timeout=30):
    result = subprocess.run(ADB + ['shell', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Device command failed; no raw device output retained.')
    return result.stdout.decode().replace('\r', '').strip()


def read(path):
    # Only managed public binaries/startup files are read, never settings/SMS/SIM.
    with tempfile.TemporaryDirectory(prefix='mf79u-public-read-') as tmp:
        p = Path(tmp) / 'artifact'
        result = subprocess.run(ADB + ['pull', path, str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)
        if not result.returncode:
            return p.read_bytes()
        streamed = subprocess.run(ADB + ['exec-out', 'cat', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        if not streamed.returncode and hashlib.md5(streamed.stdout).hexdigest() == hash_remote(path):
            return streamed.stdout
        # The B03 ADB sync service can fail on large files. ASCII transport
        # avoids the shell protocol's binary newline conversion.
        bb = DATA + '/tools/busybox'
        encoded = shell(bb + ' base64 ' + shlex.quote(path), timeout=180)
        return base64.b64decode(''.join(encoded.split()), validate=True)


def status():
    def get(path):
        raw = shell('if [ -f ' + path + ' ]; then cat ' + path + '; fi')
        return json.loads(raw) if raw else {}
    native = get('/dev/.mf79u-native-status.json')
    sip = get('/dev/.mf79u-gateway-status.json')
    return native, sip


def safe_status():
    n, s = status()
    return {'nativeRunning': bool(n.get('pid')), 'sipRunning': bool(s.get('running')),
            'imsReady': n.get('imsReady', False), 'imsAccess': n.get('imsAccess'),
            'voiceMode': n.get('voiceMode'), 'voiceReady': s.get('voiceReady', False),
            'activeCall': bool(s.get('activeCall')) or n.get('callBackend', 'none') != 'none',
            'nativePid': n.get('pid'), 'sipPid': s.get('pid'),
            'ringOnlyGuard': shell('test ! -e ' + DATA + '/native-ring-only || echo YES') == 'YES'}


def idle():
    n, s = status()
    if s.get('activeCall') or n.get('callBackend', 'none') != 'none':
        raise RuntimeError('Active call; no changes made.')
    bb = DATA + '/tools/busybox'
    for name in ['sms-sip-state.json', 'sms-ims-state.json']:
        path = DATA + '/' + name
        jobs = shell('set -e; if [ -f ' + path + ' ]; then ' + bb + " grep -o '\"State\"[[:space:]]*:[[:space:]]*\"\\(queued\\|sending\\)\"' " + path + ' || test "$?" = 1; fi; echo MF79U_SMS_CHECKED')
        if not jobs.endswith('MF79U_SMS_CHECKED'):
            raise RuntimeError('Cannot verify SMS idle state; no changes made.')
        if jobs != 'MF79U_SMS_CHECKED':
            raise RuntimeError('SMS job in progress; no changes made.')


def hash_remote(path):
    value = shell('if [ -f ' + shlex.quote(path) + ' ]; then md5sum ' + shlex.quote(path) + '; fi')
    return value.split()[0] if value else None


def sha_remote(path):
    bb = DATA + '/tools/busybox'
    value = shell('if [ -x ' + bb + ' ]; then ' + bb + ' sha256sum ' + shlex.quote(path) + '; elif command -v sha256sum >/dev/null 2>&1; then sha256sum ' + shlex.quote(path) + '; fi')
    return value.split()[0] if value else hashlib.sha256(read(path)).hexdigest()


def payload():
    path = ROOT / os.environ.get('PACKAGE', 'dist/mf79u-gateway.tar.gz')
    manifest = check(path)
    with tarfile.open(path) as archive:
        files = {name: archive.extractfile(name).read() for name in manifest['files']}
    return files, manifest


def compatible():
    if shell('uname -r') != '3.4.110-rt140':
        raise RuntimeError('Unsupported kernel; exact MF79U B03 required.')
    for name, metadata in ABI.items():
        locations = ['/lib/' + name, '/usr/lib/' + name]
        location = next((p for p in locations if hash_remote(p)), None)
        if not location or sha_remote(location) != metadata['vendor_sha256']:
            raise RuntimeError('Unexpected B03 runtime library: ' + name)
    # Exact kernel image binds the exported Thumb/ARM modes. B03 does not
    # expose a useful /proc/kallsyms; do not infer its absence as a mismatch.
    if hash_remote('/mnt/imagefs/ap_cpuap.bin') != KERNEL['kernel_md5']:
        raise RuntimeError('Unexpected B03 kernel image.')
    if sha_remote('/mnt/imagefs/ap_cpuap.bin') != KERNEL['kernel_sha256']:
        raise RuntimeError('Unexpected B03 kernel SHA256.')
    cfg = '/lib/modules/3.4.110-rt140/kernel/drivers/cfg/cfg.ko'
    if sha_remote(cfg) != KERNEL['cfg_sha256']:
        raise RuntimeError('Unexpected B03 module loader ABI.')
    if sha_remote('/lib/cpko/cpko.ko') != 'ab0f783acee6ac13833e8f8fac1ee8cf79f5ae5b8ba18f941b03155cd8cdd261':
        raise RuntimeError('Unexpected CP kernel module.')


def patched_private(files):
    recipe = json.loads(files['recipes/private-ims.json'])
    original = read('/bin/zte_volte_main')
    if hashlib.sha256(original).hexdigest() != recipe['source_sha256']:
        raise RuntimeError('Unexpected original IMS executable.')
    data = bytearray(original)
    for patch in recipe['patches']:
        offset, old, new = patch['offset'], bytes.fromhex(patch['old']), bytes.fromhex(patch['new'])
        if data[offset:offset + len(old)] != old or len(old) != len(new):
            raise RuntimeError('Unexpected IMS patch instruction.')
        data[offset:offset + len(new)] = new
    if hashlib.sha256(data).hexdigest() != recipe['result_sha256']:
        raise RuntimeError('Derived IMS checksum mismatch.')
    return bytes(data)


def root_policy(files):
    spec = importlib.util.spec_from_file_location('adb_boot', FW / 'adb_boot.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rc = read('/etc/rc')
    marker = b'\n# MF79U owned management service 0.7\nsh /mnt/userdata/mf79u/start-control.sh >/dev/null 2>&1 &\n'
    base = m.unpatch_rc(rc)
    if base.endswith(marker):
        base = base[:-len(marker)]
    if hashlib.md5(base).hexdigest() != '9b070d96d9bd752f579c8c00d9167204':
        raise RuntimeError('Unrecognized startup script; no changes made.')
    result = {'/etc/rc': m.patch_rc(base + marker), '/usr/zte/mf79u/adb-boot': files['helpers/adb-boot'],
              '/usr/zte_web/web/index.html': files['recipes/boot-wait.html']}
    for target, backup, expected in [
        ('/usr/zte/zte_conf/config/zte_topsw_daemon.conf', 'daemon.vendor.b03.conf', 'c77d275ae5617de23689c1827ab9d4f2'),
        ('/usr/zte/zte_conf/scripts/zte_debug.sh', 'debug.vendor.b03.sh', None)]:
        original = read(DATA + '/' + backup) if hash_remote(DATA + '/' + backup) else read(target)
        if expected and hashlib.md5(original).hexdigest() != expected:
            raise RuntimeError('Unrecognized B03 daemon policy.')
        if target.endswith('.conf'):
            remove = {b'zte_topsw_led', b'zte_topsw_self_regist', b'zte_topsw_data_stat', b'zte_topsw_ussd', b'zte_topsw_pbm'}
            candidate = b''.join(line for line in original.splitlines(keepends=True) if not (len(line.split()) >= 3 and line.split()[0] in (b'run', b'sync') and line.split()[2] in remove))
            allowed = {original, candidate}
            for previous in [{b'zte_topsw_led'}, {b'zte_topsw_led', b'zte_topsw_self_regist'}]:
                allowed.add(b''.join(line for line in original.splitlines(keepends=True) if not (len(line.split()) >= 3 and line.split()[0] in (b'run', b'sync') and line.split()[2] in previous)))
        else:
            if hashlib.sha256(original).hexdigest() != 'd3485b497a4ae1e95afb59add48be9b0a53140a1910d9507f866ae7884a4859d':
                raise RuntimeError('Unrecognized B03 debug policy.')
            candidate = original.replace(b'prestartdua &', b'# MF79U: stock FOTA disabled; custom firmware owns updates.').replace(b'\nzte_dm &', b'\n# MF79U: stock remote device-management agent disabled.')
            allowed = {original, candidate}
        if read(target) not in allowed:
            raise RuntimeError('Unrecognized current B03 service file.')
        result[target] = candidate
        result[DATA + '/' + backup] = original
    library = read('/lib/libatext.so')
    if hashlib.sha256(library).hexdigest() == '1c34f29d61f98a39c6241a70972b1989b6932c3a5e7844fb550ca443779b9678':
        data = bytearray(library)
        if data[0x5a32:0x5a34] != bytes.fromhex('0bd0'):
            raise RuntimeError('Unexpected IMEI authorization branch.')
        data[0x5a33] = 0xd1
        result['/lib/libatext.so'] = bytes(data)
    else:
        original = bytearray(library)
        if len(original) != 101072 or original[0x5a32:0x5a34] != bytes.fromhex('0bd1'):
            raise RuntimeError('Unrecognized IMEI authorization library.')
        original[0x5a33] = 0xd0
        if hashlib.sha256(original).hexdigest() != '1c34f29d61f98a39c6241a70972b1989b6932c3a5e7844fb550ca443779b9678':
            raise RuntimeError('Unrecognized IMEI authorization library.')
        result['/lib/libatext.so'] = library
    return result


def storage_plan(changed, sizes):
    # Transfer the largest compressed files first, while the disk is emptiest.
    # Give no credit for shrinkage (JFFS2 garbage collection is asynchronous).
    ordered = dict(sorted(changed.items(), key=lambda item: len(gzip.compress(item[1], 9, mtime=0)), reverse=True))
    growth = peak = 0
    for name, data in ordered.items():
        stage = len(gzip.compress(data, 9, mtime=0))
        extra = 0
        if name.startswith(DATA + '/'):
            old = sizes[name]['oldBytes']
            extra = max(0, len(data) - old)
            # BusyBox must remain available until its replacement is complete.
            if name == DATA + '/tools/busybox':
                peak = max(peak, growth + stage + len(data))
        peak = max(peak, growth + stage + extra)
        growth += extra
    return ordered, peak + 512 * 1024


def loaded_driver():
    if shell('test ! -d /sys/module/mf79u_cs_voice || echo LOADED') != 'LOADED':
        return None
    value = shell('cat /dev/.mf79u-cs-driver.md5')
    if not re.fullmatch(r'[a-f0-9]{32}', value):
        raise RuntimeError('Loaded CS driver ownership fingerprint is unavailable.')
    return value


def plan():
    idle()
    compatible()
    files, manifest = payload()
    targets = {'/' + k: v for k, v in files.items() if k.startswith(DATA.lstrip('/') + '/')}
    targets[DATA + '/.mf79u-volte-private'] = patched_private(files)
    targets.update(root_policy(files))
    targets[DATA + '/control-internal-preferred'] = b''
    if not hash_remote(DATA + '/settings.json'):
        for name, value in [('native-enabled', b'1\n'), ('native-ring-only', b'')]:
            if not hash_remote(DATA + '/' + name):
                targets[DATA + '/' + name] = value
    driver = targets[DATA + '/.mf79u-cs-voice.ko']
    loaded = loaded_driver()
    if loaded and loaded != hashlib.md5(driver).hexdigest() and os.environ.get('REBOOT') != '1':
        raise RuntimeError('Pinned CS driver differs. Use REBOOT=1 for a checked software reboot; live unload is forbidden.')
    changed = {name: data for name, data in targets.items() if hash_remote(name) != hashlib.md5(data).hexdigest()}
    startup_changed = any(name in changed for name in ['/etc/rc', '/usr/zte/zte_conf/config/zte_topsw_daemon.conf', '/usr/zte/zte_conf/scripts/zte_debug.sh', '/lib/libatext.so'])
    reboot_required = startup_changed or bool(loaded and loaded != hashlib.md5(driver).hexdigest())
    if reboot_required and os.environ.get('REBOOT') != '1':
        raise RuntimeError('Applying startup policy or a different pinned driver requires REBOOT=1; no changes made.')
    # Worst-case final storage plus the largest per-file compressed stage and its
    # replacement. Existing unrelated configuration/SMS is never removed.
    disk = shell('df -k /mnt/userdata').splitlines()[-1].split()
    free = int(disk[3]) * 1024
    sizes = {}
    for name, data in changed.items():
        if not name.startswith(DATA + '/'):
            continue
        oldsize = shell('if [ -f ' + shlex.quote(name) + ' ]; then wc -c < ' + shlex.quote(name) + '; else echo 0; fi')
        sizes[name] = {'oldBytes': int(oldsize), 'newBytes': len(data)}
    changed, required = storage_plan(changed, sizes)
    root_free = int(shell('df -k /').splitlines()[-1].split()[3]) * 1024
    root_required = sum(len(v) for n, v in changed.items() if n in ROOT_TARGETS) + 64 * 1024
    result = {'compatible': True, 'idle': True, 'changedFiles': sorted(changed), 'packageFiles': len(manifest['files']),
              'freeBytes': free, 'minimumAdditionalBytes': required, 'softwareRebootRequired': reboot_required,
              'spaceAvailable': free >= required and root_free >= root_required, 'changedSizes': sizes,
              'rootFreeBytes': root_free, 'rootRequiredBytes': root_required,
              'deviceChanged': False, 'callsOrSMSInitiated': False}
    return changed, files, result


def wait_exit(pid):
    for _ in range(150):
        if shell('test ! -e /proc/' + str(pid) + '/exe && echo GONE') == 'GONE':
            return
        time.sleep(.2)
    raise RuntimeError('Owned process did not stop.')


def stop_owned():
    idle()
    n, _ = status()
    supervisor = shell('if [ -f /dev/.mf79u-native-supervisor.pid ]; then cat /dev/.mf79u-native-supervisor.pid; fi')
    if supervisor:
        if not supervisor.isdigit() or int(supervisor) <= 1 or 'start-native.sh' not in shell('cat /proc/' + supervisor + '/cmdline'):
            raise RuntimeError('Unrecognized native supervisor.')
        shell('kill -TERM ' + supervisor)
        wait_exit(supervisor)
        for key in ['pid', 'sipPid']:
            if n.get(key):
                wait_exit(n[key])
    control = shell('if [ -f /dev/.mf79u-control.pid ]; then cat /dev/.mf79u-control.pid; fi')
    if control:
        if not control.isdigit() or int(control) <= 1 or shell('test /proc/' + control + '/exe -ef ' + DATA + '/.mf79u-control && echo OWNED') != 'OWNED':
            raise RuntimeError('Unrecognized Control process.')
        parent = shell('cat /proc/' + control + '/stat').split()[3]
        shell('kill -TERM ' + control)
        wait_exit(control)
        if 'start-control.sh' in shell('if [ -e /proc/' + parent + '/cmdline ]; then cat /proc/' + parent + '/cmdline; fi'):
            wait_exit(parent)
    for program in [DATA + '/tools/dropbearmulti', DATA + '/.mf79u-net-led']:
        pids = shell('for p in /proc/[0-9]*/exe; do if test "$p" -ef ' + shlex.quote(program) + '; then echo "$p"; fi; done').splitlines()
        for value in pids:
            pid = value.split('/')[2]
            if not pid.isdigit() or int(pid) <= 1:
                raise RuntimeError('Unrecognized owned daemon PID.')
            shell('test /proc/' + pid + '/exe -ef ' + shlex.quote(program) + ' && kill -TERM ' + pid)
            wait_exit(pid)


@contextlib.contextmanager
def server(directory):
    # Serve only explicit public artifact names, never a workspace directory.
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            name = self.path.lstrip('/')
            if '/' in name or name not in directory:
                self.send_error(404)
                return
            data = directory[name]
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *args):
            pass
    ip = os.environ.get('HOST_IP', '192.168.0.169')
    port = int(os.environ.get('HTTP_PORT', '18089'))
    http = http.server.ThreadingHTTPServer((ip, port), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    try:
        yield 'http://' + ip + ':' + str(port)
    finally:
        http.shutdown()
        http.server_close()


def put(target, data, url, index):
    bb = DATA + '/tools/busybox' if hash_remote(DATA + '/tools/busybox') else '/bin/busybox'
    stage = DATA + '/.gateway-stage.gz'
    rootfile = target in ROOT_TARGETS
    command = 'set -e; ' + bb + ' wget -q -O ' + stage + ' ' + url + '/' + str(index) + '; '
    command += 'test "$(md5sum ' + stage + ' | cut -d " " -f 1)" = ' + hashlib.md5(gzip.compress(data, 9, mtime=0)).hexdigest() + '; '
    if rootfile:
        command += "trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; "
    command += 'mkdir -p ' + shlex.quote(str(Path(target).parent)) + '; '
    # Runtime daemons have stopped; free their old JFFS2 inode before expansion.
    if not rootfile and target != DATA + '/tools/busybox':
        command += 'rm -f ' + shlex.quote(target) + '; '
    command += bb + ' gzip -dc ' + stage + ' > ' + shlex.quote(target + '.gateway-next') + '; '
    command += 'chmod ' + ('644' if target.endswith(('.conf', '.html')) else '600' if target.endswith('.md5') else '700') + ' ' + shlex.quote(target + '.gateway-next') + '; '
    command += 'test "$(md5sum ' + shlex.quote(target + '.gateway-next') + ' | cut -d " " -f 1)" = ' + hashlib.md5(data).hexdigest() + '; '
    command += 'mv ' + shlex.quote(target + '.gateway-next') + ' ' + shlex.quote(target) + '; rm -f ' + stage + '; sync'
    shell(command, timeout=180)
    if hash_remote(target) != hashlib.md5(data).hexdigest():
        raise RuntimeError('Installed checksum mismatch.')


def start(files):
    # adb push transfers a small public helper only, never a large runtime.
    with tempfile.TemporaryDirectory(prefix='mf79u-detach-') as tmp:
        p = Path(tmp) / 'detach'
        p.write_bytes(files['helpers/detach-control'])
        subprocess.run(ADB + ['push', str(p), '/dev/.mf79u-detach'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    shell('chmod 700 /dev/.mf79u-detach; /dev/.mf79u-detach; rm -f /dev/.mf79u-detach')


def verify():
    files, _ = payload()
    targets = {'/' + k: v for k, v in files.items() if k.startswith(DATA.lstrip('/') + '/')}
    targets[DATA + '/.mf79u-volte-private'] = patched_private(files)
    failures = [name for name, value in targets.items() if hash_remote(name) != hashlib.md5(value).hexdigest()]
    n, s = status()
    control = shell('if [ -f /dev/.mf79u-control.pid ]; then cat /dev/.mf79u-control.pid; fi')
    owned_control = control.isdigit() and int(control) > 1 and shell('test /proc/' + control + '/exe -ef ' + DATA + '/.mf79u-control && echo OWNED') == 'OWNED'
    owned = bool(n.get('pid')) and shell('test /proc/' + str(n['pid']) + '/exe -ef ' + DATA + '/.mf79u-native-gateway && echo OWNED') == 'OWNED'
    owned = owned and bool(s.get('pid')) and shell('test /proc/' + str(s['pid']) + '/exe -ef ' + DATA + '/.mf79u-sip-gateway && echo OWNED') == 'OWNED'
    provisioning = not hash_remote(DATA + '/settings.json')
    result = {'passed': not failures and owned_control and (provisioning or owned and bool(s.get('running'))), 'differentFiles': failures, 'processOwnership': owned,
              'controlOwnership': bool(owned_control), 'provisioningPending': provisioning,
              'runtime': safe_status(), 'callsOrSMSInitiated': False}
    (REPORTS / 'device-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['passed']:
        raise RuntimeError('Installed file or process verification failed; see local report.')
    print('PASS all installed runtime hashes and owned processes; no call/SMS initiated.')


def install():
    changed, files, result = plan()
    if not result['spaceAvailable']:
        raise RuntimeError('Insufficient userdata space; no changes made. See make install-plan.')
    if not changed:
        verify()
        return
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'private/backups' / timestamp
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup.parent.parent, 0o700)
    metadata = {'schema': 1, 'files': {}, 'createdAt': timestamp}
    for i, name in enumerate(changed):
        data = read(name) if hash_remote(name) else None
        filename = str(i)
        metadata['files'][name] = None if data is None else {'file': filename, 'sha256': hashlib.sha256(data).hexdigest()}
        if data is not None:
            (backup / filename).write_bytes(data)
            (backup / filename).chmod(0o600)
    (backup / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
    boot = shell('cat /proc/sys/kernel/random/boot_id')
    settings = shell('if [ -f ' + DATA + '/settings.json ]; then md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini; fi')
    guard = hash_remote(DATA + '/native-ring-only')
    idle()
    try:
        compressed = {str(i): gzip.compress(data, 9, mtime=0) for i, data in enumerate(changed.values())}
        compressed['probe'] = b'mf79u-transfer-ready\n'
        with server(compressed) as url:
            bb = DATA + '/tools/busybox' if hash_remote(DATA + '/tools/busybox') else '/bin/busybox'
            probe = shell('set -e; ' + bb + ' wget -q -O /dev/.mf79u-transfer-probe ' + url + '/probe; test "$(md5sum /dev/.mf79u-transfer-probe | cut -d " " -f 1)" = ' + hashlib.md5(compressed['probe']).hexdigest() + '; rm -f /dev/.mf79u-transfer-probe; echo MF79U_TRANSFER_READY')
            if probe != 'MF79U_TRANSFER_READY':
                raise RuntimeError('Device cannot fetch checked artifacts; no service stopped.')
            stop_owned()
            shell('mkdir -p ' + DATA + '; chmod 700 ' + DATA)
            for i, (name, data) in enumerate(changed.items()):
                put(name, data, url, i)
        shell('set -e; mkdir -p ' + DATA + '/tools/bin ' + DATA + '/ssh-home; chmod 700 ' + DATA + '/tools ' + DATA + '/ssh-home; ln -sf dropbearmulti ' + DATA + '/tools/dropbear; ln -sf dropbearmulti ' + DATA + '/tools/dropbearkey; ' + DATA + '/tools/busybox --install -s ' + DATA + '/tools/bin; ln -sf ../busybox ' + DATA + '/tools/bin/busybox')
        if result['softwareRebootRequired']:
            try:
                shell('sync; reboot')
            except (subprocess.SubprocessError, RuntimeError):
                pass
        else:
            start(files)
        for attempt in range(180):
            try:
                n, s = status()
                mode = n.get('voiceMode')
                control = shell('if [ -f /dev/.mf79u-control.pid ]; then cat /dev/.mf79u-control.pid; fi')
                control_ready = control.isdigit() and shell('test /proc/' + control + '/exe -ef ' + DATA + '/.mf79u-control && echo OWNED') == 'OWNED'
                ready = control_ready and (not settings or s.get('running') and (s.get('role') == 'DISABLED' or mode == 'CS' or n.get('voiceReady')))
                if ready:
                    break
            except (subprocess.SubprocessError, RuntimeError, ValueError):
                pass
            if attempt and attempt % 15 == 0:
                print('Waiting for owned runtime recovery.', flush=True)
            time.sleep(2)
        else:
            raise RuntimeError('Runtime recovery timeout.')
        if settings and shell('md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini') != settings:
            raise RuntimeError('Existing configuration changed unexpectedly.')
        if guard != hash_remote(DATA + '/native-ring-only') and settings:
            raise RuntimeError('Existing voice guard changed unexpectedly.')
        if not result['softwareRebootRequired'] and shell('cat /proc/sys/kernel/random/boot_id') != boot:
            raise RuntimeError('Unexpected reboot.')
        if result['softwareRebootRequired'] and shell('cat /proc/sys/kernel/random/boot_id') == boot:
            raise RuntimeError('New driver did not receive a fresh boot.')
        verify()
    except Exception:
        print('Installation failed. Checked backup:', backup, 'Use make restore BACKUP=' + str(backup), flush=True)
        raise
    result.update({'deviceChanged': True, 'backupDirectory': str(backup), 'settingsPreserved': True, 'voiceGuardPreserved': bool(settings)})
    (REPORTS / 'installation.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS complete overlay installed and verified; backup retained locally.')


def restore():
    path = Path(os.environ.get('BACKUP', '')).resolve()
    base = (ROOT / 'private/backups').resolve()
    if not path.is_relative_to(base) or path == base:
        raise RuntimeError('BACKUP must be a checked backup under private/backups.')
    metadata = json.loads((path / 'manifest.json').read_text())
    allowed = {DATA + '/' + n for n in set(ARTIFACTS) | set(SCRIPTS) | {'cs-runtime.md5', '.mf79u-volte-private', 'daemon.vendor.b03.conf', 'debug.vendor.b03.sh', 'control-internal-preferred', 'native-enabled', 'native-ring-only'}} | set(ROOT_TARGETS)
    if not set(metadata['files']).issubset(allowed):
        raise RuntimeError('Unexpected backup targets.')
    restore_files = {}
    for name, item in metadata['files'].items():
        if item is not None:
            p = path / item['file']
            if p.parent != path or p.is_symlink():
                raise RuntimeError('Unsafe backup member.')
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != item['sha256']:
                raise RuntimeError('Backup checksum mismatch.')
            restore_files[name] = data
    loaded = loaded_driver()
    olddriver = restore_files.get(DATA + '/.mf79u-cs-voice.ko')
    newboot = bool(olddriver and loaded and loaded != hashlib.md5(olddriver).hexdigest())
    if newboot and os.environ.get('REBOOT') != '1':
        raise RuntimeError('Restoring a different pinned driver requires REBOOT=1.')
    idle()
    packed = {str(i): gzip.compress(data, 9, mtime=0) for i, data in enumerate(restore_files.values())}
    with server(packed) as url:
        stop_owned()
        for i, (name, data) in enumerate(restore_files.items()):
            put(name, data, url, i)
    for name, item in metadata['files'].items():
        if item is None:
            prefix = "set -e; trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; " if name in ROOT_TARGETS else ''
            shell(prefix + 'rm -f ' + shlex.quote(name))
    files, _ = payload()
    if newboot:
        with contextlib.suppress(subprocess.SubprocessError, RuntimeError):
            shell('sync; reboot')
    else:
        start(files)
    print('Checked artifact backup restored; use make device-status to verify recovery.')


def main():
    action = argparse.ArgumentParser(description=__doc__)
    action.add_argument('action', choices=['status', 'plan', 'verify', 'install', 'restore'])
    args = action.parse_args()
    if args.action == 'status':
        print(json.dumps(safe_status(), indent=2))
    elif args.action == 'plan':
        _, _, result = plan()
        (REPORTS / 'install-plan.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    else:
        globals()[args.action]()


if __name__ == '__main__':
    main()
