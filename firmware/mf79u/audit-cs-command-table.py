#!/usr/bin/env python3
"""Offline audit of the verified B03 CP AT command table. Never writes a device."""
from pathlib import Path
import hashlib,json,struct,argparse

ROOT=Path(__file__).resolve().parents[2]
B03_SHA256='ab0f783acee6ac13833e8f8fac1ee8cf79f5ae5b8ba18f941b03155cd8cdd261'

def audit(binary):
    data=binary.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if digest!=B03_SHA256:
        raise ValueError('Unrecognized CP binary; B03 address mapping cannot be assumed')
    def string(pointer):
        offset=pointer-0xbf003194
        if not 0x536e6c<=offset<0x554feb:
            return None
        end=data.find(b'\0',offset,0x554feb)
        if end<offset or end-offset>=150:
            return None
        return data[offset:end].decode('ascii')
    def row(offset):
        name,identifier,help_pointer=struct.unpack_from('<III',data,offset)
        name=string(name)
        if name is not None and identifier<0x1000 and (name.startswith(('+','^','$','&','\\')) or len(name)<=3):
            return {'offset':hex(offset),'id':identifier,'name':name,'test':string(help_pointer)}
        return None
    start=end=0x50d65c
    if row(start)['name']!='+CVMOD':
        raise ValueError('CVMOD anchor mismatch')
    while row(start-12):start-=12
    while row(end+12):end+=12
    rows=[row(offset) for offset in range(start,end+1,12)]
    if len(rows)!=245:raise ValueError('Unexpected B03 command table length')
    names={entry['name'] for entry in rows}
    commands=('A','H','D','+CLCC','+CHLD','+VTS','^ZCSVOICESPT','+CVMOD')
    return {'binary':str(binary.relative_to(ROOT)) if binary.is_relative_to(ROOT) else binary.name,
        'sha256':digest,'md5':hashlib.md5(data).hexdigest(),
        'mapping':'B03 .rodata.str1.1 pointer = file offset + 0xbf003194',
        'table_range':[hex(start),hex(end)],'entries':rows,
        'cs_commands':{name:name in names for name in commands},
        'limitations':'Table membership does not establish RF voice capability, incoming routing, or an audio transport.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,default=ROOT/'work/zte/b03mod-extracted/lib/cpko/cpko.ko')
    parser.add_argument('--report',type=Path,default=ROOT/'firmware/mf79u/build/cpko-at-command-audit.json')
    args=parser.parse_args();result=audit(args.binary.resolve())
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'md5':result['md5'],'entries':len(result['entries']),'cs_commands':result['cs_commands']}))

if __name__=='__main__':main()
