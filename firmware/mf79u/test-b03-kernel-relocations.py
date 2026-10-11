#!/usr/bin/env python3
"""Regression against the preserved reboot-associated ELF and corrected sampler."""
from pathlib import Path
from b03_kernel_relocations import audit_module,mode_safe,kernel_export,KERNEL
BASE=Path(__file__).resolve().parent
bad=BASE/'build/quarantined/2b0f3686d99a46cf8c7d35fdfd21a25340f03105a2f11ae3be7594343b981430.ko'
report=audit_module(bad)
unsafe=[c for c in report['direct_thumb_calls'] if not c['safe']]
assert not report['safe']
assert len(unsafe)==1 and unsafe[0]['symbol']=='memset' and unsafe[0]['offset']=='0x232'
assert unsafe[0]['target']=='0xc010cb40' and unsafe[0]['symbol_type']==0
assert not mode_safe(10,0xc010cb40) and not mode_safe(30,0xc010cb40)
assert mode_safe(10,0xc010cc1d) and mode_safe(30,0xc010cc1d)
image=KERNEL.read_bytes()
assert kernel_export(image,'printk')&1 # String suffix sharing must be handled.
try:kernel_export(image,'mf79u_nonexistent_export')
except ValueError:pass
else:raise AssertionError('Missing export was accepted')
good=audit_module(BASE/'build/mf79u_cs_channels.ko')
assert good['safe'] and good['module_sha256']!=report['module_sha256']
assert all(c['symbol']!='memset' for c in good['direct_thumb_calls'])
assert any(c['symbol']=='probe_kernel_read' for c in good['direct_thumb_calls'])
print('PASS: quarantined NOTYPE Thumb-to-ARM call rejected; corrected TCH sampler contains only Thumb kernel calls')
