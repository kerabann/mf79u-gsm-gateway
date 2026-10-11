#!/usr/bin/env python3
"""Sanitized one-answer MT lifecycle fixture; never uses a modem."""
from pathlib import Path
import json,subprocess,tempfile
BASE=Path(__file__).resolve().parent
source=r'''
#include <assert.h>
#include "cs-mt-state.h"
#include "cs-wire.h"
int main(void) {
 struct cs_mt_state s={0};struct cs_mt_packet p[3];struct cs_wire_metadata m;
 assert(!cs_mt_receive(&s,0x83,5,1,p) && !s.budget);
 assert(!cs_mt_receive(&s,0x13,5,1,p) && !s.budget);
 assert(!cs_mt_receive(&s,3,5,0,p) && !s.budget);
 assert(!cs_mt_receive(&s,3,15,1,p) && !s.stage);
 assert(cs_mt_receive(&s,3,5,1,p)==3 && s.budget==1 && s.stage==CS_MT_ANSWER_PENDING);
 assert(p[0].bytes[1]==8 && p[1].bytes[1]==1 && p[2].bytes[1]==7);
 assert(p[0].length==2 && p[1].length==2 && p[2].length==2 && p[2].bytes[0]==0x83);
 assert(!cs_mt_receive(&s,3,5,1,p)); /* retransmission cannot answer again */
 assert(!cs_mt_receive(&s,0x83,15,1,p) && s.stage==CS_MT_ANSWER_PENDING);
 assert(!cs_mt_receive(&s,3,15,1,p) && s.stage==CS_MT_CONNECTED);
 assert(!cs_mt_receive(&s,3,5,1,p) && s.stage==CS_MT_CONNECTED);
 assert(cs_mt_hangup(&s,p)==1 && s.stage==CS_MT_DISCONNECTING);
 assert(p[0].length==5 && p[0].bytes[1]==0x25);
 assert(!cs_wire_metadata(p[0].bytes,5,5,&m) && m.cause==16);
 assert(!cs_mt_hangup(&s,p));
 assert(cs_mt_receive(&s,3,0x2d,0,p)==1 && s.stage==CS_MT_MM_CLEARING && p[0].bytes[1]==0x2a);
 s.stage=0;assert(!cs_mt_receive(&s,3,5,1,p) && s.budget==1);
 s=(struct cs_mt_state){0};assert(cs_mt_receive(&s,3,5,1,p)==3);
 assert(cs_mt_receive(&s,3,0x25,0,p)==1 && s.stage==CS_MT_RELEASING);
 assert(p[0].length==6 && p[0].bytes[1]==0x2d);
 assert(!cs_wire_metadata(p[0].bytes,6,6,&m) && m.cause==16);
 assert(!cs_mt_receive(&s,3,0x2a,0,p) && s.stage==CS_MT_MM_CLEARING);
 assert(!cs_mt_receive(&s,3,15,1,p) && s.stage==CS_MT_MM_CLEARING);
 s=(struct cs_mt_state){0};assert(!cs_mt_receive(&s,3,0x2d,0,p) && !s.stage);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'check.c').write_text(source)
 subprocess.run(['docker','run','--rm','-v',str(BASE/'src')+':/src:ro','-v',str(p)+':/check:ro',
 'mf79u-system-tools:local','sh','-eu','-c',
 'gcc -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined -I/src /check/check.c -o /tmp/check\n/tmp/check'],check=True,timeout=30)
report={'single_answer_and_no_retransmission_answer':True,'connect_requires_network_ack':True,
 'only_ti0':True,'no_answer_after_window':True,'disconnect_cause_lv_verified':True,
 'release_cause_tlv_verified':True,'mm_clearing_required':True,'sanitizers':True,'hardware_test':False}
(BASE/'build/cs-mt-state-fixture.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
