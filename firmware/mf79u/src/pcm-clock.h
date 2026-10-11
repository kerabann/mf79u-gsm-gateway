#ifndef MF79U_PCM_CLOCK_H
#define MF79U_PCM_CLOCK_H
#include <stdint.h>
#include <time.h>
#include <unistd.h>
static inline int64_t mf79u_pcm_now(void){
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;
    return (int64_t)t.tv_sec*1000000+t.tv_nsec/1000;
}
static inline int64_t mf79u_pcm_deadline(int64_t previous,int64_t now,unsigned period){
    if(!previous || now-previous>100000 || previous-now>100000)previous=now;
    return previous+period;
}
static inline void mf79u_pcm_pace(int64_t *deadline,unsigned period){
    int64_t now=mf79u_pcm_now();*deadline=mf79u_pcm_deadline(*deadline,now,period);
    while((now=mf79u_pcm_now())<*deadline)usleep((unsigned)(*deadline-now));
}
#endif
