/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03 static MMIO mappings, non-consuming control registers only.
 * No clock enable, FIFO data access, register writes or call operations.
 */
typedef unsigned int u32;
extern int printk(const char *,...);
extern long probe_kernel_read(void *,const void *,unsigned long);
extern void *clk_get(void *,const char *);
extern void clk_put(void *);
extern unsigned long clk_get_rate(void *);
int init_module(void) {
    static const u32 addresses[]={0xf8440060U,0xf8a00014U,0xf8a00018U,0xf8a0001cU,
        0xf8a00058U,0xf8a0005cU,0xf8a00060U,0xf8a00064U,0xf8a00068U,
        0xf843b068U,0xf8a05004U,0xf8a05008U,
        0xf8a0500cU,0xf8a05010U,0xf8a05014U,0xf8a05018U,0xf8a05020U,
        0xf8a06004U,0xf8a06008U,0xf8a0600cU,0xf8a06010U,0xf8a06014U};
    static const char *const names[]={"i2s0_apb_clk","i2s0_work_clk","i2s1_apb_clk","i2s1_work_clk"};
    for(u32 i=0;i<4U;i++) {
        void *clock=clk_get((void *)0,names[i]);
        if((u32)clock>=0xfffff001U){printk("<6>MF79U_CS_I2S clock=%s lookup_error=%d no_enable=1\n",names[i],(int)clock);continue;}
        printk("<6>MF79U_CS_I2S clock=%s rate=%lu no_enable=1\n",names[i],clk_get_rate(clock));
        clk_put(clock);
    }
    for(u32 i=0;i<sizeof(addresses)/sizeof(addresses[0]);i++) {
        u32 value=0;
        if(probe_kernel_read(&value,(const void *)addresses[i],4U))return -14;
        printk("<6>MF79U_CS_I2S address=%08x value=%08x non_consuming=1\n",addresses[i],value);
    }
    /* Exact B03 CP clock records, including gsm_48m. No clock enable/reset.
     * The extra LSP clock controls are within the same static MMIO mapping;
     * they are control words, never FIFO data or interrupt acknowledgments. */
    static const u32 indices[]={29U,30U,31U,32U,53U};
    for(u32 i=0;i<sizeof(indices)/sizeof(indices[0]);i++) {
        u32 index=indices[i];
        unsigned short flags=0;
        u32 hardware=0,software=0;
        u32 record=0xbf55c5a0U+index*0x48U;
        if(probe_kernel_read(&flags,(const void *)(record+0x16U),2U) ||
           probe_kernel_read(&hardware,(const void *)(record+0x1cU),4U) ||
           probe_kernel_read(&software,(const void *)(record+0x24U),4U))return -14;
        printk("<6>MF79U_CS_I2S cp_clock_index=%u hw_flag=%u sw_flag=%u hw_register=%08x sw_register=%08x no_enable=1\n",
            index,flags&255U,flags>>8,hardware,software);
    }
    printk("<6>MF79U_CS_I2S preflight=verified no_writes=1 no_fifo_data=1\n");
    return 0;
}
void cleanup_module(void) {printk("<6>MF79U_CS_I2S unloaded\n");}
