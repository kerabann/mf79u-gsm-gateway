/* SPDX-License-Identifier: GPL-2.0-only
 * Separate one-answer TI0 diagnostic. No number decoding or outgoing SETUP.
 * MM clearing is acknowledged by real MM state outside this packet machine.
 */
#ifndef MF79U_CS_MT_STATE_H
#define MF79U_CS_MT_STATE_H
enum { CS_MT_IDLE,CS_MT_ANSWER_PENDING,CS_MT_RELEASING,CS_MT_CONNECTED,
       CS_MT_DISCONNECTING,CS_MT_MM_CLEARING };
struct cs_mt_state { unsigned int stage,budget; };
struct cs_mt_packet { unsigned int length;unsigned char bytes[6]; };
static void cs_mt_packet(unsigned int type,struct cs_mt_packet *p) {
    p->bytes[0]=0x83;p->bytes[1]=(unsigned char)type;p->length=2;
    if(type==0x25U) {
        /* DISCONNECT mandatory Cause is LV, unlike RELEASE's optional TLV. */
        p->bytes[2]=2;p->bytes[3]=0xe0;p->bytes[4]=0x90;p->length=5;
    } else if(type==0x2dU) {
        p->bytes[2]=8;p->bytes[3]=2;p->bytes[4]=0xe0;p->bytes[5]=0x90;p->length=6;
    }
}
static int cs_mt_receive(struct cs_mt_state *s,unsigned int header,unsigned int type,
                         int answer_window,struct cs_mt_packet p[3]) {
    for(unsigned int i=0;i<3;i++)p[i].length=0;
    if(header!=3U)return 0;
    switch(type) {
    case 5:
        if(s->budget || s->stage || !answer_window)return 0;
        s->budget=1;s->stage=CS_MT_ANSWER_PENDING;
        cs_mt_packet(8,&p[0]);cs_mt_packet(1,&p[1]);cs_mt_packet(7,&p[2]);return 3;
    case 15: /* CONNECT ACK, not just our enqueued CONNECT. */
        if(s->stage==CS_MT_ANSWER_PENDING)s->stage=CS_MT_CONNECTED;
        return 0;
    case 0x25:
        if(!s->stage || s->stage==CS_MT_MM_CLEARING)return 0;
        cs_mt_packet(0x2d,&p[0]);s->stage=CS_MT_RELEASING;return 1;
    case 0x2d:
        if(!s->budget)return 0;
        cs_mt_packet(0x2a,&p[0]);s->stage=CS_MT_MM_CLEARING;return 1;
    case 0x2a:
        if(s->stage)s->stage=CS_MT_MM_CLEARING;
        return 0;
    default:return 0;
    }
}
static int cs_mt_hangup(struct cs_mt_state *s,struct cs_mt_packet *p) {
    p->length=0;
    if(s->stage!=CS_MT_ANSWER_PENDING && s->stage!=CS_MT_CONNECTED)return 0;
    cs_mt_packet(0x25,p);s->stage=CS_MT_DISCONNECTING;return 1;
}
#endif
