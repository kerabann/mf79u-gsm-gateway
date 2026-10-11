/* 31-tap half-band FIR (Hamming-windowed sinc, Q15), 8k <-> 16k only.
 * Wideband PCM passes directly; this is used only for AMR-NB fallback. */
#ifndef MF79U_PCM_RESAMPLE_H
#define MF79U_PCM_RESAMPLE_H
#include <stdint.h>
struct mf79u_resample {int16_t history[31];unsigned next;};
static inline int16_t mf79u_fir(struct mf79u_resample *s,int16_t sample,int gain){
    static const int16_t coefficients[31]={-56,0,96,0,-221,0,462,0,-878,0,1609,0,-3176,0,10356,16384,10356,0,-3176,0,1609,0,-878,0,462,0,-221,0,96,0,-56};
    s->history[s->next]=sample;unsigned at=s->next;int64_t sum=0;
    for(unsigned i=0;i<31;i++){sum+=(int32_t)s->history[at]*coefficients[i];at=at?at-1:30;}
    s->next=(s->next+1)%31;sum=sum*gain/32768;
    if(sum>32767)sum=32767;
    if(sum<-32768)sum=-32768;
    return (int16_t)sum;
}
static inline void mf79u_upsample(struct mf79u_resample *s,const int16_t in[160],int16_t out[320]){
    for(unsigned i=0;i<160;i++){out[2*i]=mf79u_fir(s,in[i],2);out[2*i+1]=mf79u_fir(s,0,2);}
}
static inline void mf79u_downsample(struct mf79u_resample *s,const int16_t in[320],int16_t out[160]){
    for(unsigned i=0;i<160;i++){out[i]=mf79u_fir(s,in[2*i],1);(void)mf79u_fir(s,in[2*i+1],1);}
}
#endif
