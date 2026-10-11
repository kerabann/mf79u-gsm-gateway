/* One producer and one consumer per queue. Producer never advances read;
 * consumer never advances write. Release/acquire publishes complete data. */
#ifndef MF79U_CS_PCM_SPSC_H
#define MF79U_CS_PCM_SPSC_H
#include "cs-pcm-ring.h"
static inline int cs_pcm_spsc_push(struct cs_pcm_ring *q,u32 word) {
    u32 w=__atomic_load_n(&q->write,__ATOMIC_RELAXED);
    u32 r=__atomic_load_n(&q->read,__ATOMIC_ACQUIRE);
    if(w-r==CS_PCM_RING_WORDS){q->dropped++;return 0;}
    q->words[w&(CS_PCM_RING_WORDS-1U)]=word;
    __atomic_store_n(&q->write,w+1,__ATOMIC_RELEASE);return 1;
}
static inline int cs_pcm_spsc_pop(struct cs_pcm_ring *q,u32 *word) {
    u32 r=__atomic_load_n(&q->read,__ATOMIC_RELAXED);
    u32 w=__atomic_load_n(&q->write,__ATOMIC_ACQUIRE);
    if(w==r)return 0;
    u32 at=r&(CS_PCM_RING_WORDS-1U);*word=q->words[at];q->words[at]=0;
    __atomic_store_n(&q->read,r+1,__ATOMIC_RELEASE);return 1;
}
static inline int cs_pcm_spsc_read_frame(struct cs_pcm_ring *q,u8 *out) {
    u32 r=__atomic_load_n(&q->read,__ATOMIC_RELAXED);
    u32 w=__atomic_load_n(&q->write,__ATOMIC_ACQUIRE);
    if(w-r<CS_PCM_FRAME_WORDS)return 0;
    for(u32 i=0;i<CS_PCM_FRAME_WORDS;i++) {
        u32 at=(r+i)&(CS_PCM_RING_WORDS-1U);cs_pcm_pack(out+4*i,q->words[at]);q->words[at]=0;
    }
    __atomic_store_n(&q->read,r+CS_PCM_FRAME_WORDS,__ATOMIC_RELEASE);return 1;
}
static inline int cs_pcm_spsc_write_frame(struct cs_pcm_ring *q,const u8 *in) {
    u32 w=__atomic_load_n(&q->write,__ATOMIC_RELAXED);
    u32 r=__atomic_load_n(&q->read,__ATOMIC_ACQUIRE);
    if(CS_PCM_RING_WORDS-(w-r)<CS_PCM_FRAME_WORDS)return 0;
    for(u32 i=0;i<CS_PCM_FRAME_WORDS;i++)q->words[(w+i)&(CS_PCM_RING_WORDS-1U)]=cs_pcm_unpack(in+4*i);
    __atomic_store_n(&q->write,w+CS_PCM_FRAME_WORDS,__ATOMIC_RELEASE);return 1;
}
#endif
