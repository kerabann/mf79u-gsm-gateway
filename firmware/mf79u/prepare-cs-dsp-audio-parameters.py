#!/usr/bin/env python3
"""Generate the bounded DSP candidate parameters from offline reference evidence.

No device access. Run emulate-mf283u-audio.py --tone-uplink first. The reference
tone resource is required: a muted generic media route is insufficient.
"""
from pathlib import Path
import argparse, hashlib, json, re

BASE = Path(__file__).resolve().parent / 'build'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', default='mf283u-tone-uplink-emulation.json')
args = parser.parse_args()
if not re.fullmatch(r'mf283u-tone-uplink(?:-volume\d{1,3}-amplitude\d{1,4})?-emulation\.json', args.report):
    raise SystemExit('Bounded reference report basename required')
source = BASE / args.report
data = json.loads(source.read_text())
if (data.get('reference_sha256') != '49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
    or data.get('device_access') is not False
    or data.get('hardware_calls_executed') is not False
    or data.get('tone_resource') != 1
    or data.get('tone_mixer_gains') != [32767, 32767]):
    raise SystemExit('Hash-pinned offline tone mixer evidence required')
commands = data['dsp_commands'][-7:] + [data['audio_disable_command']]
if [(c['command'], c['total_halfwords']) for c in commands] != [
    ('0x10', 12), ('0x10', 12), ('0x19', 8), ('0x11', 23),
    ('0x17', 13), ('0x18', 2), ('0xf', 28), ('0xf', 28)]:
    raise SystemExit('Unexpected reference command sequence')
if commands[3]['payload'][18:20] != [32767, 32767] or not commands[3]['payload'][8]:
    raise SystemExit('Tone mixer is muted')
digest = hashlib.sha256(source.read_bytes()).hexdigest()
rows = ['/* Generated offline reference tone resource; B03 compatibility unverified. */',
        '#ifndef MF79U_CS_DSP_AUDIO_PARAMETERS_H', '#define MF79U_CS_DSP_AUDIO_PARAMETERS_H']
for index, command in enumerate(commands):
    values = command['payload']
    if len(values) != command['total_halfwords'] - 1 or any(type(v) is not int or not 0 <= v <= 65535 for v in values):
        raise SystemExit('Invalid reference halfwords')
    rows.append('static const unsigned short cs_audio_params_'+str(index)+'[]={'+','.join(map(str, values))+'};')
waveform = data.get('tone_waveform', [
    {'frequency_hz':500,'coefficient':30272,'amplitude':1530},
    {'frequency_hz':1000,'coefficient':23170,'amplitude':2828},
    {'frequency_hz':1500,'coefficient':12539,'amplitude':3695}])
if [row['frequency_hz'] for row in waveform] != [500,1000,1500] or any(
    not 0 < row['coefficient'] <= 32767 or not 0 < row['amplitude'] <= 8000 for row in waveform):
    raise SystemExit('Invalid bounded tone waveform')
for key in ('coefficient','amplitude'):
    rows.append('static const unsigned short cs_audio_tone_'+key+'[]={'+','.join(str(row[key]) for row in waveform)+'};')
rows += ['#define CS_AUDIO_PARAMETER_REPORT "'+source.name+'"',
         '#define CS_AUDIO_PARAMETER_REPORT_SHA256 "'+digest+'"', '#endif', '']
(BASE/'cs-dsp-audio-parameters.h').write_text('\n'.join(rows))
print(json.dumps({'report': source.name, 'sha256': digest, 'tone_mixer_gains': [32767,32767], 'device_access': False}))
