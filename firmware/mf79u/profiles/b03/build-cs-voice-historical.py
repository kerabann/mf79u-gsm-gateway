#!/usr/bin/env python3
"""Build persistent CS using the physically validated B03 voice profile."""
from pathlib import Path
import hashlib,json,re,subprocess
from b03_kernel_relocations import audit_module
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];B=BASE/'build'
header=B/'cs-i2s-parameters.h';saved=header.read_bytes()
archive=(B/'cs-full-voice-open-parameters.h').read_text()
name=re.search(r'^#define CS_I2S_CONFIGURATION_REPORT "([a-z0-9-]+\.json)"$',archive,re.M)[1]
cfg=B/name;saved_cfg=cfg.read_bytes()
try:
    header.write_text(archive);cfg.write_bytes((B/'cs-full-voice-open-configuration.json').read_bytes())
    options=['--mo','--instance','64','--seconds','240','--connected-seconds','40',
             '--i2s-pcm-candidate','--i2s-port-tone','--i2s-full-voice-open','--i2s-arm-tone',
             '--i2s-arm-echo','--i2s-arm1-echo','--i2s-arm1-rx-only','--i2s-arm1-tx-switch',
             '--i2s-userspace-pcm','--i2s-streaming-pcm']
    subprocess.run(['python3',str(BASE/'build-cs-kernel-probe.py'),*options],check=True,stdout=subprocess.DEVNULL)
    proof=json.loads((B/'cs-mo-probe64-build.json').read_text())
    meta=(B/'cs-mo-probe-meta.S').read_text()
    module='mf79u_cs_voice'
    meta=re.sub(r'\.asciz "mf79u_cs_mo64"\n\.zero \d+',
                '.asciz "'+module+'"\n.zero '+str(188-12-len(module)-1),meta)
    (B/'cs-voice-driver-meta.S').write_text(meta)
    defines=['CS_I2S_PCM_TEST','CS_I2S_PORT_TONE_TEST','CS_I2S_ARM_TONE_TEST','CS_I2S_ARM_ECHO_TEST',
             'CS_I2S_ARM1_ECHO_TEST','CS_I2S_ARM1_RX_ONLY','CS_I2S_ARM1_TX_SWITCH',
             'CS_I2S_USERSPACE_PCM','CS_I2S_STREAMING_PCM','CS_I2S_REUSABLE']
    command='''arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-pic -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables -march=armv7-a -mthumb -mfloat-abi=soft '''
    command+=' '.join('-D'+d+'=1' for d in defines)
    command+=''' -c firmware/mf79u/src/cs-voice-driver.c -o firmware/mf79u/build/cs-voice-driver.o
arm-linux-gnueabi-gcc -march=armv7-a -mthumb -mfloat-abi=soft -c firmware/mf79u/build/cs-voice-driver-meta.S -o firmware/mf79u/build/cs-voice-driver-meta.o
arm-linux-gnueabi-ld -r firmware/mf79u/build/cs-voice-driver.o firmware/mf79u/build/cs-voice-driver-meta.o -o firmware/mf79u/build/mf79u_cs_voice.ko'''
    subprocess.run(['docker','run','--rm','-v',str(ROOT)+':/work','-w','/work',
                    'mf79u-build-tools:local','sh','-eu','-c',command],check=True)
    binary=B/(module+'.ko');audit=audit_module(binary)
    if not audit['safe']:raise RuntimeError('Unsafe kernel relocation')
    files=['cs-voice-driver.c','cs-driver-runtime.inc','cs-call-state.h','cs-caller.h','cs-wire.h','cs-wcdma-codec.h',
           'cs-i2s-pcm-candidate.h','cs-pcm-stream.h','cs-kernel-status.h','cs-mo-state.h','cs-owner-lease.h']
    report={'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'md5':hashlib.md5(binary.read_bytes()).hexdigest(),
            'kernel_relocation_audit':audit,'initially_suspended':True,'connected_timeout':None,
            'explicit_incoming_answer':True,'reusable_after_mm_idle_and_pcm_owner_close':True,
            'owner_lease_seconds':10,'profile_proof':proof,
            'sources':{f:hashlib.sha256((BASE/'src'/f).read_bytes()).hexdigest() for f in files}}
    (B/'cs-voice-driver-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Built persistent CS driver; checked kernel relocations; initially suspended.')
finally:
    header.write_bytes(saved);cfg.write_bytes(saved_cfg)
