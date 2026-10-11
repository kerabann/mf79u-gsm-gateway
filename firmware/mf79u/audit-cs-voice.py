#!/usr/bin/env python3
"""Read-only device probes; RAM executables removed. No calls/SMS/flags/flash."""
from pathlib import Path
import datetime,hashlib,json,subprocess
base=Path(__file__).resolve().parent;root=base.parents[1];adb=[str(root/'outputs/adb')]
def shell(c):return subprocess.check_output(adb+['shell',c],stderr=subprocess.PIPE,timeout=35).decode().replace('\r','').strip()
results={}
for name in ['cs-voice-probe']:
 local=base/'build'/name;remote='/dev/.mf79u-'+name
 subprocess.run(adb+['push',str(local),remote],check=True,capture_output=True,timeout=60)
 try:
  shell('chmod 700 '+remote)
  if shell('md5sum '+remote).split()[0]!=hashlib.md5(local.read_bytes()).hexdigest():raise RuntimeError('Probe checksum mismatch')
  results[name]=shell(remote)
 finally:shell('rm -f '+remote)
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'probes':results,'runtime':json.loads(shell('cat /dev/.mf79u-native-status.json')),'gateway':json.loads(shell('cat /dev/.mf79u-gateway-status.json')),'calls_sms_or_flag_mutations':False,'gsm_voice_implemented':False}
(base/'build/cs-voice-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(results,indent=2))
