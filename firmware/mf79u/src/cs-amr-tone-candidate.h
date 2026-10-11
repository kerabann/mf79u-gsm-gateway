/* Exact-B03 experiment, not a speech backend. The original <=46-byte UL
 * copier is known; its use by the AMR speech coder is a hypothesis. No DSP
 * commands, control/ACK writes, FACCH, PCM hardware or unclassified buffers.
 * Three packed bit-order candidates, 2s each, only in our connected AMR-FR MO.
 */
#ifndef MF79U_CS_AMR_TONE_CANDIDATE_H
#define MF79U_CS_AMR_TONE_CANDIDATE_H
#include "cs-tone-pack.h"
static u32 cs_tone_ticks,cs_tone_sent,cs_tone_done,cs_tone_started,cs_tone_phase=99U;
static int cs_tone_ram(u32 p,u32 n) {
    return ram(p,n) || (p>=0xbf59e000U && p<=0xbf619ba8U-n);
}
static int cs_tone_layout(void) {
    static const u8 writer[8]={0x08,0xb5,0x0b,0x46,0x01,0x46,0x40,0xb1};
    if(!match(0xbf3f5114U,writer,8))return 0;
    return *(const volatile u32 *)0xbf59f4e4U==0xfad01348U &&
           *(const volatile u32 *)0xbf59f4c4U==0xfad012feU;
}
static int cs_tone_channel(u32 *mode) {
    u32 p=0,c=0;u8 m=0,ch=0;
    if(probe_kernel_read(&p,(const void *)0xbf5a7720U,4) || !cs_tone_ram(p,0x147U) ||
       probe_kernel_read(&c,(const void *)(p+0x120U),4) || !cs_tone_ram(c,10U) ||
       probe_kernel_read(&ch,(const void *)(c+8U),1) || ch!=1U ||
       probe_kernel_read(&m,(const void *)(p+0x12aU),1) || m!=9U || !cs_tone_layout())return 0;
    const volatile unsigned short *control=(const volatile unsigned short *)0xfad012feU;
    u32 set=control[0],index=control[1];
    return cs_tone_mode(set,index,mode);
}
static void cs_tone_restore(void) {
    if(!cs_tone_started)return;
    /* Before our first write the exact original UL range was all zero. */
    if(cs_tone_layout()) {
        u8 zero[46];for(u32 i=0;i<46U;i++)zero[i]=0;
        ((void (*)(const void *,u32,u32))0xbf3f5115U)(zero,46U,0U);
        printk("<6>MF79U_CS_MO amr_candidate_stopped=1 ul_zero_restored=1 frames_written=%u\n",cs_tone_sent);
    }
    cs_tone_started=0;
}
static void cs_tone_step(u32 connected) {
    if(!connected){if(cs_tone_started){cs_tone_restore();cs_tone_done=1;}return;}
    if(cs_tone_done)return;
    if(++cs_tone_ticks<=50U)return; /* one second after CONNECT */
    u32 mode=0;if(!cs_tone_channel(&mode)) {
        if(cs_tone_started){cs_tone_restore();cs_tone_done=1;}
        return;
    }
    if(!cs_tone_started) {
        const volatile unsigned short *p=(const volatile unsigned short *)0xfad01348U;
        for(u32 i=0;i<23U;i++)if(p[i]) {
            cs_tone_done=1;printk("<4>MF79U_CS_MO amr_candidate_rejected=ul_not_zero\n");return;
        }
        cs_tone_started=1;
    }
    if(cs_tone_sent>=300U){cs_tone_restore();cs_tone_done=1;return;}
    u32 phase=cs_tone_sent/100U,frame=cs_tone_sent%100U;
    u8 data[46];if(!cs_tone_pack(data,mode,frame,phase))return;
    if(cs_status_state!=CS_MO_CONNECTED){cs_tone_restore();cs_tone_done=1;return;}
    ((void (*)(const void *,u32,u32))0xbf3f5115U)(data,46U,0U);
    if(phase!=cs_tone_phase) {
        cs_tone_phase=phase;
        printk("<6>MF79U_CS_MO amr_candidate_phase=%u codec_mode=%u ul_bytes=46 control_writes=0 speech_format_unverified=1\n",phase,mode);
    }
    cs_tone_sent++;
}
#endif
