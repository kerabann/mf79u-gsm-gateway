#include <stdint.h>
#include <pthread.h>
#include <sched.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;typedef unsigned char u8;
#include "cs-pcm-spsc.h"
static struct cs_pcm_ring q;
#define FRAMES 20000U
static void *produce(void *unused) {
    (void)unused;u8 bytes[320];
    for(u32 frame=0;frame<FRAMES;frame++) {
        for(u32 i=0;i<80;i++)cs_pcm_pack(bytes+4*i,frame*80+i+1);
        while(!cs_pcm_spsc_write_frame(&q,bytes))sched_yield();
    }
    return NULL;
}
static void *consume(void *unused) {
    (void)unused;u32 word;
    for(u32 i=0;i<FRAMES*80;i++) {
        while(!cs_pcm_spsc_pop(&q,&word))sched_yield();
        assert(word==i+1);
    }
    return NULL;
}
static void *produce_words(void *unused) {
    (void)unused;
    for(u32 i=0;i<FRAMES*80;i++)while(!cs_pcm_spsc_push(&q,i+1))sched_yield();
    return NULL;
}
static void *consume_frames(void *unused) {
    (void)unused;u8 bytes[320];
    for(u32 frame=0;frame<FRAMES;frame++) {
        while(!cs_pcm_spsc_read_frame(&q,bytes))sched_yield();
        for(u32 i=0;i<80;i++)assert(cs_pcm_unpack(bytes+4*i)==frame*80+i+1);
    }
    return NULL;
}
int main(void) {
    for(int direction=0;direction<2;direction++) {
        cs_pcm_ring_clear(&q);q.read=q.write=UINT32_MAX-500;
        pthread_t p,c;
        assert(!pthread_create(&p,NULL,direction?produce_words:produce,NULL));
        assert(!pthread_create(&c,NULL,direction?consume_frames:consume,NULL));
        assert(!pthread_join(p,NULL));assert(!pthread_join(c,NULL));
        assert(q.read==q.write);
        for(u32 i=0;i<CS_PCM_RING_WORDS;i++)assert(!q.words[i]);
    }
    puts("PASS SPSC: 3.2 million ordered words, concurrent frame/word transfer, cursor wrap, consumed storage cleared");
}
