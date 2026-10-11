/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03 passive DSP self-check observer. Chains the original function;
 * never creates a DSP command, varies its arguments, or initiates radio/calls.
 * The only CP write is the checked caller's function literal, restored after
 * the bounded watch. Pinned until reboot because a caller can retain our PC.
 */
typedef unsigned int u32;
typedef unsigned char u8;
typedef unsigned short u16;
extern int printk(const char *,...);
extern long probe_kernel_read(void *,const void *,unsigned long);
extern char __this_module[];
extern int try_module_get(void *);
extern void module_put(void *);
extern void *kthread_create_on_node(int (*)(void *),void *,int,const char *,...);
extern int wake_up_process(void *);
extern int kthread_stop(void *);
extern int kthread_should_stop(void);
extern void msleep(unsigned int);
#ifndef CS_WATCH_SECONDS
#define CS_WATCH_SECONDS 120
#endif
#define PREFIX "MF79U_CS_DSP_BOOT"
static volatile u32 *const slot=(volatile u32 *)0xbf3e9b98U;
static u32 (*const original)(u32)=(u32 (*)(u32))0xbf3ea119U;
static volatile u32 events;
static int match(u32 a,const u8 *expected,u32 n) {
    u8 actual[8];
    if(n>8U || probe_kernel_read(actual,(const void *)a,n))return 0;
    for(u32 i=0;i<n;i++)if(actual[i]!=expected[i])return 0;
    return 1;
}
static u32 observe(u32 connection) {
    /* Collect only after a real vendor invocation. This fixed host parameter
     * range is initialized by BF3EA118, not a speech payload or SIM buffer.
     * 1020's address-space meaning is not assumed; no speculative read there.
     */
    u32 result=original(connection);
    u32 count=__sync_add_and_fetch(&events,1U);
    if(count<=16U) {
        const volatile u16 *p=(const volatile u16 *)0xfad0100aU;
        u16 ack=p[0],field1=p[1],field2=p[2],field3=p[3],field4=p[4];
        printk("<6>" PREFIX " observed=%u connection=%u result=%u ack=%04x fields=%04x,%04x,%04x,%04x original_chained=1 new_commands=0\n",
            count,connection,result,ack,field1,field2,field3,field4);
    }
    return result;
}
static int expiry(void *unused) {
    (void)unused;
    for(u32 i=0;i<CS_WATCH_SECONDS;i++) {
        if(kthread_should_stop())return 0;
        msleep(1000U);
    }
    if(kthread_should_stop())return 0;
    u32 restored=__sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
    printk("<6>" PREFIX " expired seconds=%u events=%u literal_restored=%u pinned_until_reboot=1\n",
        CS_WATCH_SECONDS,events,restored);
    return 0;
}
int init_module(void) {
    static const u8 selfcheck[8]={0x2d,0xe9,0xf0,0x41,0x21,0x23,0xdf,0xf8};
    static const u8 caller[8]={0x20,0x46,0x2d,0x4b,0x98,0x47,0x82,0x46};
    if(!match(0xbf3ea118U,selfcheck,8U) || !match(0xbf3e9ae0U,caller,8U))return -19;
    if(*slot!=(u32)original)return -16;
    void *worker=kthread_create_on_node(expiry,(void *)0,-1,"mf79u_dsp_boot_expire");
    if(!worker || (u32)worker>=0xfffff001U)return -12;
    if(!try_module_get(__this_module)){kthread_stop(worker);return -16;}
    if(!__sync_bool_compare_and_swap(slot,(u32)original,(u32)observe)) {
        kthread_stop(worker);module_put(__this_module);return -16;
    }
    printk("<6>" PREFIX " armed seconds=%u literal=%08x original=%08x observer=%08x no_sends=1 no_calls=1 dsp_program_upload=0 pinned_until_reboot=1\n",
        CS_WATCH_SECONDS,(u32)slot,(u32)original,(u32)observe);
    wake_up_process(worker);return 0;
}
void cleanup_module(void) {}
