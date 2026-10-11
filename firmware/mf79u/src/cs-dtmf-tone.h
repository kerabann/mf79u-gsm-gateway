/* SPDX-License-Identifier: GPL-2.0-only
 * One bounded network DTMF diagnostic per outgoing connection. TS24.008
 * START/STOP DTMF are call-control signaling, not a PCM/DSP media backend.
 * Requires cs-mo-state.h. No retry and no STOP before START ACK.
 */
#ifndef MF79U_CS_DTMF_TONE_H
#define MF79U_CS_DTMF_TONE_H
enum cs_dtmf_stage { CS_DTMF_UNUSED,CS_DTMF_START_PENDING,CS_DTMF_ACTIVE,
    CS_DTMF_STOP_PENDING,CS_DTMF_DONE,CS_DTMF_FAILED };
struct cs_dtmf_tone { unsigned int stage,started,acknowledged,stopped; };
static int cs_dtmf_tick(struct cs_dtmf_tone *s,unsigned int connected,
                        unsigned int age,unsigned int now,struct cs_mo_packet *p) {
    if(!connected) {
        if(s->stage && s->stage<CS_DTMF_DONE)s->stage=CS_DTMF_FAILED;
        return 0;
    }
    if(!s->stage && age>=2U) {
        cs_mo_simple(p,0x35U,0);p->bytes[2]=0x2cU;p->bytes[3]='5';p->length=4;
        s->stage=CS_DTMF_START_PENDING;s->started=now;return 1;
    }
    if(s->stage==CS_DTMF_ACTIVE && now-s->acknowledged>=2U) {
        cs_mo_simple(p,0x31U,0);s->stage=CS_DTMF_STOP_PENDING;s->stopped=now;return 1;
    }
    if((s->stage==CS_DTMF_START_PENDING && now-s->started>=6U) ||
       (s->stage==CS_DTMF_STOP_PENDING && now-s->stopped>=6U))s->stage=CS_DTMF_FAILED;
    return 0;
}
static void cs_dtmf_receive(struct cs_dtmf_tone *s,unsigned int connected,
                           unsigned int header,unsigned int type,unsigned int now) {
    if(!connected || header!=0x83U)return;
    if(s->stage==CS_DTMF_START_PENDING && type==0x36U) {
        s->stage=CS_DTMF_ACTIVE;s->acknowledged=now;
    } else if(s->stage==CS_DTMF_START_PENDING && type==0x37U)s->stage=CS_DTMF_FAILED;
    else if(s->stage==CS_DTMF_STOP_PENDING && type==0x32U)s->stage=CS_DTMF_DONE;
}
#endif
