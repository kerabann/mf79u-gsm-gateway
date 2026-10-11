#!/usr/bin/env python3
"""Encode a synthetic 1kHz tone in all AMR-NB modes on ARM; no radio commands."""
from pathlib import Path
import datetime,hashlib,json,math,struct,subprocess,sys
from ram_transfer import ram_push
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];BUILD=BASE/'build'
ADB=[str(ROOT/'outputs/adb')];SIZES=[12,13,15,17,19,20,26,31]
def shell(c):return subprocess.check_output(ADB+['shell',c],timeout=30).decode().replace('\r','').strip()
def spectrum(data):
 values=struct.unpack('<'+str(len(data)//2)+'h',data)
 # Exclude codec/FIR warmup and the tone-to-silence transition.
 signal=values[3200:16000];n=len(signal)
 power=sum(v*v for v in signal)/n
 def energy(f):
  a=sum(v*math.cos(2*math.pi*f*i/16000) for i,v in enumerate(signal))*2/n
  b=sum(v*math.sin(2*math.pi*f*i/16000) for i,v in enumerate(signal))*2/n
  return (a*a+b*b)/2
 e=energy(1000);off=max(energy(f) for f in [400,600,800,1200,1500,2000])
 return {'rms':round(math.sqrt(power),2),'tone_energy_fraction':round(e/power,4),
         'tone_to_off_frequency_db':round(10*math.log10(e/max(off,1)),2)}
if len(sys.argv)!=2 or sys.argv[1]!='--device-conversion':raise SystemExit('Use --device-conversion for synthetic RAM file conversion only')
frames=100;input_path=BUILD/'cs-test-tone-16k.s16le'
pcm=[]
for i in range(frames*320):
 t=i/16000;edge=min(1,t/.01,max(0,(1.5-t)/.01))
 pcm.append(round(8192*edge*math.sin(2*math.pi*1000*t)))
input_path.write_bytes(struct.pack('<'+str(len(pcm))+'h',*pcm))
remotes=['/dev/.mf79u-tone-codec','/dev/.mf79u-tone-input','/dev/.mf79u-tone-amr','/dev/.mf79u-tone-decoded']
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'synthetic_only':True,
 'no_radio_or_dsp_access':True,'pcm_contract':{'format':'mono PCM16LE','rate':16000,'samples':320,'period_ms':20},
 'frames_per_mode':frames,'tone_hz':1000,'tone_seconds':1.5,'modes':[]}
all_frames=[]
try:
 ram_push(ADB,BUILD/'cs-tone-codec',remotes[0]);ram_push(ADB,input_path,remotes[1])
 for mode,size in enumerate(SIZES):
  response=shell(f'{remotes[0]} {mode} {remotes[1]} {remotes[2]} > {remotes[3]}; echo MF79U_CODEC_EXIT=$?')
  if 'MF79U_CODEC_EXIT=0' not in response:raise RuntimeError('ARM synthetic conversion failed')
  amr=BUILD/f'cs-test-tone-mode{mode}.amr';decoded=BUILD/f'cs-test-tone-mode{mode}-16k.s16le'
  for remote,local in [(remotes[2],amr),(remotes[3],decoded)]:
   subprocess.run(ADB+['pull',remote,str(local)],check=True,capture_output=True,timeout=20)
   if shell('md5sum '+remote).split()[0]!=hashlib.md5(local.read_bytes()).hexdigest():raise RuntimeError('Synthetic file transfer mismatch')
  data=amr.read_bytes()
  if len(data)!=6+frames*(size+1) or data[:6]!=b'#!AMR\n':raise RuntimeError('AMR frame count/header mismatch')
  packets=[]
  for offset in range(6,len(data),size+1):
   if data[offset]!=(mode<<3|4):raise RuntimeError('AMR frame mode/quality mismatch')
   packets.append(data[offset+1:offset+1+size])
  if len(decoded.read_bytes())!=frames*640:raise RuntimeError('Decoded external PCM contract mismatch')
  metric=spectrum(decoded.read_bytes())
  if metric['tone_energy_fraction']<.15 or metric['tone_to_off_frequency_db']<12:raise RuntimeError('Decoded tone verification failed')
  report['modes'].append({'mode':mode,'amr_sha256':hashlib.sha256(data).hexdigest(),'payload_bytes':size,'frames':len(packets),'decoded':metric})
  all_frames.append(packets)
 lines=['/* Generated synthetic tone; no captured audio or identifiers. */',
        '#define CS_TONE_FRAMES 100U','static const u8 cs_tone_payload_size[8]={12,13,15,17,19,20,26,31};',
        'static const u8 cs_tone_payloads[8][100][31]={']
 for packets in all_frames:
  lines.append('{')
  lines.extend('{'+','.join(str(v) for v in p)+'},' for p in packets)
  lines.append('},')
 lines.append('};')
 header=BUILD/'cs-tone-frames.h';header.write_text('\n'.join(lines)+'\n')
 report['header_sha256']=hashlib.sha256(header.read_bytes()).hexdigest();report['verified']=True
finally:
 shell('rm -f '+' '.join(remotes));report['remote_synthetic_files_removed']=True
 (BUILD/'cs-tone-frames-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
