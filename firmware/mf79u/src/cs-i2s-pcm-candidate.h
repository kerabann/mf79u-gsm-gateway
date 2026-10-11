/* Exact B03 reversible I2S PCM diagnostic. Internal ARM0 <-> DSP loop;
 * no GPIO/pin mux, DSP code upload or external analog audio device.
 * GSM/SIP PCM remains 16k/320 externally. The generated FIFO rate is a
 * diagnostic selection; two sequential mono16 samples occupy each word.
 */
#ifndef CS_I2S_PCM_CANDIDATE_H
#define CS_I2S_PCM_CANDIDATE_H
#include "../build/cs-i2s-parameters.h"
#ifndef CS_I2S_FIFO_RATE_HZ
#define CS_I2S_FIFO_RATE_HZ 8000U
#endif
#include "cs-dsp-mailbox.h"
#if defined(CS_I2S_ARM_TONE_TEST) && (!defined(CS_I2S_PORT_TONE_TEST) || !defined(CS_I2S_FULL_VOICE_API))
#error ARM tone comparison requires the complete voice API and DSP control stage
#endif
#if defined(CS_I2S_ARM_ECHO_TEST) && !defined(CS_I2S_ARM_TONE_TEST)
#error ARM echo requires the explicit full voice ARM tone diagnostic
#endif
#if defined(CS_I2S_CONNECTED_RX_START_TEST) && !defined(CS_I2S_ARM_ECHO_TEST)
#error Late startup profile requires the bounded ARM echo diagnostic
#endif
#if defined(CS_I2S_ARM1_ECHO_TEST)
#if !defined(CS_I2S_ARM_ECHO_TEST) || defined(CS_I2S_CONNECTED_RX_START_TEST)
#error ARM1 receive requires a separate full voice echo test
#endif
#define CS_I2S_REFERENCE_OPEN_CLOCKS 1
#endif
#if defined(CS_I2S_BOTH_PORTS_TEST)
#if !defined(CS_I2S_IDLE_LOOP_TEST) || !defined(CS_I2S_FULL_VOICE_API)
#error Both port comparison requires an idle full voice diagnostic
#endif
#define CS_I2S_REFERENCE_OPEN_CLOCKS 1
#endif
#if defined(CS_I2S_REFERENCE_OPEN_CLOCKS) && !defined(CS_I2S_PORT_TONE_TEST) && !defined(CS_I2S_BOTH_PORTS_TEST)
#error Reference Open clocks are limited to the connected port diagnostic
#endif
#if defined(CS_I2S_ARM1_RX_ONLY) && !defined(CS_I2S_BOTH_PORTS_TEST) && !defined(CS_I2S_ARM1_ECHO_TEST)
#error ARM1 RX only requires the bounded two-port or ARM1 echo diagnostic
#endif
#if defined(CS_I2S_ARM1_TX_SWITCH) && (!defined(CS_I2S_ARM1_RX_ONLY) || !defined(CS_I2S_ARM1_ECHO_TEST))
#error TX port comparison requires explicit ARM1 RX-only echo control
#endif
#if defined(CS_I2S_USERSPACE_PCM) && !defined(CS_I2S_ARM1_TX_SWITCH)
#error Userspace PCM requires the physically verified ARM1 duplex diagnostic
#endif
#if defined(CS_I2S_STREAMING_PCM) && !defined(CS_I2S_USERSPACE_PCM)
#error Streaming PCM requires the verified userspace duplex transport
#endif
#ifdef CS_I2S_USERSPACE_PCM
#include "cs-pcm-stream.h"
#endif
#ifdef CS_I2S_ARM1_TX_SWITCH
static u32 cs_arm1_tx_switched;
#endif
extern void usleep_range(unsigned long,unsigned long);
static u32 cs_audio_started,cs_audio_done;
#ifdef CS_I2S_REUSABLE
static u32 cs_audio_restored=1;
#endif
#ifdef CS_I2S_CALL_ACTIVE
static u32 cs_audio_media_done;
#endif
static unsigned long long cs_audio_connected_at,cs_audio_play_at;
#ifndef CS_I2S_USERSPACE_PCM
static unsigned long long cs_audio_next_sample;
#endif
static const u32 cs_i2s_addresses[]={0xf8440060U,0xf8a00014U,0xf8a00058U,0xf8a0005cU,
    0xf8a05004U,0xf8a05008U,0xf8a0500cU,0xf8a05014U,0xf8a05020U,0xf8a0001cU};
#ifdef CS_I2S_REFERENCE_OPEN_CLOCKS
static const u32 cs_i2s_clock_indices[]={29U,31U,30U,32U};
static const u32 cs_i2s_port1_addresses[]={0xf8a06004U,0xf8a06008U,0xf8a0600cU,0xf8a06014U,0xf8a06020U
#if defined(CS_I2S_BOTH_PORTS_TEST) || defined(CS_I2S_ARM1_ECHO_TEST)
    ,0xf8a00060U,0xf8a00064U
#endif
};
#define CS_I2S_PORT1_SAVED_COUNT (sizeof(cs_i2s_port1_addresses)/sizeof(cs_i2s_port1_addresses[0]))
static u32 cs_i2s_port1_saved[CS_I2S_PORT1_SAVED_COUNT];
#else
static const u32 cs_i2s_clock_indices[]={29U,31U};
#endif
#define CS_I2S_CLOCK_COUNT (sizeof(cs_i2s_clock_indices)/sizeof(cs_i2s_clock_indices[0]))
static u32 cs_i2s_saved[10],cs_i2s_clock_flags[CS_I2S_CLOCK_COUNT],cs_i2s_tx,cs_i2s_rx,cs_i2s_rx_nonzero;
static unsigned short cs_i2s_saved_mailbox[28];
static u32 cs_i2s_last_rx,cs_i2s_failed;
#if defined(CS_I2S_ARM1_RX_ONLY) && defined(CS_I2S_ARM1_ECHO_TEST)
static u32 cs_rx_window_words,cs_rx_window_active,cs_rx_window_peak;
#endif
#ifdef CS_I2S_ARM_ECHO_TEST
/* 128 ms maximum storage, with an 80 ms echo delay at 8 kHz mono16.
 * No samples leave this bounded RAM buffer or appear in diagnostic logs. */
static u32 cs_echo_words[512],cs_echo_read,cs_echo_write,cs_echo_started;
static u32 cs_echo_nonzero,cs_echo_underrun,cs_echo_overrun,cs_echo_rx_peak;
#endif
#if (!defined(CS_I2S_PORT_TONE_TEST) || defined(CS_I2S_ARM_TONE_TEST)) && !defined(CS_I2S_STREAMING_PCM)
static u32 cs_i2s_phase;
#endif
#ifdef CS_I2S_PORT_TONE_TEST
#include "../build/cs-dsp-audio-parameters.h"
static u32 cs_port_tone_started;
static unsigned long long cs_port_tone_at;
#ifndef CS_I2S_ARM_TONE_TEST
static unsigned long long cs_port_next_refresh;
#endif
static unsigned short cs_port_saved_tone[11];
#endif
static u32 cs_i2s_read(u32 a) {return *(const volatile u32 *)a;}
static void cs_i2s_write(u32 a,u32 v) {*(volatile u32 *)a=v;__asm__ volatile("dmb sy":::"memory");}
static int cs_i2s_layout(void) {
    /* Exact CP clock vtable and records, under the checksum-bound armer. */
    return cs_audio_layout() && cs_i2s_read(0xbf4f9650U)==0xbf439151U &&
        cs_i2s_read(0xbf4f9654U)==0xbf4391d1U && cs_i2s_read(0xbf4f965cU)==0xbf43930dU &&
        cs_i2s_read(0xbf55cde4U)==0xf8a00014U && cs_i2s_read(0xbf55ce74U)==0xf8a00014U
#ifdef CS_I2S_REFERENCE_OPEN_CLOCKS
        && cs_i2s_read(0xbf55ce2cU)==0xf8a0001cU && cs_i2s_read(0xbf55cebcU)==0xf8a0001cU
        && cs_i2s_read(0xf8a06000U)==0x01030000U && !cs_i2s_read(0xf8a06004U) && !cs_i2s_read(0xf8a06014U)
#endif
        ;
}
static void cs_i2s_gate(u32 index,u32 hardware,u32 software) {
    ((void (*)(u32,u32))0xbf439151U)(index,hardware);
    ((void (*)(u32,u32))0xbf4391d1U)(index,software);
}
#ifdef CS_I2S_CALL_ACTIVE
static void cs_audio_hold_silence(void) {
    if(!cs_audio_started && !cs_port_tone_started)return;
    if(!cs_audio_media_done) {
        /* Close the userspace stream once, but keep the DSP and both clock
         * pairs running until the signaling worker observes MM release. */
        cs_audio_media_done=1;
        printk("<6>" CS_AUDIO_LOG " media_stop_begin=1 call_active=1 hardware_close_deferred=1\n");
        if(cs_audio_started)cs_pcm_stop();
        cs_i2s_last_rx=0;
        printk("<6>" CS_AUDIO_LOG " media_stopped=1 call_active=1 clocks_retained=1\n");
    }
    if(!cs_audio_started)return;
    for(u32 port=0;port<2U;port++) {
        u32 base=port?0xf8a06000U:0xf8a05000U;
        for(u32 i=0;i<32U && ((cs_i2s_read(base+0x10U)>>16)&63U);i++)
            (void)cs_i2s_read(base+0x1cU);
        if(cs_i2s_read(base+4U)&1U)
            for(u32 i=0;i<32U && ((cs_i2s_read(base+0x10U)>>8)&63U);i++)
                cs_i2s_write(base+0x1cU,0);
    }
}
#endif
static void cs_audio_restore(void) {
    if(!cs_audio_started
#ifdef CS_I2S_PORT_TONE_TEST
       && !cs_port_tone_started
#endif
       )return;
    if(cs_audio_started)cs_i2s_write(0xf8a05004U,0);
#ifdef CS_I2S_USERSPACE_PCM
    if(cs_audio_started
#ifdef CS_I2S_CALL_ACTIVE
       && !cs_audio_media_done
#endif
       )cs_pcm_stop();
#endif
#if defined(CS_I2S_BOTH_PORTS_TEST) || defined(CS_I2S_ARM1_ECHO_TEST)
    if(cs_audio_started)cs_i2s_write(0xf8a06004U,0);
#endif
#ifdef CS_I2S_PORT_TONE_TEST
    u32 tone_stopped=cs_audio_command(0x13U,1U,(const unsigned short *)0);
    u32 disabled=cs_audio_command(0x0fU,28U,cs_audio_started?cs_i2s_params_7:cs_audio_params_7);
#else
    u32 disabled=cs_audio_command(0x0fU,28U,cs_i2s_params_7);
#endif
    u32 ended=cs_audio_command(0x15U,1U,(const unsigned short *)0);
    u32 ap_restored=0;
    if(cs_audio_layout() && !(cs_i2s_read(0xfad00024U)&4U)) {
        volatile unsigned short *box=(volatile unsigned short *)0xfad0107aU;
        for(u32 i=0;i<28U;i++)box[i]=cs_i2s_saved_mailbox[i];
#ifdef CS_I2S_PORT_TONE_TEST
        volatile unsigned short *tone=(volatile unsigned short *)0xfad011b0U;
        for(u32 i=0;i<11U;i++)if(i!=7U)tone[i]=cs_port_saved_tone[i];
#endif
        ap_restored=1;
    }
    u32 restored=1;
    if(cs_audio_started) {
    for(u32 i=4U;i<9U;i++)cs_i2s_write(cs_i2s_addresses[i],cs_i2s_saved[i]);
#ifdef CS_I2S_REFERENCE_OPEN_CLOCKS
    for(u32 i=0;i<CS_I2S_PORT1_SAVED_COUNT;i++)cs_i2s_write(cs_i2s_port1_addresses[i],cs_i2s_port1_saved[i]);
#endif
    cs_i2s_write(0xf8440060U,(cs_i2s_read(0xf8440060U)&~CS_I2S_LOOP_MASK)|(cs_i2s_saved[0]&CS_I2S_LOOP_MASK));
    cs_i2s_write(0xf8a00058U,cs_i2s_saved[2]);cs_i2s_write(0xf8a0005cU,cs_i2s_saved[3]);
    for(u32 i=0;i<CS_I2S_CLOCK_COUNT;i++)
        cs_i2s_gate(cs_i2s_clock_indices[i],cs_i2s_clock_flags[i]&255U,cs_i2s_clock_flags[i]>>8);
    /* Only I2S0 clock selection/gating/reset fields; preserve other owners. */
    cs_i2s_write(0xf8a00014U,(cs_i2s_read(0xf8a00014U)&~0xf0f33U)|(cs_i2s_saved[1]&0xf0f33U));
#ifdef CS_I2S_REFERENCE_OPEN_CLOCKS
    /* Reset/release may clear unused ARM1 controls; restore them above.
     * The explicit idle two-port variant also restores ARM1 dividers.
     * No GPIO or IRQ handler is used. */
    cs_i2s_write(0xf8a0001cU,(cs_i2s_read(0xf8a0001cU)&~0xf03U)|(cs_i2s_saved[9]&0xf03U));
#endif
    for(u32 i=0;i<9U;i++)if(cs_i2s_read(cs_i2s_addresses[i])!=cs_i2s_saved[i])restored=0;
#ifdef CS_I2S_REFERENCE_OPEN_CLOCKS
    if(cs_i2s_read(0xf8a0001cU)!=cs_i2s_saved[9])restored=0;
    for(u32 i=0;i<CS_I2S_PORT1_SAVED_COUNT;i++)if(cs_i2s_read(cs_i2s_port1_addresses[i])!=cs_i2s_port1_saved[i])restored=0;
#endif
    }
    printk("<6>" CS_AUDIO_LOG " i2s_stopped=1 audio_disabled=%u audio_ended=%u registers_restored=%u tx_words=%u rx_words=%u rx_nonzero=%u failed=%u saved_ap_fields_restored=%u dsp_internal_state_unverified=1\n",
        disabled,ended,restored,cs_i2s_tx,cs_i2s_rx,cs_i2s_rx_nonzero,cs_i2s_failed,ap_restored);
#ifdef CS_I2S_PORT_TONE_TEST
    printk("<6>" CS_AUDIO_LOG " port_tone_stopped=%u saved_tone_restored=%u\n",tone_stopped,ap_restored);
    cs_port_tone_started=0;
#endif
    cs_audio_started=0;cs_audio_done=1;
#ifdef CS_I2S_REUSABLE
    cs_audio_restored=disabled && ended && restored && ap_restored && !cs_i2s_failed;
#endif
#ifdef CS_I2S_ARM_ECHO_TEST
    for(u32 i=0;i<512U;i++)((volatile u32 *)cs_echo_words)[i]=0;
    cs_echo_read=cs_echo_write=0;cs_i2s_last_rx=0;
    printk("<6>" CS_AUDIO_LOG " arm_echo_stopped=1 tx_nonzero=%u underrun=%u overrun=%u rx_peak=%u buffer_cleared=1\n",
        cs_echo_nonzero,cs_echo_underrun,cs_echo_overrun,cs_echo_rx_peak);
#endif
}
#ifdef CS_I2S_REUSABLE
/* Only the worker invokes this after MM idle, DSP/register restoration, and
 * the owner has closed the previous userspace PCM endpoint. */
static int cs_audio_rearm(void) {
    if(cs_audio_started || cs_port_tone_started || cs_pcm_online || !cs_audio_restored)return 0;
    cs_audio_done=cs_audio_media_done=0;
    cs_audio_connected_at=cs_audio_play_at=cs_port_tone_at=0;
    cs_i2s_tx=cs_i2s_rx=cs_i2s_rx_nonzero=cs_i2s_last_rx=cs_i2s_failed=0;
    cs_rx_window_words=cs_rx_window_active=cs_rx_window_peak=0;
    cs_echo_read=cs_echo_write=cs_echo_started=0;
    cs_echo_nonzero=cs_echo_underrun=cs_echo_overrun=cs_echo_rx_peak=0;
    cs_arm1_tx_switched=0;
    for(u32 i=0;i<512U;i++)((volatile u32 *)cs_echo_words)[i]=0;
    cs_pcm_rx_busy=cs_pcm_tx_busy=cs_pcm_tx_empty=cs_pcm_rx_frames=cs_pcm_tx_frames=0;
    return 1;
}
#endif
#ifdef CS_I2S_PORT_TONE_TEST
static int cs_port_tone_start(void) {
    if(!cs_i2s_layout() || cs_i2s_read(0xfad00024U)&4U)return 0;
    volatile unsigned short *tone=(volatile unsigned short *)0xfad011b0U;
    for(u32 i=0;i<11U;i++)cs_port_saved_tone[i]=tone[i];
    for(u32 i=0;i<28U;i++)cs_i2s_saved_mailbox[i]=((const volatile unsigned short *)0xfad0107aU)[i];
    cs_port_tone_started=1;
#ifdef CS_I2S_REUSABLE
    cs_audio_restored=0;
#endif
    if(!(cs_audio_command(0x10U,12U,cs_audio_params_0) &&
         cs_audio_command(0x10U,12U,cs_audio_params_1) &&
         cs_audio_command(0x19U,8U,cs_audio_params_2) &&
         cs_audio_command(0x11U,23U,cs_audio_params_3) &&
         cs_audio_command(0x17U,13U,cs_audio_params_4) &&
         cs_audio_command(0x18U,2U,cs_audio_params_5) &&
         cs_audio_command(0x0fU,28U,cs_audio_params_6)))return 0;
#ifndef CS_I2S_STREAMING_PCM
    tone[0]=cs_audio_tone_coefficient[1];tone[1]=cs_audio_tone_amplitude[1];
    tone[2]=32767U;tone[3]=0;tone[4]=32767U;tone[5]=0;
    tone[6]=16000U;tone[8]=10U;tone[9]=160U;tone[10]=160U;
    if(!cs_audio_command(0x12U,1U,(const unsigned short *)0))return 0;
#endif
    cs_port_tone_at=cs_monotonic_ns();
#ifdef CS_I2S_STREAMING_PCM
    printk("<6>" CS_AUDIO_LOG " voice_bootstrap=1 synthetic_tone=0\n");
#else
    printk("<6>" CS_AUDIO_LOG " port_tone_stage=dsp_only frequency_hz=1000 pcm_port_enabled=0\n");
#endif
    return 1;
}
#endif
static int cs_i2s_start(void) {
    if(!cs_i2s_layout() || cs_i2s_read(0xf8a05004U) || cs_i2s_read(0xf8a05014U) || (cs_i2s_read(0xfad00024U)&4U))return 0;
    for(u32 i=0;i<10U;i++)cs_i2s_saved[i]=cs_i2s_read(cs_i2s_addresses[i]);
#ifdef CS_I2S_REFERENCE_OPEN_CLOCKS
    for(u32 i=0;i<CS_I2S_PORT1_SAVED_COUNT;i++)cs_i2s_port1_saved[i]=cs_i2s_read(cs_i2s_port1_addresses[i]);
#endif
    for(u32 i=0;i<CS_I2S_CLOCK_COUNT;i++) {
        u32 a=0xbf55c5a0U+cs_i2s_clock_indices[i]*0x48U;
        cs_i2s_clock_flags[i]=*(const volatile unsigned short *)(a+0x16U);
        if((cs_i2s_clock_flags[i]&255U)>1U || (cs_i2s_clock_flags[i]>>8)>1U)return 0;
    }
#ifndef CS_I2S_PORT_TONE_TEST
    for(u32 i=0;i<28U;i++)cs_i2s_saved_mailbox[i]=((const volatile unsigned short *)0xfad0107aU)[i];
#endif
    cs_audio_started=1;
#if defined(CS_I2S_ARM_TONE_TEST) && !defined(CS_I2S_STREAMING_PCM)
    /* End the known DSP control tone before the ARM-only stage. Do not mix
     * a DSP oscillator into the audible result of the PCM transmitter. */
    if(!cs_audio_command(0x13U,1U,(const unsigned short *)0)) {
        cs_i2s_failed=1;cs_audio_restore();return 0;
    }
#endif
    for(u32 i=0;i<CS_I2S_CLOCK_COUNT;i++)cs_i2s_gate(cs_i2s_clock_indices[i],1U,1U);
    for(u32 i=0;i<CS_I2S_CLOCK_COUNT;i++) {
        u32 index=cs_i2s_clock_indices[i];
        ((void (*)(u32,u32))0xbf43930dU)(index,0U);
        ((void (*)(u32,u32))0xbf43930dU)(index,1U);
    }
    cs_i2s_write(0xf8a05004U,0);cs_i2s_write(0xf8a05014U,0);
    cs_i2s_write(0xf8a05018U,0xffffU);
    cs_i2s_write(0xf8a05008U,CS_I2S_TIMING);
    cs_i2s_write(0xf8a0500cU,(cs_i2s_read(0xf8a0500cU)&~0x1f1f30U)|0x70f03U);
    cs_i2s_write(0xf8a00014U,(cs_i2s_read(0xf8a00014U)&~0xf0330U)|0x10f03U);
#if CS_I2S_CLOCK_MASTER
    cs_i2s_write(0xf8a0005cU,cs_i2s_read(0xf8a0005cU)&~0x10000U);
    cs_i2s_write(0xf8a00058U,CS_I2S_DIV_LO);cs_i2s_write(0xf8a0005cU,CS_I2S_DIV_HI);
#endif
    /* Reference driver Init owns bits 8:0, while mode selection alone owns
     * bits 8:3. The generated report binds both value and restoration mask. */
    cs_i2s_write(0xf8440060U,(cs_i2s_saved[0]&~CS_I2S_LOOP_MASK)|CS_I2S_LOOP);
    if(!(cs_audio_command(0x10U,12U,cs_i2s_params_0) &&
         cs_audio_command(0x10U,12U,cs_i2s_params_1) &&
         cs_audio_command(0x19U,8U,cs_i2s_params_2) &&
         cs_audio_command(0x11U,23U,cs_i2s_params_3) &&
         cs_audio_command(0x17U,13U,cs_i2s_params_4) &&
         cs_audio_command(0x18U,2U,cs_i2s_params_5) &&
         cs_audio_command(0x0fU,28U,cs_i2s_params_6))) {
        cs_i2s_failed=1;cs_audio_restore();return 0;
    }
#ifdef CS_I2S_ARM1_ECHO_TEST
    /* Idle signal test verified changing DSP tone at ARM1 RX, while ARM0
     * TX is the user-confirmed GSM uplink. Use the same exact ARM1 profile. */
    cs_i2s_write(0xf8a06004U,0);cs_i2s_write(0xf8a06014U,0);
    cs_i2s_write(0xf8a06018U,0xffffU);
    cs_i2s_write(0xf8a06008U,0x01ef2001U);
    cs_i2s_write(0xf8a0600cU,(cs_i2s_read(0xf8a0600cU)&~0x1f1f30U)|0x70f03U);
    cs_i2s_write(0xf8a00064U,cs_i2s_read(0xf8a00064U)&~0x10000U);
    cs_i2s_write(0xf8a00060U,0x00200019U);cs_i2s_write(0xf8a00064U,0x00010032U);
#ifdef CS_I2S_ARM1_RX_ONLY
    cs_i2s_write(0xf8a06004U,6U);
#else
    for(u32 i=0;i<16U;i++)cs_i2s_write(0xf8a0601cU,0);
    cs_i2s_write(0xf8a06004U,7U);
#endif
    printk("<6>" CS_AUDIO_LOG " arm1_receive_enabled=1 timing=%08x divisor=%08x/%08x tx_port=0 rx_port=1\n",
        cs_i2s_read(0xf8a06008U),cs_i2s_read(0xf8a00060U),cs_i2s_read(0xf8a00064U));
#endif
    /* Prime with 16 words of silence, two sequential mono samples per word. */
    for(u32 i=0;i<16U;i++)cs_i2s_write(0xf8a0501cU,0);
    cs_i2s_write(0xf8a05004U,7U);
    cs_audio_play_at=cs_monotonic_ns();
#if defined(CS_I2S_PORT_TONE_TEST) && !defined(CS_I2S_ARM_TONE_TEST)
    volatile unsigned short *tone=(volatile unsigned short *)0xfad011b0U;
    tone[0]=cs_audio_tone_coefficient[1];tone[1]=cs_audio_tone_amplitude[1];
    tone[2]=32767U;tone[3]=0;tone[4]=32767U;tone[5]=0;
    tone[6]=16000U;tone[8]=10U;tone[9]=160U;tone[10]=160U;
    if(!cs_audio_command(0x12U,1U,(const unsigned short *)0)) {
        cs_i2s_failed=1;cs_audio_restore();return 0;
    }
    printk("<6>" CS_AUDIO_LOG " port_tone_stage=dsp_and_arm_rx arm_tx_silence=1 dsp_tone_both_mixers=1\n");
    cs_port_next_refresh=cs_monotonic_ns()+2000000000ULL;
#endif
#ifdef CS_I2S_STREAMING_PCM
    printk("<6>" CS_AUDIO_LOG " streaming_pcm=1 synthetic_tone=0 media_deadline=0\n");
#elif defined(CS_I2S_ARM_TONE_TEST)
#ifdef CS_I2S_ARM_ECHO_TEST
#ifdef CS_I2S_USERSPACE_PCM
    printk("<6>" CS_AUDIO_LOG " port_tone_stage=arm_pcm_then_userspace dsp_tone_stopped=1 arm_tone_seconds=2 userspace_seconds=20 amplitude=10000\n");
#else
    printk("<6>" CS_AUDIO_LOG " port_tone_stage=arm_pcm_then_echo dsp_tone_stopped=1 arm_tone_seconds=2 echo_seconds=4 amplitude=10000\n");
#endif
#else
    printk("<6>" CS_AUDIO_LOG " port_tone_stage=arm_pcm_only dsp_tone_stopped=1 frequencies_hz=500,1000,1500 amplitude=10000\n");
#endif
#endif
    printk("<6>" CS_AUDIO_LOG " i2s_pcm_started=1 fifo_rate_hz=%u internal_loop=%02x timing=%08x external_pcm_unchanged=1\n",CS_I2S_FIFO_RATE_HZ,CS_I2S_LOOP,CS_I2S_TIMING);
#ifdef CS_I2S_REFERENCE_OPEN_CLOCKS
    printk("<6>" CS_AUDIO_LOG " reference_open_clocks=4 clock0=%08x clock1=%08x\n",
        cs_i2s_read(0xf8a00014U),cs_i2s_read(0xf8a0001cU));
#endif
    return 1;
}
static void cs_audio_step(u32 connected,unsigned long long now) {
#ifdef CS_I2S_CALL_ACTIVE
    if(!connected || cs_audio_media_done) {
        if(CS_I2S_CALL_ACTIVE())cs_audio_hold_silence();
        else cs_audio_restore();
        return;
    }
#else
    if(!connected){cs_audio_restore();return;}
#endif
    if(cs_audio_done)return;
    if(!cs_audio_connected_at)cs_audio_connected_at=now;
    if(now-cs_audio_connected_at<1000000000ULL)return;
#ifndef CS_I2S_IDLE_LOOP_TEST
    if(!cs_audio_channel())return;
#endif
#ifdef CS_I2S_PORT_TONE_TEST
    if(!cs_port_tone_started) {
        if(!cs_port_tone_start()){cs_i2s_failed=1;cs_audio_restore();cs_audio_done=1;}
        return;
    }
#ifndef CS_I2S_STREAMING_PCM
    if(now<cs_port_tone_at+2000000000ULL)return;
#endif
#endif
    if(!cs_audio_started) {
        if(!cs_i2s_start()){cs_i2s_failed=1;cs_audio_restore();cs_audio_done=1;return;}
        now=cs_monotonic_ns();
    }
#if defined(CS_I2S_USERSPACE_PCM) && !defined(CS_I2S_STREAMING_PCM)
    if(now>=cs_audio_play_at+22000000000ULL){
#ifdef CS_I2S_CALL_ACTIVE
        cs_audio_hold_silence();
#else
        cs_audio_restore();
#endif
        return;
    }
#elif !defined(CS_I2S_STREAMING_PCM)
    if(now>=cs_audio_play_at+6000000000ULL){cs_audio_restore();return;}
#endif
#if defined(CS_I2S_PORT_TONE_TEST) && !defined(CS_I2S_ARM_TONE_TEST)
    /* Reuse the observed MT19 two-second duration and restart sequence.
     * Longer duration values have not been validated on the B03 DSP. */
    if(now>=cs_port_next_refresh) {
        volatile unsigned short *tone=(volatile unsigned short *)0xfad011b0U;
        tone[0]=cs_audio_tone_coefficient[1];tone[1]=cs_audio_tone_amplitude[1];
        tone[2]=32767U;tone[3]=0;tone[4]=32767U;tone[5]=0;
        tone[6]=16000U;tone[8]=10U;tone[9]=160U;tone[10]=160U;
        if(!cs_audio_command(0x14U,1U,(const unsigned short *)0) ||
           !cs_audio_command(0x12U,1U,(const unsigned short *)0)) {
            cs_i2s_failed=1;cs_audio_restore();return;
        }
        printk("<6>" CS_AUDIO_LOG " port_tone_refreshed=1 validated_duration_raw=16000\n");
        cs_port_next_refresh=cs_monotonic_ns()+2000000000ULL;
    }
#endif
#ifdef CS_I2S_ARM_ECHO_TEST
    if(!cs_echo_started
#ifndef CS_I2S_STREAMING_PCM
       && now-cs_audio_play_at>=2000000000ULL
#endif
       ) {
#ifdef CS_I2S_CONNECTED_RX_START_TEST
        /* Exact late ARM0 profile observed at reference vp_VoiceI2sStart;
         * initial audible ARM control keeps the proven MO21 configuration. */
        cs_i2s_write(0xf8a05004U,0);
        cs_i2s_write(0xf8a0005cU,cs_i2s_read(0xf8a0005cU)&~0x10000U);
        cs_i2s_write(0xf8a00058U,0x00400019U);cs_i2s_write(0xf8a0005cU,0x00010019U);
        cs_i2s_write(0xf8a05008U,0x01ff2005U);
        cs_i2s_write(0xf8a0500cU,cs_i2s_read(0xf8a0500cU)|3U);
        for(u32 i=0;i<16U;i++)cs_i2s_write(0xf8a0501cU,0);
        cs_i2s_write(0xf8a05004U,7U);
        printk("<6>" CS_AUDIO_LOG " echo_late_start_profile=1 timing=%08x divisor=%08x/%08x\n",
            cs_i2s_read(0xf8a05008U),cs_i2s_read(0xf8a00058U),cs_i2s_read(0xf8a0005cU));
#endif
        cs_echo_started=1;
#ifdef CS_I2S_USERSPACE_PCM
        cs_pcm_start();
#else
        printk("<6>" CS_AUDIO_LOG " arm_echo_started=1 delay_samples=640 capacity_samples=1024 speech_saved=0\n");
#endif
    }
#endif
#ifdef CS_I2S_ARM1_TX_SWITCH
    if(!cs_arm1_tx_switched
#ifndef CS_I2S_STREAMING_PCM
       && now-cs_audio_play_at>=1000000000ULL
#endif
       ) {
        cs_i2s_write(0xf8a05004U,6U);
        for(u32 i=0;i<16U;i++)cs_i2s_write(0xf8a0601cU,0);
        cs_i2s_write(0xf8a06004U,7U);
        cs_arm1_tx_switched=1;
        printk("<6>" CS_AUDIO_LOG " transmit_port_switched=1 old_port=0 new_port=1 arm0_process=%08x arm1_process=%08x previous_tx_words=%u\n",
            cs_i2s_read(0xf8a05004U),cs_i2s_read(0xf8a06004U),cs_i2s_tx);
    }
    const u32 transmit_base=cs_arm1_tx_switched?0xf8a06000U:0xf8a05000U;
#else
    const u32 transmit_base=0xf8a05000U;
#endif
    /* Measured self-loop: bits 13:8 are free TX words, bits 21:16 are
     * occupied RX words. Low flags are thresholds, not empty/full flags.
     * Each batch bounded to 32 words; no IRQ ownership change. */
#ifdef CS_I2S_ARM1_ECHO_TEST
    const u32 receive_base=0xf8a06000U;
    /* Drain the unused ARM0 receive direction and clock ARM1 with silence. */
    for(u32 i=0;i<32U && ((cs_i2s_read(0xf8a05010U)>>16)&63U);i++)(void)cs_i2s_read(0xf8a0501cU);
#ifndef CS_I2S_ARM1_RX_ONLY
    for(u32 i=0;i<32U && ((cs_i2s_read(0xf8a06010U)>>8)&63U);i++)cs_i2s_write(0xf8a0601cU,0);
#endif
#else
    const u32 receive_base=0xf8a05000U;
#endif
    for(u32 i=0;i<32U && ((cs_i2s_read(receive_base+0x10U)>>16)&63U);i++) {
        u32 word=cs_i2s_read(receive_base+0x1cU);
        cs_i2s_last_rx=word;cs_i2s_rx++;if(word)cs_i2s_rx_nonzero++;
#if defined(CS_I2S_ARM1_RX_ONLY) && defined(CS_I2S_ARM1_ECHO_TEST)
        cs_rx_window_words++;
        for(u32 half=0;half<2U;half++) {
            int sample=(short)(word>>(half*16U));
            u32 magnitude=sample<0?(u32)-sample:(u32)sample;
            if(magnitude>64U)cs_rx_window_active++;
            if(magnitude>cs_rx_window_peak)cs_rx_window_peak=magnitude;
        }
#endif
#ifdef CS_I2S_ARM_ECHO_TEST
        if(cs_echo_started) {
#ifdef CS_I2S_USERSPACE_PCM
            cs_pcm_receive_word(word);
#else
            if(cs_echo_write-cs_echo_read>=512U){cs_echo_read++;cs_echo_overrun++;}
            cs_echo_words[cs_echo_write++&511U]=word;
            for(u32 half=0;half<2U;half++) {
                int sample=(short)(word>>(half*16U));
                u32 magnitude=sample<0?(u32)-sample:(u32)sample;
                if(magnitude>cs_echo_rx_peak)cs_echo_rx_peak=magnitude;
            }
#endif
        }
#endif
    }
#if (!defined(CS_I2S_PORT_TONE_TEST) || defined(CS_I2S_ARM_TONE_TEST)) && !defined(CS_I2S_STREAMING_PCM)
    static const short sine[16]={0,3827,7071,9239,10000,9239,7071,3827,0,-3827,-7071,-9239,-10000,-9239,-7071,-3827};
#define CS_I2S_SINE_MASK 15U
    unsigned long long elapsed=now-cs_audio_play_at;
    u32 step=elapsed<2000000000ULL?1U:elapsed<4000000000ULL?2U:3U;
#ifdef CS_I2S_ARM1_RX_ONLY
    /* Separate the ARM uplink control from the initial 1 kHz DSP beep. */
    step=elapsed<1000000000ULL?1U:3U;
#endif
#endif
    for(u32 i=0;i<32U && ((cs_i2s_read(transmit_base+0x10U)>>8)&63U);i++) {
#ifdef CS_I2S_STREAMING_PCM
        u32 word=cs_pcm_transmit_word();
        if(word)cs_echo_nonzero++;
        cs_i2s_write(transmit_base+0x1cU,word);cs_i2s_tx++;
#elif defined(CS_I2S_PORT_TONE_TEST) && !defined(CS_I2S_ARM_TONE_TEST)
        cs_i2s_write(transmit_base+0x1cU,0);cs_i2s_tx++;
#else
#ifdef CS_I2S_ARM_ECHO_TEST
        if(cs_echo_started) {
            u32 word=0;
#ifdef CS_I2S_USERSPACE_PCM
            word=cs_pcm_transmit_word();
#else
            if(cs_echo_write-cs_echo_read>320U) {
                u32 index=cs_echo_read++&511U;
                word=cs_echo_words[index];cs_echo_words[index]=0;
            } else cs_echo_underrun++;
#endif
            if(word)cs_echo_nonzero++;
            cs_i2s_write(transmit_base+0x1cU,word);cs_i2s_tx++;continue;
        }
#endif
        unsigned short first=(unsigned short)sine[cs_i2s_phase&CS_I2S_SINE_MASK];cs_i2s_phase+=step;
        unsigned short second=(unsigned short)sine[cs_i2s_phase&CS_I2S_SINE_MASK];cs_i2s_phase+=step;
        cs_i2s_write(transmit_base+0x1cU,(u32)first<<16|second);cs_i2s_tx++;
#endif
    }
#ifndef CS_I2S_USERSPACE_PCM
    if(now>=cs_audio_next_sample) {
#if defined(CS_I2S_ARM1_RX_ONLY) && defined(CS_I2S_ARM1_ECHO_TEST)
        printk("<6>" CS_AUDIO_LOG " arm1_rx_window words=%u active_samples=%u peak=%u echo=%u process=%08x no_samples_logged=1\n",
            cs_rx_window_words,cs_rx_window_active,cs_rx_window_peak,cs_echo_started,cs_i2s_read(0xf8a06004U));
        cs_rx_window_words=cs_rx_window_active=cs_rx_window_peak=0;
#endif
        printk("<6>" CS_AUDIO_LOG " i2s_pcm_sample tx_words=%u rx_words=%u rx_nonzero=%u fifo_status=%08x irq_status=%08x\n",
            cs_i2s_tx,cs_i2s_rx,cs_i2s_rx_nonzero,cs_i2s_read(receive_base+0x10U),cs_i2s_read(receive_base+0x18U));
#ifdef CS_I2S_ARM_TONE_TEST
        printk("<6>" CS_AUDIO_LOG " i2s_control_readback loop=%08x timing=%08x process=%08x clock=%08x divisor=%08x/%08x\n",
            cs_i2s_read(0xf8440060U),cs_i2s_read(0xf8a05008U),cs_i2s_read(0xf8a05004U),
            cs_i2s_read(0xf8a00014U),cs_i2s_read(0xf8a00058U),cs_i2s_read(0xf8a0005cU));
#endif
#ifdef CS_I2S_PORT_TONE_TEST
        const volatile unsigned short *tone=(const volatile unsigned short *)0xfad011b0U;
        printk("<6>" CS_AUDIO_LOG " port_tone_sample tone_status_raw=%u duration_raw=%u\n",tone[7],tone[6]);
#endif
        cs_audio_next_sample=now+1000000000ULL;
    }
#endif
}
#endif
