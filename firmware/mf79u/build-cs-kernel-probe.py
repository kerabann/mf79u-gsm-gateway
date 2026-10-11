#!/usr/bin/env python3
"""Recover exact B03 module metadata and build a header-free, read-only CP probe."""
from pathlib import Path
import struct,hashlib,subprocess,json,argparse,re
from b03_kernel_relocations import audit_module
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'firmware/mf79u';BUILD=BASE/'build'
CFG=ROOT/'work/zte/b03mod-extracted/lib/modules/3.4.110-rt140/kernel/drivers/cfg/cfg.ko'
parser=argparse.ArgumentParser(description=__doc__)
mode=parser.add_mutually_exclusive_group()
mode.add_argument('--watch',action='store_true')
mode.add_argument('--headers',action='store_true',help='CC AA45 metadata and two L3 header bytes only')
mode.add_argument('--routing',action='store_true',help='Read-only CC/ASC OSS route metadata')
mode.add_argument('--i2s-loop',action='store_true',help='Bounded reversible ARM I2S loop; no DSP/CC or SIM calls')
mode.add_argument('--i2s-dsp-loop',action='store_true',help='Bounded no-call ARM to DSP digital tone-loop diagnostic')
mode.add_argument('--i2s-preflight',action='store_true',help='Non-consuming B03 I2S control registers and clock rates')
mode.add_argument('--dsp-boot-watch',action='store_true',help='Passive bounded self-check caller observer; no new DSP commands or calls')
mode.add_argument('--module-layout',action='store_true',help='Read-only exact B03 module-loader metadata; no DSP or hooks')
mode.add_argument('--dsp-load-watch',action='store_true',help='Module notifier ABI preflight; no CP hook or DSP access by default')
mode.add_argument('--ring',action='store_true',help='Bounded TI0 incoming confirm/alert/release experiment, no CONNECT')
mode.add_argument('--sysfs',action='store_true',help='Verify live kernel sysfs attribute implementation; no CP IO')
mode.add_argument('--pcm-stream-loop',action='store_true',help='RAM-only binary PCM sysfs transport fixture; no CP or radio access')
mode.add_argument('--channels',action='store_true',help='Non-consuming bounded RPMSG cursor sampler')
mode.add_argument('--asc',action='store_true',help='Passive ASC dispatch/state and two-byte outgoing wire header observer')
mode.add_argument('--mo',action='store_true',help='Separate one-call outgoing signaling diagnostic; no audio/incoming answers')
mode.add_argument('--connect-probe',action='store_true',help='Offline build only: one incoming CONNECT; separate explicit permission needed to arm')
parser.add_argument('--instance',type=int,default=1,help='Distinct pinned observer instance (1..64)')
parser.add_argument('--seconds',type=int,default=600)
parser.add_argument('--connected-seconds',type=int,help='MO only: bounded connected-call timeout independent of PCM duration')
parser.add_argument('--mm-release-delay',type=int,default=0,choices=(0,2),help='MO diagnostic: defer MM release after queued RELEASE COMPLETE')
parser.add_argument('--tch-metadata',action='store_true',help='Read-only TCH scalars with checked Thumb kernel calls; experimental RAM sampler')
parser.add_argument('--dsp-status',action='store_true',help='Observe exact B03 DSP control halfwords and RX status, no frame bytes or writes')
parser.add_argument('--dsp-frame-metadata',action='store_true',help='Summarize changes in two exact TCH/CSD data buffers; no contents logged or DSP writes')
parser.add_argument('--dsp-speech-candidates',action='store_true',help='Extend read-only summaries to five adjacent exact-B03 buffers; classification unknown')
parser.add_argument('--dsp-pcm-metadata',action='store_true',help='Read-only periodicity statistics in exact pointer-bounded B03 SRAM; no sample bytes or PCM ownership claim')
parser.add_argument('--dtmf-tone',action='store_true',help='MO only: one bounded network DTMF tone; no PCM/DSP media')
parser.add_argument('--amr-tone-candidate',action='store_true',help='MO only: bounded synthetic AMR write to checked UL copier; speech format unverified')
parser.add_argument('--dsp-tone-candidate',action='store_true',help='Bounded reference DSP audio hypothesis for separate MO or one-answer MT probe')
parser.add_argument('--i2s-pcm-candidate',action='store_true',help='One-answer MT internal I2S PCM diagnostic; reversible peripheral setup')
parser.add_argument('--i2s-port-tone',action='store_true',help='With I2S PCM: DSP-only control then DSP tone plus ARM RX, connected call only')
parser.add_argument('--i2s-reference-open-clocks',action='store_true',help='Port diagnostic only: reset/release and gate all four clocks as actual reference Open')
parser.add_argument('--i2s-full-voice-open',action='store_true',help='Connected port diagnostic using complete voice API parameters already accepted in a restored idle test')
parser.add_argument('--i2s-arm-tone',action='store_true',help='Full voice MO: two-second DSP control, then ARM-only PCM tones')
parser.add_argument('--i2s-arm-echo',action='store_true',help='After two-second ARM tone, return received FIFO speech through bounded RAM for four seconds')
parser.add_argument('--i2s-both-ports',action='store_true',help='Idle full voice diagnostic reading both ARM FIFOs with actual startup profiles')
parser.add_argument('--i2s-rx-start',action='store_true',help='No-call comparison of initial and actual late voice-start ARM0 timing')
parser.add_argument('--i2s-rx-slots',action='store_true',help='No-call full-voice DSP tone with three reference mono/stereo selectors')
parser.add_argument('--i2s-public-pcm',action='store_true',help='One MO public PCM port test only after matching restored idle receipt')
parser.add_argument('--dsp-load-observe',action='store_true',help='With load-watch: opt-in passive initial CP self-check observer, before CP only')
parser.add_argument('--i2s-both-ports-signal',action='store_true',help='Tone on/off/on with bounded FIFO signal statistics')
parser.add_argument('--i2s-arm1-echo',action='store_true',help='Echo using physically observed ARM1 RX and verified ARM0 TX')
parser.add_argument('--i2s-arm1-rx-only',action='store_true',help='Enable ARM1 RX without its unused transmitter')
parser.add_argument('--i2s-arm1-tx-switch',action='store_true',help='Compare ARM0/ARM1 transmit then echo on ARM1')
parser.add_argument('--i2s-userspace-pcm',action='store_true',help='Bounded root-only PCM interface on the verified duplex ARM1 profile')
parser.add_argument('--i2s-streaming-pcm',action='store_true',help='No synthetic tones or media deadline; explicit call control still bounded')
args=parser.parse_args()
if args.i2s_streaming_pcm and not args.i2s_userspace_pcm:parser.error('Streaming mode requires userspace PCM')
if args.connected_seconds is not None and (not args.mo or not 8<=args.connected_seconds<=40):parser.error('Connected timeout requires MO and 8..40 seconds')
if args.mm_release_delay and not args.mo:parser.error('MM release delay requires MO')
if args.i2s_userspace_pcm and not (args.mo and args.i2s_arm1_tx_switch):parser.error('Userspace PCM requires the verified MO ARM1 duplex profile')
if args.i2s_arm1_tx_switch and not (args.i2s_arm1_rx_only and args.i2s_arm1_echo):parser.error('TX switch requires ARM1 RX-only echo control')
if args.i2s_arm1_rx_only and not (args.i2s_both_ports_signal or args.i2s_arm1_echo):parser.error('RX only requires signal test or ARM1 echo')
if args.i2s_arm1_echo and (not args.i2s_arm_echo or args.i2s_rx_start):parser.error('ARM1 echo requires a separate full voice echo diagnostic')
if args.i2s_both_ports_signal and not args.i2s_both_ports:parser.error('Signal metadata requires both port diagnostic')
if args.i2s_both_ports and (not args.i2s_dsp_loop or args.i2s_rx_start or args.i2s_rx_slots):raise SystemExit('Both ports requires a separate idle full voice test')
if args.i2s_rx_start and (not (args.i2s_dsp_loop or args.i2s_arm_echo) or args.i2s_rx_slots):raise SystemExit('RX start requires a separate idle or full voice echo test')
if args.i2s_rx_slots and not args.i2s_dsp_loop:raise SystemExit('RX slot comparison is no-call only')
if args.i2s_pcm_candidate and (not (args.connect_probe or args.mo) or args.dsp_tone_candidate):raise SystemExit('I2S PCM requires separate one-call probe')
if args.mo and args.i2s_pcm_candidate and not (args.i2s_public_pcm or args.i2s_arm_tone):raise SystemExit('MO I2S requires explicit public PCM or full voice ARM tone diagnostic')
if args.i2s_arm_tone and (not (args.mo and args.i2s_full_voice_open and args.i2s_port_tone) or args.i2s_public_pcm):raise SystemExit('ARM tone requires separate full voice MO port diagnostic')
if args.i2s_arm_echo and not args.i2s_arm_tone:raise SystemExit('ARM echo requires the explicit ARM tone diagnostic')
if args.i2s_public_pcm and not (args.mo and args.i2s_port_tone):raise SystemExit('Public PCM connected variant requires separate MO port-tone diagnostic')
if args.i2s_port_tone and not args.i2s_pcm_candidate:raise SystemExit('Port tone requires the I2S PCM MT probe')
if args.i2s_reference_open_clocks and not args.i2s_port_tone:raise SystemExit('Reference Open clocks require the connected port diagnostic')
if args.i2s_full_voice_open and not args.i2s_port_tone:raise SystemExit('Full voice API requires the connected port diagnostic')
if args.dsp_load_observe and not args.dsp_load_watch:raise SystemExit('Initial-load observer requires --dsp-load-watch')
if args.i2s_pcm_candidate or args.i2s_dsp_loop:
 parameter_name=re.search(r'^#define CS_I2S_PARAMETER_REPORT "(mf283u-(?:(?:i2s|afe|afe-slave(?:-voice-profile)?(?:-speech-mixer)?|pcm-slave)-duplex-parameters|idle-afe-tone-loop|voice(?:-master)?-port-tone-parameters|full-voice-open(?:-arm-slave)?-port-tone|public-pcm(?:-arm-slave)?)-emulation\.json)"$',(BUILD/'cs-i2s-parameters.h').read_text(),re.M)
 if not parameter_name:raise SystemExit('I2S parameter report basename missing')
 i2s_parameters=BUILD/parameter_name.group(1)
 i2s_parameter_sha=hashlib.sha256(i2s_parameters.read_bytes()).hexdigest()
 if 'public-pcm' in i2s_parameters.name:
  if not (args.i2s_dsp_loop or args.i2s_public_pcm):raise SystemExit('Public PCM route is limited to the bounded no-call diagnostic or explicit gated MO')
  public=json.loads(i2s_parameters.read_bytes())
  if (public.get('generator_sha256')!=hashlib.sha256((ROOT/'work/zte/voice/emulate-mf283u-public-pcm.py').read_bytes()).hexdigest()
      or public.get('source_sha256')!='49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
      or public.get('device_access') is not False or public.get('b03_compatibility_verified') is not False
      or not public.get('pcm_tail_active') or not public.get('pcm_profile_applied_after_public_refresh')):
   raise SystemExit('Exact offline public PCM trace required')
 elif 'full-voice-open' in i2s_parameters.name:
  if not (args.i2s_dsp_loop or args.i2s_full_voice_open):raise SystemExit('Full voice API parameters require an explicit diagnostic')
  full=json.loads(i2s_parameters.read_bytes())
  if (full.get('generator_sha256')!=hashlib.sha256((ROOT/'work/zte/voice/emulate-mf283u-voice-open.py').read_bytes()).hexdigest() or not full.get('pcm_tail_inactive') or full.get('b03_compatibility_verified') is not False):raise SystemExit('Full voice API trace changed or unverified provenance')
 elif args.i2s_full_voice_open:raise SystemExit('Full voice API parameter report required')
 if i2s_parameter_sha not in (BUILD/'cs-i2s-parameters.h').read_text():raise SystemExit('I2S parameter report/header mismatch')
 configuration_name=re.search(r'^#define CS_I2S_CONFIGURATION_REPORT "(mf283u-(?:i2s|pcm-i2s1|voice-inner(?:-slave)?(?:-init)?(?:-extra-cycle[01])?|public-pcm(?:-arm-slave)?)-configuration-emulation\.json)"$',(BUILD/'cs-i2s-parameters.h').read_text(),re.M)
 if not configuration_name:raise SystemExit('I2S configuration report basename missing')
 i2s_configuration=BUILD/configuration_name.group(1)
 i2s_configuration_sha=hashlib.sha256(i2s_configuration.read_bytes()).hexdigest()
 if i2s_configuration_sha not in (BUILD/'cs-i2s-parameters.h').read_text():raise SystemExit('I2S configuration report/header mismatch')
 clock_master=re.search(r'^#define CS_I2S_CLOCK_MASTER ([01])$',(BUILD/'cs-i2s-parameters.h').read_text(),re.M)
 if not clock_master or bool(int(clock_master.group(1)))!=json.loads(i2s_configuration.read_text()).get('arm_clock_master',True):raise SystemExit('I2S clock direction report/header mismatch; regenerate parameters')
 rate_match=re.search(r'#define CS_I2S_FIFO_RATE_HZ (8000)U',(BUILD/'cs-i2s-parameters.h').read_text())
 fifo_rate=int(rate_match.group(1)) if rate_match else 8000
 configuration_rate=int.from_bytes(bytes.fromhex(json.loads(i2s_configuration.read_text())['configuration_hex'])[8:12],'little')
 if fifo_rate!=configuration_rate:raise SystemExit('I2S rate report/header mismatch; regenerate parameters')
 if args.i2s_full_voice_open:
  idle_stem='cs-full-voice-open'+('-arm-slave' if not int(clock_master.group(1)) else '')
  idle_path=BUILD/(idle_stem+'-live.json');idle=json.loads(idle_path.read_bytes())
  idle_build=json.loads((BUILD/(idle_stem+'-build.json')).read_bytes())
  if (not all(idle.get(k) is True for k in ('runtime_restored','previous_configuration_restored','all_commands_negative_ack','no_sim_calls'))
      or idle.get('fifo_totals',{}).get('failed')!=0
      or idle.get('probe',{}).get('module_sha256')!=idle_build.get('sha256')
      or idle_build.get('i2s_parameter_report_sha256')!=i2s_parameter_sha
      or idle_build.get('i2s_configuration_report_sha256')!=i2s_configuration_sha):raise SystemExit('Matching restored idle test with all DSP ACKs required')
  full_idle_sha=hashlib.sha256(idle_path.read_bytes()).hexdigest()
 if args.i2s_public_pcm:
  if 'public-pcm' not in i2s_parameters.name:raise SystemExit('Public PCM report required')
  idle_stem='cs-public-pcm'+('-arm-slave' if not int(clock_master.group(1)) else '')
  idle_path=BUILD/(idle_stem+'-live.json');idle=json.loads(idle_path.read_bytes())
  idle_build=json.loads((BUILD/(idle_stem+'-build.json')).read_bytes())
  if (not all(idle.get(k) is True for k in ('runtime_restored','previous_configuration_restored','all_commands_negative_ack','no_sim_calls'))
      or idle.get('fifo_totals',{}).get('failed')!=0
      or idle.get('probe',{}).get('module_sha256')!=idle_build.get('sha256')
      or idle_build.get('i2s_parameter_report_sha256')!=i2s_parameter_sha
      or idle_build.get('i2s_configuration_report_sha256')!=i2s_configuration_sha):raise SystemExit('Matching restored public PCM idle test with all DSP ACKs required')
  public_idle_sha=hashlib.sha256(idle_path.read_bytes()).hexdigest()
 if args.i2s_port_tone and not (args.i2s_full_voice_open or args.i2s_public_pcm) and (i2s_parameters.name not in ('mf283u-voice-port-tone-parameters-emulation.json','mf283u-voice-master-port-tone-parameters-emulation.json') or not json.loads(i2s_parameters.read_text()).get('connected_port_tone_diagnostic')):raise SystemExit('Connected port-tone DSP report required')
 if not args.i2s_port_tone and 'port-tone' in i2s_parameters.name and not (args.i2s_dsp_loop and 'full-voice-open' in i2s_parameters.name):raise SystemExit('Port tone header requires explicit diagnostic flag')
 if '-extra-cycle' in i2s_configuration.name and not args.i2s_dsp_loop:
  raise SystemExit('Extra-cycle alternative is limited to a no-call DSP loop probe')
if args.dtmf_tone and not args.mo:raise SystemExit('Network DTMF tone only applies to the MO diagnostic')
if args.amr_tone_candidate and (not args.mo or args.dtmf_tone):raise SystemExit('AMR candidate requires separate MO build without network DTMF')
if args.dsp_tone_candidate and (not (args.mo or args.connect_probe) or args.dtmf_tone or args.amr_tone_candidate):raise SystemExit('DSP tone requires a separate MO or one-answer MT build')
if args.dsp_tone_candidate or args.i2s_port_tone:
 parameter_header=(BUILD/'cs-dsp-audio-parameters.h').read_text()
 parameter_name=re.search(r'^#define CS_AUDIO_PARAMETER_REPORT "(mf283u-tone-uplink(?:-volume\d{1,3}-amplitude\d{1,4})?-emulation\.json)"$',parameter_header,re.M)
 if not parameter_name:raise SystemExit('Audio parameter report basename missing')
 parameters=BUILD/parameter_name.group(1)
 expected=hashlib.sha256(parameters.read_bytes()).hexdigest()
 if expected not in parameter_header:raise SystemExit('Audio parameter report/header mismatch')
if args.amr_tone_candidate:
 frames=json.loads((BUILD/'cs-tone-frames-verification.json').read_text())
 if not frames.get('verified') or frames['header_sha256']!=hashlib.sha256((BUILD/'cs-tone-frames.h').read_bytes()).hexdigest():raise SystemExit('Verified synthetic tone frames required')
if args.tch_metadata and not args.channels:raise SystemExit('TCH metadata only applies to channels')
if args.dsp_status and not args.tch_metadata:raise SystemExit('DSP status requires the checked TCH layout sampler')
if args.dsp_frame_metadata and not args.dsp_status:raise SystemExit('DSP frame metadata requires the checked DSP status layout')
if args.dsp_speech_candidates and not args.dsp_frame_metadata:raise SystemExit('DSP speech candidates require frame summaries and exact DSP layout')
if args.dsp_pcm_metadata:
 if not args.dsp_status:raise SystemExit('PCM window statistics require checked GSM DSP/TCH layout')
 pcm_window_path=BUILD/'b03-dsp-pcm-windows.json';pcm_windows=json.loads(pcm_window_path.read_bytes())
 pcm_window_sha=hashlib.sha256(pcm_window_path.read_bytes()).hexdigest()
 if (pcm_windows.get('generator_sha256')!=hashlib.sha256((ROOT/'work/zte/voice/prepare-b03-pcm-windows.py').read_bytes()).hexdigest()
     or pcm_windows.get('source_sha256')!='ab0f783acee6ac13833e8f8fac1ee8cf79f5ae5b8ba18f941b03155cd8cdd261'
     or pcm_windows.get('device_access') is not False or pcm_windows.get('pcm_classification_verified') is not False
     or pcm_window_sha not in (BUILD/'cs-dsp-pcm-windows.h').read_text()):raise SystemExit('Exact hash-bound offline B03 windows required')
if not 15<=args.seconds<=900:raise SystemExit('Watch duration must be15..900 seconds')
if not 1<=args.instance<=64 or (args.instance!=1 and not (args.headers or args.ring or args.connect_probe or args.asc or args.mo)):raise SystemExit('Instance2..64 is for pinned observers only')
observer=args.watch or args.headers or args.ring or args.connect_probe
suffix=str(args.instance) if args.instance!=1 else ''
name='mf79u_cs_ring'+suffix if args.ring else ('mf79u_cs_header'+suffix if args.headers else ('mf79u_cs_watch' if args.watch else ('mf79u_cs_route' if args.routing else ('mf79u_cs_sysfs' if args.sysfs else ('mf79u_cs_channels' if args.channels else 'mf79u_cs_probe')))))
if args.connect_probe:name='mf79u_cs_connect'+suffix
if args.asc:name='mf79u_cs_asc'+suffix
if args.mo:name='mf79u_cs_mo'+suffix
source='cs-kernel-watch' if observer else ('cs-route-probe' if args.routing else ('cs-sysfs-probe' if args.sysfs else ('cs-channel-watch' if args.channels else 'cs-kernel-probe')))
if args.asc:source='cs-asc-watch'
if args.mo:source='cs-mo-probe'
if args.i2s_preflight:name='mf79u_cs_i2s';source='cs-i2s-preflight'
if args.dsp_boot_watch:name='mf79u_cs_dsp_boot';source='cs-dsp-boot-watch'
if args.module_layout:name='mf79u_cs_module_layout';source='cs-module-layout-probe'
if args.dsp_load_watch:name='mf79u_cs_dsp_load';source='cs-dsp-load-watch'
if args.i2s_loop:name='mf79u_cs_i2s_loop';source='cs-i2s-loop-probe'
if args.i2s_dsp_loop:name='mf79u_cs_i2s_dsp_loop';source='cs-i2s-dsp-loop-probe'
if args.pcm_stream_loop:name='mf79u_pcm_loop';source='cs-pcm-loop-probe'
if args.connect_probe and args.dsp_tone_candidate:source='cs-mt-tone-probe'
if args.i2s_pcm_candidate and args.connect_probe:source='cs-mt-tone-probe'
if args.mo and source!='cs-mo-probe':raise SystemExit('MO must compile its outgoing-only source')
output='cs-kernel-ring'+suffix if args.ring else ('cs-kernel-header'+suffix if args.headers else source)
if args.connect_probe:output='cs-connect-probe'+suffix
if args.asc:output='cs-asc-watch'+suffix
if args.mo:output='cs-mo-probe'+suffix
if args.i2s_preflight or args.i2s_loop or args.i2s_dsp_loop:output=source
padding=188-12-len(name)-1
SHA='75b4308591cf6a3ed9ab423bb158c86da6e131dff6ef79ac75bc8d7f0178b1f5'
data=CFG.read_bytes()
if hashlib.sha256(data).hexdigest()!=SHA:raise SystemExit('Unrecognized B03 module ABI')
# Bounded ELF32 parsing; the vendor module supplies authoritative layout.
if data[:7]!=b'\x7fELF\x01\x01\x01' or struct.unpack_from('<H',data,18)[0]!=40:raise SystemExit('Not ARM32 ELF')
shoff=struct.unpack_from('<I',data,32)[0];shentsize,count,names=struct.unpack_from('<HHH',data,46)
if shentsize!=40 or count>100:raise SystemExit('Unexpected section layout')
headers=[struct.unpack_from('<10I',data,shoff+i*40) for i in range(count)]
nh=headers[names];pool=data[nh[4]:nh[4]+nh[5]]
sections={pool[h[0]:].split(b'\0',1)[0].decode():h for h in headers}
def section(name):
 h=sections[name];return data[h[4]:h[4]+h[5]]
module=section('.gnu.linkonce.this_module');info=section('.modinfo');symbols=sections['.symtab'];strings=section('.strtab')
entries=section('.rel.gnu.linkonce.this_module');relocs={}
for i in range(0,len(entries),8):
 offset,rel=struct.unpack_from('<II',entries,i)
 if rel&255!=2:raise SystemExit('Unexpected module relocation')
 symbol_name=struct.unpack_from('<I',data,symbols[4]+(rel>>8)*16)[0]
 relocs[strings[symbol_name:].split(b'\0',1)[0].decode()]=offset
if len(module)!=328 or module[12:16]!=b'cfg\0' or relocs!={'init_module':188,'cleanup_module':320}:
 raise SystemExit('Unexpected module layout')
if module[:12]+module[16:]!=bytes(324):raise SystemExit('Unexpected nonzero module metadata')
vermagic='3.4.110-rt140 preempt mod_unload ARMv7 thumb2 '
if ('vermagic='+vermagic).encode()+b'\0' not in info or '__versions' in sections:raise SystemExit('Unexpected version ABI')
assembly='''/* Generated from checksum-verified B03 cfg.ko metadata; all other fields zero. */
.section .gnu.linkonce.this_module,"aw",%progbits
.balign 4
.global __this_module
.type __this_module,%object
__this_module:
.zero 12
.asciz "'''+name+'''"
.zero '''+str(padding)+'''
.word init_module
.zero 128
.word cleanup_module
.zero 4
.size __this_module, .-__this_module
.section .modinfo,"a",%progbits
.asciz "license=GPL"
.asciz "depends="
.asciz "vermagic='''+vermagic+'''"
.section .note.GNU-stack,"",%progbits
'''
# 12 + len(name)+NUL + padding must equal recovered init offset188.
if 12+len(name)+1+padding!=188:raise SystemExit('Metadata assembly alignment error')
(BUILD/(source+'-meta.S')).write_text(assembly)
command='''arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-pic -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables -march=armv7-a -mthumb -mfloat-abi=soft -c firmware/mf79u/src/cs-kernel-probe.c -o firmware/mf79u/build/cs-kernel-probe.o
arm-linux-gnueabi-gcc -march=armv7-a -mthumb -mfloat-abi=soft -c firmware/mf79u/build/cs-kernel-probe-meta.S -o firmware/mf79u/build/cs-kernel-probe-meta.o
arm-linux-gnueabi-ld -r firmware/mf79u/build/cs-kernel-probe.o firmware/mf79u/build/cs-kernel-probe-meta.o -o firmware/mf79u/build/mf79u_cs_probe.ko'''
command=command.replace('cs-kernel-probe',source).replace('mf79u_cs_probe',name)
if observer:command=command.replace('-ffreestanding','-ffreestanding -DCS_WATCH_SECONDS='+str(args.seconds)+(' -DCS_WATCH_HEADERS=1' if args.headers or args.ring or args.connect_probe else '')+(' -DCS_WATCH_RING=1' if args.ring or args.connect_probe else '')+(' -DCS_WATCH_CONNECT_PROBE=1' if args.connect_probe else ''))
if args.channels:command=command.replace('-ffreestanding','-ffreestanding -DCS_WATCH_SECONDS='+str(args.seconds))
if args.asc or args.mo or args.dsp_boot_watch:command=command.replace('-ffreestanding','-ffreestanding -DCS_WATCH_SECONDS='+str(args.seconds))
if args.connected_seconds is not None:command=command.replace('-ffreestanding','-ffreestanding -DCS_MO_CONNECTED_SECONDS='+str(args.connected_seconds))
if args.mm_release_delay:command=command.replace('-ffreestanding','-ffreestanding -DCS_MO_MM_RELEASE_DELAY_SECONDS='+str(args.mm_release_delay))
if args.dsp_load_observe:command=command.replace('-ffreestanding','-ffreestanding -DCS_DSP_LOAD_OBSERVE=1 -DCS_WATCH_SECONDS='+str(args.seconds))
if args.i2s_rx_start or args.i2s_both_ports or args.i2s_arm1_echo:
 start_path=BUILD/'mf283u-full-voice-start-config-audit.json';start=json.loads(start_path.read_bytes())
 if (start.get('device_access') is not False or not start.get('simulated_start_completed')
     or start.get('audit_generator_sha256')!=hashlib.sha256((ROOT/'work/zte/voice/emulate-mf283u-voice-start-audit.py').read_bytes()).hexdigest()
     or start.get('startup_generator_sha256')!=hashlib.sha256((ROOT/'work/zte/voice/emulate-mf283u-voice-start.py').read_bytes()).hexdigest()
     or start.get('source_sha256')!='49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
     or 'full-voice-open-port-tone' not in i2s_parameters.name):raise SystemExit('Exact startup trace and full voice required')
 for address,value in [('0x1405008',0x01ff2005),('0x1400058',0x00400019),('0x140005c',0x00010019)]:
  if int(start['final_registers'][address],0)!=value:raise SystemExit('Late ARM0 startup register differs')
 if args.i2s_both_ports or args.i2s_arm1_echo:
  for address,value in [('0x1406008',0x01ef2001),('0x1400060',0x00200019),('0x1400064',0x00010032),('0x1406004',7),('0x1405004',7)]:
   if int(start['final_registers'][address],0)!=value:raise SystemExit('Two port startup register differs')
  if args.i2s_both_ports:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_BOTH_PORTS_TEST=1')
 elif args.i2s_arm_echo:
  late_idle_path=BUILD/'cs-full-voice-rx-start-live.json';late_idle=json.loads(late_idle_path.read_bytes())
  if (not all(late_idle.get(k) is True for k in ('runtime_restored','all_commands_negative_ack','no_sim_calls','rx_start_comparison')) or late_idle.get('fifo_totals',{}).get('failed')!=0):raise SystemExit('Restored late-profile idle test required')
  command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_CONNECTED_RX_START_TEST=1')
 else:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_RX_START_TEST=1')
if args.i2s_arm1_echo:
 arm1_path=BUILD/('cs-full-voice-both-ports-signal'+('-rx-only' if args.i2s_arm1_rx_only else '')+'-live.json');arm1=json.loads(arm1_path.read_bytes())
 if (not all(arm1.get(k) is True for k in ('runtime_restored','both_ports_signal','all_commands_negative_ack','no_sim_calls')) or not arm1.get('arm1_tone_signal_verified')):raise SystemExit('Verified ARM1 tone on/off/on and full restoration required')
 command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_ARM1_ECHO_TEST=1')
if args.i2s_arm1_tx_switch:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_ARM1_TX_SWITCH=1')
if args.i2s_userspace_pcm:
 duplex_path=BUILD/'cs-mo26-full-voice-arm-echo-arm1-rx-only-tx-switch-test.json';duplex=json.loads(duplex_path.read_bytes())
 transport_path=BUILD/'cs-pcm-transport-live.json';transport=json.loads(transport_path.read_bytes())
 if not all(duplex.get(k) is True for k in ('runtime_restored','heard_speech_echo','physical_duplex_verified')):raise SystemExit('Restored physically verified ARM1 duplex required')
 if not all(transport.get(k) is True for k in ('unloaded','object_removed','runtime_unchanged')) or not transport.get('result',{}).get('passed'):raise SystemExit('Verified binary PCM transport required')
 command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_USERSPACE_PCM=1')
if args.i2s_streaming_pcm:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_STREAMING_PCM=1')
if args.i2s_arm1_rx_only:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_ARM1_RX_ONLY=1')
if args.i2s_both_ports_signal:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_BOTH_PORTS_SIGNAL_TEST=1')
if args.i2s_rx_slots:
 slot_path=BUILD/'mf283u-rx-slots-emulation.json';slot=json.loads(slot_path.read_bytes())
 if (slot.get('device_access') is not False or slot.get('source_sha256')!='49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
     or slot.get('generator_sha256')!=hashlib.sha256((ROOT/'work/zte/voice/emulate-mf283u-rx-slots.py').read_bytes()).hexdigest()
     or slot.get('baseline_generator_sha256')!=hashlib.sha256((ROOT/'work/zte/voice/emulate-mf283u-i2s.py').read_bytes()).hexdigest()
     or 'full-voice-open-port-tone' not in i2s_parameters.name):raise SystemExit('Exact full voice and RX slot provenance required')
 for case,timing in zip(slot['cases'],[0x01ef2001,0x01ef4001,0x01ef6101],strict=True):
  regs=case['registers']
  if any(int(regs[a],0)!=v for a,v in [('0x1405008',timing),('0x140060',0xa9),('0x1400058',0x200019),('0x140005c',0x10032)]):raise SystemExit('Reference RX slot registers differ')
 command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_RX_SLOT_TEST=1')
if args.tch_metadata:command=command.replace('-ffreestanding','-ffreestanding -DCS_WATCH_TCH_METADATA=1')
if args.dsp_status:command=command.replace('-ffreestanding','-ffreestanding -DCS_WATCH_DSP_STATUS=1')
if args.dsp_frame_metadata:command=command.replace('-ffreestanding','-ffreestanding -DCS_WATCH_DSP_FRAME_METADATA=1')
if args.dsp_speech_candidates:command=command.replace('-ffreestanding','-ffreestanding -DCS_WATCH_DSP_SPEECH_CANDIDATES=1')
if args.dsp_pcm_metadata:command=command.replace('-ffreestanding','-ffreestanding -DCS_WATCH_DSP_PCM_METADATA=1')
if args.dtmf_tone:command=command.replace('-ffreestanding','-ffreestanding -DCS_MO_DTMF_TONE=1')
if args.amr_tone_candidate:command=command.replace('-ffreestanding','-ffreestanding -DCS_MO_AMR_TONE_CANDIDATE=1')
if args.dsp_tone_candidate:command=command.replace('-ffreestanding','-ffreestanding -DCS_MO_DSP_TONE_CANDIDATE=1')
if args.i2s_pcm_candidate:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_PCM_TEST=1')
if args.i2s_port_tone:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_PORT_TONE_TEST=1')
if args.i2s_arm_tone:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_ARM_TONE_TEST=1')
if args.i2s_arm_echo:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_ARM_ECHO_TEST=1')
if args.i2s_reference_open_clocks:command=command.replace('-ffreestanding','-ffreestanding -DCS_I2S_REFERENCE_OPEN_CLOCKS=1')
subprocess.run(['docker','run','--rm','-v',str(ROOT)+':/work','-w','/work','mf79u-build-tools:local','sh','-eu','-c',command],check=True)
p=BUILD/(name+'.ko')
audit=audit_module(p)
if args.mo and (b'call_budget=1 incoming_answer=0 audio=0' not in p.read_bytes() or b'connect_budget=1' in p.read_bytes()):
 raise SystemExit('Compiled MO artifact does not implement the outgoing-only contract')
r={'cfg_sha256':SHA,'vermagic':vermagic,'module_bytes':328,'name_offset':12,'init_offset':188,'exit_offset':320,'modversions':False,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'readonly':not observer}
r.update(source=source+'.c',source_sha256=hashlib.sha256((BASE/'src'/(source+'.c')).read_bytes()).hexdigest())
r.update(kernel_relocation_audit=audit,live_arm_allowed=audit['safe'])
if args.pcm_stream_loop:r.update(no_calls=True,no_cp_io=True,unloadable=True,pcm_stream_loop=True,source_headers_sha256={n:hashlib.sha256((BASE/'src'/n).read_bytes()).hexdigest() for n in ('cs-kernel-status.h','cs-pcm-stream.h','cs-pcm-ring.h','cs-pcm-spsc.h')})
if args.i2s_pcm_candidate or args.i2s_dsp_loop:r['i2s_source_headers_sha256']={n:hashlib.sha256((BASE/'src'/n).read_bytes()).hexdigest() for n in ('cs-i2s-pcm-candidate.h','cs-dsp-mailbox.h')}
if observer:r.update(seconds=args.seconds,hook='CC task callback, original chained unchanged',pinned_until_reboot=True,header_bytes=2 if args.headers or args.ring else 0,ring_signaling=args.ring)
if args.connect_probe:r.update(header_bytes=2,ring_signaling=True,no_dial=True,no_answer=False,connect_budget=1,explicit_authorization_required=True,production_voice_backend=False)
if args.connect_probe and args.dsp_tone_candidate:r.update(incoming_tone_probe=True,connected_requires_network_ack=True,auto_hangup_seconds=10,verified_mm_clearing_before_restore=True)
if args.channels:r.update(seconds=args.seconds,interval_ms=20,payload_read=False,cursor_writes=False,unloadable=True)
if args.tch_metadata:r.update(tch_metadata=True,metadata_revision=4,logging_max_lines_per_50_samples=3 if args.dsp_status else 2)
if args.dsp_status:r.update(dsp_status=True,dsp_halfword_reads=8,dsp_pointer_layout_verified=True,dsp_writes=False,frame_bytes_read=False)
if args.dsp_pcm_metadata:r.update(dsp_pcm_metadata=True,pcm_window_report=pcm_window_path.name,pcm_window_report_sha256=pcm_window_sha,pcm_sample_bytes_logged=False,pcm_hash_logged=False,pcm_ownership_verified=False,pcm_halfwords_per_tick=sum(w['halfwords'] for w in pcm_windows['windows']),pcm_window_count=len(pcm_windows['windows']))
if args.dsp_frame_metadata:r.update(dsp_frame_metadata=True,frame_bytes_read=True,frame_contents_logged=False,frame_hash_logged=False,tch_buffer_bytes_per_sample=46,tch_buffer_directions=2,frame_ownership_verified=False,logging_max_lines_per_50_samples=5)
if args.dsp_speech_candidates:r.update(dsp_speech_candidates=True,tch_buffer_ranges=[['0xfad01348',46],['0xfad01318',48],['0xfad01376',46],['0xfad013a4',48],['0xfad013d4',48],['0xfad01404',48],['0xfad01434',54]],tch_buffer_directions=7,logging_max_lines_per_50_samples=10)
if args.asc:r.update(seconds=args.seconds,readonly=False,hook='ASC task callback, original chained unchanged',pinned_until_reboot=True,header_bytes=2,clearing_prefix_max_bytes=7,no_sends=True,no_dial_or_answer=True,asc_context_scalar_offsets=[0,1,6,8])
if args.mo:r.update(seconds=args.seconds,readonly=False,hook='CC callback and normal-voice admission data literal',pinned_until_reboot=True,call_budget=1,incoming_answer=False,audio=False,number_storage='RAM only',explicit_dial_authorization_required=True,production_voice_backend=False,outgoing_source_verified=True)
if args.mo:r.update(connected_seconds=args.connected_seconds if args.connected_seconds is not None else 28 if args.i2s_userspace_pcm else 10,timeout_trace_version=1,mm_release_delay_seconds=args.mm_release_delay)
if args.mo:
 nsd_path=BUILD/'cs-nsd-b03-offline.json';nsd=json.loads(nsd_path.read_text())
 if not nsd.get('passed') or nsd.get('device_access') is not False or len(nsd.get('cases',[]))!=8:raise SystemExit('Exact B03 N(SD) offline verification required')
 r.update(nsd_allocator='vendor_bf29be71',nsd_context_guard=True,nsd_fixture_sha256=hashlib.sha256(nsd_path.read_bytes()).hexdigest())
if args.dtmf_tone:r.update(network_dtmf_tone=True,dtmf_tone_seconds=2,dsp_writes=False,pcm_audio=False)
if args.amr_tone_candidate:r.update(test_amr_injection=True,dsp_writes=True,control_writes=False,amr_tone_budget_frames=300,ul_writer='0xbf3f5115',ul_buffer='0xfad01348',ul_bytes=46,speech_format_verified=False,tone_frames_sha256=frames['header_sha256'])
if args.dsp_tone_candidate:r.update(test_dsp_audio_tone=True,dsp_writes=True,audio_mailbox='0xfad0107a',tone_parameters='0xfad011b0',tone_seconds=6,monotonic_deadlines=True,dsp_compatibility_verified=False,audio_parameter_report=parameters.name,audio_parameter_report_sha256=expected,tone_mixer_resource=1,dsp_program_patch=False,pcm_peripheral_writes=False)
if args.i2s_pcm_candidate:r.update(test_i2s_pcm=True,dsp_writes=True,pcm_peripheral_writes=True,dsp_program_patch=False,pcm_rate=8000,external_pcm_rate=16000,internal_loop='0xf8440060',i2s0='0xf8a05000',test_seconds=6,production_voice_backend=False,i2s_parameter_report=i2s_parameters.name,i2s_parameter_report_sha256=i2s_parameter_sha)
if args.i2s_port_tone:r.update(connected_port_tone=True,dsp_only_control_seconds=2,arm_tx_silence=True,tone_duration_raw=16000,tone_refresh_seconds=2,audio_parameter_report=parameters.name,audio_parameter_report_sha256=expected)
if args.i2s_arm_tone:r.update(arm_pcm_tone=True,arm_tx_silence=False,dsp_tone_stopped_before_pcm=True,tone_refresh_seconds=None,arm_tone_frequencies_hz=[500,1000,1500],control_readback=True)
if args.i2s_rx_start:r.update(rx_start_comparison=True,rx_start_report=start_path.name,rx_start_report_sha256=hashlib.sha256(start_path.read_bytes()).hexdigest(),no_sim_calls=args.i2s_dsp_loop)
if args.i2s_rx_start and args.i2s_arm_echo:r.update(late_idle_receipt=late_idle_path.name,late_idle_receipt_sha256=hashlib.sha256(late_idle_path.read_bytes()).hexdigest())
if args.i2s_both_ports_signal:r.update(both_ports_signal=True,tone_phases=['on','off','on'],sample_bytes_logged=False)
if args.i2s_both_ports:r.update(both_ports=True,startup_report=start_path.name,startup_report_sha256=hashlib.sha256(start_path.read_bytes()).hexdigest(),clock_indices=[29,31,30,32],arm1_must_be_idle=True,arm1_control_divider_restore=True,no_sim_calls=True,arm_tx_silence=True)
if args.i2s_rx_slots:r.update(rx_slot_comparison=True,rx_slot_report=slot_path.name,rx_slot_report_sha256=hashlib.sha256(slot_path.read_bytes()).hexdigest(),no_sim_calls=True,arm_tx_silence=True)
if args.i2s_arm1_rx_only:r.update(arm1_rx_only=True,arm1_tx_words=0,arm1_process=6)
if args.i2s_arm1_echo:r.update(arm1_echo=True,arm1_idle_receipt=arm1_path.name,arm1_idle_receipt_sha256=hashlib.sha256(arm1_path.read_bytes()).hexdigest(),tx_port=0,rx_port=1,startup_report_sha256=hashlib.sha256(start_path.read_bytes()).hexdigest())
if args.i2s_arm_echo:r.update(arm_pcm_echo=True,arm_tone_frequencies_hz=[500],arm_tone_seconds=2,echo_seconds=4,echo_delay_samples=640,echo_capacity_samples=1024,speech_saved=False)
if args.i2s_arm1_rx_only and args.i2s_arm1_echo:r['arm_tone_frequencies_hz']=[500,1500]
if args.i2s_arm1_tx_switch:r.update(arm1_tx_switch=True,arm1_tx_words=None,arm1_process=[6,7],tx_port=[0,1],echo_tx_port=1,tx_switch_after_seconds=1)
if args.i2s_userspace_pcm:r.update(userspace_pcm=True,hardware_close_after_mm_idle=True,userspace_pcm_seconds=20,echo_seconds=0,external_pcm_samples=320,pcm_headers_sha256={n:hashlib.sha256((BASE/'src'/n).read_bytes()).hexdigest() for n in ('cs-pcm-ring.h','cs-pcm-stream.h','cs-kernel-status.h','cs-pcm-spsc.h')},duplex_receipt_sha256=hashlib.sha256(duplex_path.read_bytes()).hexdigest(),transport_receipt_sha256=hashlib.sha256(transport_path.read_bytes()).hexdigest())
if args.i2s_streaming_pcm:
 # Legacy selection flags reuse the verified voice bootstrap and ARM1 path;
 # report the actual streaming behavior, not the excluded diagnostic phases.
 r.update(streaming_pcm=True,synthetic_tones=False,test_seconds=None,
          userspace_pcm_seconds=None,connected_port_tone=False,
          dsp_only_control_seconds=0,tone_duration_raw=None,tone_refresh_seconds=None,
          arm_pcm_tone=False,dsp_tone_stopped_before_pcm=False,
          arm_tone_seconds=0,arm_tone_frequencies_hz=[],tx_switch_after_seconds=0,
          arm_pcm_echo=False,echo_seconds=0,echo_delay_samples=0,echo_capacity_samples=0)
if args.i2s_public_pcm:r.update(public_pcm_route=True,public_idle_receipt=idle_path.name,public_idle_receipt_sha256=public_idle_sha)
if args.i2s_reference_open_clocks:r.update(reference_open_clocks=True,clock_indices=[29,31,30,32],reference_open='0x24780310',reference_reset_release='0x24780394..0x247803d0',reference_gate='0x247803dc..0x24780438',arm1_must_be_idle=True,arm1_fifo_data_used=False,arm1_control_restore=True)
if args.i2s_full_voice_open:r.update(full_reference_voice_api=True,full_voice_idle_report=idle_path.name,full_voice_idle_report_sha256=full_idle_sha,pcm_tail_inactive=True,reference_afe_route_only=True)
if args.dsp_boot_watch:r.update(readonly=False,seconds=args.seconds,hook='self-check caller literal 0xbf3e9b98',original='0xbf3ea119',original_chained=True,pinned_until_reboot=True,new_dsp_commands=False,dsp_program_patch=False,no_sim_calls=True,host_parameter_halfwords=5,parameter_semantics_verified=False)
if args.dsp_load_watch:r.update(readonly=not args.dsp_load_observe,module_notifier=True,notifications_only=not args.dsp_load_observe,dynamic_cp_base=True,no_sim_calls=True,new_dsp_commands=False,dsp_program_patch=False,pinned_until_reboot=args.dsp_load_observe)
if args.dsp_load_observe:r.update(seconds=args.seconds,original_chained=True,hook='verified CP core plus self-check caller offset 0x3e9b98',parameter_semantics_verified=False,host_parameter_halfwords=17,live_arm_allowed=False,blocked_reason='Initial-load method quarantined: loading before CP changes its base without full relocation compatibility proof')
if args.i2s_loop:r.update(readonly=False,pcm_peripheral_writes=True,no_calls=True,no_dsp_commands=True,reversible_bounded_init=True)
if args.i2s_pcm_candidate or args.i2s_dsp_loop:r.update(i2s_configuration_report=i2s_configuration.name,i2s_configuration_report_sha256=i2s_configuration_sha,pcm_rate=fifo_rate,external_pcm_rate=16000)
if args.i2s_dsp_loop:r.update(readonly=False,pcm_peripheral_writes=True,dsp_writes=True,no_calls=True,no_cc_hooks=True,dsp_program_patch=False,reversible_bounded_init=True,i2s_parameter_report=i2s_parameters.name,i2s_parameter_report_sha256=i2s_parameter_sha)
if not audit['safe']:r['blocked_reason']='Unsafe direct Thumb call to ARM kernel export'
(BUILD/(output+'-build.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
if not audit['safe']:raise SystemExit('Unsafe kernel relocation: build quarantined, live loading prohibited')
