#include <stdio.h>
#include <stdarg.h>
typedef unsigned int u32;
typedef unsigned short u16;
static int metadata_read(void *p,u32 a,u32 n){(void)p;(void)a;(void)n;return 0;}
static int printk(const char *s,...){(void)s;return 0;}
#include "cs-dsp-pcm-metadata.h"
int main(void) {
    const short sine[16]={0,4592,8485,11087,12000,11087,8485,4592,0,-4592,-8485,-11087,-12000,-11087,-8485,-4592};
    short data[160];u32 seed=1;
    for(u32 step=1;step<=3;step++) {
        for(u32 i=0;i<160;i++)data[i]=sine[(i*step)&15U];
        if(!cs_pcm_period(data,160,step==2?8:16))return 1;
    }
    for(u32 i=0;i<160;i++)data[i]=0;
    if(cs_pcm_period(data,160,8))return 2;
    for(u32 i=0;i<160;i++)data[i]=12000;
    if(cs_pcm_period(data,160,8))return 3;
    for(u32 trial=0;trial<100;trial++) {
        for(u32 i=0;i<160;i++){seed=seed*1664525U+1013904223U;data[i]=(short)(seed>>16);}
        for(u32 lag=8;lag<=32;lag*=2)if(cs_pcm_period(data,160,lag))return 4;
    }
    /* Keep the full header checked by the compiler without executing SRAM IO. */
    if(cs_pcm_layout_valid())sample_pcm_metadata(0);
    puts("PASS: periodic tones; silence, DC and 100 noise blocks rejected");return 0;
}
