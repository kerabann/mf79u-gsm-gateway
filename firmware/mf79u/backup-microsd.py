#!/usr/bin/env python3
"""Verified whole-card backup over USB LAN. Never writes to or mounts the card."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import secrets
import select
import signal
import socket
import struct
import subprocess
import time
from zoneinfo import ZoneInfo

from ram_transfer import ram_push

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ADB = [str(ROOT / 'outputs/adb'), '-s', '123456789ABCDEF']
CHUNK = 16 * 1024 * 1024


def shell(command):
    return subprocess.check_output(ADB + ['shell', command], timeout=20).decode().replace('\r', '').strip()


def identity():
    size = int(shell('cat /sys/block/mmcblk0/size')) * 512
    cid = hashlib.sha256(shell('cat /sys/block/mmcblk0/device/cid').encode()).hexdigest()
    return size, cid


def exact(connection, count):
    data = bytearray()
    while len(data) < count:
        part = connection.recv(min(1024 * 1024, count - len(data)))
        if not part:
            raise RuntimeError('SD transfer ended before the complete range arrived')
        data.extend(part)
    return data


class Reader:
    def __init__(self, size):
        self.size = size
        self.token = secrets.token_hex(16)
        self.pid = None
        self.process = subprocess.Popen(ADB + ['shell', '/dev/.mf79u-sd-backup-server ' + self.token],
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            ready, _, _ = select.select([self.process.stdout], [], [], 20)
            if not ready:
                raise RuntimeError('Read-only SD helper did not start')
            line = self.process.stdout.readline().decode().strip()
            match = re.fullmatch(r'SD_BACKUP_READY pid=(\d+) bytes=(\d+)', line)
            if not match or int(match[2]) != size:
                raise RuntimeError('Read-only SD helper returned an unexpected device size')
            self.pid = int(match[1])
        except BaseException:
            self.close()
            raise

    def read(self, offset, length):
        with socket.create_connection(('192.168.0.1', 18191), timeout=45) as connection:
            connection.settimeout(45)
            connection.sendall(self.token.encode() + struct.pack('>QQ', offset, length))
            header = exact(connection, 32)
            if header[:8] != b'MF79USD1' or struct.unpack('>QQQ', header[8:]) != (self.size, offset, length):
                raise RuntimeError('Invalid SD range header')
            data = exact(connection, length)
            device_hash = exact(connection, 32)
            if hashlib.sha256(data).digest() != device_hash:
                raise RuntimeError('Device/host SHA256 mismatch; range was not saved')
            return data

    def close(self):
        if self.pid:
            executable = shell('ls -l /proc/' + str(self.pid) + '/exe')
            executable = re.sub(r'\x1b\[[0-9;]*m', '', executable).partition(' -> ')[2]
            if executable == '/dev/.mf79u-sd-backup-server':
                shell('kill -15 ' + str(self.pid))
        if self.process.poll() is None:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
        self.token = ''


def save(path, report):
    staged = path.with_suffix('.next')
    with staged.open('w') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    staged.replace(path)


def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--disk', required=True, help='Mac whole disk mapped to ZTE MMC')
    arguments.add_argument('--output', required=True, type=Path)
    args = arguments.parse_args()
    os.umask(0o077)
    if not re.fullmatch(r'disk\d+', args.disk):
        raise RuntimeError('Expected a whole Mac disk identifier')
    size, cid = identity()
    disk = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', args.disk], timeout=20))
    if disk.get('Internal') is not False or disk.get('TotalSize') != size or not disk.get('IORegistryEntryName', '').startswith('ZTE MMC '):
        raise RuntimeError('Mac disk does not match the modem microSD capacity and ZTE media')
    if '/dev/mmcblk0' in shell('cat /proc/mounts'):
        raise RuntimeError('Card is mounted by the modem; stop writers before creating a consistent image')
    subprocess.run(['diskutil', 'unmountDisk', args.disk], check=True, capture_output=True, timeout=20)
    destination = args.output.resolve()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = HERE / 'build/sd-backup-server'
    ram_push(ADB, source, '/dev/.mf79u-sd-backup-server')
    tests = shell('/dev/.mf79u-sd-backup-server --selftest').splitlines()
    if len(tests) != 8:
        raise RuntimeError('Native SHA256 selftest did not complete')
    pattern = bytes((i * 17 + 13) & 255 for i in range(256))
    for line in tests:
        length, digest = line.split()
        length = int(length)
        data = (pattern * ((length + 255) // 256))[:length]
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError('Native SHA256 selftest disagrees with hashlib')
    print('PASS native SHA256 padding/streaming fixtures', flush=True)
    report = {'started_at': datetime.now(ZoneInfo('Asia/Nicosia')).isoformat(),
              'state': 'copying', 'source': '/dev/mmcblk0', 'card_bytes': size,
              'card_cid_sha256': cid, 'source_read_only': True,
              'mac_disk': args.disk, 'helper_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'completed_bytes': 0, 'ranges': []}
    manifest = destination / 'manifest.json'
    image = destination / 'microsd.img.partial'
    reader = Reader(size)
    started = last = time.monotonic()
    stream_hash = hashlib.sha256()
    try:
        # Independently compare one range with the stock dd+md5sum path and
        # validate a seek beyond 2 GiB before committing the complete image.
        first = reader.read(0, 1024 * 1024)
        reference = shell('dd if=/dev/mmcblk0 bs=512 count=2048 2>/dev/null | md5sum').split()[0]
        if hashlib.md5(first).hexdigest() != reference:
            raise RuntimeError('Independent block-device read disagrees with the USB LAN transfer')
        reader.read(size - 1024 * 1024, 1024 * 1024)
        report['independent_first_mib_verified'] = True
        report['large_offset_seek_verified'] = True
        print(f'SD_BACKUP_STARTED bytes={size} output={destination}', flush=True)
        with image.open('xb') as out:
            for offset in range(0, size, CHUNK):
                length = min(CHUNK, size - offset)
                error = None
                for attempt in range(3):
                    try:
                        data = reader.read(offset, length)
                        error = None
                        break
                    except (OSError, RuntimeError) as e:
                        error = e
                        if identity() != (size, cid):
                            raise RuntimeError('Card identity changed; incomplete backup preserved') from e
                if error:
                    raise error
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
                stream_hash.update(data)
                report['ranges'].append({'offset': offset, 'bytes': length, 'sha256': hashlib.sha256(data).hexdigest()})
                report['completed_bytes'] = offset + length
                save(manifest, report)
                now = time.monotonic()
                if now - last >= 25 or offset + length == size:
                    elapsed = now - started
                    done = offset + length
                    speed = done / elapsed
                    print(json.dumps({'state': 'copying', 'percent': round(100 * done / size, 2),
                                      'copied_gib': round(done / 1024**3, 2),
                                      'mib_per_second': round(speed / 1024**2, 2),
                                      'remaining_minutes_estimate': round((size - done) / speed / 60, 1)}), flush=True)
                    last = now
        if identity() != (size, cid) or image.stat().st_size != size:
            raise RuntimeError('Final source identity or image size check failed')
        report['state'] = 'verifying_local_image'
        report['source_stream_sha256'] = stream_hash.hexdigest()
        save(manifest, report)
        reader.close()
        reader = None
        print('SD_BACKUP_VERIFYING_LOCAL_IMAGE', flush=True)
        stored_hash = hashlib.sha256()
        with image.open('rb') as stored:
            while data := stored.read(8 * 1024 * 1024):
                stored_hash.update(data)
        if stored_hash.digest() != stream_hash.digest():
            raise RuntimeError('Full image SHA256 differs from the verified source stream')
        final = image.with_suffix('')
        image.replace(final)
        final.chmod(0o400)
        report.update(state='verified', image='microsd.img', sha256=stored_hash.hexdigest(),
                      finished_at=datetime.now(ZoneInfo('Asia/Nicosia')).isoformat(),
                      verification='device SHA256 per range + independent first MiB + full local image SHA256')
        save(manifest, report)
        (destination / 'SHA256SUMS').write_text(report['sha256'] + '  microsd.img\n')
        print(json.dumps({'state': 'verified', 'bytes': size, 'sha256': report['sha256'],
                          'image': str(final)}), flush=True)
    except BaseException:
        report['state'] = 'incomplete'
        save(manifest, report)
        raise
    finally:
        if reader is not None:
            reader.close()
        shell('rm -f /dev/.mf79u-sd-backup-server')


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
