#include <stdint.h>
#include <stdio.h>
#include <assert.h>
typedef uint32_t u32;
typedef unsigned char u8;
#include "cs-pcm-ring.h"
int main(void) {
    struct cs_pcm_ring q;
    cs_pcm_ring_clear(&q);u32 word=0;
    assert(!cs_pcm_ring_pop(&q,&word));
    /* Exercise unsigned cursor wrap, full/backpressure, oldest-drop, and
     * clearing consumed speech storage across more than one ring wrap. */
    q.read=q.write=UINT32_MAX-500;
    for(u32 i=0;i<CS_PCM_RING_WORDS;i++)assert(cs_pcm_ring_push(&q,i+1,0));
    assert(!cs_pcm_ring_push(&q,9999,0));
    assert(cs_pcm_ring_push(&q,9999,1) && q.dropped==1);
    for(u32 i=1;i<CS_PCM_RING_WORDS;i++) {
        assert(cs_pcm_ring_pop(&q,&word) && word==i+1);
        assert(!q.words[(q.read-1)&(CS_PCM_RING_WORDS-1)]);
    }
    assert(cs_pcm_ring_pop(&q,&word) && word==9999);
    for(u32 i=0;i<10000;i++) {
        assert(cs_pcm_ring_push(&q,i,0));
        assert(cs_pcm_ring_pop(&q,&word) && word==i);
    }
    const u8 signed_samples[]={0x00,0x80,0xff,0x7f};u8 roundtrip[4];
    assert(cs_pcm_unpack(signed_samples)==0x80007fffU);
    cs_pcm_pack(roundtrip,cs_pcm_unpack(signed_samples));
    for(u32 i=0;i<4;i++)assert(roundtrip[i]==signed_samples[i]);
    assert(cs_pcm_ring_push(&q,0xdeadbeefU,0));cs_pcm_ring_clear(&q);
    assert(!q.read && !q.write && !q.dropped);
    for(u32 i=0;i<CS_PCM_RING_WORDS;i++)assert(!q.words[i]);
    puts("PASS PCM queue: wrap, backpressure, oldest drop, consumed/full erase, signed sample order");
    return 0;
}
