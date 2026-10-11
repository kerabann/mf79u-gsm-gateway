#!/usr/bin/env python3
"""One explicitly authorized normal-SIM CS diagnostic; number from stdin only.

Does not arm the module. Saves sanitized protocol/state metadata, never number,
SIM identities, raw PDU, gateway credentials, or unrelated kernel log lines.
"""
from pathlib import Path
import datetime,json,re,subprocess,sys,time
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];ADB=[str(ROOT/'outputs/adb')]
def shell(cmd):
 return subprocess.check_output(ADB+['shell',cmd],stderr=subprocess.PIPE,timeout=15).decode().replace('\r','').strip()
def native():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def write_control(value):
 # Legacy ADB shell does not propagate stdin EOF. Read one newline-terminated
 # value, then exit; no destination in the remote command/argv or a temp file.
 # Vendor shell printf returned1 even after a successful write. Use our
 # already verified BusyBox shell's builtin and check its real return code.
 command="/mnt/userdata/mf79u/tools/busybox sh -c 'read cs_probe_value; if printf \"%s\\n\" \"$cs_probe_value\" > /sys/mf79u_cs_mo/control; then echo MF79U_CS_WRITE_OK; else echo MF79U_CS_WRITE_FAILED; fi; unset cs_probe_value'"
 r=subprocess.run(ADB+['shell',command],input=value+b'\n',capture_output=True,timeout=15)
 # An interactive legacy shell can echo the command text (both branches).
 # Only complete marker lines describe execution; never expose echoed input.
 markers=[v.strip() for v in r.stdout.replace(b'\r',b'').splitlines() if v.strip() in (b'MF79U_CS_WRITE_OK',b'MF79U_CS_WRITE_FAILED')]
 return 0 if r.returncode==0 and markers and markers[-1]==b'MF79U_CS_WRITE_OK' else 1
number=sys.stdin.buffer.readline(34).strip()
if not re.fullmatch(rb'[0-9]{5,32}',number):raise SystemExit('Only a normal numeric destination is accepted')
before=native();boot=shell('cat /proc/sys/kernel/random/boot_id')
if not before.get('csOnly') or not before.get('ringOnly') or before.get('imsReady') or before.get('csRegistration') not in (1,5):raise SystemExit('Registered guarded CS-only runtime required')
if json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):raise SystemExit('SIP call already active')
initial=shell('cat /sys/mf79u_cs_mo/status').split()
if initial[:2]!=['MF79U_CS','1'] or len(initial)!=8 or initial[2:4]!=['1','0']:raise SystemExit('Fresh armed outgoing diagnostic required')
log=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep -E 'MF79U_CS_(MO|ASC)' | tail -n 100")
armed=[line for line in log.splitlines() if 'MF79U_CS_MO armed seconds=' in line]
if not armed:raise SystemExit('Outgoing diagnostic arming evidence missing')
start=float(re.search(r'\[\s*([0-9.]+)\]',armed[-1]).group(1))
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'boot_id':boot,
 'explicitly_authorized_single_dial':True,'number_saved':False,'incoming_answer':False,'audio_implemented':False,
 'initial_status':initial,'status_samples':[],'resource_samples':[],'remote_hangup_verified':False}
path=BASE/'build/cs-mo-outgoing-live.json'
def save():path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
def capture_metadata():
 lines=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep -E 'MF79U_CS_(MO|ASC|PCM)' | tail -n 400").splitlines()
 previous=report.setdefault('messages',[])
 for line in lines:
  match=re.search(r'\[\s*([0-9.]+)\]',line)
  if match and float(match.group(1))>=start and line not in previous:previous.append(line)
 # Same metadata allowlist as the final snapshot; never raw PDUs/audio.
 report['messages']=previous[-800:]
 # Bound scalar memory/CPU evidence to distinguish starvation/OOM from a
 # signal-path failure. Never collect processes, addresses or sample data.
 resources=shell('cat /proc/uptime /proc/meminfo')
 rows=resources.splitlines();entry={}
 if rows and re.fullmatch(r'[0-9.]+ [0-9.]+',rows[0]):entry['uptime_seconds'],entry['idle_seconds']=map(float,rows[0].split())
 for line in rows[1:]:
  match=re.fullmatch(r'(MemFree|Cached|SwapFree|SwapTotal|Slab):\s+(\d+) kB',line)
  if match:entry[match[1]+'_kib']=int(match[2])
 report['resource_samples'].append(entry);report['resource_samples']=report['resource_samples'][-60:]
save()
try:report['command_exit']=write_control(number)
except subprocess.TimeoutExpired:
 report['command_outcome']='unknown_timeout';save();raise SystemExit('Control write outcome unknown; do not repeat the destination')
finally:number=b''
save()
deadline=time.monotonic()+100
last=None
while time.monotonic()<deadline:
 if shell('cat /proc/sys/kernel/random/boot_id')!=boot:report['reboot']=True;break
 present=shell('test -e /sys/mf79u_cs_mo/status && echo PRESENT')=='PRESENT'
 if not present:report['sysfs_removed']=True;break
 row=shell('cat /sys/mf79u_cs_mo/status')
 if row!=last:report['status_samples'].append(row);last=row
 capture_metadata();save()
 time.sleep(2)
else:
 report['observation_timeout']=True
 # A stop request remains inside the real CC task; never guess raw AT hangup.
 report['stop_command_exit']=write_control(b'stop')
capture_metadata()
trace='\n'.join(report['messages'])
report.update(mm_established='mm_established=1' in trace,connected='state=5 ' in trace,
 dsp_audio_candidate_started='dsp_audio_tone_phase=0 ' in trace,
 dsp_audio_candidate_all_phases=all('dsp_audio_tone_phase='+str(i)+' ' in trace for i in range(3)),
 dsp_audio_candidate_stopped='dsp_audio_stopped=1 disabled=1 ended=1 saved_ap_fields_restored=1 ' in trace,
 synthetic_amr_candidate_started='amr_candidate_phase=0 ' in trace,
 synthetic_amr_candidate_all_phases=all('amr_candidate_phase='+str(i)+' ' in trace for i in range(3)),
 synthetic_amr_ul_zero_restored='amr_candidate_stopped=1 ul_zero_restored=1 ' in trace,
 network_dtmf_requested='tx_type=35 ' in trace,network_dtmf_start_ack='dtmf_state=2 ' in trace,
 network_dtmf_stop_ack='dtmf_state=4 ' in trace,network_dtmf_failed='dtmf_state=5 ' in trace,
 mm_request_sent='mm_request=aa3c ' in trace,setup_sent='tx_type=05 ' in trace,
 mm_service_released='mm_cc_service_released=1' in trace or 'mm_release_indication=1' in trace,
 local_disconnect_sent='tx_type=25 ' in trace,local_release_received='cc_type=2d ' in trace,
 local_release_complete_sent='tx_type=2a ' in trace,
 callback_restored='callback_restored=1 admission_restored=1 call_idle=1' in trace,
 after=native(),same_boot=shell('cat /proc/sys/kernel/random/boot_id')==boot)
report['same_native_sip_pids']=all(before[k]==report['after'][k] for k in ['pid','sipPid'])
save()
print(json.dumps({k:report[k] for k in ['command_exit','mm_established','connected','callback_restored','same_boot','same_native_sip_pids']}))
