/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03 module notification ABI probe; optional passive initial DSP load
 * observer. Default build installs no CP hook and touches no DSP. The opt-in
 * build must load before CP. It chains only the real vendor self-check, never
 * requests DSP memory, changes command arguments or uploads DSP programs.
 */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
extern int printk(const char *,...);
extern long probe_kernel_read(void *,const void *,unsigned long);
struct notifier_block {
    int (*call)(struct notifier_block *,unsigned long,void *);
    struct notifier_block *next;
    int priority;
};
extern int register_module_notifier(struct notifier_block *);
extern int unregister_module_notifier(struct notifier_block *);
#define PREFIX "MF79U_CS_DSP_LOAD"
static u32 registered;
static int name_is(const volatile u8 *m,const char *name) {
    for(u32 i=0;i<48U;i++) {
        if(m[12U+i]!=(u8)name[i])return 0;
        if(!name[i])return 1;
    }
    return 0;
}
#ifdef CS_DSP_LOAD_OBSERVE
extern char __this_module[];
extern int try_module_get(void *);
extern void module_put(void *);
extern void *kthread_create_on_node(int (*)(void *),void *,int,const char *,...);
extern int wake_up_process(void *);
extern int kthread_stop(void *);
extern int kthread_should_stop(void);
extern void msleep(unsigned int);
#ifndef CS_WATCH_SECONDS
#define CS_WATCH_SECONDS 180
#endif
static volatile u32 *slot;
static u32 (*original)(u32);
static volatile u32 events;
static u32 cp_base;
static volatile u32 watching=1U;
static u16 saved_parameters[4][17];
static u32 saved_connections[4],saved_results[4];
static volatile u32 saved_valid;
static int match(u32 a,const u8 *expected) {
    u8 actual[8];
    if(probe_kernel_read(actual,(const void *)a,8U))return 0;
    for(u32 i=0;i<8U;i++)if(actual[i]!=expected[i])return 0;
    return 1;
}
static u32 observe(u32 connection) {
    u32 result=original(connection);
    u32 count=__sync_add_and_fetch(&events,1U);
    if(count<=4U) {
        /* Fixed host command/parameter window, immediately after its real
         * initial-load self-check. This is neither a DSP ROM address mapping
         * nor a voice/SIM payload reader. Extra halfword meanings are unknown.
         */
        const volatile u16 *p=(const volatile u16 *)0xfad0100aU;
        for(u32 i=0;i<17U;i++)saved_parameters[count-1U][i]=p[i];
        saved_connections[count-1U]=connection;saved_results[count-1U]=result;
        __sync_fetch_and_or(&saved_valid,1U<<(count-1U));
        printk("<6>" PREFIX " observed=%u connection=%u result=%u ack=%04x fields=%04x,%04x,%04x,%04x original_chained=1 new_commands=0\n",
            count,connection,result,p[0],p[1],p[2],p[3],p[4]);
        for(u32 i=5U;i<17U;i+=4U)
            printk("<6>" PREFIX " host_parameter_offset=%u halfwords=%04x,%04x,%04x,%04x semantics_unverified=1\n",
                i,p[i],p[i+1U],p[i+2U],p[i+3U]);
    }
    return result;
}
static u32 restore_slot(void) {
    u32 flags,restored=0;
    __asm__ volatile("mrs %0,cpsr\n\tcpsid i":"=r"(flags)::"memory");
    watching=0;
    if(slot)restored=__sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
    slot=(volatile u32 *)0;
    __asm__ volatile("dmb sy\n\tmsr cpsr_c,%0"::"r"(flags):"memory");
    return restored;
}
#endif
static int notification(struct notifier_block *nb,unsigned long state,void *pointer) {
    (void)nb;
    const volatile u8 *m=(const volatile u8 *)pointer;
    if((u32)m<0xbf000000U || (u32)m>0xbf800000U-328U)return 0;
    if(name_is(m,"mf79u_cs_module_layout")) {
        printk("<6>" PREFIX " notifier_probe_state=%lu structure_state=%u core=%08x size=%u abi_notification_seen=1 no_cp_hook=1\n",
            state,*(const volatile u32 *)m,*(const volatile u32 *)(m+196U),*(const volatile u32 *)(m+204U));
        return 0;
    }
#ifdef CS_DSP_LOAD_OBSERVE
    if(!name_is(m,"cpko"))return 0;
    if(state==2U) {
        u32 restored=restore_slot();
        printk("<6>" PREFIX " cp_going=1 literal_restored=%u\n",restored);
        return 0;
    }
    if(state!=1U || !watching)return 0;
    u32 core=*(const volatile u32 *)(m+196U);
    u32 size=*(const volatile u32 *)(m+204U);
    u32 init=*(const volatile u32 *)(m+188U);
    static const u8 selfcheck[8]={0x2d,0xe9,0xf0,0x41,0x21,0x23,0xdf,0xf8};
    static const u8 caller[8]={0x20,0x46,0x2d,0x4b,0x98,0x47,0x82,0x46};
    if(cp_base || *(const volatile u32 *)m!=1U || core<0xbf000000U ||
       core>0xbf800000U-6397096U || size!=6397096U || init!=core+0x3e30d8U ||
       !match(core+0x3ea118U,selfcheck) || !match(core+0x3e9ae0U,caller)) {
        printk("<4>" PREFIX " cp_coming_rejected=1 core=%08x size=%u init=%08x no_cp_hook=1\n",core,size,init);
        return 0;
    }
    volatile u32 *candidate=(volatile u32 *)(core+0x3e9b98U);
    u32 target=core+0x3ea119U;
    if(*candidate!=target || !try_module_get(pointer))return 0;
    u32 flags,armed=0;
    __asm__ volatile("mrs %0,cpsr\n\tcpsid i":"=r"(flags)::"memory");
    if(watching && !slot) {
        original=(u32 (*)(u32))target;
        armed=__sync_bool_compare_and_swap(candidate,target,(u32)observe);
        if(armed){slot=candidate;cp_base=core;}
    }
    __asm__ volatile("dmb sy\n\tmsr cpsr_c,%0"::"r"(flags):"memory");
    if(!armed){module_put(pointer);return 0;}
    /* Retain CP and observer references until reboot. No rmmod can free a
     * callback retained by the real initialization stack. */
    printk("<6>" PREFIX " cp_coming_verified=1 core=%08x literal=%08x original=%08x observer=%08x unchanged_selfcheck=1 pinned_until_reboot=1\n",
        core,(u32)candidate,target,(u32)observe);
#else
    (void)state;
#endif
    return 0;
}
static struct notifier_block notifier={notification,(struct notifier_block *)0,0};
#ifdef CS_DSP_LOAD_OBSERVE
static int expiry(void *unused) {
    (void)unused;
    for(u32 i=0;i<CS_WATCH_SECONDS;i++) {
        if(kthread_should_stop())return 0;
        msleep(1000U);
    }
    u32 restored=restore_slot();
    int result=unregister_module_notifier(&notifier);
    if(!result)registered=0;
    printk("<6>" PREFIX " expired seconds=%u events=%u core=%08x literal_restored=%u notifier_removed=%u pinned_until_reboot=1\n",
        CS_WATCH_SECONDS,events,cp_base,restored,!registered);
    /* Repeat bounded cached initialization evidence after boot-log churn. */
    u32 valid=saved_valid;
    __asm__ volatile("dmb sy":::"memory");
    for(u32 n=0;n<4U;n++)if(valid&(1U<<n)) {
        const u16 *p=saved_parameters[n];
        printk("<6>" PREFIX " saved_observed=%u connection=%u result=%u ack=%04x fields=%04x,%04x,%04x,%04x original_chained=1 new_commands=0\n",
            n+1U,saved_connections[n],saved_results[n],p[0],p[1],p[2],p[3],p[4]);
        for(u32 i=5U;i<17U;i+=4U)
            printk("<6>" PREFIX " saved_host_parameter_offset=%u halfwords=%04x,%04x,%04x,%04x semantics_unverified=1\n",
                i,p[i],p[i+1U],p[i+2U],p[i+3U]);
    }
    return 0;
}
#endif
int init_module(void) {
#ifdef CS_DSP_LOAD_OBSERVE
    void *worker=kthread_create_on_node(expiry,(void *)0,-1,"mf79u_dsp_load_expire");
    if(!worker || (u32)worker>=0xfffff001U)return -12;
    if(!try_module_get(__this_module)){kthread_stop(worker);return -16;}
#endif
    int result=register_module_notifier(&notifier);
    if(result) {
#ifdef CS_DSP_LOAD_OBSERVE
        kthread_stop(worker);module_put(__this_module);
#endif
        return result;
    }
    registered=1;
#ifdef CS_DSP_LOAD_OBSERVE
    wake_up_process(worker);
    printk("<6>" PREFIX " registered=1 passive_initial_load=1 seconds=%u dynamic_cp_base=1 new_commands=0 no_calls=1\n",CS_WATCH_SECONDS);
#else
    printk("<6>" PREFIX " registered=1 notifications_only=1 no_cp_hook=1 no_dsp_access=1\n");
#endif
    return 0;
}
void cleanup_module(void) {
    if(registered)unregister_module_notifier(&notifier);
    printk("<6>" PREFIX " unloaded notifier_removed=1\n");
}
