/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03 CC task observer. Chain the original stub with all five arguments,
 * collect ONLY event id/phase/length, and restore the callback after a timeout.
 * Optional header mode reads AA45 metadata and TWO L3 header bytes only.
 * Ring mode adds only confirm/alert/release packets and read-only own sysfs.
 * No AT, no answer/dial, no CP instruction patches.
 * Keep the module pinned until reboot: the vendor dispatcher has no RCU/lifetime
 * contract, so a CPU may have already loaded our callback when we restore it.
 */
typedef unsigned int u32;
typedef unsigned char u8;
typedef void (*cc_callback)(u32,u32,void *,u32,void *);
extern int printk(const char *,...);
extern char __this_module[];
extern int try_module_get(void *);
extern void module_put(void *);
extern void *kthread_create_on_node(int (*)(void *),void *,int,const char *,...);
extern int wake_up_process(void *);
extern int kthread_stop(void *);
extern int kthread_should_stop(void);
extern void msleep(unsigned int);
#ifndef CS_WATCH_SECONDS
#define CS_WATCH_SECONDS 600
#endif
#ifdef CS_WATCH_HEADERS
extern long probe_kernel_read(void *,const void *,unsigned long);
#ifdef CS_WATCH_RING
#include "cs-ring-state.h"
#ifdef CS_WATCH_CONNECT_PROBE
#define CS_STATUS_ANSWER_FORBIDDEN 0U
#endif
#include "cs-kernel-status.h"
#ifdef CS_WATCH_CONNECT_PROBE
#include "cs-connect-probe.h"
static struct cs_connect_probe connect_probe;
static volatile u32 diagnostic_cleared,diagnostic_answer_window=1;
#endif
extern void *__kmalloc_node(unsigned int,unsigned int,int);
extern void kfree(const void *);
#ifdef CS_WATCH_CONNECT_PROBE
#define CS_LOG "MF79U_CS_KCONNECT"
#else
#define CS_LOG "MF79U_CS_KRING"
#endif
static struct cs_ring_state ring_state;
static u32 asc_task;
static int transmit(const struct cs_ring_packet *packet) {
    if(packet->length!=2U && packet->length!=6U)return -71;
    int connect=0;
#ifdef CS_WATCH_CONNECT_PROBE
    connect=packet->bytes[1]==7U && packet->length==2U && connect_probe.attempted==1U;
#endif
    if(packet->bytes[0]!=0x83U || (!connect && packet->bytes[1]!=1U && packet->bytes[1]!=8U &&
       packet->bytes[1]!=0x2dU && packet->bytes[1]!=0x2aU))return -71;
    u32 *envelope=__kmalloc_node(12U,0xd0U,-1);
    u8 *wire=__kmalloc_node(packet->length,0xd0U,-1);
    if(!envelope || !wire){kfree(envelope);kfree(wire);return -12;}
    for(u32 i=0;i<packet->length;++i)wire[i]=packet->bytes[i];
    /* Exact NAS AAD4 layout: CS connection0, discriminator flag1, byte length,
     * owned wire pointer. Send from the real CC task to the verified ASC task.
     * OSS transfers the outer envelope on success. ASC owns the nested wire. */
    envelope[0]=0x100U;envelope[1]=packet->length;envelope[2]=(u32)wire;
    int result=((int (*)(u32,void *,u32,u32))0xbf438315U)(0xaad4U,envelope,12U,asc_task);
    if(result){kfree(wire);kfree(envelope);cs_status_errors++;}
    else cs_status_sent++;
    printk("<6>" CS_LOG " tx_type=%02x wire_length=%u queue_result=%d answer_forbidden=%u\n",packet->bytes[1],packet->length,result,connect?0U:1U);
    return result;
}
#else
#define CS_LOG "MF79U_CS_KHEADER"
#endif
#else
#define CS_LOG "MF79U_CS_KWATCH"
#endif
static volatile u32 *slot;
static volatile u32 events;
static cc_callback original;
static int match(const volatile u8 *a,const u8 *b,u32 n) {
    for(u32 i=0;i<n;++i)if(a[i]!=b[i])return 0;
    return 1;
}
static void observe(u32 phase,u32 id,void *payload,u32 length,void *work) {
    u32 count=__sync_add_and_fetch(&events,1);
#ifdef CS_WATCH_RING
    cs_status_events=count;
#endif
    if(count<=32U)printk("<6>" CS_LOG " event=%u phase=%u id=%04x length=%u\n",count,phase,id,length);
#ifdef CS_WATCH_HEADERS
    /* Logging is bounded; protocol handling must continue for subsequent calls
     * and registration events throughout the armed interval. */
    if(id==0xaa45U) {
        u32 address=(u32)payload,sdu_length=0,pointer=0;
        u8 header[2];
        /* This first pass admits only direct System RAM, excluding MMIO and
         * unknown vmalloc mappings. The original still owns/frees everything.
         * Recover +12 length/+16 pointer from exact B03 MM/SMS code. */
        if(length!=20U || address<0xc0000000U || address>0xc3bbffecU ||
           (address&3U) || probe_kernel_read(&sdu_length,(const void *)(address+12U),4) ||
           probe_kernel_read(&pointer,(const void *)(address+16U),4)) {
            printk("<6>" CS_LOG " header=%u rejected=envelope\n",count);
        } else if(sdu_length<2U || sdu_length>2048U || pointer<0xc0000000U ||
                  pointer>0xc3bbfffeU || probe_kernel_read(header,(const void *)pointer,2)) {
            printk("<6>" CS_LOG " header=%u rejected=sdu sdu_length=%u\n",count,sdu_length);
        } else {
            u32 pd=header[0]&15U,ti=(header[0]>>4)&7U;
            /* Extended transaction identifiers require a third byte. Reject
             * them here instead of confusing that byte with the message type. */
            if(pd!=3U || ti==7U)
                printk("<6>" CS_LOG " header=%u rejected=protocol pd=%u extended_ti=%u sdu_length=%u\n",count,pd,ti==7U,sdu_length);
            else {
                u32 type=header[1]>>2;
                printk("<6>" CS_LOG " header=%u pd=%u upper_nibble=%u message_type=%02x decoded_body_length=%u representation=b03_model\n",count,pd,header[0]>>4,type,sdu_length);
#ifdef CS_WATCH_RING
                u8 connection=255;
                if(!probe_kernel_read(&connection,payload,1) && connection==0U) {
                    struct cs_ring_packet packets[2];
                    int n=cs_ring_receive(&ring_state,header[0],type,packets);
                    int success=1;
                    for(int i=0;i<n;++i)if(transmit(&packets[i])) {
                        success=0;ring_state.state=CS_RING_IDLE;break;
                    }
#ifdef CS_WATCH_CONNECT_PROBE
                    struct cs_ring_packet connect;
                    if(cs_connect_probe_packet(&connect_probe,header[0],type,n==2 && success && diagnostic_answer_window,&connect))
                        transmit(&connect);
                    if(connect_probe.attempted && ring_state.state==CS_RING_IDLE &&
                       (type==0x2aU || type==0x2dU))diagnostic_cleared=1;
#else
                    (void)success;
#endif
                    cs_status_state=ring_state.state;
                } else printk("<6>" CS_LOG " header=%u rejected=connection\n",count);
#endif
            }
        }
    }
#endif
    original(phase,id,payload,length,work);
}
static int expiry(void *unused) {
    (void)unused;
    for(u32 i=0;i<CS_WATCH_SECONDS;++i) {
        if(kthread_should_stop())return 0;
        msleep(1000);
#ifdef CS_WATCH_CONNECT_PROBE
        /* Never start an answered call close to callback expiry. Once network
         * clearing is observed, release this diagnostic hook promptly. */
        if(i+60U>=CS_WATCH_SECONDS)diagnostic_answer_window=0;
        if(diagnostic_cleared)break;
#endif
    }
    if(kthread_should_stop())return 0;
    int restored=__sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
#ifdef CS_WATCH_RING
    u32 call_idle=cs_status_state==0U;
    cs_status_armed=0;cs_status_state=0;cs_status_remove();
#else
    u32 call_idle=1U;
#endif
    printk("<6>" CS_LOG " expired seconds=%u events=%u callback_restored=%u call_idle=%u pinned_until_reboot=1\n",CS_WATCH_SECONDS,events,restored,call_idle);
    return 0;
}
int init_module(void) {
    static const u8 signature[8]={0x01,0x4b,0x93,0xf8,0x5d,0x03,0x70,0x47};
    static const u8 stub[8]={0x38,0xb5,0x14,0x46,0xa1,0xf5,0x33,0x43};
    if(!match((const volatile u8 *)0xbf3e527cU,signature,8) ||
       !match((const volatile u8 *)0xbf30053cU,stub,8) ||
       *(const volatile u32 *)0xbf59e3c0U!=0xbf55a954U ||
       *(const volatile u32 *)0xbf59e3bcU!=39U)return -19;
    u32 list=*(const volatile u32 *)0xbf5bcd88U;
    if(list<0xc0000000U || list>0xc3bbff64U || (list&3U))return -71;
    u32 task=((const volatile u32 *)list)[9];
    static const u8 name[3]={'C','C',0};
    if(task<0xc0000000U || task>0xc3bbff44U || (task&3U) ||
       !match((const volatile u8 *)(task+0x10U),name,3) ||
       *(const volatile u32 *)(task+8U)!=1U)return -71;
    slot=(volatile u32 *)(task+0x50U);original=(cc_callback)*slot;
    if((u32)original!=0xbf30053dU)return -16;
#ifdef CS_WATCH_RING
    static const u8 send_code[8]={0x2d,0xe9,0xf3,0x41,0x80,0x46,0x0d,0x46};
    if(!match((const volatile u8 *)0xbf438314U,send_code,8) ||
       *(const volatile u8 *)0xbf59e7e1U!=1U ||
       *(const volatile u8 *)0xbf59e8e3U!=1U ||
       *(const volatile u32 *)0xbf55e8bcU!=task)return -19;
    asc_task=((const volatile u32 *)list)[38];
    static const u8 asc_name[4]={'A','S','C',0};
    if(asc_task<0xc0000000U || asc_task>0xc3bbff44U || (asc_task&3U) ||
       !match((const volatile u8 *)(asc_task+16U),asc_name,4) ||
       *(const volatile u32 *)0xbf55f0e4U!=asc_task ||
       *(const volatile u32 *)(asc_task+8U)!=1U ||
       *(const volatile u32 *)(asc_task+0x50U)!=0xbf47be95U ||
       *(const volatile u8 *)(asc_task+0x9aU)!=2U)return -71;
#endif
#ifdef CS_WATCH_RING
    int status_result=cs_status_create();if(status_result)return status_result;
#endif
    void *worker=kthread_create_on_node(expiry,(void *)0,-1,"mf79u_cs_expire");
    if((u32)worker>=0xfffff001U || !worker)goto no_worker;
    if(!try_module_get(__this_module)) {kthread_stop(worker);goto no_reference;}
    if(!__sync_bool_compare_and_swap(slot,(u32)original,(u32)observe)) {
        kthread_stop(worker);module_put(__this_module);goto no_reference;
    }
#ifdef CS_WATCH_RING
    cs_status_armed=1;
#endif
    printk("<6>" CS_LOG " armed seconds=%u callback_slot=%08x original=%08x observer=%08x header_mode=%u no_dial=1 answer_forbidden=%u pinned_until_reboot=1\n",CS_WATCH_SECONDS,(u32)slot,(u32)original,(u32)observe,
#ifdef CS_WATCH_HEADERS
           1U
#else
           0U
#endif
           ,
#ifdef CS_WATCH_CONNECT_PROBE
           0U
#else
           1U
#endif
    );
#ifdef CS_WATCH_CONNECT_PROBE
    printk("<4>" CS_LOG " diagnostic_connect_budget=1 ordinary_voice_backend=0 answer_requires_explicit_authorization=1\n");
#endif
    wake_up_process(worker);return 0;
no_worker:
#ifdef CS_WATCH_RING
    cs_status_remove();
#endif
    return -12;
no_reference:
#ifdef CS_WATCH_RING
    cs_status_remove();
#endif
    return -16;
}
void cleanup_module(void) { /* A successful observer is deliberately pinned. */ }
