#!/usr/bin/env python3
"""Check selective Cause reads and one-call MO transitions, without a modem."""
from pathlib import Path
import json,subprocess,tempfile
BASE=Path(__file__).resolve().parent
source=r'''
#include <assert.h>
#include <string.h>
#include "cs-wire.h"
#include "cs-wcdma-codec.h"
#include "cs-mo-state.h"
#include "cs-mt-state.h"
#include "cs-dtmf-tone.h"
static void clearing(const unsigned char *p,unsigned n,unsigned ti,unsigned type) {
 struct cs_wire_metadata m;
 assert(!cs_wire_metadata(p,n,n,&m));
 assert(m.pd==3 && m.ti==ti && m.type==type);
 assert(m.cause_present && m.cause==16 && m.coding==3 && m.location==0);
}
int main(void) {
 struct cs_wire_metadata m;
 unsigned char offer[32]={3,5};
 const unsigned char nb[]={0x40,6,0,1,0x1f,4,1,0x60};
 assert(cs_wcdma_codec_offer(offer,2,32,2)==2 && offer[2]==0);
 assert(cs_wcdma_codec_offer(offer,2,9,3)==0 && offer[2]==0);
 assert(cs_wcdma_codec_offer(offer,2,32,3)==10 && !memcmp(offer+2,nb,8));
 offer[1]=8;assert(cs_wcdma_codec_offer(offer,2,32,3)==10 && !memcmp(offer+2,nb,8));
 offer[1]=1;assert(cs_wcdma_codec_offer(offer,2,32,3)==2);
 assert(!cs_wcdma_codec_offer(offer,33,32,3));
 unsigned char d[]={0x83,0x25,2,0x82,0x90};
 assert(cs_wire_metadata(d,5,5,&m)==0 && m.cause_present && m.cause==16 && m.location==2);
 for(unsigned i=0;i<5;i++)assert(cs_wire_metadata(d,i,5,&m)<0);
 unsigned char r[]={0x83,0x2d,8,3,0x02,0x80,0xa9};
 assert(!cs_wire_metadata(r,7,7,&m) && m.cause==41 && m.coding==0);
 r[4]=0x82;
 assert(!cs_wire_metadata(r,7,7,&m) && m.cause==0);
 r[3]=4;assert(cs_wire_metadata(r,7,7,&m)<0);
 r[3]=3;r[4]=0x02;r[5]=0;assert(cs_wire_metadata(r,7,7,&m)<0);
 unsigned char setup[]={0x83,5,0xff};
 assert(!cs_wire_metadata(setup,2,100,&m) && !m.cause_present);
 setup[0]=0xf3;setup[1]=0x25;
 assert(!cs_wire_metadata(setup,2,100,&m) && !m.cause_present);
 unsigned char numbered[]={5,0x59};
 assert(!cs_wire_metadata(numbered,2,2,&m) && m.pd==5 && m.type==0x19 && m.nsd==1);
 numbered[1]=0xc5;assert(!cs_wire_metadata(numbered,2,2,&m) && m.type==5 && m.nsd==3);
 unsigned char mm[]={5,0x25};
 assert(!cs_wire_metadata(mm,2,2,&m) && !m.cause_present);
 struct cs_mo_state s={0};struct cs_mo_packet p;
 assert(cs_mo_begin(&s,(const unsigned char *)"112",3)<0);
 assert(cs_mo_begin(&s,(const unsigned char *)"12;45",5)<0);
 assert(!cs_mo_begin(&s,(const unsigned char *)"55501234",8));
 assert(s.stage==CS_MO_MM_PENDING && s.budget==1);
 assert(!cs_mo_receive(&s,3,5,&p)); /* MT never answered */
 assert(cs_mo_established(&s,&p)==1 && s.stage==CS_MO_SETUP && s.number_length==0);
 const unsigned char expected[]={3,5,4,6,0x60,4,5,2,0,0x81,0x5e,5,0x81,0x55,0x05,0x21,0x43};
 assert(p.length==sizeof(expected) && !memcmp(p.bytes,expected,sizeof(expected)));
 assert(!cs_mo_established(&s,&p)); /* duplicate MM confirm never repeats SETUP */
 assert(!cs_mo_receive(&s,0x83,2,&p) && s.stage==CS_MO_PROCEEDING);
 assert(!cs_mo_receive(&s,0x83,1,&p) && s.stage==CS_MO_ALERTING);
 assert(cs_mo_receive(&s,0x83,7,&p)==1 && s.stage==CS_MO_CONNECTED && p.bytes[1]==15 && p.length==2);
 assert(!cs_mo_receive(&s,0x83,7,&p)); /* duplicate CONNECT */
 assert(cs_mo_hangup(&s,&p)==1 && p.bytes[1]==0x25 && p.length==5);
 clearing(p.bytes,p.length,0,0x25);
 assert(!cs_mo_hangup(&s,&p));
 assert(cs_mo_receive(&s,0x83,0x2d,&p)==1 && p.bytes[1]==0x2a && s.stage==CS_MO_MM_CLEARING);
 s.stage=0;assert(cs_mo_begin(&s,(const unsigned char *)"55501234",8)<0); /* budget exhausted */
 s=(struct cs_mo_state){0};
 assert(!cs_mo_begin(&s,(const unsigned char *)"55501",5));
 assert(cs_mo_established(&s,&p) && p.bytes[p.length-1]==0xf1);
 assert(cs_mo_receive(&s,0x83,0x25,&p)==1 && p.bytes[1]==0x2d && p.length==6);
 clearing(p.bytes,p.length,0,0x2d);
 assert(!cs_mo_receive(&s,0x83,0x2a,&p) && s.stage==CS_MO_MM_CLEARING);
 struct cs_mt_state mt={0};struct cs_mt_packet mp[3];
 assert(cs_mt_receive(&mt,3,5,1,mp)==3);
 assert(!cs_mt_receive(&mt,3,15,1,mp) && mt.stage==CS_MT_CONNECTED);
 assert(cs_mt_hangup(&mt,mp));clearing(mp[0].bytes,mp[0].length,8,0x25);
 assert(cs_mt_receive(&mt,3,0x25,1,mp)==1);
 clearing(mp[0].bytes,mp[0].length,8,0x2d);
 struct cs_dtmf_tone tone={0};
 assert(!cs_dtmf_tick(&tone,0,10,10,&p) && !tone.stage);
 assert(!cs_dtmf_tick(&tone,1,1,20,&p));
 assert(cs_dtmf_tick(&tone,1,2,21,&p) && p.length==4);
 assert(p.bytes[0]==3 && p.bytes[1]==0x35 && p.bytes[2]==0x2c && p.bytes[3]=='5');
 assert(!cs_dtmf_tick(&tone,1,4,23,&p)); /* no STOP before ACK */
 cs_dtmf_receive(&tone,1,3,0x36,23);assert(tone.stage==CS_DTMF_START_PENDING);
 cs_dtmf_receive(&tone,1,0x83,0x36,23);assert(tone.stage==CS_DTMF_ACTIVE);
 assert(!cs_dtmf_tick(&tone,1,5,24,&p));
 assert(cs_dtmf_tick(&tone,1,6,25,&p) && p.length==2 && p.bytes[1]==0x31);
 cs_dtmf_receive(&tone,1,0x83,0x36,25);assert(tone.stage==CS_DTMF_STOP_PENDING);
 cs_dtmf_receive(&tone,1,0x83,0x32,26);assert(tone.stage==CS_DTMF_DONE);
 assert(!cs_dtmf_tick(&tone,1,99,119,&p)); /* never repeat tone */
 tone=(struct cs_dtmf_tone){0};assert(cs_dtmf_tick(&tone,1,2,2,&p));
 assert(!cs_dtmf_tick(&tone,1,8,8,&p) && tone.stage==CS_DTMF_FAILED);
 cs_dtmf_receive(&tone,1,0x83,0x36,9);assert(tone.stage==CS_DTMF_FAILED);
 tone=(struct cs_dtmf_tone){0};assert(cs_dtmf_tick(&tone,1,2,2,&p));
 cs_dtmf_receive(&tone,1,0x83,0x37,3);assert(tone.stage==CS_DTMF_FAILED);
 tone=(struct cs_dtmf_tone){0};assert(cs_dtmf_tick(&tone,1,2,2,&p));
 cs_dtmf_receive(&tone,1,0x83,0x36,3);assert(cs_dtmf_tick(&tone,1,5,5,&p));
 assert(!cs_dtmf_tick(&tone,0,6,6,&p) && tone.stage==CS_DTMF_FAILED);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'check.c').write_text(source)
 subprocess.run(['docker','run','--rm','-v',str(BASE/'src')+':/src:ro','-v',str(p)+':/check:ro',
  'mf79u-system-tools:local','sh','-eu','-c',
  'gcc -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined -I/src /check/check.c -o /tmp/check\n/tmp/check'],check=True,timeout=30)
r={'cause_lv_tlv_bounds':True,'cause_recommendation_bounds':True,'gsm_plmn_cause_coding_mo_mt':True,'no_identity_decode':True,'nas_sequence_metadata':True,
   'separate_mm_before_setup':True,'normal_speech_bcd':True,'no_incoming_answer':True,
   'single_call_budget':True,'clear_and_connect_ack':True,'address_undefined_sanitizers':True,
   'network_dtmf_wire_and_ack_order':True,'dtmf_no_repeat_and_timeouts':True,
   'hardware_test':False}
(BASE/'build/cs-wire-mo-fixture.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
