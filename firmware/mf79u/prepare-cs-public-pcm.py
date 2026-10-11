#!/usr/bin/env python3
"""Prepare a bounded no-call PCM route from the real public API trace."""
from pathlib import Path
import argparse, hashlib, json

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];BUILD=BASE/'build'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--arm-slave',action='store_true');args=p.parse_args()
stem='mf283u-public-pcm'+('-arm-slave' if args.arm_slave else '')
path=BUILD/(stem+'-emulation.json');r=json.loads(path.read_bytes())
script=ROOT/'work/zte/voice/emulate-mf283u-public-pcm.py'
cfgpath=BUILD/(stem+'-configuration-emulation.json');cfg=json.loads(cfgpath.read_bytes())
if (r['generator_sha256']!=hashlib.sha256(script.read_bytes()).hexdigest()
    or r['source_sha256']!='49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
    or not r['offline_only'] or r['device_access'] is not False or r['b03_compatibility_verified'] is not False
    or r['uplink_paths']!=[2,20,20] or r['downlink_paths']!=[4,27]
    or r['arm_clock_master']!=(not args.arm_slave) or r['pcm_configuration_index']!=(0 if args.arm_slave else 1)
    or not r['pcm_tail_active'] or not r['baseline_receipt_unchanged'] or not r['tone_both_mixers']
    or not r['pcm_profile_applied_after_public_refresh']
    or any(r['results'][k] for k in ['public_pcm_inner_config','public_pcm_tx_prepare','public_pcm_rx_prepare',
                                   'public_pcm_loop','public_pcm_input','public_pcm_output'])
    or cfg['configuration_hex']!=r['configuration_hex']):
    raise SystemExit('Exact successful offline public PCM route required')
registers={w['address']:int(w['value'],0) for w in cfg['register_writes']}
if registers['0x140060']!=0x99 or registers['0x1405008']!=(0x01ef0008 if args.arm_slave else 0x01ef0009):
    raise SystemExit('Exact PCM Init/loop/timing required')
commands=r['preparation_sequence']+[r['disable_command']]
if [(c['command'],c['count']) for c in commands]!=[('0x10',12),('0x10',12),('0x19',8),('0x11',23),('0x17',13),('0x18',2),('0xf',28),('0xf',28)]:raise SystemExit('Unexpected command layout')
if commands[3]['payload'][0:2]!=[8192,8192] or commands[3]['payload'][18:20]!=[32767,32767]:raise SystemExit('Full reference mixers required')
if commands[6]['payload'][0]!=3 or commands[7]['payload'][0]!=1:raise SystemExit('Exact PCM enable/disable required')
if commands[6]['payload'][18:23]!=([48,4113,3250,4113,3250] if args.arm_slave else [154,4112,1625,4112,1625]):raise SystemExit('Clock-matched PCM profile required')
rows=['/* Real public PCM route; idle-only, B03 compatibility unverified. */','#ifndef CS_I2S_PARAMETERS_H','#define CS_I2S_PARAMETERS_H']
for i,c in enumerate(commands):
    assert len(c['payload'])==c['count']-1
    rows.append('static const unsigned short cs_i2s_params_'+str(i)+'[]={'+','.join(map(str,c['payload']))+'};')
rows+=['#define CS_I2S_PUBLIC_PCM_API 1','#define CS_I2S_PARAMETER_REPORT "'+path.name+'"',
       '#define CS_I2S_PARAMETER_SHA256 "'+hashlib.sha256(path.read_bytes()).hexdigest()+'"',
       '#define CS_I2S_CONFIGURATION_REPORT "'+cfgpath.name+'"',
       '#define CS_I2S_CONFIGURATION_SHA256 "'+hashlib.sha256(cfgpath.read_bytes()).hexdigest()+'"']
for name,address in [('TIMING','0x1405008'),('DIV_LO','0x1400058'),('DIV_HI','0x140005c'),('LOOP','0x140060')]:
    rows.append('#define CS_I2S_'+name+' 0x'+format(registers.get(address,0),'08x')+'U')
rows+=['#define CS_I2S_CLOCK_MASTER '+str(int(not args.arm_slave)), '#define CS_I2S_LOOP_MASK 0x1ffU',
       '#define CS_I2S_TDM_EXTRA_CYCLE 1','#define CS_I2S_FIFO_RATE_HZ 8000U','#endif','']
(BUILD/'cs-i2s-parameters.h').write_text('\n'.join(rows))
print(json.dumps({'report':path.name,'device_access':False,'b03_compatibility_verified':False}))
