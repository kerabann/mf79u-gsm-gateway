#!/usr/bin/env python3
"""Bind the complete reference voice API trace to an explicit I2S diagnostic."""
from pathlib import Path
import argparse, hashlib, json

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
BUILD = BASE / 'build'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--arm-slave', action='store_true')
args = parser.parse_args()
path = BUILD / ('mf283u-full-voice-open'+('-arm-slave' if args.arm_slave else '')+'-port-tone-emulation.json')
r = json.loads(path.read_bytes())
script = ROOT/'work/zte/voice/emulate-mf283u-voice-open.py'
if (r.get('generator_sha256') != hashlib.sha256(script.read_bytes()).hexdigest()
        or r.get('source_sha256') != '49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
        or not r.get('offline_only') or r.get('device_access') is not False
        or r.get('b03_compatibility_verified') is not False
        or r.get('arm_clock_master') != (not args.arm_slave)
        or r.get('fifo_sample_rate_hz') != 8000 or not r.get('pcm_tail_inactive')
        or not r.get('tone_both_mixers') or r.get('tone_volume') != 100
        or r.get('disable_switch') != 1 or not r.get('disable_requires_scheduler_stop_0x15')
        or r.get('uplink_paths') != [0, 20, 20] or r.get('downlink_paths') != [0, 27]):
    raise SystemExit('Complete hash-bound reference AFE trace required')
for name in ('voice_open', 'voice_input_path', 'voice_output_path', 'voice_enable', 'voice_unmute'):
    if r['results'].get(name) != 0:
        raise SystemExit('Reference API failure: '+name)
commands = r['preparation_sequence']+[r['disable_command']]
if [(c['command'], c['count']) for c in commands] != [
        ('0x10',12), ('0x10',12), ('0x19',8), ('0x11',23),
        ('0x17',13), ('0x18',2), ('0xf',28), ('0xf',28)]:
    raise SystemExit('Unexpected command layout')
if commands[3]['payload'][0:2] != [8192,8192] or commands[3]['payload'][18:20] != [32767,32767]:
    raise SystemExit('Reference master and tone mixer levels required')
if commands[6]['payload'][0] != 2 or commands[6]['payload'][18:] != [0]*9:
    raise SystemExit('AFE-only start required')
cfgpath = BUILD / ('mf283u-voice-inner'+('-slave' if args.arm_slave else '')+'-init-configuration-emulation.json')
cfg = json.loads(cfgpath.read_bytes())
if (cfg.get('reference_sha256') != r['source_sha256'] or cfg.get('device_access') is not False
        or not cfg.get('driver_init') or cfg.get('arm_clock_master') != (not args.arm_slave)
        or cfg.get('configuration_hex') != r['inner_configuration_hex']):
    raise SystemExit('Matching voice I2S configuration required')
registers = {c['address']:int(c['value'],0) for c in cfg['register_writes']}
if registers['0x140060'] != 0xa9 or registers['0x1405008'] != (0x01ef2000 if args.arm_slave else 0x01ef2001):
    raise SystemExit('Unexpected AFE timing or internal route')
rows = ['/* Full reference voice API parameters; bounded diagnostic only. */',
        '#ifndef CS_I2S_PARAMETERS_H', '#define CS_I2S_PARAMETERS_H']
for i, c in enumerate(commands):
    values = c['payload']
    if len(values) != c['count']-1 or any(type(x) is not int or not 0 <= x <= 65535 for x in values):
        raise SystemExit('Invalid parameter words')
    rows.append('static const unsigned short cs_i2s_params_'+str(i)+'[]={'+','.join(map(str,values))+'};')
rows += ['#define CS_I2S_FULL_VOICE_API 1',
         '#define CS_I2S_PARAMETER_REPORT "'+path.name+'"',
         '#define CS_I2S_PARAMETER_SHA256 "'+hashlib.sha256(path.read_bytes()).hexdigest()+'"',
         '#define CS_I2S_CONFIGURATION_REPORT "'+cfgpath.name+'"',
         '#define CS_I2S_CONFIGURATION_SHA256 "'+hashlib.sha256(cfgpath.read_bytes()).hexdigest()+'"']
for name, address in [('TIMING','0x1405008'), ('DIV_LO','0x1400058'), ('DIV_HI','0x140005c'), ('LOOP','0x140060')]:
    rows.append('#define CS_I2S_'+name+' 0x'+format(registers.get(address,0),'08x')+'U')
rows += ['#define CS_I2S_CLOCK_MASTER '+str(int(not args.arm_slave)),
         '#define CS_I2S_LOOP_MASK 0x1ffU', '#define CS_I2S_TDM_EXTRA_CYCLE 1',
         '#define CS_I2S_FIFO_RATE_HZ 8000U', '#endif', '']
(BUILD/'cs-i2s-parameters.h').write_text('\n'.join(rows))
print(json.dumps(dict(report=path.name, device_access=False, pcm_tail_inactive=True)))
