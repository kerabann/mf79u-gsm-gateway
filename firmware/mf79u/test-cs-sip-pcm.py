#!/usr/bin/env python3
"""Synthetic on-device SIP/PBX echo, no SIM call and no GSM hardware access."""
from pathlib import Path
import argparse,datetime,importlib.util,json,subprocess
from ram_transfer import ram_push
from cs_sip_media_diagnostic import Diagnostic
BASE=Path(__file__).resolve().parent;BUILD=BASE/'build'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bridge',action='store_true');parser.add_argument('--compare',action='store_true');parser.add_argument('--allow-unregistered',action='store_true',help='Run only synthetic media while production IMS registration is unavailable');args=parser.parse_args()
if args.compare and not args.bridge:parser.error('--compare requires --bridge')
spec=importlib.util.spec_from_file_location('pcm_radio',BASE/'test-cs-reattach.py');radio=importlib.util.module_from_spec(spec);spec.loader.exec_module(radio)
before=radio.status();boot=radio.shell('cat /proc/sys/kernel/random/boot_id')
if (not before.get('imsReady') and not args.allow_unregistered) or before.get('ringOnly') or before.get('csOnly'):raise RuntimeError('Idle ordinary radio policy required')
if json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):raise RuntimeError('Production call active')
test=Diagnostic(radio);p=None;remote='/dev/.mf79u-sip-pcm-selftest';r={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'no_sim_calls':True,'no_cp_io':True,'audio_saved':False,'compare_mode':args.compare}
try:
 ram_push([radio.ADB],BUILD/('cs-pcm-bridge-sip-fixture' if args.bridge else 'cs-sip-pcm-selftest'),remote);radio.shell('chmod 700 '+remote)
 test.prepare()
 p=subprocess.Popen([radio.ADB,'shell',remote+(' --compare-sip' if args.compare else ' --udp' if args.bridge else '')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL)
 ready=p.stdout.readline().decode().strip()
 if ready!=('CS_PCM_BRIDGE waiting=1 external_rate=16000 external_samples=320 speech_saved=0' if args.bridge else 'SIP_PCM_SYNTH_READY'):raise RuntimeError('Synthetic PCM peer failed')
 test.command('INCOMING');test.expect('SIP_MEDIA_CONNECTED')
 output,error=p.communicate(timeout=15)
 rows=[line for line in output.decode().replace('\r','').splitlines() if line.startswith('{')]
 if len(rows)!=1:raise RuntimeError('Synthetic result missing')
 r['media']=json.loads(rows[0])
 r['bridge_messages']=[line for line in output.decode().replace('\r','').splitlines() if line.startswith('CS_PCM_BRIDGE ')]
finally:
 if p and p.poll() is None:p.wait(timeout=12)
 r['sip']=test.close();radio.shell('rm -f '+remote)
 after=radio.status()
 r['ims_ready_before']=bool(before.get('imsReady'));r['ims_ready_after']=bool(after.get('imsReady'))
 r['runtime_restored']=all(before.get(k)==after.get(k) for k in ('pid','sipPid','ringOnly','csOnly')) and (not before.get('imsReady') or after.get('imsReady')) and boot==radio.shell('cat /proc/sys/kernel/random/boot_id')
 r['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();(BUILD/('cs-sip-pcm-compare-synthetic-live.json' if args.compare else 'cs-sip-pcm-bridge-synthetic-live.json' if args.bridge else 'cs-sip-pcm-synthetic-live.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
if (not r.get('runtime_restored') or not r.get('media',{}).get('passed') or r.get('sip',{}).get('failure')
    or not all(r.get('sip',{}).get(k) for k in ('pbx_extension_removed','pbx_idle'))):raise SystemExit(1)
