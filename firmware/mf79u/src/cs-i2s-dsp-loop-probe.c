/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03 bounded no-call digital audio-port diagnostic. No CC callbacks,
 * SIM answer/dial, GPIO, DSP program upload, DMA or IRQ handlers. Synthetic
 * tone only; sample bytes never logged. Peripheral and AP fields restored.
 */
typedef unsigned int u32;
typedef unsigned char u8;
extern int printk(const char *,...);
extern long probe_kernel_read(void *,const void *,unsigned long);
extern void msleep(unsigned int);
union cs_ktime {signed long long tv64;};
extern union cs_ktime ktime_get(void);
static unsigned long long cs_monotonic_ns(void){return (unsigned long long)ktime_get().tv64;}
static int ram(u32 a,u32 n){return n && a>=0xc0000000U && a<=0xc3bc0000U-n;}
static int match(u32 a,const u8 *bytes,u32 n){
    u8 actual[8];if(n>8 || probe_kernel_read(actual,(const void *)a,n))return 0;
    for(u32 i=0;i<n;i++)if(actual[i]!=bytes[i])return 0;
    return 1;
}
#define CS_AUDIO_LOG "MF79U_CS_I2S_DSP_LOOP"
#define CS_I2S_IDLE_LOOP_TEST 1
#include "cs-i2s-pcm-candidate.h"
#ifdef CS_I2S_BOTH_PORTS_SIGNAL_TEST
#ifndef CS_I2S_BOTH_PORTS_TEST
#error Signal metadata requires the bounded two port test
#endif
static u32 signal_words[2],signal_changes[2],signal_allones[2],signal_peak[2],signal_last[2],signal_sign[2],signal_crossings[2];
static void signal_metadata(u32 port,u32 word) {
    if(signal_words[port] && word!=signal_last[port])signal_changes[port]++;
    signal_last[port]=word;signal_words[port]++;
    if(word==0xffffffffU)signal_allones[port]++;
    for(u32 shift=0;shift<32U;shift+=16U) {
        int sample=(short)(word>>shift);
        u32 absolute=sample<0?(u32)-sample:(u32)sample;
        if(absolute>signal_peak[port])signal_peak[port]=absolute;
        if(absolute>32U) {
            u32 sign=sample<0?1U:2U;
            if(signal_sign[port] && signal_sign[port]!=sign)signal_crossings[port]++;
            signal_sign[port]=sign;
        }
    }
}
#endif
int init_module(void){
    if(!cs_i2s_layout() || cs_i2s_read(0xf8a05000U)!=0x01030000U ||
       cs_i2s_read(0xf8a05004U) || cs_i2s_read(0xf8a05014U))return -71;
    if(cs_audio_channel())return -16; /* Never replace an assigned speech path. */
    unsigned short saved_tone[11];
    volatile unsigned short *tone=(volatile unsigned short *)0xfad011b0U;
    for(u32 i=0;i<11;i++)saved_tone[i]=tone[i];
    printk("<6>" CS_AUDIO_LOG " configured no_calls=1 no_cc_hooks=1 dsp_program_upload=0\n");
    printk("<6>" CS_AUDIO_LOG " reference_tdm_extra_cycle=%u timing=%08x b03_bit5_semantics_unverified=1\n",CS_I2S_TDM_EXTRA_CYCLE,CS_I2S_TIMING);
    if(!cs_i2s_start())return -71;
    tone[0]=23170;tone[1]=5656;tone[2]=32767;tone[3]=0;tone[4]=32767;tone[5]=0;
    tone[6]=16000;tone[8]=10;tone[9]=160;tone[10]=160;
    u32 started=cs_audio_command(0x12U,1U,(const unsigned short *)0);
#if defined(CS_I2S_RX_SLOT_TEST) || defined(CS_I2S_RX_START_TEST) || defined(CS_I2S_BOTH_PORTS_TEST)
    (void)cs_audio_step; /* This variant uses its own bounded silent FIFO pump. */
#ifndef CS_I2S_FULL_VOICE_API
#error RX slot comparison requires the complete voice API
#endif
    /* Real reference timing selectors 0/1/2. Only the mono/stereo slot
     * selection changes; the generated divider and DSP profile are equal. */
#ifdef CS_I2S_BOTH_PORTS_SIGNAL_TEST
    static const u32 timings[]={0x01ef2001U,0x01ef2001U,0x01ef2001U};
    static const u32 div_lo[]={0x00200019U,0x00200019U,0x00200019U};
    static const u32 div_hi[]={0x00010032U,0x00010032U,0x00010032U};
#elif defined(CS_I2S_RX_START_TEST) || defined(CS_I2S_BOTH_PORTS_TEST)
    static const u32 timings[]={0x01ef2001U,0x01ff2005U};
    static const u32 div_lo[]={0x00200019U,0x00400019U};
    static const u32 div_hi[]={0x00010032U,0x00010019U};
#else
    static const u32 timings[]={0x01ef2001U,0x01ef4001U,0x01ef6101U};
#endif
#ifdef CS_I2S_BOTH_PORTS_TEST
    u32 port1_tx=0,port1_rx=0,port1_nonzero=0;
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
#endif
    for(u32 phase=0;phase<sizeof(timings)/sizeof(timings[0]) && started;phase++) {
#ifdef CS_I2S_BOTH_PORTS_SIGNAL_TEST
        if(phase==2) {
            /* STOP clears the DSP tone duration/state. Rebuild the same
             * verified tone parameters before START, as connected tests do. */
            tone[0]=23170;tone[1]=5656;tone[2]=32767;tone[3]=0;tone[4]=32767;tone[5]=0;
            tone[6]=16000;tone[8]=10;tone[9]=160;tone[10]=160;
        }
        if(phase && !cs_audio_command(phase==1?0x13U:0x12U,1U,(const unsigned short *)0)) {
            cs_i2s_failed=1;break;
        }
        for(u32 p=0;p<2;p++)signal_words[p]=signal_changes[p]=signal_allones[p]=signal_peak[p]=signal_last[p]=signal_sign[p]=signal_crossings[p]=0;
#else
        if(phase && (!cs_audio_command(0x13U,1U,(const unsigned short *)0) ||
                     !cs_audio_command(0x12U,1U,(const unsigned short *)0))) {
            cs_i2s_failed=1;break;
        }
 #endif
        cs_i2s_write(0xf8a05004U,0);
#if defined(CS_I2S_RX_START_TEST) || defined(CS_I2S_BOTH_PORTS_TEST)
        cs_i2s_write(0xf8a0005cU,cs_i2s_read(0xf8a0005cU)&~0x10000U);
        cs_i2s_write(0xf8a00058U,div_lo[phase]);cs_i2s_write(0xf8a0005cU,div_hi[phase]);
#endif
        cs_i2s_write(0xf8a05008U,timings[phase]);
        cs_i2s_write(0xf8a0500cU,cs_i2s_read(0xf8a0500cU)|3U);
        for(u32 i=0;i<16U;i++)cs_i2s_write(0xf8a0501cU,0);
        cs_i2s_write(0xf8a05004U,7U);
        u32 tx0=cs_i2s_tx,rx0=cs_i2s_rx,nz0=cs_i2s_rx_nonzero;
#ifdef CS_I2S_BOTH_PORTS_TEST
        u32 ptx0=port1_tx,prx0=port1_rx,pnz0=port1_nonzero;
#endif
        unsigned long long end=cs_monotonic_ns()+1600000000ULL;
        while(cs_monotonic_ns()<end) {
            for(u32 i=0;i<32U && ((cs_i2s_read(0xf8a05010U)>>16)&63U);i++) {
                u32 word=cs_i2s_read(0xf8a0501cU);
                cs_i2s_rx++;if(word)cs_i2s_rx_nonzero++;
#ifdef CS_I2S_BOTH_PORTS_SIGNAL_TEST
                signal_metadata(0,word);
#endif
            }
            for(u32 i=0;i<32U && ((cs_i2s_read(0xf8a05010U)>>8)&63U);i++) {
                cs_i2s_write(0xf8a0501cU,0);cs_i2s_tx++;
            }
#ifdef CS_I2S_BOTH_PORTS_TEST
            for(u32 i=0;i<32U && ((cs_i2s_read(0xf8a06010U)>>16)&63U);i++) {
                u32 word=cs_i2s_read(0xf8a0601cU);
                port1_rx++;if(word)port1_nonzero++;
#ifdef CS_I2S_BOTH_PORTS_SIGNAL_TEST
                signal_metadata(1,word);
#endif
            }
#ifndef CS_I2S_ARM1_RX_ONLY
            for(u32 i=0;i<32U && ((cs_i2s_read(0xf8a06010U)>>8)&63U);i++) {
                cs_i2s_write(0xf8a0601cU,0);port1_tx++;
            }
#endif
#endif
            usleep_range(1000,1500);
        }
        printk("<6>" CS_AUDIO_LOG " rx_slot_phase=%u timing=%08x tx_words=%u rx_words=%u rx_nonzero=%u arm_tx_silence=1\n",
            phase,cs_i2s_read(0xf8a05008U),cs_i2s_tx-tx0,cs_i2s_rx-rx0,cs_i2s_rx_nonzero-nz0);
#ifdef CS_I2S_BOTH_PORTS_TEST
        printk("<6>" CS_AUDIO_LOG " arm1_phase=%u timing=%08x process=%08x clock=%08x divider_lo=%08x divider_hi=%08x tx_words=%u rx_words=%u rx_nonzero=%u arm_tx_silence=1\n",
            phase,cs_i2s_read(0xf8a06008U),cs_i2s_read(0xf8a06004U),cs_i2s_read(0xf8a0001cU),
            cs_i2s_read(0xf8a00060U),cs_i2s_read(0xf8a00064U),port1_tx-ptx0,port1_rx-prx0,port1_nonzero-pnz0);
#ifdef CS_I2S_BOTH_PORTS_SIGNAL_TEST
        for(u32 p=0;p<2;p++)printk("<6>" CS_AUDIO_LOG " signal_phase=%u port=%u tone_enabled=%u words=%u word_changes=%u all_ones=%u peak=%u sign_crossings=%u no_samples_logged=1\n",
            phase,p,phase!=1,signal_words[p],signal_changes[p],signal_allones[p],signal_peak[p],signal_crossings[p]);
#endif
#endif
    }
#else
    unsigned long long end=cs_monotonic_ns()+4000000000ULL;
    cs_audio_connected_at=cs_monotonic_ns()-2000000000ULL;
    while(started && cs_monotonic_ns()<end){
        cs_audio_step(1,cs_monotonic_ns());usleep_range(1000,1500);
    }
#endif
    u32 duration=tone[6],status=tone[7];
    u32 stopped=cs_audio_command(0x13U,1U,(const unsigned short *)0);
    cs_audio_restore();
    u32 restored=0;
    if(cs_audio_layout() && !(cs_i2s_read(0xfad00024U)&4U)){
        for(u32 i=0;i<11;i++)if(i!=7)tone[i]=saved_tone[i];
        restored=1;
    }
    printk("<6>" CS_AUDIO_LOG " completed=1 tone_started=%u tone_stopped=%u tone_duration_raw=%u tone_status_raw=%u saved_tone_restored=%u no_calls=1\n",started,stopped,duration,status,restored);
    return restored && !cs_i2s_failed?0:-71;
}
void cleanup_module(void){printk("<6>" CS_AUDIO_LOG " unloaded\n");}
