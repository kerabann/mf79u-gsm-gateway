#!/usr/bin/env python3
"""Reproducible offline extraction/decoding of the two pinned GSM DSP patches.

No hardware access. Decode contiguous program records together so a loader
record boundary cannot truncate a two-word instruction. Do not interpret
Teakra's Nintendo MMIO layout as a ZTE map or coherent text as hardware proof.
"""
from pathlib import Path
import datetime, hashlib, json, re, struct, subprocess

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'firmware/mf79u'
WORK=ROOT/'work/zte/voice'
REPORT=BASE/'build/mf283u-b03-gsm-dsp-boot-comparison.json'
REPORT_SHA='0ade5d6905a93793d527b4d37d10e43d9ae51c6c4be5583d5a369a1819139a4b'
TEAKRA_COMMIT='3d697a18df504f4677b65129d9ab14c7c597e3eb'
SOURCES={
    'b03':(ROOT/'work/zte/b03mod-extracted/lib/cpko/cpko.ko',
           'ab0f783acee6ac13833e8f8fac1ee8cf79f5ae5b8ba18f941b03155cd8cdd261'),
    'mf283u':(WORK/'mf283u-reference/partitions/evb_cpups.img.gzip-4150.raw',
              '49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513')}

def sha(data): return hashlib.sha256(data).hexdigest()
if sha(REPORT.read_bytes())!=REPORT_SHA: raise SystemExit('Changed boot comparison report')
commit=subprocess.check_output(['git','-C',str(WORK/'teakra'),'rev-parse','HEAD'],text=True).strip()
if commit!=TEAKRA_COMMIT: raise SystemExit('Unexpected Teakra revision')
if subprocess.check_output(['git','-C',str(WORK/'teakra'),'diff','--name-only'],text=True).strip():
    raise SystemExit('Modified Teakra source')
decoder=WORK/'inspect-teak-image'
source=WORK/'inspect-teak-image.cpp'
output=WORK/'gsm-teak-static'
output.mkdir(exist_ok=True)
comparison=json.loads(REPORT.read_text())
result={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'comparison_sha256':REPORT_SHA,'teakra_commit':commit,
        'teakra_url':'https://github.com/wwylele/teakra',
        'decoder_source_sha256':sha(source.read_bytes()),'decoder_binary_sha256':sha(decoder.read_bytes()),
        'offline_only':True,'zte_isa_fully_verified':False,'zte_mmio_map_from_teakra':False,
        'dsp_program_uploaded':False,'images':{}}
for name,(path,expected_sha) in SOURCES.items():
    raw=path.read_bytes()
    if sha(raw)!=expected_sha: raise SystemExit('Unexpected source: '+name)
    entry=comparison[name]
    start=int(entry['start'],0)
    if sha(raw[start:start+entry['size']])!=entry['sha256']: raise SystemExit('Boot record range changed')
    programs=[]
    data_records=[]
    for record in entry['records']:
        at=record['byte_offset']
        command,target=struct.unpack_from('<2H',raw,at)
        if command!=record['command'] or target!=int(record['target'],0):
            raise SystemExit('Record header mismatch')
        if record.get('terminal'):
            if command!=2 or target!=0x20: raise SystemExit('Unexpected DSP entry point')
            continue
        word_count=struct.unpack_from('<H',raw,at+4)[0]
        if word_count!=record['words'] or record.get('flag'):
            raise SystemExit('Unexpected record size or flags')
        payload=raw[at+6:at+6+word_count*2]
        if sha(payload)!=record['sha256'] or target+word_count>0x10000:
            raise SystemExit('Record payload mismatch')
        if command==1:
            data_records.append({'target':hex(target),'words':word_count,'sha256':sha(payload)})
        elif command==0:
            if programs and programs[-1][0]+len(programs[-1][1])//2==target:
                programs[-1][1].extend(payload)
            else:
                programs.append((target,bytearray(payload)))
        else: raise SystemExit('Unknown boot record command')
    decoded=[]
    for target,payload in programs:
        binary=output/f'{name}-merged-{target:04x}.bin'
        listing=output/f'{name}-merged-{target:04x}.txt'
        binary.write_bytes(payload)
        text=subprocess.check_output([str(decoder),str(binary),hex(target)],text=True)
        if 'TRUNCATED' in text: raise SystemExit('Truncated contiguous program segment')
        listing.write_text(text)
        instructions=[]
        unknown=[]
        transfers=[]
        for line in text.splitlines():
            match=re.fullmatch(r'([0-9a-f]{4}) ([0-9a-f]{4}) ([0-9a-f]{4}) (.*)',line)
            if not match: raise SystemExit('Unexpected decoder output')
            address=int(match[1],16)
            if not target<=address<target+len(payload)//2: raise SystemExit('Invalid decoded address')
            instructions.append(address)
            asm=match[4]
            if '?' in asm or asm.startswith('[unknown'): unknown.append({'address':hex(address),'asm':asm})
            branch=re.match(r'(br|call) +0x([0-9a-f]+) +([a-z]+)',asm)
            if branch: transfers.append({'address':hex(address),'operation':branch[1],
                                         'target':hex(int(branch[2],16)),'condition':branch[3]})
        decoded.append({'start_word':hex(target),'words':len(payload)//2,'sha256':sha(payload),
                        'instructions':len(instructions),'decoder_uncertain_instructions':unknown,
                        'absolute_control_transfers':transfers,
                        'binary':str(binary.relative_to(ROOT)), 'listing':str(listing.relative_to(ROOT))})
    result['images'][name]={'source':str(path.relative_to(ROOT)),'source_sha256':expected_sha,
                           'program_segments':decoded,'data_records':data_records}
destination=BASE/'build/gsm-teak-static-decoding.json'
destination.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'report':str(destination.relative_to(ROOT)),
                  'images':{n:[{'start':s['start_word'],'words':s['words'],'instructions':s['instructions'],
                                'uncertain':len(s['decoder_uncertain_instructions'])}
                               for s in d['program_segments']] for n,d in result['images'].items()}},indent=2))
