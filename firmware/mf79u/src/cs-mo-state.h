/* SPDX-License-Identifier: GPL-2.0-only
 * Single normal outgoing TI0 GSM call diagnostic. Number kept only in RAM.
 * MM establishment is a separate primitive before SETUP. No incoming answer.
 * This is a signaling probe; no claim of a working voice/audio backend.
 */
#ifndef MF79U_CS_MO_STATE_H
#define MF79U_CS_MO_STATE_H
enum cs_mo_stage { CS_MO_IDLE,CS_MO_MM_PENDING,CS_MO_SETUP,CS_MO_PROCEEDING,
    CS_MO_ALERTING,CS_MO_CONNECTED,CS_MO_DISCONNECTING,CS_MO_RELEASING,CS_MO_MM_CLEARING };
struct cs_mo_state { unsigned int stage,budget,number_length;unsigned char number[32]; };
struct cs_mo_packet { unsigned int length;unsigned char bytes[64]; };
static void cs_mo_forget(struct cs_mo_state *s) {
    for(unsigned int i=0;i<32;i++)s->number[i]=0;
    s->number_length=0;
}
static int cs_mo_begin(struct cs_mo_state *s,const unsigned char *number,unsigned int n) {
    if(!s || !number || s->budget || s->stage || n<5 || n>32)return -1;
    for(unsigned int i=0;i<n;i++)if(number[i]<'0' || number[i]>'9')return -1;
    /* Short/emergency/service numbers and supplementary commands are excluded. */
    for(unsigned int i=0;i<n;i++)s->number[i]=number[i];
    s->number_length=n;s->budget=1;s->stage=CS_MO_MM_PENDING;return 0;
}
static int cs_mo_established(struct cs_mo_state *s,struct cs_mo_packet *p) {
    if(s->stage!=CS_MO_MM_PENDING || !s->number_length)return 0;
    /* Bearer capability: speech, circuit, GSM, full/half rate; AMR-FR,
     * AMR-HR, EFR, FR, HR. Called number is unknown TON/ISDN numbering plan. */
    static const unsigned char head[]={0x03,0x05,0x04,0x06,0x60,0x04,0x05,0x02,0x00,0x81,0x5e};
    unsigned int n=s->number_length,j=sizeof(head);
    for(unsigned int i=0;i<j;i++)p->bytes[i]=head[i];
    p->bytes[j++]=(unsigned char)(1U+(n+1U)/2U);p->bytes[j++]=0x81;
    for(unsigned int i=0;i<n;i+=2) {
        unsigned int high=i+1U<n?(unsigned int)(s->number[i+1U]-'0'):15U;
        p->bytes[j++]=(unsigned char)((s->number[i]-'0')|(high<<4));
    }
    p->length=j;s->stage=CS_MO_SETUP;cs_mo_forget(s);return 1;
}
static void cs_mo_simple(struct cs_mo_packet *p,unsigned int type,int cause) {
    p->bytes[0]=3;p->bytes[1]=(unsigned char)type;p->length=2;
    if(cause) {
        unsigned int j=2;
        if(type!=0x25U)p->bytes[j++]=8;
        /* TS24.008 10.5.4.11: ext=1, coding=GSM PLMN(3), location=user(0).
         * Q.931 coding(0) is not required to be supported by the GSM peer. */
        p->bytes[j++]=2;p->bytes[j++]=0xe0;p->bytes[j++]=0x90;p->length=j;
    }
}
static int cs_mo_receive(struct cs_mo_state *s,unsigned int header,unsigned int type,
                         struct cs_mo_packet *p) {
    /* Only network responses to our MO TI0. MT SETUP is never answered. */
    if(!s->stage || header!=0x83U)return 0;
    if(type==0x2dU) {cs_mo_simple(p,0x2aU,0);s->stage=CS_MO_MM_CLEARING;cs_mo_forget(s);return 1;}
    if(type==0x2aU) {s->stage=CS_MO_MM_CLEARING;cs_mo_forget(s);return 0;}
    if(type==0x25U) {cs_mo_simple(p,0x2dU,1);s->stage=CS_MO_RELEASING;return 1;}
    if(s->stage>=CS_MO_DISCONNECTING)return 0;
    if(type==2U && s->stage==CS_MO_SETUP)s->stage=CS_MO_PROCEEDING;
    if(type==1U && (s->stage==CS_MO_SETUP || s->stage==CS_MO_PROCEEDING))s->stage=CS_MO_ALERTING;
    if(type==7U && s->stage>=CS_MO_SETUP && s->stage<=CS_MO_ALERTING) {
        cs_mo_simple(p,0xfU,0);s->stage=CS_MO_CONNECTED;return 1;
    }
    return 0;
}
static int cs_mo_hangup(struct cs_mo_state *s,struct cs_mo_packet *p) {
    if(s->stage>=CS_MO_SETUP && s->stage<CS_MO_DISCONNECTING) {
        cs_mo_simple(p,0x25U,1);s->stage=CS_MO_DISCONNECTING;return 1;
    }
    return 0;
}
#endif
