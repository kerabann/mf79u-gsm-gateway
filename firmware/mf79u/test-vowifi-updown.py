#!/usr/bin/env python3
"""Source-specific route ownership and overlapping IKE reauthentication leases."""
import json,os,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as d:
 p=Path(d);state=p/'state.json';state.write_text('{}');runtime=p/'runtime';runtime.mkdir()
 script=p/'updown.sh';script.write_text((root/'vowifi-updown.sh').read_text().replace('/dev/mf79u/vowifi',str(runtime)))
 tool=p/'ip';tool.write_text('''#!/usr/bin/env python3
import os,json,sys
p=os.environ['FIXTURE_STATE'];s=json.load(open(p));a=sys.argv[1:]
if a==['rule','show']:print(s.get('rule',''))
elif a==['route','show','table','79']:print(s.get('route',''))
elif a[0:2]==['route','replace']:s['route']='default dev vowifi0  scope link'
elif a[0:2]==['route','del']:s.pop('route',None)
elif a[0:2]==['rule','add']:s['rule']='1079: from '+a[5].removesuffix('/32')+' lookup 79'
elif a[0:2]==['rule','del']:s.pop('rule',None)
else:raise SystemExit('Unexpected operation')
json.dump(s,open(p,'w'))
''');tool.chmod(0o700)
 env={**os.environ,'PATH':str(p)+':'+os.environ['PATH'],'FIXTURE_STATE':str(state),'PLUTO_MY_SOURCEIP4_1':'10.64.1.2'}
 def run(verb,lease,ok=True,force=False):
  r=subprocess.run(['/bin/sh',str(script)],env={**env,'PLUTO_VERB':verb,'PLUTO_UNIQUEID':str(lease),'MF79U_VOWIFI_CLEANUP':'1' if force else '0'},capture_output=True)
  assert (r.returncode==0)==ok,(verb,r.stderr.decode())
 run('up-client',1);run('up-client',2);run('down-client',1)
 assert (runtime/'address').exists() and 'route' in json.loads(state.read_text())
 assert (runtime/'generation').read_text().strip()=='2'
 run('down-client',2);assert json.loads(state.read_text())=={} and not (runtime/'address').exists()
 state.write_text(json.dumps({'route':'foreign route'}));run('up-client',3,False);run('down-client',3)
 assert json.loads(state.read_text())=={'route':'foreign route'}
 state.write_text('{}');run('up-client',4);run('up-client',5);run('down-client',0,force=True)
 assert json.loads(state.read_text())=={} and not (runtime/'leases').exists()
 # Reaped manager/charon may already have deleted the bridge ownership marker.
 # Cleanup still owns and must release the saved source selector.
 run('up-client',6)
 updown=p/'vowifi-updown.sh';updown.write_text(script.read_text().replace('#!/mnt/userdata/mf79u/tools/busybox sh','#!/bin/sh'));updown.chmod(0o700)
 manager=p/'start-vowifi.sh';manager.write_text((root/'start-vowifi.sh').read_text().replace('base=/mnt/userdata/mf79u','base='+str(p)).replace('/dev/mf79u/vowifi',str(runtime)))
 r=subprocess.run(['/bin/sh',str(manager),'--cleanup-only'],env=env,capture_output=True)
 assert r.returncode==0,r.stderr.decode()
 assert json.loads(state.read_text())=={} and not (runtime/'address').exists()
 state.write_text(json.dumps({'route':'foreign route'}))
 r=subprocess.run(['/bin/sh',str(manager),'--cleanup-only'],env=env,capture_output=True)
 assert r.returncode==0 and json.loads(state.read_text())=={'route':'foreign route'}
print('PASS route ownership, overlapping IKE leases, foreign routes, reaped manager cleanup')
