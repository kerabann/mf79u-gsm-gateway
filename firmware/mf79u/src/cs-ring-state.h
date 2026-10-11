/* SPDX-License-Identifier: GPL-2.0-only
 * Small CS MT-call experiment. This stage admits only the observed TI0 model.
 * It can confirm/alert/release an incoming call; CONNECT and SETUP cannot be sent.
 * No numbers, bearer codec selection, audio or SIP bridge are implemented here.
 */
#ifndef MF79U_CS_RING_STATE_H
#define MF79U_CS_RING_STATE_H
struct cs_ring_state { unsigned int state; };
struct cs_ring_packet { unsigned int length; unsigned char bytes[6]; };
enum { CS_RING_IDLE,CS_RING_ALERTING,CS_RING_RELEASING };
static int cs_ring_packet(unsigned int type,struct cs_ring_packet *packet) {
    /* The received network-assigned TI0 has flag0; replies use flag1. */
    packet->length=0;
    if(type!=0x08U && type!=0x01U && type!=0x2dU && type!=0x2aU)return -1;
    packet->bytes[0]=0x83;packet->bytes[1]=(unsigned char)type;packet->length=2;
    if(type==0x2dU) {
        packet->bytes[2]=0x08;packet->bytes[3]=2;
        packet->bytes[4]=0xe0;packet->bytes[5]=0x90; /* GSM PLMN, user, cause16 */
        packet->length=6;
    }
    return 0;
}
static int cs_ring_receive(struct cs_ring_state *state,unsigned int model_header,
                           unsigned int type,struct cs_ring_packet packets[2]) {
    packets[0].length=packets[1].length=0;
    /* Other TIs/flags and extended IDs wait for recovered native-field ABI. */
    if(model_header!=0x03U)return 0;
    switch(type) {
    case 0x05: /* SETUP */
        if(state->state==CS_RING_RELEASING)return 0;
        cs_ring_packet(0x08,&packets[0]);cs_ring_packet(0x01,&packets[1]);
        state->state=CS_RING_ALERTING;return 2;
    case 0x25: /* DISCONNECT */
        if(state->state==CS_RING_IDLE)return 0;
        cs_ring_packet(0x2d,&packets[0]);state->state=CS_RING_RELEASING;return 1;
    case 0x2d: /* RELEASE; acknowledge even after local state was lost */
        cs_ring_packet(0x2a,&packets[0]);state->state=CS_RING_IDLE;return 1;
    case 0x2a: /* RELEASE COMPLETE */
        state->state=CS_RING_IDLE;return 0;
    default:return 0;
    }
}
#endif
