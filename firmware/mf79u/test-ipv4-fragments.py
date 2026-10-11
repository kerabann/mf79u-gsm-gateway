#!/usr/bin/env python3
"""Independent header/checksum/reassembly checks using public fake ESP bytes."""
import ctypes as C
from pathlib import Path
import random
import struct
import subprocess

base=Path(__file__).resolve().parent
subprocess.run(['clang','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
                str(base/'src/ipv4-fragments.c'),'-o',str(base/'build/ipv4-fragments-host.so')],check=True)
lib=C.CDLL(str(base/'build/ipv4-fragments-host.so'))
Emit=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_size_t)
fn=lib.ipv4_emit_fragments
fn.argtypes=[C.c_void_p,C.c_size_t,C.c_uint,C.c_uint16,Emit,C.c_void_p];fn.restype=C.c_int
packets=[]
@Emit
def emit(_context,data,size):packets.append(C.string_at(data,size));return 0
def ipv4(body):
    return struct.pack('!BBHHHBBH4s4s',0x45,0,len(body)+20,0,0,64,50,0,
                       bytes([127,0,0,2]),bytes([127,0,0,1]))+body
rng=random.Random(79)
for mtu in [576,599,600,1280,1428,1500,4096]:
    for size in [32,mtu-20,mtu-19,min(2*mtu,8172),7000,8172]:
        body=bytes(rng.randrange(256) for _ in range(size));packet=ipv4(body);packets.clear()
        count=fn(packet,len(packet),mtu,0x7901,emit,None)
        assert count==len(packets)>0
        reconstructed=bytearray(size);ranges=[]
        for fragment in reversed(packets):
            header=fragment[:20];words=struct.unpack('!10H',header)
            checksum=sum(words)
            while checksum>>16:checksum=(checksum&65535)+(checksum>>16)
            assert checksum==65535 and len(fragment)<=mtu
            length,ident,flags=struct.unpack('!HHH',fragment[2:8]);assert length==len(fragment) and ident==0x7901
            offset=(flags&0x1fff)*8;part=fragment[20:]
            assert flags&0x4000==0 and header[8:10]==b'\x40\x32'
            assert header[12:20]==packet[12:20] and offset+len(part)<=size
            if flags&0x2000:assert len(part)%8==0 and offset+len(part)<size
            else:assert offset+len(part)==size
            reconstructed[offset:offset+len(part)]=part;ranges.append((offset,offset+len(part)))
        ranges.sort();assert ranges[0][0]==0 and ranges[-1][1]==size
        assert all(a[1]==b[0] for a,b in zip(ranges,ranges[1:])) and reconstructed==body
packet=ipv4(b'public fixture')
for mtu,ident in [(27,1),(65536,1),(576,0)]:
    packets.clear();assert fn(packet,len(packet),mtu,ident,emit,None)==-1 and not packets
@Emit
def fail(_context,_data,_size):return -1
assert fn(packet,len(packet),576,1,fail,None)==-1
print('PASS: independent IPv4 checksums, MTU limits, fragment alignment/IDs, complete out-of-order reassembly, invalid inputs and emit failure')
