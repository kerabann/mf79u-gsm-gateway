/* Exact-B03, one-call diagnostic. Reference audio commands are a hypothesis.
 * Uses the verified B03 audio mailbox and bit2 notification, with a bounded
 * wait instead of the vendor timeout/reset path. No DSP program patch, PCM
 * peripheral, clocks, FACCH, AMR frame buffer or network signaling writes.
 */
#ifndef MF79U_CS_DSP_TONE_CANDIDATE_H
#define MF79U_CS_DSP_TONE_CANDIDATE_H
#include "../build/cs-dsp-audio-parameters.h"
#ifndef CS_AUDIO_LOG
#define CS_AUDIO_LOG "MF79U_CS_MO"
#endif
static u32 cs_audio_started,cs_audio_done,cs_audio_phase=99U,cs_audio_failed;
static unsigned long long cs_audio_connected_at,cs_audio_play_at;
static unsigned short cs_audio_saved_tone[11],cs_audio_saved_mailbox[28];
static unsigned long long cs_audio_next_sample;
#include "cs-dsp-mailbox.h"
static void cs_audio_restore(void) {
    if(!cs_audio_started)return;
    u32 stopped=cs_audio_command(0x13U,1U,(const unsigned short *)0);
    u32 disabled=cs_audio_command(0x0fU,28U,cs_audio_params_7);
    u32 ended=cs_audio_command(0x15U,1U,(const unsigned short *)0);
    u32 restored=0;
    if(cs_audio_layout() && !(*(const volatile u32 *)0xfad00024U&4U)) {
        volatile unsigned short *tonep=(volatile unsigned short *)0xfad011b0U;
        for(u32 i=0;i<11U;i++)if(i!=7U)tonep[i]=cs_audio_saved_tone[i];
        volatile unsigned short *box=(volatile unsigned short *)0xfad0107aU;
        for(u32 i=0;i<28U;i++)box[i]=cs_audio_saved_mailbox[i];
        restored=1;
    }
    printk("<6>" CS_AUDIO_LOG " dsp_audio_stopped=%u disabled=%u ended=%u saved_ap_fields_restored=%u dsp_internal_state_unverified=1\n",stopped,disabled,ended,restored);
    cs_audio_started=0;cs_audio_done=1;
}
static void cs_audio_step(u32 connected,unsigned long long now) {
    if(!connected){if(cs_audio_started)cs_audio_restore();return;}
    if(cs_audio_done)return;
    if(!cs_audio_connected_at)cs_audio_connected_at=now;
    if(now-cs_audio_connected_at<1000000000ULL)return;
    if(!cs_audio_channel()){if(cs_audio_started)cs_audio_restore();return;}
    if(!cs_audio_started) {
        volatile unsigned short *tonep=(volatile unsigned short *)0xfad011b0U;
        volatile unsigned short *box=(volatile unsigned short *)0xfad0107aU;
        for(u32 i=0;i<11U;i++)cs_audio_saved_tone[i]=tonep[i];
        for(u32 i=0;i<28U;i++)cs_audio_saved_mailbox[i]=box[i];
        cs_audio_started=1;
        cs_audio_failed=!(cs_audio_command(0x10U,12U,cs_audio_params_0) &&
          cs_audio_command(0x10U,12U,cs_audio_params_1) &&
          cs_audio_command(0x19U,8U,cs_audio_params_2) &&
          cs_audio_command(0x11U,23U,cs_audio_params_3) &&
          cs_audio_command(0x17U,13U,cs_audio_params_4) &&
          cs_audio_command(0x18U,2U,cs_audio_params_5) &&
          cs_audio_command(0x0fU,28U,cs_audio_params_6));
        if(cs_audio_failed){cs_audio_restore();return;}
        cs_audio_play_at=cs_monotonic_ns();
    }
    unsigned long long elapsed=now>=cs_audio_play_at?now-cs_audio_play_at:0;
    if(now>=cs_audio_next_sample) {
        const volatile unsigned short *p=(const volatile unsigned short *)0xfad011b0U;
        printk("<6>" CS_AUDIO_LOG " dsp_audio_sample tone_status_raw=%u duration_raw=%u scheduler=%u,%u\n",p[7],p[6],p[9],p[10]);
        cs_audio_next_sample=now+1000000000ULL;
    }
    u32 phase=elapsed<2000000000ULL?0U:(elapsed<4000000000ULL?1U:2U);
    if(elapsed>=6000000000ULL){cs_audio_restore();return;}
    if(phase==cs_audio_phase)return;
    volatile unsigned short *tonep=(volatile unsigned short *)0xfad011b0U;
    tonep[0]=cs_audio_tone_coefficient[phase];tonep[1]=cs_audio_tone_amplitude[phase];
    tonep[2]=32767U;tonep[3]=0;tonep[4]=32767U;tonep[5]=0;
    tonep[6]=16000U;tonep[8]=10U;tonep[9]=160U;tonep[10]=160U;
    printk("<6>" CS_AUDIO_LOG " dsp_audio_tone_written phase=%u duration_raw=%u tone_mixer_resource=1\n",phase,tonep[6]);
    if(phase && !cs_audio_command(0x14U,1U,(const unsigned short *)0)){cs_audio_restore();return;}
    if(!cs_audio_command(0x12U,1U,(const unsigned short *)0)){cs_audio_restore();return;}
    cs_audio_phase=phase;
    printk("<6>" CS_AUDIO_LOG " dsp_audio_tone_phase=%u frequency_hz=%u reference_format_only=1\n",phase,500U+phase*500U);
}
#endif
