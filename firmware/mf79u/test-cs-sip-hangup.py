#!/usr/bin/env python3
"""Exercise SIP teardown routing without a modem, PBX, or network socket."""
from pathlib import Path
import json
from unittest.mock import patch
from cs_sip_media_diagnostic import Diagnostic

class Radio:
    def __init__(self):self.online=True
    def shell(self,command):
        if command=='cat /dev/.mf79u-cs-sip-status.json':return '{"codec":"PCMU","voiceBackend":"cs"}'
        assert command=='test -e /sys/mf79u_cs_mo/pcm_info && cat /sys/mf79u_cs_mo/pcm_info'
        return 'MF79U_CS_PCM 1 '+str(int(self.online))+' 8000 160 320'

def check(mode):
    radio=Radio();requests=[];commands=[]
    def hangup():requests.append('owned_call');radio.online=False
    d=Diagnostic(radio,hangup);d.command=commands.append
    def expect(event,seconds):
        assert event=='SIP_MEDIA_CONNECTED'
        if mode=='setup_failure':raise RuntimeError('Synthetic failed SIP session')
        if mode=='remote_cellular':radio.online=False
        else:
            d.events.put('PCM_STATS received=1 sent=1')
            d.events.put('HANGUP');d.events.put('HANGUP')
    d.expect=expect
    with patch('cs_sip_media_diagnostic.time.sleep',lambda _:None):d.monitor()
    assert commands[0]=='INCOMING' and commands[-1]=='ENDED'
    assert requests==([] if mode=='remote_cellular' else ['owned_call'])
    assert bool(d.result.get('sip_hangup_received'))==(mode=='sip_bye')
    assert bool(d.result.get('failure'))==(mode=='setup_failure')
    return mode

checks=[check(mode) for mode in ('sip_bye','remote_cellular','setup_failure')]
report={'passed':True,'device_access':False,'checks':checks,
        'duplicate_sip_hangup_single_cs_command':True,'global_ath_used':False}
(Path(__file__).resolve().parent/'build/cs-sip-hangup-fixture.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS SIP BYE routes once to owned CS; remote cellular clear and SIP failure handled')
