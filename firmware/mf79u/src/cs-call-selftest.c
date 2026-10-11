#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "cs-call-state.h"
#include "cs-caller.h"
#include "voice-registration-policy.h"
int main(void){
    struct cs_call_state s={0};struct cs_mo_packet p[2];cs_call_init(&s);
    assert(!cs_call_receive(&s,0x73,5,1,p)); /* extended TI not supported */
    assert(!cs_call_receive(&s,0x23,5,0,p));
    assert(cs_call_receive(&s,0x23,5,1,p)==2 && s.mo.stage==9);
    assert(p[0].bytes[0]==0xa3 && p[0].bytes[1]==8 && p[1].bytes[1]==1);
    assert(cs_call_receive(&s,0x23,5,1,p)==2 && s.mo.stage==9);
    assert(!cs_call_receive(&s,3,0x2d,1,p) && s.mo.stage==9);
    assert(cs_call_answer(&s,p)==1 && p[0].bytes[1]==7 && s.mo.stage==10);
    assert(!cs_call_answer(&s,p));
    assert(!cs_call_receive(&s,0x23,15,1,p) && s.mo.stage==5);
    assert(cs_call_hangup(&s,p)==1 && p[0].bytes[0]==0xa3 && p[0].bytes[3]==0xe0);
    assert(cs_call_receive(&s,0x23,0x2d,1,p)==1 && s.mo.stage==8);
    assert(cs_call_begin(&s,(const unsigned char *)"1234567",7)<0);
    cs_call_init(&s);assert(!cs_call_begin(&s,(const unsigned char *)"+1234567",8));
    assert(cs_call_established(&s,p) && p[0].bytes[12]==0x91);
    assert(cs_call_receive(&s,0x83,7,0,p)==1 && s.mo.stage==5);
    assert(cs_call_receive(&s,0x83,7,0,p)==1 && s.mo.stage==5);
    assert(cs_call_hangup(&s,p)==1);
    assert(cs_call_receive(&s,0x83,0x2d,0,p)==1);
    cs_call_init(&s);assert(!cs_call_begin(&s,(const unsigned char *)"7654321",7));
    unsigned char raw[]={3,5,0x04,1,0x80,0x5c,5,0x11,0x80,0x21,0x43,0xf5};char caller[34];
    assert(cs_calling_number(raw,sizeof(raw),caller) && !strcmp(caller,"+12345"));
    raw[8]=0xa0;assert(!cs_calling_number(raw,sizeof(raw),caller) && !strcmp(caller,"anonymous"));
    raw[8]=0x80;raw[6]=6;assert(!cs_calling_number(raw,sizeof(raw),caller));
    enum voice_mode m;assert(!strcmp(voice_mode_name(VOICE_AUTO),"AUTO"));assert(!voice_mode_parse("CS",&m) && m==VOICE_CS);
    assert(voice_mode_parse("UMTS",&m)<0);
    assert(voice_mode_parse("INVALID",&m)<0);
    assert(voice_registration_target(VOICE_AUTO,1,10,100,0)==2);
    assert(voice_registration_target(VOICE_AUTO,2,10,100,0)==2);
    assert(voice_registration_target(VOICE_AUTO,1,100,100,0)==1);
    assert(voice_registration_target(VOICE_VOLTE,1,10,100,0)==1);
    assert(voice_registration_target(VOICE_CS,0,100,0,0)==2);
    assert(voice_registration_target(VOICE_VOLTE,0,100,0,2)==2);
    puts("PASS deferred MT answer, transaction ownership, retransmission, clearing/reuse, international dialing, caller privacy and registration policy");
}
