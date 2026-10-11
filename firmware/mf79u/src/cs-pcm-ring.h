/* Bounded raw I2S-word queue. Caller owns synchronization; no allocations. */
#ifndef MF79U_CS_PCM_RING_H
#define MF79U_CS_PCM_RING_H
#define CS_PCM_FRAME_WORDS 80U
#define CS_PCM_RING_WORDS 1024U
struct cs_pcm_ring { u32 words[CS_PCM_RING_WORDS],read,write,dropped; };
static inline void cs_pcm_ring_clear(struct cs_pcm_ring *q) {
    for(u32 i=0;i<CS_PCM_RING_WORDS;i++)((volatile u32 *)q->words)[i]=0;
    q->read=q->write=q->dropped=0;
}
static inline u32 cs_pcm_ring_used(const struct cs_pcm_ring *q) {return q->write-q->read;}
static inline int cs_pcm_ring_push(struct cs_pcm_ring *q,u32 word,int drop_old) {
    if(cs_pcm_ring_used(q)==CS_PCM_RING_WORDS) {
        if(!drop_old)return 0;
        q->words[q->read++&(CS_PCM_RING_WORDS-1U)]=0;q->dropped++;
    }
    q->words[q->write++&(CS_PCM_RING_WORDS-1U)]=word;return 1;
}
static inline int cs_pcm_ring_pop(struct cs_pcm_ring *q,u32 *word) {
    if(!cs_pcm_ring_used(q))return 0;
    u32 i=q->read++&(CS_PCM_RING_WORDS-1U);
    *word=q->words[i];q->words[i]=0;return 1;
}
/* Hardware FIFO puts the first mono sample in the high halfword. The
 * userspace boundary is explicitly 160 PCM16LE samples at 8 kHz/20 ms;
 * the SIP adapter resamples to the unchanged 16 kHz/320-sample contract. */
static inline u32 cs_pcm_unpack(const u8 *p) {
    return ((u32)p[0]|(u32)p[1]<<8)<<16|((u32)p[2]|(u32)p[3]<<8);
}
static inline void cs_pcm_pack(u8 *p,u32 word) {
    p[0]=(u8)(word>>16);p[1]=(u8)(word>>24);p[2]=(u8)word;p[3]=(u8)(word>>8);
}
#endif
