/* SPDX-License-Identifier: GPL-2.0-only
 * Exact MF79U B03, Linux 3.4.110-rt140 diagnostic module.
 * The accompanying builder recovers module metadata from checksum-verified cfg.ko.
 * No vendor headers, guessed kernel structures, patches, AT, queues, or audio IO.
 * This module only calls two instruction-verified CP boolean getters and reads
 * their known configuration bytes plus the RPMSG registry's scalar metadata.
 */
typedef unsigned int u32;
typedef unsigned char u8;
extern int printk(const char *,...);
static int matches(const volatile u8 *address,const u8 *expected,u32 size) {
    for(u32 i=0;i<size;++i)if(address[i]!=expected[i])return 0;
    return 1;
}
int init_module(void) {
    static const u8 voice_code[8]={0x01,0x4b,0x93,0xf8,0x5d,0x03,0x70,0x47};
    static const u8 open_code[8]={0x01,0x4b,0x93,0xf8,0x5f,0x04,0x70,0x47};
    if(!matches((const volatile u8 *)0xbf3e527cU,voice_code,8) ||
       !matches((const volatile u8 *)0xbf3e6034U,open_code,8)) {
        printk("<3>MF79U_CS_KPROBE signature_mismatch\n");return -19;
    }
    u32 voice=((u32 (*)(void))0xbf3e527dU)();
    u32 open=((u32 (*)(void))0xbf3e6035U)();
    if(voice>1 || open>1 || voice!=*(const volatile u8 *)0xbf59e7e1U ||
       open!=*(const volatile u8 *)0xbf59e8e3U) {
        printk("<3>MF79U_CS_KPROBE getter_mismatch\n");return -71;
    }
    printk("<6>MF79U_CS_KPROBE signature=verified cp_getters=verified voice_support=%u open_voice=%u readonly=1\n",voice,open);
    for(u32 family=0;family<2;++family) {
        const volatile u32 *r=(const volatile u32 *)(0xbf55c214U+family*0x5cU);
        u32 tx=r[0x50/4],rx=r[0x54/4],count=r[0x58/4];
        if(tx!=(family?0xf8300530U:0xf83008c0U) ||
           rx!=(family?0xf8300400U:0xf8300f80U) || count!=(family?10U:64U)) {
            printk("<3>MF79U_CS_KPROBE registry_mismatch family=%u\n",family);return -71;
        }
        printk("<6>MF79U_CS_KPROBE rpmsg_family=%u tx=%08x rx=%08x channels=%u\n",family,tx,rx,count);
        /* CP's verified create-channel code uses these SRAM descriptor tables.
         * Snapshot six scalar words only, never ring payloads or cursor writes. */
        for(u32 direction=0;direction<2;++direction) {
            const volatile u32 *table=(const volatile u32 *)(direction?rx:tx);
            for(u32 channel=0;channel<count;++channel) {
                const volatile u32 *h=table+channel*6;
                u32 base=h[0],send=h[1],recv=h[2],size=h[3],flags=h[4];
                if(!(flags&1U))continue;
                if(size>0x100000U || send>size || recv>size ||
                   ((base|size|send|recv)&3U) ||
                   !((base>=0x82000000U && base<0x82010000U && size<=0x82010000U-base) ||
                     (base>=0x20000000U && base<0x24000000U && size<=0x24000000U-base))) {
                    printk("<6>MF79U_CS_KPROBE descriptor_invalid family=%u direction=%u channel=%u\n",family,direction,channel);
                    continue;
                }
                u32 callback=*(const volatile u32 *)(0xbf5bd1b8U+(family*64U+channel)*4U);
                printk("<6>MF79U_CS_KPROBE channel family=%u direction=%u id=%u base=%08x size=%u send=%u recv=%u flags=%08x callback=%08x\n",family,direction,channel,base,size,send,recv,flags,callback);
            }
        }
    }
    /* zOss_TaskInit passes descriptor+0x44 to task allocation, which stores
     * it at task+0x50. The dispatcher reloads task+0x50 for every event.
     * Exact verified normal task table puts CC at index9 (stride0x58). */
    u32 root=*(const volatile u32 *)0xbf59e3c0U;
    u32 count=*(const volatile u32 *)0xbf59e3bcU;
    u32 list=*(const volatile u32 *)0xbf5bcd88U;
    if(root!=0xbf55a954U || count!=39U || list<0xc0000000U || list>0xc3bbff64U || (list&3U)) {
        printk("<3>MF79U_CS_KPROBE task_table_mismatch\n");return -71;
    }
    u32 task=((const volatile u32 *)list)[9];
    static const u8 cc_name[3]={'C','C',0};
    if(task<0xc0000000U || task>0xc3bbff44U || (task&3U) ||
       !matches((const volatile u8 *)(task+0x10U),cc_name,3) ||
       *(const volatile u32 *)(task+8U)!=1U || *(const volatile u32 *)(task+0x50U)!=0xbf30053dU) {
        printk("<3>MF79U_CS_KPROBE cc_task_mismatch\n");return -71;
    }
    printk("<6>MF79U_CS_KPROBE cc_dispatch=verified task=%08x callback_slot=%08x callback=bf30053d readonly=1\n",task,task+0x50U);
    return 0;
}
void cleanup_module(void) {
    printk("<6>MF79U_CS_KPROBE unloaded readonly=1\n");
}
