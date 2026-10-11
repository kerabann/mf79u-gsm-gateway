#ifndef MF79U_PCM_QUEUE_H
#define MF79U_PCM_QUEUE_H
#include <stdint.h>
#include <string.h>
#define MF79U_PCM_SAMPLES 320
#define MF79U_PCM_QUEUE 16
#define MF79U_PCM_PREFILL 3
/* Preserve every frame in bursts, then play one frame per 20ms clock tick.
 * A bounded queue adds 60ms initially and never accumulates unbounded latency. */
struct mf79u_pcm_queue {
    int16_t frames[MF79U_PCM_QUEUE][MF79U_PCM_SAMPLES];
    unsigned head,count,started,high_water;
    unsigned samples; /* 0 retains the original 8kHz / 160-sample default. */
    unsigned long received,played,underflows,overflows;
};
static inline void mf79u_pcm_push(struct mf79u_pcm_queue *q,const void *pcm){
    if(q->count==MF79U_PCM_QUEUE){q->head=(q->head+1)%MF79U_PCM_QUEUE;q->count--;q->overflows++;}
    memcpy(q->frames[(q->head+q->count)%MF79U_PCM_QUEUE],pcm,(q->samples?q->samples:160)*2);
    q->count++;q->received++;if(q->count>q->high_water)q->high_water=q->count;
}
/* 1=real audio, 0=initial buffering, -1=starved (caller applies PLC). */
static inline int mf79u_pcm_pop(struct mf79u_pcm_queue *q,void *pcm){
    if(!q->started){if(q->count<MF79U_PCM_PREFILL)return 0;q->started=1;}
    if(!q->count){q->underflows++;return -1;}
    memcpy(pcm,q->frames[q->head],(q->samples?q->samples:160)*2);q->head=(q->head+1)%MF79U_PCM_QUEUE;
    q->count--;q->played++;return 1;
}
#endif
