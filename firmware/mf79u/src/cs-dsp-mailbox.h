/* Exact B03 DSP audio mailbox transport and speech-channel validation. */
#ifndef MF79U_CS_DSP_MAILBOX_H
#define MF79U_CS_DSP_MAILBOX_H
static u32 cs_audio_channel_last=0xffffffffU;
static int cs_audio_ram(u32 p,u32 n) {
    /* The TCH context can be static CP BSS, as in the checked channel sampler,
     * rather than a kernel heap allocation. Both ranges are exact B03 RAM. */
    return ram(p,n) || (n && p>=0xbf59e000U && p<=0xbf619ba8U-n);
}
static int cs_audio_layout(void) {
    static const u8 writer[8]={0x10,0xb5,0x01,0x39,0x0b,0x4c,0x54,0xf8};
    static const u8 wrapper[6]={0x00,0x23,0xff,0xf7,0xe1,0xbf};
    return match(0xbf3e9d40U,writer,8) && match(0xbf3e9d78U,wrapper,6) &&
      *(const volatile u32 *)0xbf59f404U==0xfad0100aU &&
      *(const volatile u32 *)0xbf59f46cU==0xfad011b0U;
}
static int cs_audio_channel(void) {
    u32 p=0,c=0,reason=0;u8 mode=0,ch=0;
    if(probe_kernel_read(&p,(const void *)0xbf5a7720U,4) || !cs_audio_ram(p,0x147U))reason=1;
    else if(probe_kernel_read(&c,(const void *)(p+0x120U),4) || !cs_audio_ram(c,10U))reason=2;
    else if(probe_kernel_read(&ch,(const void *)(c+8U),1) ||
            probe_kernel_read(&mode,(const void *)(p+0x12aU),1))reason=3;
    /* B03 BF40FA60..FAA6 classifies mode 1 as speech (mask 0x783).
     * MT16 observed connected channel 1 / mode 1; keep this diagnostic
     * limited to that observed mode and the original AMR mode 9.
     * The separate AMR frame candidate still requires mode 9. */
    else if(ch!=1U || (mode!=1U && mode!=9U))reason=4;
    else if(!cs_audio_layout())reason=5;
    u32 state=reason|(u32)mode<<8|(u32)ch<<16;
    if(state!=cs_audio_channel_last) {
        printk("<6>" CS_AUDIO_LOG " dsp_audio_channel_reason=%u mode=%u channel=%u cp_bss_allowed=1\n",reason,mode,ch);
        cs_audio_channel_last=state;
    }
    return reason==0;
}
static int cs_audio_command(u32 command,u32 count,const unsigned short *params) {
    if(!cs_audio_layout() || count<1U || count>28U ||
       (command!=0x0fU && command!=0x10U && command!=0x11U && command!=0x12U &&
        command!=0x13U && command!=0x14U && command!=0x15U && command!=0x17U &&
        command!=0x18U && command!=0x19U))return 0;
    volatile u32 *pending=(volatile u32 *)0xfad00024U;
    if(*pending&4U){printk("<4>" CS_AUDIO_LOG " dsp_audio_busy_before=%02x\n",command);return 0;}
    volatile unsigned short *box=(volatile unsigned short *)0xfad0107aU;
    box[0]=(unsigned short)command;
    for(u32 i=1;i<count;i++)box[i]=params[i-1U];
    u32 flags;
    __asm__ volatile("mrs %0, cpsr\n\tcpsid i":"=r"(flags)::"memory");
    volatile u32 *request=(volatile u32 *)0xfad0001cU,*irq=(volatile u32 *)0xf9100030U;
    *request|=4U;
    __asm__ volatile("dmb sy":::"memory");
    *irq|=4U;*irq&=~4U;
    __asm__ volatile("dmb sy\n\tmsr cpsr_c, %0"::"r"(flags):"memory");
    /* Let the DSP service the notification before another audio command.
     * mailbox_idle below remains a status observation, not proof of audio. */
    msleep(2);
    unsigned long long deadline=cs_monotonic_ns()+100000000ULL;
    while((*pending&4U) && cs_monotonic_ns()<deadline)msleep(1);
    u32 ready=!(*pending&4U);
    /* The idle B03 test observed -command for every allowlisted command.
     * A cleared pending flag alone must not continue after a rejection.
     * This read is non-consuming; it proves acceptance, not PCM delivery. */
    u32 response=box[0];
    printk("<6>" CS_AUDIO_LOG " dsp_audio_command=%02x total_halfwords=%u mailbox_idle=%u response=%04x negative_ack=%u rejected_zero=%u tone_status=%u duration_raw=%u\n",
           command,count,ready,response,response==(unsigned short)(0U-command),response==0U,
           *(const volatile unsigned short *)0xfad011beU,
           *(const volatile unsigned short *)0xfad011bcU);
    return ready && response==(unsigned short)(0U-command);
}
#endif
