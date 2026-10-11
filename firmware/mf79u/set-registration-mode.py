#!/usr/bin/env python3
"""Apply only the saved registration preference, preserving protected credentials."""
import argparse,importlib.util,json
from pathlib import Path
BASE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('mode',choices=['AUTO','VOLTE','CS']);args=p.parse_args()
spec=importlib.util.spec_from_file_location('transfer',BASE/'device-transfer.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=json.loads(t.shell('cat /dev/.mf79u-native-status.json'));g=json.loads(t.shell('cat /dev/.mf79u-gateway-status.json'))
assert not g['activeCall'] and s.get('callBackend','none')=='none'
d='/mnt/userdata/mf79u';mode=args.mode
# Only fixed literals reach the shell; credential fields remain on the modem.
t.shell(f'''set -e
base={d}
if grep -q '"voiceMode"' "$base/settings.json"; then
 sed 's/"voiceMode"[[:space:]]*:[[:space:]]*"[A-Z]*"/"voiceMode":"{mode}"/' "$base/settings.json" > "$base/settings.registration-next"
else
 sed '1s/{{/{{"voiceMode":"{mode}",/' "$base/settings.json" > "$base/settings.registration-next"
fi
chmod 600 "$base/settings.registration-next"
mv "$base/settings.registration-next" "$base/settings.json"
sed 's/^voice_mode=.*/voice_mode={mode}/' "$base/gateway.ini" > "$base/gateway.registration-next"
if ! grep -q '^voice_mode=' "$base/gateway.registration-next"; then echo 'voice_mode={mode}' >> "$base/gateway.registration-next"; fi
chmod 600 "$base/gateway.registration-next"
mv "$base/gateway.registration-next" "$base/gateway.ini"
''')
# Parse readback locally, never emit credentials.
assert json.loads(t.shell('cat '+d+'/settings.json'))['voiceMode']==mode
assert t.shell("grep '^voice_mode=' "+d+'/gateway.ini')=='voice_mode='+mode
print('Saved registration preference: '+mode)
