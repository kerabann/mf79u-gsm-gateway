#!/usr/bin/env python3
"""Independent stdlib ESP/HMAC oracle; only synthetic keys and loop-free packets."""
import ctypes as C
import hashlib
import hmac
from pathlib import Path
import random
import struct
import subprocess

base=Path(__file__).resolve().parent
subprocess.run(['clang','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
                str(base/'src/esp-null.c'),'-o',str(base/'build/esp-null-host.so')],check=True)
lib=C.CDLL(str(base/'build/esp-null-host.so'))
class SA(C.Structure):
    _fields_=[('spi',C.c_uint32),('tx',C.c_uint32),('highest',C.c_uint32),('window',C.c_uint64)]
Digest=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p)
key=bytes(range(20)) # public synthetic fixture, never modem keys
@Digest
def digest(_context,data,size,out):
    value=hmac.new(key,C.string_at(data,size),hashlib.sha1).digest()
    C.memmove(out,value,len(value));return len(value)
for name in ['esp_null_encode','esp_null_decode']:
    fn=getattr(lib,name);fn.argtypes=[C.POINTER(SA),C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,Digest,C.c_void_p]
    fn.restype=C.c_int
udp=struct.pack('!HHHH',5000,5001,11,0)+b'abc'
def oracle(seq,spi=0x01020304,body=udp,protocol=17,padding=None):
    p=(-len(body)-2)%4
    trailer=bytes(range(1,p+1)) if padding is None else padding
    data=struct.pack('!II',spi,seq)+body+trailer+bytes([len(trailer),protocol])
    return data+hmac.new(key,data,hashlib.sha1).digest()[:12]
out=C.create_string_buffer(8192);sa=SA(0x01020304,0,0,0)
length=lib.esp_null_encode(C.byref(sa),udp,len(udp),out,len(out),digest,None)
assert out.raw[:length]==oracle(1) and sa.tx==1
assert lib.esp_null_encode(C.byref(sa),udp,len(udp),out,1,digest,None)==-1 and sa.tx==1
sa.tx=0xffffffff
assert lib.esp_null_encode(C.byref(sa),udp,len(udp),out,len(out),digest,None)==-1
sa=SA(0x01020304,0,0,0)
def decode(packet):
    length=lib.esp_null_decode(C.byref(sa),packet,len(packet),out,len(out),digest,None)
    return length,out.raw[:max(0,length)]
assert decode(oracle(5))==(len(udp),udp)
assert decode(oracle(5))[0]==-1 # duplicate
assert decode(oracle(3))==(len(udp),udp) # valid out-of-order
assert decode(oracle(3))[0]==-1
assert decode(oracle(70))==(len(udp),udp)
assert decode(oracle(6))[0]==-1 # outside 64-packet replay window
bad=bytearray(oracle(71));bad[-1]^=1
assert decode(bytes(bad))[0]==-1 and sa.highest==70
for packet in [oracle(0),oracle(71,spi=9),oracle(71,protocol=6),oracle(71,padding=b'\x01\x02\x04')]:
    assert decode(packet)[0]==-1 and sa.highest==70
assert decode(oracle(71))==(len(udp),udp)
rng=random.Random(790)
for _ in range(1000):
    packet=bytes(rng.randrange(256) for _ in range(rng.randrange(0,512)))
    assert decode(packet)[0]==-1
print('PASS: independent ESP encoding, integrity, padding, replay, sequence exhaustion, bounds, 1000 malformed packets')

Cipher=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_int,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p)
Random=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_size_t)
aes_key=bytes(range(16));iv=bytes(range(16)) # public test fixtures
def aes(data,encrypt,vector=iv):
    args=['openssl','enc','-aes-128-cbc','-nosalt','-nopad','-K',aes_key.hex(),'-iv',vector.hex()]
    if not encrypt:args+=['-d']
    return subprocess.run(args,input=data,capture_output=True,check=True).stdout
@Cipher
def cipher(_context,encrypt,vector,data,size,out):
    value=aes(C.string_at(data,size),encrypt,C.string_at(vector,16))
    C.memmove(out,value,len(value));return 0
@Random
def random_iv(_context,out,size):
    assert size==16;C.memmove(out,iv,16);return 0
@Digest
def md5(_context,data,size,out):
    value=hmac.new(aes_key,C.string_at(data,size),hashlib.md5).digest()
    C.memmove(out,value,len(value));return len(value)
lib.esp_cbc_encode.argtypes=lib.esp_null_encode.argtypes[:-2]+[Digest,Cipher,Random,C.c_void_p]
lib.esp_cbc_decode.argtypes=lib.esp_null_decode.argtypes[:-2]+[Digest,Cipher,C.c_void_p]
def cbc_oracle(seq,body=udp,protocol=17,padding=None):
    p=(-len(body)-2)%16;pad=bytes(range(1,p+1)) if padding is None else padding
    plain=body+pad+bytes([len(pad),protocol])
    data=struct.pack('!II',0x01020304,seq)+iv+aes(plain,1)
    return data+hmac.new(aes_key,data,hashlib.md5).digest()[:12]
sa=SA(0x01020304,0,0,0)
length=lib.esp_cbc_encode(C.byref(sa),udp,len(udp),out,len(out),md5,cipher,random_iv,None)
assert out.raw[:length]==cbc_oracle(1) and sa.tx==1
def decode_cbc(packet):
    length=lib.esp_cbc_decode(C.byref(sa),packet,len(packet),out,len(out),md5,cipher,None)
    return length,out.raw[:max(0,length)]
assert decode_cbc(cbc_oracle(5))==(len(udp),udp)
assert decode_cbc(cbc_oracle(5))[0]==-1
bad=bytearray(cbc_oracle(6));bad[8]^=1
assert decode_cbc(bytes(bad))[0]==-1 and sa.highest==5 # IV covered by ICV
assert decode_cbc(cbc_oracle(6,padding=b'\x01\x02\x04'))[0]==-1 and sa.highest==5
assert decode_cbc(cbc_oracle(6,protocol=6))[0]==-1 and sa.highest==5
assert decode_cbc(cbc_oracle(6))==(len(udp),udp)
for size in [8,14,15,16,30,31,32,1200,4096]:
    body=struct.pack('!HHHH',5000,5001,size,0)+b'x'*(size-8)
    packet=cbc_oracle(100+size,body)
    # Each fixture independently checks the wire frame, block boundary and decode.
    sa=SA(0x01020304,99+size,0,0)
    length=lib.esp_cbc_encode(C.byref(sa),body,len(body),out,len(out),md5,cipher,random_iv,None)
    assert out.raw[:length]==packet
    assert decode_cbc(packet)==(size,body)
print('PASS: AES-CBC/HMAC-MD5-96 against independent OpenSSL/stdlib oracle; IV integrity, padding, replay, packet sizes 8..4096')
