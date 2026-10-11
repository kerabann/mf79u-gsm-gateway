#include "pcm-queue.h"
#include "pcm-clock.h"
#include <stdio.h>
int main(void){
    struct mf79u_pcm_queue q={0};int16_t in[320],out[320];
    /* Bursty delivery must preserve every ordered frame, including 0-valued PCM. */
    for(int batch=0;batch<20;batch++){
        for(int j=0;j<3;j++){for(unsigned k=0;k<160;k++)in[k]=(int16_t)(batch*3+j);mf79u_pcm_push(&q,in);}
        for(int j=0;j<3;j++){
            if(mf79u_pcm_pop(&q,out)!=1)return 1;
            for(unsigned k=0;k<160;k++)if(out[k]!=batch*3+j)return 2;
        }
    }
    if(q.received!=60 || q.played!=60 || q.overflows || q.underflows)return 3;
    if(mf79u_pcm_pop(&q,out)!=-1 || q.underflows!=1)return 4;
    for(int i=0;i<20;i++){in[0]=(int16_t)i;mf79u_pcm_push(&q,in);}
    if(q.count!=16 || q.overflows!=4 || mf79u_pcm_pop(&q,out)!=1 || out[0]!=4)return 5;
    memset(&q,0,sizeof(q));q.samples=320;
    for(unsigned i=0;i<320;i++)in[i]=(int16_t)(i*13);
    for(unsigned i=0;i<3;i++)mf79u_pcm_push(&q,in);
    if(mf79u_pcm_pop(&q,out)!=1 || memcmp(in,out,sizeof(in)))return 9;
    /* 5ms work in each 20ms period must not add 250ms drift across 50 frames. */
    int64_t deadline=1000000;
    for(int i=0;i<50;i++)deadline=mf79u_pcm_deadline(deadline,deadline+5000,20000);
    if(deadline!=2000000)return 6;
    if(mf79u_pcm_deadline(deadline,deadline+200000,20000)!=2220000)return 7;
    int64_t start=mf79u_pcm_now(),paced=0;
    for(unsigned i=0;i<50;i++){mf79u_pcm_pace(&paced,20000);usleep(5000);}
    int64_t elapsed=mf79u_pcm_now()-start;
    if(elapsed<990000 || elapsed>1100000){printf("CLOCK elapsed_us=%lld\n",(long long)elapsed);return 8;}
    printf("PCM queue selftest=0; ordered bursts, silence, overflow bound, underflow, monotonic pacing elapsed_us=%lld\n",(long long)elapsed);
    return 0;
}
