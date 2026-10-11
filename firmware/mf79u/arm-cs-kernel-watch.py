#!/usr/bin/env python3
"""Arm exact-B03 bounded CC observer in RAM; no payloads/call-control commands."""
from pathlib import Path
import argparse,datetime,hashlib,json,subprocess
from ram_transfer import ram_push
from b03_kernel_relocations import audit_module
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];ADB=[str(ROOT/'outputs/adb')]
parser=argparse.ArgumentParser(description=__doc__)
mode=parser.add_mutually_exclusive_group()
mode.add_argument('--headers',action='store_true')
mode.add_argument('--ring',action='store_true')
mode.add_argument('--channels',action='store_true')
mode.add_argument('--asc',action='store_true')
mode.add_argument('--mo',action='store_true')
mode.add_argument('--connect-probe',action='store_true')
parser.add_argument('--authorized-single-answer',action='store_true',help='Only after explicit human permission for answering the ordinary SIM')
parser.add_argument('--authorized-single-dial',action='store_true',help='Only after explicit human permission for a diagnostic outgoing call; arming does not dial')
parser.add_argument('--instance',type=int,default=1)
parser.add_argument('--connected-seconds',type=int,help='Require the matching MO call-clearing deadline')
parser.add_argument('--mm-release-delay',type=int,default=0,choices=(0,2),help='Require matching MO diagnostic MM release delay')
parser.add_argument('--dtmf-tone',action='store_true',help='Require the explicit network DTMF MO build; does not implement PCM audio')
parser.add_argument('--amr-tone-candidate',action='store_true',help='Explicit synthetic AMR UL-copier candidate, own connected MO only')
parser.add_argument('--dsp-tone-candidate',action='store_true',help='Explicit reference DSP audio candidate for own connected MO or one-answer MT')
parser.add_argument('--i2s-pcm-candidate',action='store_true',help='Explicit internal I2S PCM one-answer MT test')
parser.add_argument('--i2s-port-tone',action='store_true',help='Explicit DSP control / connected ARM port diagnostic')
parser.add_argument('--i2s-reference-open-clocks',action='store_true',help='Explicit four-clock reference Open diagnostic')
parser.add_argument('--i2s-full-voice-open',action='store_true',help='Explicit complete voice API diagnostic with a matching restored idle receipt')
parser.add_argument('--i2s-arm-tone',action='store_true',help='Full voice MO: two-second DSP control, then ARM-only PCM tones')
parser.add_argument('--i2s-rx-start',action='store_true',help='Bounded echo with late ARM0 startup profile after matching restored idle test')
parser.add_argument('--i2s-arm-echo',action='store_true',help='After two-second ARM tone, return received FIFO speech through bounded RAM for four seconds')
parser.add_argument('--i2s-public-pcm',action='store_true',help='Explicit one-call MO public PCM test with matching restored idle receipt')
parser.add_argument('--dsp-frame-metadata',action='store_true',help='Explicitly select the read-only TCH buffer summary build')
parser.add_argument('--dsp-speech-candidates',action='store_true',help='Explicitly select adjacent unclassified TCH buffers')
parser.add_argument('--dsp-pcm-metadata',action='store_true',help='Explicit non-consuming periodicity statistics of exact-B03 SRAM windows')
parser.add_argument('--i2s-arm1-echo',action='store_true',help='Echo using physically observed ARM1 RX and verified ARM0 TX')
parser.add_argument('--i2s-arm1-rx-only',action='store_true',help='Enable ARM1 RX without its unused transmitter')
parser.add_argument('--i2s-arm1-tx-switch',action='store_true',help='Compare ARM0/ARM1 transmit then echo on ARM1')
parser.add_argument('--i2s-userspace-pcm',action='store_true',help='Explicit bounded PCM transport on ARM1')
parser.add_argument('--i2s-streaming-pcm',action='store_true',help='No synthetic tones or media deadline; explicit call control still bounded')
args=parser.parse_args()
if args.i2s_streaming_pcm and not args.i2s_userspace_pcm:parser.error('Streaming mode requires userspace PCM')
if args.connected_seconds is not None and (not args.mo or not 8<=args.connected_seconds<=40):parser.error('Connected timeout requires MO and 8..40 seconds')
if args.mm_release_delay and not args.mo:parser.error('MM release delay requires MO')
if args.i2s_userspace_pcm and not (args.mo and args.i2s_arm1_tx_switch):parser.error('Userspace PCM requires MO ARM1 duplex')
if args.i2s_arm1_tx_switch and not (args.i2s_arm1_rx_only and args.i2s_arm1_echo):parser.error('TX switch requires ARM1 RX-only echo control')
if args.i2s_arm1_rx_only and not args.i2s_arm1_echo:parser.error('RX only requires ARM1 echo')
if args.i2s_arm1_echo and (not args.i2s_arm_echo or args.i2s_rx_start):parser.error('ARM1 echo requires a separate full voice echo diagnostic')
if args.i2s_pcm_candidate and (not (args.connect_probe or args.mo) or args.dsp_tone_candidate):raise SystemExit('I2S PCM requires separate one-call diagnostic')
if args.mo and args.i2s_pcm_candidate and not (args.i2s_public_pcm or args.i2s_arm_tone):raise SystemExit('MO I2S requires explicit public PCM or full voice ARM tone diagnostic')
if args.i2s_arm_tone and (not (args.mo and args.i2s_full_voice_open and args.i2s_port_tone) or args.i2s_public_pcm):raise SystemExit('ARM tone requires separate full voice MO port diagnostic')
if args.i2s_rx_start and not args.i2s_arm_echo:raise SystemExit('Connected late profile requires the echo diagnostic')
if args.i2s_arm_echo and not args.i2s_arm_tone:raise SystemExit('ARM echo requires the explicit ARM tone diagnostic')
if args.i2s_public_pcm and not (args.mo and args.i2s_port_tone):raise SystemExit('Public PCM connected variant requires separate MO port-tone diagnostic')
if args.i2s_port_tone and not args.i2s_pcm_candidate:raise SystemExit('Port tone requires I2S PCM MT probe')
if args.i2s_reference_open_clocks and not args.i2s_port_tone:raise SystemExit('Reference Open clocks require the connected port diagnostic')
if args.i2s_full_voice_open and not args.i2s_port_tone:raise SystemExit('Full voice API requires the connected port diagnostic')
if args.dtmf_tone and not args.mo:raise SystemExit('Network tone applies only to MO')
if args.amr_tone_candidate and (not args.mo or args.dtmf_tone):raise SystemExit('AMR candidate requires a separate MO without network DTMF')
if args.dsp_tone_candidate and (not (args.mo or args.connect_probe) or args.dtmf_tone or args.amr_tone_candidate):raise SystemExit('DSP tone requires a separate MO or one-answer MT build')
if args.dsp_frame_metadata and not args.channels:raise SystemExit('TCH buffer summaries apply only to channels')
if args.dsp_speech_candidates and not args.dsp_frame_metadata:raise SystemExit('Speech candidates require explicit frame summaries')
if args.dsp_pcm_metadata and not args.channels:raise SystemExit('PCM window statistics apply only to the channel sampler')
if args.connect_probe and not args.authorized_single_answer:raise SystemExit('Explicit permission for one diagnostic answer is required')
if args.authorized_single_answer and not args.connect_probe:raise SystemExit('Answer authorization is only valid for the separate diagnostic')
if args.mo and not args.authorized_single_dial:raise SystemExit('Explicit permission for an outgoing diagnostic call is required')
if args.authorized_single_dial and not args.mo:raise SystemExit('Dial authorization is only valid for the MO diagnostic')
if not 1<=args.instance<=64 or (args.instance!=1 and not (args.headers or args.ring or args.connect_probe or args.asc or args.mo)):raise SystemExit('Instance2..64 is for pinned observers only')
suffix=str(args.instance) if args.instance!=1 else ''
NAME='mf79u_cs_ring'+suffix if args.ring else ('mf79u_cs_header'+suffix if args.headers else ('mf79u_cs_channels' if args.channels else 'mf79u_cs_watch'))
OUTPUT='cs-kernel-ring'+suffix if args.ring else ('cs-kernel-header'+suffix if args.headers else ('cs-channel-watch' if args.channels else 'cs-kernel-watch'))
PREFIX='MF79U_CS_KRING' if args.ring else ('MF79U_CS_KHEADER' if args.headers else ('MF79U_CS_CHANNEL' if args.channels else 'MF79U_CS_KWATCH'))
if args.connect_probe:NAME='mf79u_cs_connect'+suffix;OUTPUT='cs-connect-probe'+suffix;PREFIX='MF79U_CS_KCONNECT'
if args.asc:NAME='mf79u_cs_asc'+suffix;OUTPUT='cs-asc-watch'+suffix;PREFIX='MF79U_CS_ASC'
if args.mo:NAME='mf79u_cs_mo'+suffix;OUTPUT='cs-mo-probe'+suffix;PREFIX='MF79U_CS_MO'
REMOTE='/dev/.mf79u-'+OUTPUT+'.ko'
def shell(c):return subprocess.check_output(ADB+['shell',c],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def native():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def loaded():return any(line.split()[0]==NAME for line in shell('cat /proc/modules').splitlines())
if loaded():raise SystemExit('Observer already loaded; do not overwrite its ownership')
if shell('uname -r')!='3.4.110-rt140':raise SystemExit('Unrecognized kernel')
if shell('md5sum /mnt/imagefs/ap_cpuap.bin').split()[0]!='4a29280dfa9e0c522de9e38091ea2533':raise SystemExit('Unrecognized B03 kernel image')
for path,expected in [('/lib/cpko/cpko.ko','8138d03644b0417ec3fba9d7175200bc'),('/lib/modules/3.4.110-rt140/kernel/drivers/cfg/cfg.ko','62a4f0142042da52ea7e207c160f4dfe')]:
 if shell('md5sum '+path).split()[0]!=expected:raise SystemExit('Unrecognized B03 binary')
if not any(line.startswith('cpko 6397096 ') and '0xbf000000' in line for line in shell('cat /proc/modules').splitlines()):raise SystemExit('Unrecognized CP placement')
before=native();boot=shell('cat /proc/sys/kernel/random/boot_id')
if not before.get('ringOnly') or json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):raise SystemExit('Idle ring-only runtime required')
if (args.ring or args.connect_probe or args.mo) and (not before.get('csOnly') or before.get('csRegistration') not in (1,5) or before.get('imsReady')):raise SystemExit('Registered CS-only runtime required')
if args.mo and shell('test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE':raise SystemExit('Previous outgoing diagnostic is still active')
if args.mo and before.get('epsRegistration') in (1,5):raise SystemExit('Outgoing GSM diagnostic requires completed GSM-only preparation')
if args.connect_probe and (args.dsp_tone_candidate or args.i2s_pcm_candidate) and before.get('epsRegistration') in (1,5):raise SystemExit('Incoming audio test requires completed GSM-only preparation')
if (args.mo or args.connect_probe) and shell('test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE':raise SystemExit('Previous MO callback is still active')
if args.connect_probe and shell('test -e /sys/mf79u_cs/status && echo ACTIVE')=='ACTIVE':raise SystemExit('Wait for the previous CC hook to expire')
local=BASE/'build'/f'{NAME}.ko';build=json.loads((BASE/'build'/f'{OUTPUT}-build.json').read_text())
if build['sha256']!=hashlib.sha256(local.read_bytes()).hexdigest():raise SystemExit('Build metadata checksum mismatch')
if args.mo and (build.get('connected_seconds')!=(args.connected_seconds if args.connected_seconds is not None else 28 if args.i2s_userspace_pcm else 10) or build.get('timeout_trace_version')!=1):raise SystemExit('Rebuild required: connected timeout or trace differs')
if args.mo and (build.get('nsd_allocator')!='vendor_bf29be71' or not build.get('nsd_context_guard') or build.get('nsd_fixture_sha256')!=hashlib.sha256((BASE/'build/cs-nsd-b03-offline.json').read_bytes()).hexdigest()):raise SystemExit('Verified vendor N(SD) allocator required')
if args.mo and build.get('mm_release_delay_seconds')!=args.mm_release_delay:raise SystemExit('Rebuild required: MM release delay differs')
if bool(build.get('test_dsp_audio_tone'))!=args.dsp_tone_candidate:raise SystemExit('DSP audio candidate must be explicitly selected')
if bool(build.get('test_i2s_pcm'))!=args.i2s_pcm_candidate:raise SystemExit('I2S PCM candidate must be explicitly selected')
if bool(build.get('connected_port_tone'))!=(args.i2s_port_tone and not args.i2s_streaming_pcm):raise SystemExit('Port tone diagnostic selection differs')
if bool(build.get('reference_open_clocks'))!=args.i2s_reference_open_clocks:raise SystemExit('Reference Open clocks must be explicitly selected')
if bool(build.get('full_reference_voice_api'))!=args.i2s_full_voice_open:raise SystemExit('Full voice API must be explicitly selected')
if bool(build.get('public_pcm_route'))!=args.i2s_public_pcm:raise SystemExit('Public PCM route must be explicitly selected')
if bool(build.get('arm_pcm_tone'))!=(args.i2s_arm_tone and not args.i2s_streaming_pcm):raise SystemExit('ARM PCM tone selection differs')
if bool(build.get('rx_start_comparison'))!=args.i2s_rx_start:raise SystemExit('Late startup profile must be explicitly selected')
if args.i2s_rx_start:
 if build.get('late_idle_receipt')!='cs-full-voice-rx-start-live.json' or hashlib.sha256((BASE/'build/cs-full-voice-rx-start-live.json').read_bytes()).hexdigest()!=build.get('late_idle_receipt_sha256'):raise SystemExit('Late profile idle receipt differs')
if bool(build.get('arm1_tx_switch'))!=args.i2s_arm1_tx_switch:raise SystemExit('TX port switch must be explicitly selected')
if bool(build.get('streaming_pcm'))!=args.i2s_streaming_pcm:raise SystemExit('Streaming PCM build selection differs')
if bool(build.get('userspace_pcm'))!=args.i2s_userspace_pcm:raise SystemExit('Userspace PCM must be explicitly selected')
if args.i2s_userspace_pcm:
 if build.get('hardware_close_after_mm_idle') is not True:raise SystemExit('MM-idle audio shutdown required; rebuild the MO diagnostic')
 for key,name in [('duplex_receipt_sha256','cs-mo26-full-voice-arm-echo-arm1-rx-only-tx-switch-test.json'),('transport_receipt_sha256','cs-pcm-transport-live.json')]:
  if build.get(key)!=hashlib.sha256((BASE/'build'/name).read_bytes()).hexdigest():raise SystemExit('PCM proof changed; rebuild required')
 for name,checksum in build.get('pcm_headers_sha256',{}).items():
  if hashlib.sha256((BASE/'src'/name).read_bytes()).hexdigest()!=checksum:raise SystemExit('PCM source changed; rebuild required')
if bool(build.get('arm1_rx_only'))!=args.i2s_arm1_rx_only:raise SystemExit('ARM1 RX only must be explicitly selected')
if bool(build.get('arm1_echo'))!=args.i2s_arm1_echo:raise SystemExit('ARM1 receive echo must be explicitly selected')
if args.i2s_arm1_echo:
 if build.get('arm1_idle_receipt_sha256')!=hashlib.sha256((BASE/'build'/('cs-full-voice-both-ports-signal'+('-rx-only' if args.i2s_arm1_rx_only else '')+'-live.json')).read_bytes()).hexdigest():raise SystemExit('ARM1 idle evidence changed')
if bool(build.get('arm_pcm_echo'))!=(args.i2s_arm_echo and not args.i2s_streaming_pcm):raise SystemExit('ARM PCM echo selection differs')
if args.i2s_public_pcm:
 idle_name=build.get('public_idle_receipt')
 if idle_name not in ('cs-public-pcm-live.json','cs-public-pcm-arm-slave-live.json'):raise SystemExit('Public PCM idle receipt required')
 if hashlib.sha256((BASE/'build'/idle_name).read_bytes()).hexdigest()!=build.get('public_idle_receipt_sha256'):raise SystemExit('Public PCM idle receipt changed; rebuild required')
if args.i2s_full_voice_open:
 idle_name=build.get('full_voice_idle_report')
 if idle_name not in ('cs-full-voice-open-live.json','cs-full-voice-open-arm-slave-live.json'):raise SystemExit('Full voice idle receipt basename required')
 if hashlib.sha256((BASE/'build'/idle_name).read_bytes()).hexdigest()!=build.get('full_voice_idle_report_sha256'):raise SystemExit('Full voice idle receipt changed; rebuild required')
if bool(build.get('dsp_frame_metadata'))!=args.dsp_frame_metadata:raise SystemExit('TCH buffer observation build must be explicitly selected')
if bool(build.get('dsp_speech_candidates'))!=args.dsp_speech_candidates:raise SystemExit('Unclassified TCH buffers must be explicitly selected')
if bool(build.get('dsp_pcm_metadata'))!=args.dsp_pcm_metadata:raise SystemExit('PCM window statistics must be explicitly selected')
if build.get('live_arm_allowed') is False:raise SystemExit('Quarantined diagnostic build: '+build.get('blocked_reason','offline audit required'))
if build.get('dsp_status') and (not before.get('csOnly') or before.get('imsReady') or before.get('csRegistration') not in (1,5) or before.get('epsRegistration') in (1,5)):
 raise SystemExit('DSP status observation requires registered GSM CS-only mode; no reads while LTE may gate the GSM block')
audit=audit_module(local)
if not audit['safe']:raise SystemExit('Unsafe direct Thumb call to ARM kernel export; refusing insmod')
if audit['module_sha256']=='2b0f3686d99a46cf8c7d35fdfd21a25340f03105a2f11ae3be7594343b981430':raise SystemExit('Known reboot-associated module remains quarantined')
if audit['module_sha256']=='e2ec138969a20ae4dfc13660c01d4869e89fe83c277b64c7a3f49d986520d7fe':raise SystemExit('MO29 reboot-associated module quarantined; cause not established')
if audit['module_sha256']=='a77aee22bcb2623e6e9c9d6ee7b81193d48b2d040f4bf798e760f719e1511eb2':raise SystemExit('MO32 reboot-associated module quarantined; audio shutdown under investigation')
if audit['module_sha256']=='c20295a9712e02f305d0c127a01556381225e468edb3751b3d933f002f266ae6':raise SystemExit('MO33 reboot-associated module quarantined; failed before shutdown test')
if audit['module_sha256']=='ed7944934af0a2f8942aa7822f4d2d0d347316c2c301872873fbda57676fe20e':raise SystemExit('MO34 reboot-associated module quarantined; PCM stop did not close hardware')
if audit['module_sha256']=='839d5fbebe9e14e5c1eea359df908fcf945e729b4b152acf15a07748dd1264a9':raise SystemExit('MO35 reboot-associated module quarantined; failed before connected timeout')
result={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'build':build,'before':before,'header_bytes':2 if args.headers or args.ring or args.connect_probe or args.mo or args.asc else 0,'ring_signaling':args.ring or args.connect_probe,'no_dial_or_answer':not (args.connect_probe or args.mo)}
result['independent_kernel_relocation_audit']=audit
if args.connect_probe:
 if not build.get('explicit_authorization_required') or build.get('connect_budget')!=1 or build.get('no_answer') is not False:raise SystemExit('Wrong diagnostic build')
 result.update(no_dial=True,connect_budget=1,user_authorization='Current ordinary SIM may be answered; human explicitly confirmed in this chat',native_guard_retained=True)
if args.mo:
 if (build.get('source')!='cs-mo-probe.c' or not build.get('outgoing_source_verified')
     or build.get('source_sha256')!=hashlib.sha256((BASE/'src/cs-mo-probe.c').read_bytes()).hexdigest()
     or b'call_budget=1 incoming_answer=0 audio=0' not in local.read_bytes() or b'connect_budget=1' in local.read_bytes()):
  raise SystemExit('Compiled outgoing-only source/artifact contract required before upload')
 if build.get('call_budget')!=1 or build.get('incoming_answer') is not False or build.get('audio') is not False:raise SystemExit('Wrong outgoing diagnostic build')
 if bool(build.get('network_dtmf_tone'))!=args.dtmf_tone:raise SystemExit('Network DTMF tone build must be explicitly selected')
 if bool(build.get('test_amr_injection'))!=args.amr_tone_candidate:raise SystemExit('Synthetic AMR injection build must be explicitly selected')
 if bool(build.get('test_dsp_audio_tone'))!=args.dsp_tone_candidate:raise SystemExit('Reference DSP audio build must be explicitly selected')
 result.update(call_budget=1,incoming_answer=False,arming_dials=False,user_authorization='Human explicitly authorized an outgoing test call to the supplied number in this chat; number excluded from report',native_guard_retained=True)
report_path=BASE/'build'/f'{OUTPUT}-armed.json'
def save():
 report_path.write_text(json.dumps(result,indent=2)+'\n')
 report_path.chmod(0o600)
result['stage']='validated';save()
try:
 result['stage']='uploading';save()
 ram_push(ADB,local,REMOTE)
 result['stage']='uploaded';save()
 result['insmod_response']=shell('insmod '+REMOTE+'; echo MF79U_INSMOD_EXIT=$?')
 result['stage']='insmod_returned';save()
 result['loaded']=loaded()
 result['messages']=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep '"+PREFIX+"' | tail -n 40").splitlines()
 starts=[i for i,line in enumerate(result['messages']) if 'armed seconds=' in line]
 if starts:result['messages']=result['messages'][starts[-1]:]
 if not result['loaded'] or 'MF79U_INSMOD_EXIT=0' not in result['insmod_response']:raise RuntimeError('Kernel observer did not arm')
 if not any('armed seconds=' in line for line in result['messages']):raise RuntimeError('Observer arming evidence absent')
 result['stage']='armed'
except Exception as exc:
 result['failure']=str(exc)
 raise
finally:
 try:
  shell('rm -f '+REMOTE)
  result['remote_file_removed']=shell('test ! -e '+REMOTE+' && echo CLEAN')=='CLEAN'
 except Exception as exc:result['cleanup_error']=str(exc)
 try:result.update(after=native(),same_boot=shell('cat /proc/sys/kernel/random/boot_id')==boot)
 except Exception as exc:result['postcheck_error']=str(exc)
 save()
 print(json.dumps(result,indent=2))
if not result['same_boot'] or before['pid']!=result['after']['pid'] or before['sipPid']!=result['after']['sipPid']:raise SystemExit('Runtime changed during arming')
