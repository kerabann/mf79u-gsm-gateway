#!/usr/bin/env python3
"""Temporary, owned PF NAT for the modem; never reload the global ruleset."""
import argparse,json,os,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['start','stop','status']);p.add_argument('--modem',default='192.168.0.1');args=p.parse_args()
if os.geteuid()!=0:p.error('Run with sudo; macOS requires root for PF NAT')
import ipaddress
modem=str(ipaddress.IPv4Address(args.modem));anchor='com.apple/mf79u-usb';state=Path('/var/run/mf79u-usb-sharing')
def run(*cmd,data=None):return subprocess.check_output(cmd,input=data,text=True,stderr=subprocess.STDOUT)
if state.is_symlink():raise SystemExit('Refusing symlink state directory')
if args.action=='status':
 print(run('/usr/sbin/sysctl','net.inet.ip.forwarding').strip())
 print(run('/sbin/pfctl','-s','info').strip())
 print('Main NAT rules:',run('/sbin/pfctl','-sn').strip())
 print('MF79U anchor:',run('/sbin/pfctl','-a',anchor,'-v','-sn').strip())
 print('Modem PF states:', '\n'.join(line for line in run('/sbin/pfctl','-ss').splitlines() if modem in line))
 raise SystemExit(0)
if args.action=='stop':
 if not state.exists():raise SystemExit('No owned sharing state')
 saved=json.loads((state/'state.json').read_text());run('/sbin/pfctl','-a',anchor,'-f','/dev/stdin',data='');run('/sbin/pfctl','-X',saved['token'])
 if saved['forwarding']=='0':run('/usr/sbin/sysctl','-w','net.inet.ip.forwarding=0')
 (state/'state.json').unlink();state.rmdir();print('Removed MF79U NAT and released its PF reference');raise SystemExit(0)
rules=run('/sbin/pfctl','-sn')
if 'nat-anchor "com.apple/*"' not in rules:raise SystemExit('Active PF rules lack the Apple NAT anchor; global rules were not changed')
route=run('/sbin/route','-n','get','1.1.1.1');match=re.search(r'interface:\s*(\w+)',route)
if not match:raise SystemExit('No internet interface')
iface=match.group(1);rule=f'nat on {iface} inet from {modem}/32 to any -> ({iface})\n'
run('/sbin/pfctl','-n','-a',anchor,'-f','/dev/stdin',data=rule)
existing=run('/sbin/pfctl','-a',anchor,'-sn')
if state.exists():
 saved=json.loads((state/'state.json').read_text())
 if saved['modem']!=modem:raise SystemExit('Owned state belongs to another modem')
 if re.search(r'^nat ',existing,re.M) and not re.search(r'from '+re.escape(modem)+r'(?:/32)? ',existing):raise SystemExit('Foreign anchor rule: refusing to replace it')
 run('/sbin/pfctl','-a',anchor,'-f','/dev/stdin',data=rule);run('/usr/sbin/sysctl','-w','net.inet.ip.forwarding=1')
 saved['interface']=iface;(state/'state.json').write_text(json.dumps(saved))
 print(f'MF79U NAT refreshed via {iface}; existing PF reference retained');raise SystemExit(0)
if re.search(r'^nat ',existing,re.M):raise SystemExit('Anchor is already owned; refusing to overwrite it')
old=run('/usr/sbin/sysctl','-n','net.inet.ip.forwarding').strip();enabled=run('/sbin/pfctl','-E');token=re.search(r'Token\s*:\s*(\d+)',enabled)
if not token:raise SystemExit('PF enable token unavailable')
state.mkdir(mode=0o700);(state/'state.json').write_text(json.dumps({'token':token.group(1),'forwarding':old,'interface':iface,'modem':modem}));os.chmod(state/'state.json',0o600)
try:
 run('/sbin/pfctl','-a',anchor,'-f','/dev/stdin',data=rule);run('/usr/sbin/sysctl','-w','net.inet.ip.forwarding=1')
except Exception:
 run('/sbin/pfctl','-a',anchor,'-f','/dev/stdin',data='');run('/sbin/pfctl','-X',token.group(1));(state/'state.json').unlink();state.rmdir();raise
print(f'MF79U {modem}: USB internet via {iface}; only its /32 is translated')
