/* GSM CS call state used by the persistent driver. MM/audio quiescence is
 * acknowledged by the driver before this object can be reused. */
#ifndef MF79U_CS_CALL_STATE_H
#define MF79U_CS_CALL_STATE_H
#include "cs-mo-state.h"
enum { CS_CALL_RINGING=9,CS_CALL_ANSWER_PENDING=10 };
struct cs_call_state {struct cs_mo_state mo;unsigned int incoming,tx_header,rx_header,international;};
static void cs_call_init(struct cs_call_state *s) {
    cs_mo_forget(&s->mo);s->mo.stage=s->mo.budget=0;
    s->incoming=0;s->tx_header=3;s->rx_header=0x83;s->international=0;
}
static int cs_call_begin(struct cs_call_state *s,const unsigned char *number,unsigned n) {
    if(s->mo.stage || s->mo.budget)return -1;
    s->incoming=0;s->tx_header=3;s->rx_header=0x83;
    s->international=n && number[0]=='+';
    if(s->international){number++;n--;}
    return cs_mo_begin(&s->mo,number,n);
}
static void cs_call_packet(struct cs_call_state *s,struct cs_mo_packet *p,unsigned type,int cause) {
    cs_mo_simple(p,type,cause);p->bytes[0]=(unsigned char)s->tx_header;
}
static int cs_call_established(struct cs_call_state *s,struct cs_mo_packet *p) {
    if(s->incoming)return 0;
    int n=cs_mo_established(&s->mo,p);if(n){p->bytes[0]=(unsigned char)s->tx_header;if(s->international)p->bytes[12]=0x91;}
    return n;
}
static int cs_call_receive(struct cs_call_state *s,unsigned header,unsigned type,
                           int admit_incoming,struct cs_mo_packet p[2]) {
    p[0].length=p[1].length=0;
    if((header&15U)!=3U || (header&0x70U)==0x70U)return 0;
    if(!s->mo.stage) {
        if(type!=5U || (header&0x80U) || !admit_incoming || s->mo.budget)return 0;
        s->incoming=1;s->rx_header=header;s->tx_header=header^0x80U;
        s->mo.budget=1;s->mo.stage=CS_CALL_RINGING;
        cs_call_packet(s,&p[0],8,0);cs_call_packet(s,&p[1],1,0);return 2;
    }
    if(header!=s->rx_header)return 0;
    if(type==0x2dU) {
        cs_call_packet(s,&p[0],0x2a,0);s->mo.stage=CS_MO_MM_CLEARING;cs_mo_forget(&s->mo);return 1;
    }
    if(type==0x2aU) {s->mo.stage=CS_MO_MM_CLEARING;cs_mo_forget(&s->mo);return 0;}
    if(type==0x25U && s->mo.stage!=CS_MO_MM_CLEARING) {
        cs_call_packet(s,&p[0],0x2d,1);s->mo.stage=CS_MO_RELEASING;return 1;
    }
    if(s->incoming) {
        if(type==5U && s->mo.stage==CS_CALL_RINGING) {
            cs_call_packet(s,&p[0],8,0);cs_call_packet(s,&p[1],1,0);return 2;
        }
        if(type==15U && s->mo.stage==CS_CALL_ANSWER_PENDING)s->mo.stage=CS_MO_CONNECTED;
        return 0;
    }
    if(type==7U && s->mo.stage==CS_MO_CONNECTED) {
        /* Retransmitted network CONNECT gets an ACK, without a new call. */
        cs_call_packet(s,&p[0],15,0);return 1;
    }
    int n=cs_mo_receive(&s->mo,0x83,type,&p[0]);
    if(n)p[0].bytes[0]=(unsigned char)s->tx_header;
    return n;
}
static int cs_call_answer(struct cs_call_state *s,struct cs_mo_packet *p) {
    if(!s->incoming || s->mo.stage!=CS_CALL_RINGING)return 0;
    cs_call_packet(s,p,7,0);s->mo.stage=CS_CALL_ANSWER_PENDING;return 1;
}
static int cs_call_hangup(struct cs_call_state *s,struct cs_mo_packet *p) {
    if(!s->incoming) {
        int n=cs_mo_hangup(&s->mo,p);if(n)p->bytes[0]=(unsigned char)s->tx_header;return n;
    }
    if(s->mo.stage==CS_CALL_RINGING || s->mo.stage==CS_CALL_ANSWER_PENDING ||
       (s->mo.stage>=CS_MO_SETUP && s->mo.stage<=CS_MO_CONNECTED)) {
        cs_call_packet(s,p,0x25,1);s->mo.stage=CS_MO_DISCONNECTING;return 1;
    }
    return 0;
}
#endif
