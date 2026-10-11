#include "cs-pcm-clarity.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
static double response(unsigned hz){
    struct cs_pcm_clarity s={0};double before=0,after=0;int16_t frame[160];
    for(unsigned f=0;f<50;f++){
        for(unsigned i=0;i<160;i++)frame[i]=(int16_t)(6000*sin(2*3.141592653589793*hz*(f*160+i)/8000));
        if(f)for(unsigned i=0;i<160;i++)before+=(int32_t)frame[i]*frame[i];
        cs_pcm_clarity_apply(&s,frame);
        if(f)for(unsigned i=0;i<160;i++)after+=(int32_t)frame[i]*frame[i];
    }
    assert(!s.clipped);return 10*log10(after/before);
}
int main(void){
    for(unsigned hz=300;hz<=3500;hz+=100){
        double gain=response(hz),w=2*3.141592653589793*hz/8000;
        double expected=10*log10(1+.48*(1-cos(w))); /* |1.2-.2z^-1|^2 */
        assert(fabs(gain-expected)<.01 && gain>=0 && gain<3);
    }
    struct cs_pcm_clarity s={0};int16_t frame[160];
    for(unsigned i=0;i<160;i++)frame[i]=10000;
    cs_pcm_clarity_apply(&s,frame);for(unsigned i=1;i<160;i++)assert(frame[i]==10000);
    s=(struct cs_pcm_clarity){0};for(unsigned i=0;i<160;i++)frame[i]=(i&1)?32767:-32768;
    cs_pcm_clarity_apply(&s,frame);assert(s.clipped==160);
    for(unsigned i=0;i<160;i++)assert(frame[i]==((i&1)?32767:-32768));
    printf("CS-only emphasis passed: DC unity, 3kHz %.3fdB, bounded saturation; synthetic audio only\n",response(3000));return 0;
}
