/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03 bounded outgoing CS signaling diagnostic, one call per load.
 * CC callback ownership is preserved. The normal-voice admission stub's data
 * literal is redirected temporarily, only for our MM-pending service type1.
 * Default: no DSP access. Optional AMR candidate writes only the checked
 * original UL copier, during its own connected call. No incoming answers,
 * phone-number logging, or persistent writes.
 */
typedef unsigned int u32;
typedef unsigned char u8;
typedef void (*callback)(u32,u32,void *,u32,void *);
extern int printk(const char *,...);
extern long probe_kernel_read(void *,const void *,unsigned long);
extern void *__kmalloc_node(unsigned int,unsigned int,int);
extern void kfree(const void *);
extern char __this_module[];
extern int try_module_get(void *);
extern void module_put(void *);
extern void *kthread_create_on_node(int (*)(void *),void *,int,const char *,...);
extern int wake_up_process(void *);
extern int kthread_stop(void *);
extern int kthread_should_stop(void);
extern void msleep(unsigned int);
/* Exact B03 ktime_get returns an 8-byte union through the ARM EABI hidden
 * result pointer (C006BCE2 stores through it); a scalar declaration is unsafe. */
union cs_ktime { signed long long tv64; };
extern union cs_ktime ktime_get(void);
static inline unsigned long long cs_monotonic_ns(void) {
    return (unsigned long long)ktime_get().tv64;
}
#ifndef CS_WATCH_SECONDS
#define CS_WATCH_SECONDS 180
#endif
#ifndef CS_MO_CONNECTED_SECONDS
#ifdef CS_I2S_USERSPACE_PCM
#define CS_MO_CONNECTED_SECONDS 28U
#else
#define CS_MO_CONNECTED_SECONDS 10U
#endif
#endif
#ifndef CS_MO_MM_RELEASE_DELAY_SECONDS
#define CS_MO_MM_RELEASE_DELAY_SECONDS 0U
#endif
#define CS_STATUS_OBJECT_NAME "mf79u_cs_mo"
#define CS_STATUS_REPORT_INACTIVE_STATE 1
#include "cs-kernel-status.h"
#include "cs-mo-state.h"
#ifdef CS_MO_DTMF_TONE
#include "cs-dtmf-tone.h"
static struct cs_dtmf_tone tone;
static u32 tone_reported;
static void tone_update(void) {
    if(tone.stage!=tone_reported) {
        printk("<6>MF79U_CS_MO dtmf_state=%u previous=%u network_tone=1 pcm_audio=0\n",tone.stage,tone_reported);
        tone_reported=tone.stage;
    }
}
#endif
#define LOG "MF79U_CS_MO"
#define COMMAND_ID 0xffd0U
#define COMMAND_MAGIC 0x43534d4fU
struct command { u32 magic,action,length;u8 number[32]; };
static callback original;
static volatile u32 *slot,*admission;
static struct cs_mo_state call;
static u32 cc_task,asc_task,umm_task;
static volatile u32 command_budget,tick,stage_tick,cleared;
static volatile u32 mm_release_sent;
static u32 mm_release_deferred;
static unsigned long long mm_release_deadline_ns;
static int ram(u32 a,u32 n) {return n && a>=0xc0000000U && a<=0xc3bc0000U-n;}
static int match(u32 a,const u8 *wanted,u32 n) {
    u8 actual[8];if(n>8 || probe_kernel_read(actual,(const void *)a,n))return 0;
    for(u32 i=0;i<n;i++)if(actual[i]!=wanted[i])return 0;
    return 1;
}
#ifdef CS_MO_AMR_TONE_CANDIDATE
#include "cs-amr-tone-candidate.h"
#endif
#ifdef CS_I2S_PCM_TEST
#ifdef CS_I2S_USERSPACE_PCM
/* The PCM test deadline must not close the DSP/clock path while GSM still
 * owns its traffic channel, including DISCONNECT/RELEASE/MM clearing. */
#define CS_I2S_CALL_ACTIVE() (cs_status_state != CS_MO_IDLE)
#endif
#define CS_AUDIO_LOG LOG
#include "cs-i2s-pcm-candidate.h"
#elif defined(CS_MO_DSP_TONE_CANDIDATE)
#include "cs-dsp-tone-candidate.h"
#endif
static int writable_literal(u32 address) {
    /* Same exact B03 short-descriptor PGD/RAM mapping as cp-memory-probe.
     * Admit a privileged-writable small page only. No mprotect/MMIO writes. */
    u32 coarse=0,pte=0;
    /* RAM begins at20440000, but the kernel's linear physical offset is
     *20400000: text20448000 maps toC0048000 (verified kernel image anchors).
     * Thus the physical PGD20444000 is virtualC0044000. */
    int read=probe_kernel_read(&coarse,(const void *)(0xc0044000U+4U*(address>>20)),4);
    if(read || (coarse&3U)!=1U) {
        printk("<6>" LOG " literal_pgd_read=%d descriptor=%08x\n",read,coarse);return 0;
    }
    u32 physical=(coarse&0xfffffc00U)+4U*((address>>12)&255U);
    if(physical<0x20440000U || physical>0x23fffffcU) {
        printk("<6>" LOG " literal_pte_rejected=physical_range\n");return 0;
    }
    read=probe_kernel_read(&pte,(const void *)(0xc0000000U+physical-0x20400000U),4);
    if(read){printk("<6>" LOG " literal_pte_read=%d\n",read);return 0;}
    printk("<6>" LOG " literal_page_type=%u privileged_ap=%u apx=%u\n",pte&3U,(pte>>4)&3U,(pte>>9)&1U);
    return (pte&2U) && (pte&48U) && !(pte&512U);
}
static void publish(u32 previous) {
    cs_status_state=call.stage;
    if(previous!=call.stage) {
        stage_tick=tick;
        printk("<6>" LOG " state=%u previous=%u number_retained=%u\n",call.stage,previous,call.number_length!=0);
    }
}
static u32 ordinary_admission(const u8 *service) {
    u8 value=0;
    /* All non-diagnostic paths retain B03's original return1/reject behavior. */
    if(call.stage==CS_MO_MM_PENDING && !probe_kernel_read(&value,service,1) && value==1U) {
        printk("<6>" LOG " ordinary_service_admitted=1\n");return 0;
    }
    return 1;
}
static int mm(u32 id) {
    if(((u32 (*)(void))0xbf437bc1U)()!=cc_task) {
        cs_status_errors++;printk("<6>" LOG " mm_request=%04x rejected=task_sim_context\n",id);return -71;
    }
    u8 *body=__kmalloc_node(id==0xaa3cU?8U:4U,0xd0U,-1);
    if(!body){cs_status_errors++;return -12;}
    for(u32 i=0;i<(id==0xaa3cU?8U:4U);i++)body[i]=0;
    body[0]=3U; /* CC protocol, CS domain. */
    if(id==0xaa3cU)body[1]=1U; /* Normal voice CM service, never emergency. */
    else body[2]=1U; /* BF356C9C reason1 also clears active protocol/service. */
    /* The normal PS send route BF4AFEBC ends in zOssMsgSend(id, body, len,
     * physical destination). MM logical81 aliases UMM primary task. Using
     * BF4C5C00 here only appends to a local UMM mailbox, with no wakeup.
     * Let OSS preserve source CC/task ownership and dispatch UMM phase2. */
    int result=((int (*)(u32,void *,u32,u32))0xbf438315U)(id,body,id==0xaa3cU?8U:4U,umm_task);
    if(result){kfree(body);cs_status_errors++;}
    else if(id==0xaa3eU)mm_release_sent=1;
    printk("<6>" LOG " mm_request=%04x bytes=%u sim=0 queue_result=%d ownership_transferred=%u route=oss_umm\n",id,id==0xaa3cU?8U:4U,result,result==0);
    return result;
}
static int mm_cc_released(void) {
    u32 context=0;u8 protocol=3,reference=255;
    /* Exact B03 MM context table and mm_cmproc fields. This is a read-only
     * acknowledgement of real MM processing, not a fabricated AA3F. MM's
     * own release request normally clears references without an indication.
     * Ignore SMS/SS references: they may legitimately share the RR channel. */
    if(!mm_release_sent || probe_kernel_read(&context,(const void *)0xbf600bacU,4) ||
       (!ram(context,0x68U) && !(context>=0xbf59e000U && context<=0xbf61af98U)) ||
       probe_kernel_read(&protocol,(const void *)(context+0x15U),1) ||
       probe_kernel_read(&reference,(const void *)(context+0x65U),1))return 0;
    if(protocol==3U || reference)return 0;
    printk("<6>" LOG " mm_cc_service_released=1 references=0 active_protocol=%u\n",protocol);
    return 1;
}
static int transmit(const struct cs_mo_packet *p) {
    if(p->length<2 || p->length>sizeof(p->bytes) || p->bytes[0]!=3U || (p->bytes[1]&0xc0U))return -71;
    /* The raw AAD4 route bypasses B03's encoder at BF29BEA8, including its
     * shared MM/CC/SS send sequence. Reuse the original allocator in the
     * real CC/SIM0 context; never keep a second counter or reset its state. */
    u32 sequence_context=0;u8 sequence=255;
    if(((u32 (*)(void))0xbf437bc1U)()!=cc_task ||
       ((u32 (*)(void))0xbf4c1801U)()!=0U ||
       probe_kernel_read(&sequence_context,(const void *)0xbf5ffda4U,4) ||
       !ram(sequence_context,8U) ||
       probe_kernel_read(&sequence,(const void *)sequence_context,1) || sequence>3U) {
        cs_status_errors++;printk("<6>" LOG " tx_rejected=sequence_context\n");return -71;
    }
    if(p->bytes[1]==0x25U || p->bytes[1]==0x2dU || p->bytes[1]==0x2aU)
        printk("<6>" LOG " clearing_tx_begin=%02x bytes=%u\n",p->bytes[1],p->length);
    u32 *envelope=__kmalloc_node(12,0xd0U,-1);
    u8 *wire=__kmalloc_node(p->length,0xd0U,-1);
    if(!envelope || !wire){kfree(envelope);kfree(wire);cs_status_errors++;return -12;}
    for(u32 i=0;i<p->length;i++)wire[i]=p->bytes[i];
    u32 nsd=((u32 (*)(void))0xbf29be71U)();
    if(nsd>3U){kfree(wire);kfree(envelope);cs_status_errors++;return -71;}
    wire[1]|=(u8)(nsd<<6);
    envelope[0]=0x100U;envelope[1]=p->length;envelope[2]=(u32)wire;
    int result=((int (*)(u32,void *,u32,u32))0xbf438315U)(0xaad4U,envelope,12U,asc_task);
    if(result){kfree(wire);kfree(envelope);cs_status_errors++;}else cs_status_sent++;
    printk("<6>" LOG " tx_type=%02x bytes=%u queue_result=%d nsd=%u sequence_owner=vendor\n",p->bytes[1],p->length,result,nsd);
    return result;
}
static int enqueue(u32 action,const u8 *number,u32 length) {
    if(action==2U)printk("<6>" LOG " stop_enqueue_begin=1 stage=%u\n",cs_status_state);
    struct command *c=__kmalloc_node(sizeof(*c),0xd0U,-1);
    if(!c)return -12;
    c->magic=COMMAND_MAGIC;c->action=action;c->length=length;
    for(u32 i=0;i<32;i++)c->number[i]=i<length?number[i]:0;
    int result=((int (*)(u32,void *,u32,u32))0xbf438315U)(COMMAND_ID,c,sizeof(*c),cc_task);
    if(result) {for(u32 i=0;i<32;i++)c->number[i]=0;kfree(c);}
    if(action==2U)printk("<6>" LOG " stop_enqueue_end=1 result=%d\n",result);
    return result;
}
static int control(void *object,struct cs_kobj_attribute *attr,const char *buffer,u32 length) {
    (void)object;(void)attr;
    if(!cs_status_armed)return -19;
    if(length==5U && buffer[0]=='s' && buffer[1]=='t' && buffer[2]=='o' && buffer[3]=='p' && buffer[4]=='\n') {
        int result=enqueue(2,(const u8 *)0,0);return result?result:(int)length;
    }
    u32 n=length;if(n && buffer[n-1]=='\n')n--;
    if(n<5 || n>32)return -22;
    for(u32 i=0;i<n;i++)if(buffer[i]<'0' || buffer[i]>'9')return -22;
    if(tick+60U>=CS_WATCH_SECONDS || !__sync_bool_compare_and_swap(&command_budget,0,1))return -16;
    int result=enqueue(1,(const u8 *)buffer,n);
    if(result)command_budget=0;
    return result?result:(int)length;
}
static struct cs_kobj_attribute control_attribute={{"control",0200,0},(void *)0,(void *)control};
static void observe(u32 phase,u32 id,void *payload,u32 length,void *work) {
    u32 previous=call.stage;cs_status_events++;
    if(cs_status_events<=128)printk("<6>" LOG " event=%u phase=%u id=%04x length=%u\n",cs_status_events,phase,id,length);
    struct cs_mo_packet p;
    /* CC is B03 OSS phase1; ASC is phase2. Do not conflate the two ABIs. */
    if(phase==1U && id==COMMAND_ID && length==sizeof(struct command) && ram((u32)payload,length)) {
        struct command *c=payload;
        if(c->magic==COMMAND_MAGIC && c->length<=32U) {
            if(c->action==1U && cs_status_armed && !cs_mo_begin(&call,c->number,c->length) && mm(0xaa3cU)) {
                cs_mo_forget(&call);call.stage=0;cleared=1;
            }
            if(c->action==2U) {
                printk("<6>" LOG " stop_dispatch_begin=1 stage=%u\n",call.stage);
                if(cs_mo_hangup(&call,&p))transmit(&p);
                else if(call.stage==CS_MO_MM_PENDING || call.stage==CS_MO_RELEASING ||
                        call.stage==CS_MO_DISCONNECTING) {
                    call.stage=CS_MO_MM_CLEARING;cs_mo_forget(&call);mm(0xaa3eU);
                }
                printk("<6>" LOG " stop_dispatch_end=1 stage=%u\n",call.stage);
            }
            if(c->action==3U && call.stage==CS_MO_MM_CLEARING) {
                /* Diagnostic only: let the original lower layers deliver
                 * RELEASE COMPLETE before requesting MM release. No sleep in
                 * CC/ASC and no fabricated acknowledgement of delivery. */
                if(mm_release_deferred && cs_monotonic_ns()>=mm_release_deadline_ns) {
                    printk("<6>" LOG " mm_release_defer_elapsed=%u request_pending=1\n",tick-stage_tick);
                    if(!mm(0xaa3eU))mm_release_deferred=0;
                }
                if(mm_cc_released()) {cs_mo_forget(&call);call.stage=0;cleared=1;}
            }
#ifdef CS_MO_DTMF_TONE
            if(c->action==4U) {
                if(cs_dtmf_tick(&tone,call.stage==CS_MO_CONNECTED,tick-stage_tick,tick,&p) && transmit(&p))
                    tone.stage=CS_DTMF_FAILED;
                tone_update();
            }
#endif
            for(u32 i=0;i<32;i++)c->number[i]=0;
        }
    } else if(phase==1U && id==0xaa3dU && length==4U && ram((u32)payload,4U)) {
        u8 connection=255;
        if(!probe_kernel_read(&connection,payload,1) && !(connection&1U) && cs_mo_established(&call,&p)) {
            printk("<6>" LOG " mm_established=1\n");
            if(transmit(&p)) {call.stage=CS_MO_MM_CLEARING;mm(0xaa3eU);}
        }
    } else if(phase==1U && id==0xaa3fU && length==4U && ram((u32)payload,4U)) {
        u8 connection=255;
        if(!probe_kernel_read(&connection,payload,1) && !(connection&1U) && call.stage) {
            /* B03 MM release sender BF3A8458 stores the u16 reason at+2;
             * no raw payload, identity or uninitialized padding is logged. */
            unsigned short reason=0xffffU;
            if(!probe_kernel_read(&reason,(const u8 *)payload+2U,2U))
                printk("<6>" LOG " mm_release_reason=%u previous_state=%u\n",reason,call.stage);
            cs_mo_forget(&call);call.stage=0;cleared=1;
            printk("<6>" LOG " mm_release_indication=1\n");
        }
    } else if(phase==1U && id==0xaa45U && length==20U && ram((u32)payload,20U)) {
        u32 size=0,pointer=0;u8 connection=255,header[2];
        if(!probe_kernel_read(&connection,payload,1) && !connection &&
           !probe_kernel_read(&size,(const u8 *)payload+12,4) &&
           !probe_kernel_read(&pointer,(const u8 *)payload+16,4) && size>=2U && size<=2048U &&
           ram(pointer,size) && !probe_kernel_read(header,(const void *)pointer,2)) {
            if((header[0]&15U)==3U && (header[0]&0x70U)!=0x70U) {
                u32 type=header[1]>>2;
                printk("<6>" LOG " cc_type=%02x ti=%u representation=b03_model\n",type,header[0]>>4);
                int replied=cs_mo_receive(&call,header[0],type,&p),sent=0;
                if(replied)sent=transmit(&p)==0;
#ifdef CS_MO_DTMF_TONE
                cs_dtmf_receive(&tone,call.stage==CS_MO_CONNECTED,header[0],type,tick);
                tone_update();
#endif
                if(call.stage==CS_MO_MM_CLEARING && previous!=CS_MO_MM_CLEARING) {
                    if(CS_MO_MM_RELEASE_DELAY_SECONDS && type==0x2dU && sent) {
                        mm_release_deferred=1;
                        mm_release_deadline_ns=cs_monotonic_ns()+1000000000ULL*CS_MO_MM_RELEASE_DELAY_SECONDS;
                        printk("<6>" LOG " mm_release_deferred_seconds=%u release_complete_queued=1\n",CS_MO_MM_RELEASE_DELAY_SECONDS);
                    } else mm(0xaa3eU);
                }
            }
        }
    }
    publish(previous);original(phase,id,payload,length,work);
}
static int expiry(void *unused) {
    (void)unused;u32 stop_sent_for=0xffffffffU;
#if defined(CS_MO_DSP_TONE_CANDIDATE) || defined(CS_I2S_PCM_TEST)
    unsigned long long next_second=cs_monotonic_ns()+1000000000ULL;
#endif
    for(tick=0;tick<CS_WATCH_SECONDS || call.stage;tick++) {
        if(kthread_should_stop())return 0;
#if defined(CS_MO_DSP_TONE_CANDIDATE) || defined(CS_I2S_PCM_TEST)
        unsigned long long now;
        do {
#ifdef CS_I2S_PCM_TEST
            usleep_range(1000,1500);
#else
            msleep(10);
#endif
            now=cs_monotonic_ns();
            cs_audio_step(cs_status_state==CS_MO_CONNECTED,now);
        }while(now<next_second && !cleared);
        next_second+=1000000000ULL;
#elif defined(CS_MO_AMR_TONE_CANDIDATE)
        for(u32 period=0;period<50U;period++) {
            msleep(20);cs_tone_step(cs_status_state==CS_MO_CONNECTED);
        }
#else
        msleep(1000);
#endif
        u32 stage=cs_status_state;
#ifdef CS_MO_DTMF_TONE
        if(stage==CS_MO_CONNECTED)enqueue(4,(const u8 *)0,0);
#endif
        if(stage==CS_MO_MM_CLEARING)enqueue(3,(const u8 *)0,0);
        u32 limit=stage==CS_MO_CONNECTED?CS_MO_CONNECTED_SECONDS:
            (stage==CS_MO_MM_PENDING?25U:35U);
        if(stage && tick-stage_tick>=limit && stop_sent_for!=stage) {
            printk("<6>" LOG " timeout_begin=1 stage=%u elapsed=%u limit=%u\n",stage,tick-stage_tick,limit);
            int result=enqueue(2,(const u8 *)0,0);
            if(!result)stop_sent_for=stage;
            printk("<6>" LOG " timeout_stage=%u stop_queued=%u result=%d\n",stage,result==0,result);
        }
        if(tick+60U>=CS_WATCH_SECONDS)cs_status_armed=0;
        if(cleared)break;
        /* If network clearing is unconfirmed, retain our callback and report
         * that state; restoring the free-only CC stub would strand a call. */
        if(tick==CS_WATCH_SECONDS+60U)printk("<4>" LOG " clearing_unconfirmed=1 callback_retained=1\n");
    }
#ifdef CS_MO_AMR_TONE_CANDIDATE
    cs_tone_restore();
#endif
#if defined(CS_MO_DSP_TONE_CANDIDATE) || defined(CS_I2S_PCM_TEST)
    cs_audio_restore();
#endif
    cs_status_armed=0;cs_mo_forget(&call);
    int restored=__sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
    int gate=__sync_bool_compare_and_swap(admission,(u32)ordinary_admission,0xbf300537U);
#ifdef CS_I2S_USERSPACE_PCM
    cs_pcm_remove();
#endif
    sysfs_remove_file(cs_status_object,&control_attribute.attr);cs_status_remove();
    printk("<6>" LOG " expired seconds=%u callback_restored=%u admission_restored=%u call_idle=%u pinned_until_reboot=1\n",
        tick,restored,gate,call.stage==0);
    return 0;
}
int init_module(void) {
#ifdef CS_MO_AMR_TONE_CANDIDATE
    if(!cs_tone_layout())return -19;
#endif
#if defined(CS_MO_DSP_TONE_CANDIDATE) || defined(CS_I2S_PCM_TEST)
    if(!cs_audio_layout())return -19;
#endif
    static const u8 stub[8]={0x38,0xb5,0x14,0x46,0xa1,0xf5,0x33,0x43};
    static const u8 gate[4]={0x01,0x20,0x70,0x47};
    static const u8 caller[8]={0x6f,0x4b,0x98,0x47,0x01,0x28,0x40,0xf0};
    static const u8 send[8]={0x2d,0xe9,0xf3,0x41,0x80,0x46,0x0d,0x46};
    static const u8 nsd[8]={0x10,0xb5,0x0b,0x4b,0x98,0x47,0x0b,0x4b};
    static const u8 sim[8]={0x08,0xb5,0xff,0xf7,0x95,0xff,0x01,0x38};
    u32 signatures=match(0xbf30053cU,stub,8)|(match(0xbf300536U,gate,4)<<1)|
       (match(0xbf35609aU,caller,8)<<2)|(match(0xbf438314U,send,8)<<3)|
       (match(0xbf29be70U,nsd,8)<<4)|(match(0xbf4c1800U,sim,8)<<5);
    if(signatures!=63U || *(const volatile u32 *)0xbf356258U!=0xbf300537U ||
       *(const volatile u32 *)0xbf29bea0U!=0xbf4c1801U ||
       *(const volatile u32 *)0xbf29bea4U!=0xbf5ffe9cU) {
        printk("<6>" LOG " rejected=signature bitmap=%u literal_original=%u\n",signatures,*(const volatile u32 *)0xbf356258U==0xbf300537U);return -19;
    }
    if(!writable_literal(0xbf356258U)) {
        printk("<6>" LOG " rejected=literal_page_permissions\n");return -19;
    }
    if(
       *(const volatile u32 *)0xbf59e3c0U!=0xbf55a954U ||
       *(const volatile u32 *)0xbf59e3bcU!=39U ||
       *(const volatile u8 *)0xbf59e7e1U!=1U || *(const volatile u8 *)0xbf59e8e3U!=1U) {
        printk("<6>" LOG " rejected=runtime_identity_or_voice_flags\n");return -19;
    }
    u32 list=*(const volatile u32 *)0xbf5bcd88U;
    if(!ram(list,39U*4U) || (list&3U))return -71;
    cc_task=((const volatile u32 *)list)[9];asc_task=((const volatile u32 *)list)[38];
    umm_task=((const volatile u32 *)list)[5];
    static const u8 cc_name[3]={'C','C',0},asc_name[4]={'A','S','C',0},umm_name[4]={'U','M','M',0};
    if(!ram(cc_task,0xbcU) || !ram(asc_task,0xbcU) || !ram(umm_task,0xbcU) ||
       !match(cc_task+16U,cc_name,3) || !match(asc_task+16U,asc_name,4) ||
       !match(umm_task+16U,umm_name,4) ||
       *(const volatile u32 *)0xbf55e8bcU!=cc_task ||
       *(const volatile u32 *)0xbf55f0e4U!=asc_task ||
       *(const volatile u32 *)0xbf55e874U!=umm_task ||
       *(const volatile u32 *)0xbf55e88cU!=umm_task ||
       *(const volatile u32 *)(cc_task+8U)!=1U || *(const volatile u32 *)(asc_task+8U)!=1U ||
       *(const volatile u32 *)(umm_task+8U)!=1U ||
       *(const volatile u32 *)(umm_task+0x50U)!=0xbf4c8811U ||
       *(const volatile u8 *)(umm_task+0x9aU)!=2U ||
       *(const volatile u8 *)(cc_task+0x9aU)!=1U ||
       *(const volatile u32 *)(asc_task+0x50U)!=0xbf47be95U ||
       *(const volatile u8 *)(asc_task+0x9aU)!=2U)return -71;
    slot=(volatile u32 *)(cc_task+0x50U);original=(callback)*slot;
    if((u32)original!=0xbf30053dU)return -16;
    admission=(volatile u32 *)0xbf356258U;
    int result=cs_status_create();if(result)return result;
    result=sysfs_create_file(cs_status_object,&control_attribute.attr);
    if(result){cs_status_remove();return result;}
#ifdef CS_I2S_USERSPACE_PCM
    result=cs_pcm_create();
    if(result){sysfs_remove_file(cs_status_object,&control_attribute.attr);cs_status_remove();return result;}
#endif
    void *worker=kthread_create_on_node(expiry,(void *)0,-1,"mf79u_mo_expire");
    if(!worker || (u32)worker>=0xfffff001U)goto failed;
    if(!try_module_get(__this_module)){kthread_stop(worker);goto failed;}
    if(!__sync_bool_compare_and_swap(slot,(u32)original,(u32)observe)) {
        kthread_stop(worker);module_put(__this_module);goto failed;
    }
    if(!__sync_bool_compare_and_swap(admission,0xbf300537U,(u32)ordinary_admission)) {
        __sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
        /* Callback may have been fetched: keep module pinned even on failure. */
        kthread_stop(worker);
    #ifdef CS_I2S_USERSPACE_PCM
    cs_pcm_remove();
#endif
    sysfs_remove_file(cs_status_object,&control_attribute.attr);cs_status_remove();
        printk("<4>" LOG " inactive=1 admission_changed=0 callback_restored=1 pinned_until_reboot=1\n");
        return 0;
    }
    cs_status_armed=1;
#ifdef CS_MO_DTMF_TONE
    printk("<6>" LOG " network_dtmf_tone=1 tone_seconds=2 pcm_audio=0 dsp_writes=0\n");
#endif
#ifdef CS_MO_AMR_TONE_CANDIDATE
    printk("<6>" LOG " amr_candidate=1 budget_frames=300 speech_backend_verified=0 control_writes=0\n");
#endif
#ifdef CS_MO_DSP_TONE_CANDIDATE
    printk("<6>" LOG " dsp_audio_candidate=1 tone_seconds=6 audio_compatibility_verified=0 monotonic_deadlines=1\n");
#endif
    printk("<6>" LOG " armed seconds=%u call_budget=1 incoming_answer=0 audio=0 admission_slot=%08x pinned_until_reboot=1\n",CS_WATCH_SECONDS,(u32)admission);
    wake_up_process(worker);return 0;
failed:
#ifdef CS_I2S_USERSPACE_PCM
    cs_pcm_remove();
#endif
    sysfs_remove_file(cs_status_object,&control_attribute.attr);cs_status_remove();return -16;
}
void cleanup_module(void) {}
