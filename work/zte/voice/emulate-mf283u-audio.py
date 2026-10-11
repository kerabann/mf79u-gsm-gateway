#!/usr/bin/env python3
"""Bounded offline ARM emulation of reference audio parameter builders.

No device access. OS, DSP transport and hardware-control calls are intercepted;
the resulting halfwords are evidence about the reference, not B03 compatibility.
"""
from pathlib import Path
import argparse, hashlib, json, struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--afe-duplex',action='store_true',help='AFE speech duplex matching ARM0 internal I2S loop')
parser.add_argument('--i2s-duplex', action='store_true', help='Digital I2S RX/TX speech parameter evidence only')
parser.add_argument('--pcm-slave', action='store_true', help='With I2S duplex: reference DSP PCM slave opposite ARM master')
parser.add_argument('--afe-slave',action='store_true',help='With AFE duplex: actual voice reference ARM master / DSP AFE I2S slave')
parser.add_argument('--afe-master',action='store_true',help='Actual voice Init alternative: DSP AFE master / ARM clock slave')
parser.add_argument('--idle-tone-loop',action='store_true',help='With AFE slave: digital tone on both mixer outputs for no-call port diagnostic')
parser.add_argument('--speech-mixer',action='store_true',help='Activate speech resource through the actual updater instead of premarking it active')
parser.add_argument('--voice-profile',action='store_true',help='Apply the actual voice Init table overrides before selecting DSP AFE slave mode')
parser.add_argument('--voice-settings',action='store_true',help='Also run voice SetInnerI2sCfg to select the actual AFE route descriptor table')
parser.add_argument('--port-tone',action='store_true',help='Activate DSP tone on both mixers for a connected-call ARM port diagnostic')
parser.add_argument('--tone-uplink', action='store_true',
                    help='Also emulate reference tone resource and mixer activation')
parser.add_argument('--tone-volume', type=int, default=30)
parser.add_argument('--tone-amplitude', type=int, default=4000)
args = parser.parse_args()
if not 0 <= args.tone_volume <= 100 or not 1 <= args.tone_amplitude <= 8000:
    parser.error('Tone volume must be 0..100; bounded amplitude 1..8000')
if sum((args.i2s_duplex,args.afe_duplex,args.tone_uplink))>1:
    parser.error('Select either I2S duplex or tone')
if args.pcm_slave and not args.i2s_duplex:
    parser.error('PCM slave requires digital I2S1 duplex')
if args.afe_slave and not args.afe_duplex:parser.error('AFE slave requires AFE duplex')
if args.afe_master and (not args.afe_duplex or args.afe_slave):parser.error('AFE master requires separate AFE duplex')
if args.idle_tone_loop and not args.afe_slave:parser.error('Idle tone loop requires AFE slave')
if args.speech_mixer and (not (args.afe_slave or args.afe_master) or args.idle_tone_loop):parser.error('Speech mixer requires separate AFE duplex mode')
if args.voice_profile and not ((args.afe_slave or args.afe_master) and args.speech_mixer):parser.error('Voice profile requires AFE duplex and speech mixer')
if args.voice_settings and not args.voice_profile:parser.error('Voice settings requires voice profile')
if args.port_tone and not args.voice_profile:parser.error('Port tone requires voice profile')
if args.afe_master and not (args.port_tone and args.voice_settings):parser.error('AFE master is limited to voice-settings port-tone evidence')
custom_level = args.tone_volume != 30 or args.tone_amplitude != 4000
if custom_level and not (args.tone_uplink or args.idle_tone_loop or args.port_tone):
    parser.error('Tone level requires --tone-uplink')
DATA = (ROOT/'work/zte/voice/mf283u-reference/partitions/evb_cpups.img.gzip-4150.raw').read_bytes()
assert hashlib.sha256(DATA).hexdigest() == '49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
u.mem_map(0x23f00000, 0x2000000)
u.mem_write(0x23f00000, DATA)
u.mem_map(0x30000000, 0x20000)
u.mem_map(0x31000000, 0x1000)
REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
commands = []
skipped = []
def halfwords(addr, count):
    return list(struct.unpack('<'+'H'*count, u.mem_read(addr, count*2)))
def hook(uc, address, size, data):
    if address == 0x246c4b94:
        cmd, count, source = [uc.reg_read(r) for r in REGS[:3]]
        assert 1 <= count <= 32
        commands.append({'command':hex(cmd), 'total_halfwords':count,
                         'payload':halfwords(source,count-1) if count>1 else []})
    elif address == 0x248a013c:
        dst, src, count = [uc.reg_read(r) for r in REGS[:3]]
        assert count <= 8192
        uc.mem_write(dst, bytes(uc.mem_read(src,count)))
    elif address in (0x2478680c, 0x247864b4, 0x23f15e90) or (
            address == 0x24788c94 and not (args.tone_uplink or args.i2s_duplex or args.afe_duplex)):
        skipped.append(hex(address))
    else:
        return
    uc.reg_write(UC_ARM_REG_R0,0)
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(addr, args=()):
    u.reg_write(UC_ARM_REG_SP,0x30018000)
    u.reg_write(UC_ARM_REG_LR,0x31000000)
    for reg,value in zip(REGS,args):u.reg_write(reg,value)
    u.emu_start(addr,0x31000000,count=2000000)
    assert u.reg_read(UC_ARM_REG_PC)==0x31000000, hex(u.reg_read(UC_ARM_REG_PC))
    return u.reg_read(UC_ARM_REG_R0)

# The pointer initializer contains only address construction and RAM stores.
call(0x246b45c0,(0,))
pointers={hex(slot):hex(struct.unpack('<I',u.mem_read(slot,4))[0])
          for slot in (0x2553abf8,0x2553ad24,0x2553aba0)}
if args.voice_settings:
    # zDrvVoiceConfig_Init 248959DC calls this after the profile overrides.
    # SetInnerI2sCfg copies aud_setting_afei2s into the active descriptor table.
    voice_settings_before=list(struct.unpack('<49I',u.mem_read(0x24a64fd4,196)))
    inner_address=0x24acca68
    if args.afe_master:
        u.mem_write(0x30010200,bytes(u.mem_read(inner_address,28)))
        u.mem_write(0x30010200,struct.pack('<I',0));inner_address=0x30010200
    voice_settings_result=call(0x24784cd8,(inner_address,))
    assert voice_settings_result==0 and not commands
    assert bytes(u.mem_read(0x24a64fd4,196))==bytes(u.mem_read(0x24a64f10,196))
    voice_settings_after=list(struct.unpack('<49I',u.mem_read(0x24a64fd4,196)))
# Static-path defaults, without NV overwrite: initialize coefficient destinations
# then select digital media and an 8k scheduler. No reference hardware executes.
u.mem_write(0x255b1c2c+0x18,struct.pack('<I',0x251a4080))
u.mem_write(0x255b1c2c+0x60,struct.pack('<I',0x251a40ec))
u.mem_write(0x251a409c,bytes(([0,15] if args.afe_duplex else [2,15] if args.i2s_duplex else [12,15])+[20]*19))
u.mem_write(0x255b1b80,bytes(([0] if args.afe_duplex else [4])+[27]*27) if (args.i2s_duplex or args.afe_duplex) else bytes([27]*28))
u.mem_write(0x251a44e8,bytes(([0] if args.speech_mixer else [1])+[0]*19))
call(0x247751d4)
call(0x2477571c)
if args.voice_profile:
    # zDrvVoiceConfig_Init 2489597C/24895C44 selects these profiles when
    # ARM voice inner-I2S is master. The builders edit RAM tables only.
    afe_profile_address=0x24acc820 if args.afe_master else 0x24acc838
    pcm_profile_address=0x24a89ea8 if args.afe_master else 0x24abf540
    afe_profile=halfwords(afe_profile_address,11)
    pcm_profile=halfwords(pcm_profile_address,10)
    assert afe_profile==([2,112,1625,1625,4112,4112,19,3090,1,2,0] if args.afe_master else [3,154,2,2,1,1,19,3090,1,2,0])
    assert pcm_profile==([0,48,3250,3250,4113,4113,0,0,0,0] if args.afe_master else [1,154,1625,1625,4112,4112,0,0,0,0])
    before_profile_command_count=len(commands)
    profile_results={'afe':call(0x24786adc,(afe_profile_address,)),
                     'pcm':call(0x24786bb0,(pcm_profile_address,))}
    assert profile_results=={'afe':0,'pcm':0}
    assert len(commands)==before_profile_command_count
    assert halfwords(0x24a656dc+afe_profile[0]*22,11)==afe_profile
    assert halfwords(0x24a65db4+pcm_profile[0]*20,10)==pcm_profile
call(0x24786270,(2 if args.afe_master else 3 if args.afe_slave else 2 if args.i2s_duplex else 0,))
call(0x247863ac,(1 if args.pcm_slave else 0,))
if args.i2s_duplex or args.afe_duplex:
    call(0x24788be4)
    call(0x24785c5c,(0,1))
    if args.speech_mixer:
        # voice_SetMute(enable=0, channel=2) -> AUD mute API(enable=1)
        # -> exact resource handler event 6B, resource0, both directions.
        u.mem_write(0x30010000,struct.pack('<5I',0,0,0,1,2))
        unmute_result=call(0x247889d8,(0x6b,0x30010000))
if args.tone_uplink or args.idle_tone_loop or args.port_tone:
    # Reference tone controller 24787C50..64 activates resource 1 before
    # constructing the tone. Its mixer updater writes gain halfwords +24/+26.
    # Initialize the reference volume defaults, then run that RAM-only update.
    call(0x24788be4)
    u.mem_write(0x251a4564+3, bytes([args.tone_volume]))
    call(0x24785c5c,(1,1))
call(0x24774a68)
call(0x24774ebc,(1,))
tone_coeff=call(0x24786cb4,(1000,))
tone_amp=call(0x24786dc8,(1000,args.tone_amplitude))
waveform = [{'frequency_hz':f, 'coefficient':call(0x24786cb4,(f,)),
             'amplitude':call(0x24786dc8,(f,args.tone_amplitude))}
            for f in (500,1000,1500)] if custom_level else None
u.mem_write(0x251a409c,bytes([20]*21))
if args.i2s_duplex or args.afe_duplex:u.mem_write(0x255b1b80,bytes([27]*28))
u.mem_write(0x251a44e8,bytes(20))
call(0x24774ebc,(1,))
disabled=commands.pop()
assert disabled['command']=='0xf' and disabled['payload'][0]==0
result={'reference_sha256':hashlib.sha256(DATA).hexdigest(),
        'method':'Unicorn offline emulation of parameter builders only',
        'device_access':False,'hardware_calls_executed':False,
        'uplink_paths':[0,15] if args.afe_duplex else [2,15] if args.i2s_duplex else [12,15],'downlink_paths':[0] if args.afe_duplex else [4] if args.i2s_duplex else [],
        'tone_frequency_hz':1000,'tone_coefficient':tone_coeff,
        'tone_amplitude_parameter':tone_amp,'pointer_slots':pointers,
        'dsp_commands':commands,'audio_disable_command':disabled,
        'intercepted_calls':sorted(set(skipped)),
        'b03_audio_compatibility_verified':False}
if args.pcm_slave:
    result.update(pcm_configuration_index=1, arm_clock_master=True, dsp_pcm_clock_slave=True)
if args.afe_slave:result.update(afe_configuration_index=3,arm_clock_master=True,dsp_afe_clock_slave=True)
if args.afe_master:result.update(afe_configuration_index=2,arm_clock_master=False,dsp_afe_clock_master=True)
if args.speech_mixer:
    result.update(speech_resource_initially_inactive=True,
                  speech_resource_activation_updater='0x24785c5c',
                  speech_unmute_handler='0x247889d8',speech_unmute_event='0x6b',
                  speech_unmute_result=unmute_result,
                  speech_receive_gain=halfwords(0x255b37b0+6,1)[0],
                  speech_uplink_mute_parameter=halfwords(0x255b3784+6,1)[0])
if args.voice_profile:
    result.update(voice_profile_override=True,voice_init_selection='0x24895994' if args.afe_master else '0x24895c44',
                  voice_afe_profile_address=hex(afe_profile_address),voice_afe_profile=afe_profile,
                  voice_pcm_profile_address=hex(pcm_profile_address),voice_pcm_profile=pcm_profile,
                  voice_profile_update_results=profile_results,
                  voice_profile_updaters=['0x24786adc','0x24786bb0'],
                  pcm_configuration_index=0,pcm_profile_one_selected=False)
if args.voice_settings:
    result.update(voice_settings_selected=True,voice_inner_configuration='0x24acca68',
                  voice_inner_handler='0x24784cd8',voice_settings_selector='0x24786208',
                  voice_settings_result=voice_settings_result,
                  voice_settings_table_before=[hex(v) for v in voice_settings_before],
                  voice_settings_table_after=[hex(v) for v in voice_settings_after])
if args.idle_tone_loop:result['idle_tone_loop']=True
if args.tone_uplink or args.idle_tone_loop or args.port_tone:
    result.update(tone_resource=1, tone_resource_updater='0x24785c5c',
                  mixer_updater='0x247885f4..0x24788638',
                  tone_mixer_gains=halfwords(0x255b3784+0x24,2),
                  tone_volume=args.tone_volume, reference_volume_defaults_initialized=True)
if args.port_tone:result['connected_port_tone_diagnostic']=True
if custom_level:
    result.update(tone_waveform=waveform, tone_amplitude_input=args.tone_amplitude)
name = 'mf283u-voice-master-port-tone-parameters-emulation.json' if args.afe_master and args.port_tone else 'mf283u-voice-port-tone-parameters-emulation.json' if args.port_tone else 'mf283u-voice-settings-duplex-parameters-emulation.json' if args.voice_settings else 'mf283u-afe-slave-voice-profile-speech-mixer-duplex-parameters-emulation.json' if args.voice_profile else 'mf283u-afe-slave-speech-mixer-duplex-parameters-emulation.json' if args.speech_mixer else 'mf283u-idle-afe-tone-loop-emulation.json' if args.idle_tone_loop else 'mf283u-afe-slave-duplex-parameters-emulation.json' if args.afe_slave else 'mf283u-pcm-slave-duplex-parameters-emulation.json' if args.pcm_slave else 'mf283u-afe-duplex-parameters-emulation.json' if args.afe_duplex else 'mf283u-i2s-duplex-parameters-emulation.json' if args.i2s_duplex else ('mf283u-tone-uplink-volume'+str(args.tone_volume)+'-amplitude'+str(args.tone_amplitude)+'-emulation.json'
        if custom_level else ('mf283u-tone-uplink-emulation.json' if args.tone_uplink else 'mf283u-audio-parameter-emulation.json'))
out=ROOT/'firmware/mf79u/build'/name
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
