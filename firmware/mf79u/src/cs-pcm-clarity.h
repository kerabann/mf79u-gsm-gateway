/* CS-only 8k PCM emphasis. No IMS/shared-resampler dependency.
 * H(z)=1+0.2(1-z^-1): DC unity, +2.60dB at3kHz, bounded +2.92dB.
 * It cannot create wideband speech from a narrowband cellular stream. */
#ifndef MF79U_CS_PCM_CLARITY_H
#define MF79U_CS_PCM_CLARITY_H
#include <stdint.h>
struct cs_pcm_clarity {int16_t previous;uint64_t clipped;};
static inline void cs_pcm_clarity_apply(struct cs_pcm_clarity *s,int16_t pcm[160]){
    for(unsigned i=0;i<160;i++){
        int32_t sample=pcm[i],value=sample+(sample-s->previous)*6554/32768;
        s->previous=(int16_t)sample;
        if(value>32767){value=32767;s->clipped++;}
        if(value<-32768){value=-32768;s->clipped++;}
        pcm[i]=(int16_t)value;
    }
}
#endif
