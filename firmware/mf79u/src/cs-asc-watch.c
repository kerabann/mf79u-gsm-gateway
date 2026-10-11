/* SPDX-License-Identifier: GPL-2.0-only
 * B03 ASC observer: chain all five arguments, retain vendor ownership.
 * Fixed AAD4/ABDF envelopes and two wire header bytes are inspected.
 * For CC clearing only, at most seven bytes admit a bounded Cause reader.
 * State bytes are taken from the exact ascmain.c context. No MMIO or sends.
 * The callback remains pinned after restoration because OSS has no RCU ABI.
 */
typedef unsigned int u32;
typedef unsigned char u8;
#include "cs-wire.h"
typedef void (*asc_callback)(u32,u32,void *,u32,void *);
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
#define CS_WATCH_SECONDS 90
#endif
static volatile u32 *slot;
static asc_callback original;
static volatile u32 events,transmissions,receptions;
static int match(u32 address,const u8 *expected,u32 size) {
    u8 actual[8];
    if(size>8 || probe_kernel_read(actual,(const void *)address,size))return 0;
    for(u32 i=0;i<size;++i)if(actual[i]!=expected[i])return 0;
    return 1;
}
static int ram(u32 address,u32 size) {
    return size && address>=0xc0000000U && address<=0xc3bc0000U-size;
}
static void wire(u32 pointer,u32 length,u32 count,int uplink,u32 connection,u32 flag) {
    u8 prefix[7];struct cs_wire_metadata metadata;
    if(count>64U)return;
    if(length<2U || length>2048U || !ram(pointer,length) ||
       probe_kernel_read(prefix,(const void *)pointer,2)) {
        printk("<6>MF79U_CS_ASC %s=%u rejected=wire\n",uplink?"tx":"rx",count);return;
    }
    u32 captured=2;
    u32 type=prefix[1]&63U;
    if((prefix[0]&15U)==3U && (type==0x25U || type==0x2dU || type==0x2aU)) {
        captured=length<7U?length:7U;
        if(probe_kernel_read(prefix,(const void *)pointer,captured))return;
    }
    int decoded=cs_wire_metadata(prefix,captured,length,&metadata);
    printk("<6>MF79U_CS_ASC %s=%u connection=%u raw_flag=%u wire_length=%u pd=%u ti=%u type=%02x nsd=%u reached_asc=1\n",
        uplink?"tx":"rx",count,connection,flag,length,metadata.pd,metadata.ti,metadata.type,prefix[1]>>6);
    if(metadata.cause_present)printk("<6>MF79U_CS_ASC %s=%u cause=%u coding=%u location=%u\n",
        uplink?"tx":"rx",count,metadata.cause,metadata.coding,metadata.location);
    else if(decoded<0)printk("<6>MF79U_CS_ASC %s=%u cause_rejected=truncated_or_invalid\n",uplink?"tx":"rx",count);
}
static int state(u8 *bytes) {
    /* The current SIM lookup is only invoked in the actual ASC task context.
     * BF47BECA/BF47A9C0 use the same helper and indexed context table. */
    u32 sim=((u32 (*)(void))0xbf47cdfdU)();
    u32 context=0;
    if(sim>1 || probe_kernel_read(&context,(const void *)(0xbf5cad68U+4U*sim),4))return -1;
    /* CP's per-SIM context can live in its own pinned .bss, as well as kmalloc
     * RAM. Admit only those two proven memory regions, never DSP/MMIO. */
    if((!ram(context,9U) && !(context>=0xbf59e000U && context<=0xbf61aff7U)) ||
       probe_kernel_read(bytes,(const void *)context,9))return -1;
    return (int)sim;
}
static void observe(u32 phase,u32 id,void *payload,u32 length,void *work) {
    u32 count=__sync_add_and_fetch(&events,1);
    u8 before[9],after[9];int sim=phase==2U?state(before):-1;
    int log=count<=128U || (id>=0xaad2U && id<=0xaad5U);
    if(log && count<=512U) {
        if(sim>=0)printk("<6>MF79U_CS_ASC event=%u phase=%u id=%04x length=%u sim=%u state_before=%u substate_before=%u rat_before=%u connection_before=%u\n",
            count,phase,id,length,(u32)sim,before[0],before[1],before[6],before[8]);
        else printk("<6>MF79U_CS_ASC event=%u phase=%u id=%04x length=%u context_unavailable=1\n",count,phase,id,length);
    }
    if(phase==2U && id==0xaad4U && length==12U && ram((u32)payload,12U)) {
        u32 envelope[3];
        u32 tx=__sync_add_and_fetch(&transmissions,1);
        if(!probe_kernel_read(envelope,payload,12))wire(envelope[2],envelope[1],tx,1,envelope[0]&255U,(envelope[0]>>8)&255U);
        else if(tx<=64U)printk("<6>MF79U_CS_ASC tx=%u rejected=envelope\n",tx);
    }
    /* BF05D620 constructs ABDF: byte0 CS connection, length word+4, pointer+8.
     * No raw wire data is retained or printed; original retains all ownership. */
    if(phase==2U && id==0xabdfU && length==12U && ram((u32)payload,12U)) {
        u32 envelope[3];u32 rx=__sync_add_and_fetch(&receptions,1);
        if(!probe_kernel_read(envelope,payload,12))wire(envelope[2],envelope[1],rx,0,envelope[0]&255U,0);
    }
    /* Exact RR release constructor BF05D184: zeroed8-byte body; byte0 comes
     * from gsma context+38A, byte1 from+38F, u16+4 from+38C, byte2 fixed0.
     * Scalar fields only; their enum meanings are not assumed from 3GPP. */
    if(phase==2U && id==0xabd9U && length==8U && ram((u32)payload,8U)) {
        u8 field0=255,field1=255;unsigned short field4=65535;
        if(!probe_kernel_read(&field0,payload,1) &&
           !probe_kernel_read(&field1,(const u8 *)payload+1U,1) &&
           !probe_kernel_read(&field4,(const u8 *)payload+4U,2))
            printk("<6>MF79U_CS_ASC rr_release_field0=%u field1=%u field4=%u constructor_verified=1\n",field0,field1,field4);
    }
    original(phase,id,payload,length,work);
    /* The original has freed payload. Only the persistent ASC context remains. */
    if(log && count<=512U && sim>=0 && state(after)==sim)
        printk("<6>MF79U_CS_ASC event=%u state_after=%u substate_after=%u rat_after=%u connection_after=%u\n",
            count,after[0],after[1],after[6],after[8]);
}
static int expiry(void *unused) {
    (void)unused;
    for(u32 i=0;i<CS_WATCH_SECONDS;++i) {
        if(kthread_should_stop())return 0;
        msleep(1000);
    }
    if(kthread_should_stop())return 0;
    int restored=__sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
    printk("<6>MF79U_CS_ASC expired seconds=%u events=%u transmissions=%u receptions=%u callback_restored=%u pinned_until_reboot=1\n",
        CS_WATCH_SECONDS,events,transmissions,receptions,restored);
    return 0;
}
int init_module(void) {
    static const u8 callback[8]={0x70,0xb5,0x0c,0x46,0x15,0x46,0x1e,0x46};
    static const u8 sim_code[8]={0x08,0xb5,0xda,0x20,0x01,0x4b,0x98,0x47};
    static const u8 rr_release_code[8]={0x38,0xb5,0xa7,0x20,0x14,0x4b,0x98,0x47};
    if(!match(0xbf47be94U,callback,8) || !match(0xbf47cdfcU,sim_code,8) ||
       !match(0xbf05d184U,rr_release_code,8) ||
       *(const volatile u32 *)0xbf59e3c0U!=0xbf55a954U ||
       *(const volatile u32 *)0xbf59e3bcU!=39U)return -19;
    u32 list=*(const volatile u32 *)0xbf5bcd88U;
    if(!ram(list,39U*4U) || (list&3U))return -71;
    u32 task=((const volatile u32 *)list)[38];
    static const u8 name[4]={'A','S','C',0};
    if(!ram(task,0xbcU) || (task&3U) || !match(task+16U,name,4) ||
       *(const volatile u32 *)(task+8U)!=1U ||
       *(const volatile u32 *)0xbf55f0e4U!=task ||
       *(const volatile u8 *)(task+0x9aU)!=2U)return -71;
    slot=(volatile u32 *)(task+0x50U);original=(asc_callback)*slot;
    if((u32)original!=0xbf47be95U)return -16;
    for(u32 i=0;i<2;++i) {
        u32 context=0;
        if(!probe_kernel_read(&context,(const void *)(0xbf5cad68U+4U*i),4))
            printk("<6>MF79U_CS_ASC context_index=%u address=%08x\n",i,context);
    }
    void *worker=kthread_create_on_node(expiry,(void *)0,-1,"mf79u_asc_expire");
    if(!worker || (u32)worker>=0xfffff001U)return -12;
    if(!try_module_get(__this_module)){kthread_stop(worker);return -16;}
    if(!__sync_bool_compare_and_swap(slot,(u32)original,(u32)observe)) {
        kthread_stop(worker);module_put(__this_module);return -16;
    }
    printk("<6>MF79U_CS_ASC armed seconds=%u callback_slot=%08x original=%08x observer=%08x no_sends=1 wire_header_bytes=2 pinned_until_reboot=1\n",
        CS_WATCH_SECONDS,(u32)slot,(u32)original,(u32)observe);
    wake_up_process(worker);return 0;
}
void cleanup_module(void) {}
