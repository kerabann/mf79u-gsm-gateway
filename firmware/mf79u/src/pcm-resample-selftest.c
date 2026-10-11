#include "pcm-resample.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static double tone(unsigned rate,unsigned frequency,int up){
    struct mf79u_resample state={0};int16_t in[320],out[320];double energy=0;unsigned count=0;
    for(unsigned f=0;f<20;f++){
        for(unsigned i=0;i<rate/50;i++)in[i]=(short)(10000*sin(2*3.141592653589793*frequency*(f*rate/50+i)/rate));
        if(up)mf79u_upsample(&state,in,out);else mf79u_downsample(&state,in,out);
        if(f>2)for(unsigned i=0;i<(up?320u:160u);i++){energy+=(int32_t)out[i]*out[i];count++;}
    }
    return sqrt(energy/count);
}
int main(void){
    double pass=tone(16000,3000,0),stop=tone(16000,6000,0),up=tone(8000,3000,1);
    if(pass<6000 || pass>7500 || up<6000 || up>7500 || stop>400)return 1;
    struct mf79u_resample state={0};int16_t in[160],out[320];
    for(unsigned i=0;i<160;i++)in[i]=10000;
    mf79u_upsample(&state,in,out);
    for(unsigned i=64;i<320;i++)if(out[i]<9990 || out[i]>10010)return 2;
    printf("FIR fallback selftest passed: 3kHz down=%.1f up=%.1f; rejected 6kHz alias=%.1f; DC unity\n",pass,up,stop);return 0;
}
