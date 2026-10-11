/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef MF79U_CS_CHANNEL_DELTA_H
#define MF79U_CS_CHANNEL_DELTA_H
struct cs_channel_snapshot { unsigned int base,send,recv,size,flags,end; };
static int cs_channel_valid(const struct cs_channel_snapshot *s) {
    if(!(s->flags&1U) || s->size<4U || s->size>0x100000U ||
       s->send>=s->size || s->recv>=s->size ||
       ((s->base|s->size|s->send|s->recv)&3U))return 0;
    return (s->base>=0x82000000U && s->base<0x82010000U && s->size<=0x82010000U-s->base) ||
           (s->base>=0x20000000U && s->base<0x24000000U && s->size<=0x24000000U-s->base);
}
/* A complete revolution between samples cannot be detected from cursors.
 * These are lower bounds, never voice-frame or PCM throughput claims. */
static int cs_channel_delta(const struct cs_channel_snapshot *old,
                            const struct cs_channel_snapshot *now,
                            unsigned int *sent,unsigned int *received) {
    *sent=*received=0;
    if(!cs_channel_valid(old) || !cs_channel_valid(now) ||
       old->base!=now->base || old->size!=now->size || old->flags!=now->flags)return 0;
    *sent=now->send>=old->send?now->send-old->send:now->size-old->send+now->send;
    *received=now->recv>=old->recv?now->recv-old->recv:now->size-old->recv+now->recv;
    return 1;
}
#endif
