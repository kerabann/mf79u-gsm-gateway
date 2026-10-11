#!/usr/bin/env python3
"""Bind opt-in I2S DSP parameters to the hash-pinned offline reference report."""
from pathlib import Path
import hashlib,json,argparse
parser=argparse.ArgumentParser()
mode=parser.add_mutually_exclusive_group()
mode.add_argument("--afe",action="store_true")
mode.add_argument("--pcm-teak-i2s1",action="store_true")
mode.add_argument("--afe-slave",action="store_true")
mode.add_argument("--afe-master",action="store_true")
mode.add_argument("--idle-tone-loop",action="store_true")
parser.add_argument("--driver-init",action="store_true")
parser.add_argument("--speech-mixer",action="store_true")
parser.add_argument("--voice-profile",action="store_true")
parser.add_argument("--port-tone",action="store_true")
parser.add_argument("--tdm-extra-cycle",type=int,choices=(0,1),default=None)
args=parser.parse_args()
if args.driver_init and not (args.afe_slave or args.afe_master or args.idle_tone_loop):
    parser.error('--driver-init requires --afe-slave or --idle-tone-loop')
if args.speech_mixer and not (args.afe_slave or args.afe_master):
    parser.error('--speech-mixer requires --afe-slave')
if args.voice_profile and not ((args.afe_slave or args.afe_master) and args.speech_mixer and args.driver_init):
    parser.error('--voice-profile requires --afe-slave --speech-mixer --driver-init')
if args.port_tone and not args.voice_profile:parser.error('--port-tone requires --voice-profile')
if args.afe_master and not args.port_tone:parser.error('--afe-master is limited to the connected port diagnostic')
if args.tdm_extra_cycle==0 and not (args.idle_tone_loop and args.driver_init):
    parser.error('Extra-cycle alternative is limited to the no-call idle tone-loop diagnostic')
afe=args.afe or args.afe_slave or args.afe_master or args.idle_tone_loop
base=Path(__file__).resolve().parent/'build'
path=base/('mf283u-voice-master-port-tone-parameters-emulation.json' if args.afe_master else 'mf283u-voice-port-tone-parameters-emulation.json' if args.port_tone else 'mf283u-afe-slave-voice-profile-speech-mixer-duplex-parameters-emulation.json' if args.voice_profile else 'mf283u-afe-slave-speech-mixer-duplex-parameters-emulation.json' if args.speech_mixer else 'mf283u-idle-afe-tone-loop-emulation.json' if args.idle_tone_loop else 'mf283u-afe-slave-duplex-parameters-emulation.json' if args.afe_slave else 'mf283u-pcm-slave-duplex-parameters-emulation.json' if args.pcm_teak_i2s1 else 'mf283u-afe-duplex-parameters-emulation.json' if args.afe else 'mf283u-i2s-duplex-parameters-emulation.json')
r=json.loads(path.read_text())
if (r.get('reference_sha256')!='49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
    or r.get('device_access') is not False or r.get('hardware_calls_executed') is not False
    or r.get('uplink_paths')!=([0,15] if afe else [2,15]) or r.get('downlink_paths')!=([0] if afe else [4])):
    raise SystemExit('Hash-pinned offline duplex route required')
commands=r['dsp_commands'][-7:]+[r['audio_disable_command']]
if [(c['command'],c['total_halfwords']) for c in commands]!=[
    ('0x10',12),('0x10',12),('0x19',8),('0x11',23),('0x17',13),('0x18',2),('0xf',28),('0xf',28)]:
    raise SystemExit('Unexpected DSP command sequence')
if commands[-2]['payload'][0]!=(2 if afe else 3) or commands[-1]['payload'][0]!=0:
    raise SystemExit('Expected duplex start and idle stop')
if args.pcm_teak_i2s1 and (r.get('pcm_configuration_index')!=1 or r.get('dsp_pcm_clock_slave') is not True):
    raise SystemExit('Reference DSP PCM slave required with ARM PCM master')
if (args.afe_slave or args.idle_tone_loop) and (r.get('afe_configuration_index')!=3 or r.get('dsp_afe_clock_slave') is not True):
    raise SystemExit('Reference DSP AFE slave required with actual ARM voice configuration')
if args.afe_master and (r.get('afe_configuration_index')!=2 or r.get('dsp_afe_clock_master') is not True or r.get('arm_clock_master') is not False):raise SystemExit('Reference DSP AFE master required with ARM slave')
if args.speech_mixer and (r.get('speech_resource_initially_inactive') is not True or r.get('speech_resource_activation_updater')!='0x24785c5c' or r.get('speech_unmute_result')!=1 or not r.get('speech_receive_gain') or commands[2]['payload'][3]!=r['speech_receive_gain']):
    raise SystemExit('Reference speech activation and nonzero receive mixer required')
if args.voice_profile and (r.get('voice_profile_override') is not True or r.get('voice_afe_profile')!=([2,112,1625,1625,4112,4112,19,3090,1,2,0] if args.afe_master else [3,154,2,2,1,1,19,3090,1,2,0]) or r.get('voice_profile_update_results')!={'afe':0,'pcm':0} or r.get('pcm_profile_one_selected') is not False):
    raise SystemExit('Actual voice Init table overrides required')
if args.port_tone and (r.get('connected_port_tone_diagnostic') is not True or r.get('tone_volume')!=100 or r.get('tone_amplitude_input')!=8000 or r.get('tone_mixer_gains')!=[32767,32767]):
    raise SystemExit('Reference tone on both mixers required for port diagnostic')
configuration=base/('mf283u-voice-inner-slave-init-configuration-emulation.json' if args.afe_master else 'mf283u-voice-inner-init-configuration-emulation.json' if args.driver_init else 'mf283u-voice-inner-configuration-emulation.json' if args.afe_slave or args.idle_tone_loop else 'mf283u-pcm-i2s1-configuration-emulation.json' if args.pcm_teak_i2s1 else 'mf283u-i2s-configuration-emulation.json')
if args.tdm_extra_cycle is not None:
    configuration=configuration.with_name(configuration.name.replace('-configuration-emulation','-extra-cycle'+str(args.tdm_extra_cycle)+'-configuration-emulation'))
cfg=json.loads(configuration.read_text())
if cfg.get('reference_sha256')!=r['reference_sha256'] or cfg.get('device_access') is not False or cfg.get('mmio_simulated') is not True or any(cfg['results'].values()):
    raise SystemExit('Successful simulated reference configuration required')
registers={w['address']:int(w['value'],16) for w in cfg['register_writes']}
if args.tdm_extra_cycle is not None:
    original=json.loads((base/'mf283u-voice-inner-init-configuration-emulation.json').read_text())
    default_bytes=bytearray.fromhex(original['configuration_hex'])
    default_bytes[23]=args.tdm_extra_cycle
    original_registers={w['address']:int(w['value'],16) for w in original['register_writes']}
    expected_registers=dict(original_registers)
    if args.tdm_extra_cycle==0:expected_registers['0x1405008']|=0x20
    if (cfg.get('tdm_extra_cycle')!=args.tdm_extra_cycle or cfg.get('tdm_extra_cycle_config_offset')!=23 or
        cfg['configuration_hex']!=default_bytes.hex() or registers!=expected_registers or
        not any(w['pc']==('0x247801c4' if args.tdm_extra_cycle==0 else '0x247802b4') for w in cfg['register_writes'])):
        raise SystemExit('Only the reference extra-cycle enum and resulting timing bit5 may differ')
if args.driver_init and (cfg.get('driver_init') is not True or cfg.get('driver_init_loop_write_pc')!='0x247820c0' or registers['0x140060']!=0xa9 or cfg.get('loop_owned_mask')!='0x1ff'):
    raise SystemExit('Actual reference driver init and voice-inner loop required')
if args.pcm_teak_i2s1 and (registers['0x140060']!=0x98 or registers['0x1405008']!=0x01ef0009):
    raise SystemExit('Expected mono PCM TDM timing and Teak I2S1 loop')
if args.afe_master and (cfg.get('arm_clock_master') is not False or registers['0x1405008']!=0x01ef2000 or '0x1400058' in registers or '0x140005c' in registers):raise SystemExit('Actual ARM slave setup must not program its clock divider')
rows=['/* Offline I2S duplex reference parameters; opt-in B03 diagnostic only. */',
      '#ifndef CS_I2S_PARAMETERS_H','#define CS_I2S_PARAMETERS_H']
for i,c in enumerate(commands):
    values=c['payload']
    if len(values)!=c['total_halfwords']-1 or any(type(v)is not int or not 0<=v<=65535 for v in values):
        raise SystemExit('Invalid halfwords')
    rows.append('static const unsigned short cs_i2s_params_'+str(i)+'[]={'+','.join(map(str,values))+'};')
rows+=['#define CS_I2S_PARAMETER_REPORT "'+path.name+'"','#define CS_I2S_PARAMETER_SHA256 "'+hashlib.sha256(path.read_bytes()).hexdigest()+'"','#endif','']
rows[-2:-2]=['#define CS_I2S_CONFIGURATION_REPORT "'+configuration.name+'"',
    '#define CS_I2S_CONFIGURATION_SHA256 "'+hashlib.sha256(configuration.read_bytes()).hexdigest()+'"']
for name,address in [('TIMING','0x1405008'),('DIV_LO','0x1400058'),('DIV_HI','0x140005c'),('LOOP','0x140060')]:
    rows[-2:-2]=['#define CS_I2S_'+name+' 0x'+format(registers.get(address,0),'08x')+'U']
rows[-2:-2]=['#define CS_I2S_CLOCK_MASTER '+('0' if args.afe_master else '1')]
rows[-2:-2]=['#define CS_I2S_LOOP_MASK '+cfg.get('loop_owned_mask','0x1f8')+'U']
rows[-2:-2]=['#define CS_I2S_TDM_EXTRA_CYCLE '+str(1 if args.tdm_extra_cycle is None else args.tdm_extra_cycle)]
rows[-2:-2]=['#define CS_I2S_FIFO_RATE_HZ 8000U']
(base/'cs-i2s-parameters.h').write_text('\n'.join(rows))
print(json.dumps({'report':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'device_access':False}))
