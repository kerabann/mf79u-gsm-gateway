#ifndef MF79U_CS_TONE_PACK_H
#define MF79U_CS_TONE_PACK_H
#include "../build/cs-tone-frames.h"
static int cs_tone_mode(u32 set,u32 index,u32 *mode) {
    if(!set || set>255U || index>3U)return 0;
    u32 count=0;for(u32 i=0;i<8U;i++)count+=!!(set&(1U<<i));
    if(count>4U)return 0;
    for(u32 i=0;i<8U;i++)if(set&(1U<<i)) {
        if(!index){*mode=i;return 1;}index--;
    }
    return 0;
}
static u8 cs_tone_reverse(u8 v) {
    v=(u8)(((v&0x55U)<<1)|((v>>1)&0x55U));
    v=(u8)(((v&0x33U)<<2)|((v>>2)&0x33U));
    return (u8)((v<<4)|(v>>4));
}
static int cs_tone_pack(u8 data[46],u32 mode,u32 frame,u32 phase) {
    if(mode>7U || frame>=CS_TONE_FRAMES || phase>2U)return 0;
    for(u32 i=0;i<46U;i++)data[i]=0;
    for(u32 i=0;i<cs_tone_payload_size[mode];i++)data[i]=cs_tone_payloads[mode][frame][i];
    if(phase==1U)for(u32 i=0;i<46U;i++)data[i]=cs_tone_reverse(data[i]);
    if(phase==2U)for(u32 i=0;i<46U;i+=2U){u8 a=data[i];data[i]=data[i+1U];data[i+1U]=a;}
    return 1;
}
#endif
