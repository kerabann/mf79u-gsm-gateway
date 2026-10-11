#!/usr/bin/env python3
"""Production CS from the accepted B03 profile, without historical call receipts."""
from pathlib import Path
import hashlib,json,subprocess
from b03_kernel_relocations import audit_module
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];B=BASE/'build';P=BASE/'profiles/b03'
B.mkdir(exist_ok=True)
(B/'cs-dsp-audio-parameters.h').write_bytes((P/'cs-dsp-audio-parameters.h').read_bytes())
(B/'cs-i2s-parameters.h').write_bytes((P/'cs-full-voice-open-parameters.h').read_bytes())
(B/'cs-voice-driver-meta.S').write_bytes((P/'cs-voice-driver-meta.S').read_bytes())
defines=['CS_I2S_PCM_TEST','CS_I2S_PORT_TONE_TEST','CS_I2S_ARM_TONE_TEST','CS_I2S_ARM_ECHO_TEST','CS_I2S_ARM1_ECHO_TEST','CS_I2S_ARM1_RX_ONLY','CS_I2S_ARM1_TX_SWITCH','CS_I2S_USERSPACE_PCM','CS_I2S_STREAMING_PCM','CS_I2S_REUSABLE']
command='arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-pic -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables -march=armv7-a -mthumb -mfloat-abi=soft '
command+=' '.join('-D'+d+'=1' for d in defines)
command+=' -c firmware/mf79u/src/cs-voice-driver.c -o firmware/mf79u/build/cs-voice-driver.o\n'
command+='arm-linux-gnueabi-gcc -march=armv7-a -mthumb -mfloat-abi=soft -c firmware/mf79u/build/cs-voice-driver-meta.S -o firmware/mf79u/build/cs-voice-driver-meta.o\n'
command+='arm-linux-gnueabi-ld -r firmware/mf79u/build/cs-voice-driver.o firmware/mf79u/build/cs-voice-driver-meta.o -o firmware/mf79u/build/mf79u_cs_voice.ko'
subprocess.run(['docker','run','--rm','-v',str(ROOT)+':/work','-w','/work','mf79u-build-tools:local','sh','-eu','-c',command],check=True)
binary=B/'mf79u_cs_voice.ko';audit=audit_module(binary)
if not audit['safe']:raise RuntimeError('Unsafe kernel relocation')
report={'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'md5':hashlib.md5(binary.read_bytes()).hexdigest(),'kernel_audit':audit,'device_access':False,'external_pcm':{'rate':16000,'samples':320,'channels':1,'format':'s16le'}}
(B/'cs-voice-build.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS production CS module and kernel relocation audit.')
