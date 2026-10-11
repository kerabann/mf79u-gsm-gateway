#!/usr/bin/env python3
"""Isolated NV-policy tests; no device access or real NV writes."""
import os
from pathlib import Path
import subprocess
import tempfile
from adb_boot import patch_rc, unpatch_rc, BLOCK, ANCHOR

HERE = Path(__file__).resolve().parent
base = (HERE / 'build/stock-rootfs/etc/rc').read_bytes()
for rc in [base, base + b'\n# management fixture\n']:
    patched = patch_rc(rc)
    assert patch_rc(patched) == patched and unpatch_rc(patched) == rc
    assert patched.count(BLOCK) == 1 and patched.index(BLOCK) < patched.index(b'zte_usb_cfg &\n')
    assert patched.replace(BLOCK, b'') == rc
for invalid in [base.replace(ANCHOR, b'changed\n'), base + ANCHOR, patch_rc(base).replace(b'--ensure', b'--other')]:
    try:
        patch_rc(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('Unexpected rc accepted')
with tempfile.TemporaryDirectory(prefix='mf79u-adb-test-') as temp:
    temp = Path(temp)
    fixture = temp / 'nv-fixture.c'
    fixture.write_text('''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
static int written;
int nv_get_item(const char *area,const char *key,char *out,int size) {
 assert(!strcmp(area,"ro") && !strcmp(key,"usb_modetype"));
 if(getenv("READ_FAIL"))return -1;
 snprintf(out,size,"%s",written && !getenv("READBACK_FAIL") ? "debug" : getenv("MODE"));return 0;
}
int nv_set_item(const char *area,const char *key,const char *value,int save) {
 assert(!strcmp(area,"ro") && !strcmp(key,"usb_modetype") && !strcmp(value,"debug") && save==1);
 assert(!strcmp(getenv("MODE"),"user") || !*getenv("MODE"));
 assert(!written);puts("FIXTURE_WRITE");written=1;return getenv("WRITE_FAIL") ? -1 : 0;
}
int nv_commit(const char *area) {
 assert(!strcmp(area,"ro") && written);puts("FIXTURE_COMMIT");return getenv("COMMIT_FAIL") ? -1 : 0;
}
''')
    executable = temp / 'adb-boot'
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-DMF79U_ADB_BOOT_HOST_TEST',
                    str(HERE / 'src/adb-boot.c'), str(fixture), '-o', str(executable)], check=True)
    cases = [('debug','--ensure',0,False,{}), ('debug','--check',0,False,{}),
             ('user','--check',4,False,{}), ('user','--ensure',0,True,{}),
             ('','--ensure',0,True,{}), ('factory','--ensure',5,False,{}),
             ('amt','--ensure',5,False,{}), ('unknown','--ensure',5,False,{}),
             ('user','--ensure',3,False,{'READ_FAIL':'1'}),
             ('user','--ensure',6,True,{'WRITE_FAIL':'1'}),
             ('user','--ensure',7,True,{'COMMIT_FAIL':'1'}),
             ('user','--ensure',8,True,{'READBACK_FAIL':'1'}),
             ('user','--invalid',2,False,{})]
    for mode, option, code, write, fields in cases:
        result = subprocess.run([str(executable), option], env={**os.environ,'MODE':mode,**fields}, capture_output=True, text=True, timeout=6)
        assert result.returncode == code, (mode, fields, result)
        assert ('FIXTURE_WRITE' in result.stdout) == write
        if fields.get('WRITE_FAIL'): assert 'FIXTURE_COMMIT' not in result.stdout
print('PASS: rc placement/idempotence/guards and 13 isolated NV cases')
