#!/usr/bin/env python3
"""Measure the original recording without normalization or alteration.
These metrics describe levels/gaps; they do not estimate MOS or intelligibility.
"""
import array
import json
import math
from pathlib import Path
import statistics
import sys
import wave

path=Path(sys.argv[1]).resolve()
with wave.open(str(path),'rb') as audio:
    rate=audio.getframerate();channels=audio.getnchannels();width=audio.getsampwidth()
    if width!=2 or channels!=1:raise RuntimeError('Expected original mono PCM16 WAV')
    samples=array.array('h',audio.readframes(audio.getnframes()))
if sys.byteorder!='little':samples.byteswap()
def db(value):return round(20*math.log10(max(value,1)/32768),2)
frames=[samples[i:i+rate//50] for i in range(0,len(samples),rate//50)]
rms=[math.sqrt(sum(x*x for x in frame)/len(frame)) for frame in frames if frame]
peak=max((abs(x) for x in samples),default=0)
full_rms=math.sqrt(sum(x*x for x in samples)/max(1,len(samples)))
zero_runs=[];start=None
for i,frame in enumerate(frames):
    zero=not any(frame)
    if zero and start is None:start=i
    if not zero and start is not None:
        if i-start>=5:zero_runs.append({'start_s':round(start*.02,2),'duration_s':round((i-start)*.02,2)})
        start=None
if start is not None and len(frames)-start>=5:
    zero_runs.append({'start_s':round(start*.02,2),'duration_s':round((len(frames)-start)*.02,2)})
report={'path':str(path),'duration_s':round(len(samples)/rate,3),'sample_rate':rate,
        'channels':channels,'sample_width':width,'samples':len(samples),
        'nonzero_samples':sum(x!=0 for x in samples),'peak_dbfs':db(peak),
        'rms_dbfs':db(full_rms),'clipped_sample_percent':round(100*sum(abs(x)>=32760 for x in samples)/max(1,len(samples)),5),
        'frames_20ms':len(frames),'low_level_frame_percent':round(100*sum(x<33 for x in rms)/max(1,len(rms)),2),
        'long_exact_zero_runs':zero_runs,'normalized':False,
        'quality_score_estimated':False,
        'notes':'Pauses and missing audio can both produce silence. These level measurements do not prove speech quality.'}
path.with_suffix('.analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
