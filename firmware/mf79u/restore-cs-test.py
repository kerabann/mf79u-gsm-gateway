#!/usr/bin/env python3
"""Explicitly restore saved radio/voice policy after the CS experiment.

Keeps ring-only protection armed. Does not reboot, dial, answer, or replace
the native binary. Run only after stopping both passive observers.
"""
from pathlib import Path
import json,re,subprocess
ROOT=Path(__file__).resolve().parents[2];ADB=[str(ROOT/'outputs/adb')]
WAIT_HELPER=ROOT/'firmware/mf79u/build/cs-at-wait'
HELPER=str(WAIT_HELPER if WAIT_HELPER.exists() else ROOT/'outputs/zte-native-usb');DATA='/mnt/userdata/mf79u'
def shell(c):return subprocess.check_output(ADB+['shell',c],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def at(cmd):
 r=subprocess.run([HELPER,cmd]+(['0','30'] if WAIT_HELPER.exists() else []),capture_output=True,timeout=40)
 s=r.stdout.decode()
 if r.returncode or '\r\nOK\r\n' not in s:raise RuntimeError('AT operation failed: '+cmd.split('=')[0])
 return s
def main():
 if json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):raise RuntimeError('Active call; refusing restore')
 if shell('test -e /sys/mf79u_cs/status && echo PRESENT')=='PRESENT':raise RuntimeError('Wait for CS callback expiry before restoring IMS')
 if shell('test -e /sys/mf79u_cs_mo/status && echo PRESENT')=='PRESENT':raise RuntimeError('Outgoing CS diagnostic is still active; clearing/expiry required')
 # Busy GSM kernel logs can rotate within minutes. Accept a fresh read-only
 # route audit of the actual callback/literal/MM reference state, tied to this
 # boot and the exact still-loaded diagnostic set; absence alone is not proof.
 route_verified=False
 route_path=ROOT/'firmware/mf79u/build/cs-route-probe-live.json'
 if route_path.exists():
  audit=json.loads(route_path.read_text())
  current_modules=sorted(row.split()[0] for row in shell('cat /proc/modules').splitlines() if row.startswith('mf79u_cs_'))
  route_verified=all(audit.get(k) is True for k in ['same_boot','unloaded','no_calls_or_cp_writes','restoration_verified']) and audit.get('boot_id')==shell('cat /proc/sys/kernel/random/boot_id') and audit.get('diagnostic_modules')==current_modules
 if any(row.split()[0].startswith('mf79u_cs_mo') for row in shell('cat /proc/modules').splitlines()):
  mo_log=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_MO | tail -n 1")
  if not route_verified and not all(s in mo_log for s in ['expired seconds=','callback_restored=1','admission_restored=1','call_idle=1']):raise RuntimeError('Outgoing diagnostic restoration not verified')
 if any(row.split()[0].startswith('mf79u_cs_asc') for row in shell('cat /proc/modules').splitlines()):
  asc_log=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_ASC | tail -n 1")
  if not route_verified and not all(s in asc_log for s in ['expired seconds=','callback_restored=1']):raise RuntimeError('ASC observer restoration not verified')
 if any(row.startswith('mf79u_cs_ring') for row in shell('cat /proc/modules').splitlines()):
  ring_log=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_KRING | tail -n 1")
  if 'expired seconds=' not in ring_log or 'callback_restored=1' not in ring_log:raise RuntimeError('Original CC callback restoration not verified')
 if any(row.split()[0].startswith('mf79u_cs_connect') for row in shell('cat /proc/modules').splitlines()):
  probe_log=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_KCONNECT | tail -n 1")
  if not route_verified and not all(s in probe_log for s in ['expired seconds=','callback_restored=1','call_idle=1']):
   raise RuntimeError('Diagnostic CS call clearing/callback restoration not verified')
 if any(row.split()[:1]==['4131'] for row in shell('cat /proc/sysvipc/msg').splitlines()[1:]):raise RuntimeError('Stop exclusive CS receiver before restore')
 profile=json.loads(shell('cat '+DATA+'/native-cs-radio-profile.json'))
 values=profile.get('sysconfig')
 if not isinstance(values,list) or len(values)!=4 or any(type(v)!=int or not 0<=v<=999 for v in values):raise RuntimeError('Invalid saved radio profile')
 flags=json.loads(shell('cat '+DATA+'/native-cs-voice-flags.json'))['original']
 if set(flags)!=set(['OPEN_VOICE_FLAG','VOICE_SUPPORT']) or any(type(v)!=int or v not in (0,1) for v in flags.values()):raise RuntimeError('Invalid saved voice flags')
 if not json.loads(shell('cat /dev/.mf79u-native-status.json')).get('ringOnly'):raise RuntimeError('Ring-only protection must remain armed')
 for name,value in flags.items():
  at('AT+ZSET="'+name+'",'+str(value))
  response=at('AT+ZSET="'+name+'"')
  if not re.search(r'\+ZSET:\s*"'+name+r'",'+str(value)+r'\b',response):raise RuntimeError('Voice flag restore readback failed')
 at('AT^SYSCONFIG='+','.join(map(str,values)))
 response=at('AT^SYSCONFIG?');match=re.search(r'\^SYSCONFIG:\s*(\d+),(\d+),(\d+),(\d+)',response)
 if not match or [int(v) for v in match.groups()]!=values:raise RuntimeError('Radio restore readback failed')
 shell('rm -f '+DATA+'/native-cs-only; sync')
 print('Original radio preference and voice flags restored; IMS policy enabled; ring-only retained. Boot-time voice policy may require a later reboot.')
if __name__=='__main__':main()
