#!/usr/bin/env python3
"""Read-only installed multipart gate/queue check; no message fields or sends."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import struct
import subprocess
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
DATA = '/mnt/userdata/mf79u'
ADB = [str(ROOT/'outputs/adb')]
spec = importlib.util.spec_from_file_location('sms_receive_transfer', BASE/'device-transfer.py')
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)
shell = transfer.shell


def read(stream, count):
    data = b''
    while len(data) < count:
        chunk = stream.recv(count-len(data))
        if not chunk:
            raise RuntimeError('Short metadata reply')
        data += chunk
    return data


def sms_status():
    with socket.create_connection(('127.0.0.1', 18191), timeout=3) as stream:
        stream.sendall(b'MSM1\x04\0\0\0\0')
        header = read(stream, 9)
        size = struct.unpack('!I', header[5:])[0]
        if header[:5] != b'MSM1\0' or size > 4096:
            raise RuntimeError('Invalid SMS metadata reply')
        value = json.loads(read(stream, size))
        return {key: value.get(key) for key in ['enabled', 'vendorReady', 'incoming', 'pendingIncoming', 'bufferedIncoming', 'queued', 'delivered']}


subprocess.run(ADB+['forward', 'tcp:18191', 'localfilesystem:'+DATA+'/sms-sip.sock'], check=True, capture_output=True)
try:
    diagnostic = json.loads(shell(DATA+'/.mf79u-control -native -sms-receive-diagnose'))
    if diagnostic.get('error'):
        raise RuntimeError('The metadata-only inbox query failed')
    snapshots = []
    for i in range(2):
        native = json.loads(shell('cat /dev/.mf79u-native-status.json'))
        gateway = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
        snapshot = {key: native.get(key) for key in ['pid', 'sipPid', 'voiceMode', 'imsAccess', 'imsReady', 'voiceReady', 'callBackend', 'cellularSmsRadioReady', 'csSignalingReady', 'csAudioReady']}
        snapshot['localRegistered'] = gateway.get('localRegistered')
        snapshot['sms'] = sms_status()
        if snapshot['voiceMode'] != 'VOWIFI_SMS' or snapshot['imsAccess'] != 'WIFI' or not snapshot['imsReady'] or not snapshot['voiceReady']:
            raise RuntimeError('Voice registration changed')
        if not snapshot['sms']['vendorReady'] or snapshot['sms']['queued']:
            raise RuntimeError('SMS service is unavailable or an outgoing job is pending')
        snapshots.append(snapshot)
        if i == 0:
            time.sleep(6) # Observe another production worker poll.
    digest = hashlib.md5((BASE/'build/mf79u-control').read_bytes()).hexdigest()
    installed = shell('md5sum '+DATA+'/.mf79u-control').split()[0]
    if digest != installed or snapshots[0]['pid'] != snapshots[1]['pid'] or snapshots[0]['sipPid'] != snapshots[1]['sipPid']:
        raise RuntimeError('Installed Control or native/SIP processes changed')
    report = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'controlMD5': installed,
              'readOnly': True, 'realSmsOrCallsSubmitted': False, 'modemMessagesDeletedByCheck': False,
              'metadata': diagnostic, 'snapshots': snapshots, 'passed': True,
              'liveMultipartReceptionTested': False}
    (ROOT/'reports/sms-multipart-live-20261012.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
finally:
    subprocess.run(ADB+['forward', '--remove', 'tcp:18191'], capture_output=True)
