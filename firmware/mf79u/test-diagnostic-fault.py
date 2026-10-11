#!/usr/bin/env python3
"""Host-only fatal-signal receipt test; never induce a modem crash."""
from pathlib import Path
import hashlib,json,resource,subprocess,tempfile
BASE=Path(__file__).resolve().parent
header=BASE/'src/diagnostic-fault.h'
with tempfile.TemporaryDirectory(prefix='mf79u-fault-') as tmp:
    c=Path(tmp)/'fault.c';binary=Path(tmp)/'fault'
    c.write_text('#define _POSIX_C_SOURCE 200809L\n#include "'+str(header)+'"\n'
                 'int main(void){if(mf79u_diagnostic_fault_install())return 70;raise(SIGSEGV);return 1;}\n')
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(c),'-o',str(binary)],check=True,timeout=30)
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=5,
                          preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
    assert result.returncode==139 and result.stdout.startswith('MF79U_DIAG_FAULT signal=0000000b ') and not result.stderr
receipt={'passed':True,'device_access':False,'exit':result.returncode,'core_saved':False,
         'metadata_only':True,'header_sha256':hashlib.sha256(header.read_bytes()).hexdigest()}
(BASE/'build/diagnostic-fault-host-test.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
