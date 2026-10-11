/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03, separately selected one-answer incoming DSP tone hypothesis.
 * All signaling runs in the real CC task. Keep the callback until real MM
 * clearing; pin the module because OSS provides no callback lifetime barrier.
 * No outgoing SETUP, identities, production SIP media or CP instruction patch.
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
/* Checked B03 hidden-result-pointer ABI, not a scalar u64 return. */
union cs_ktime { signed long long tv64; };
extern union cs_ktime ktime_get(void);
static inline unsigned long long cs_monotonic_ns(void) {return (unsigned long long)ktime_get().tv64;}
#ifndef CS_WATCH_SECONDS
#define CS_WATCH_SECONDS 240
#endif
#define CS_STATUS_ANSWER_FORBIDDEN 0U
#define CS_STATUS_REPORT_INACTIVE_STATE 1
#include "cs-kernel-status.h"
#include "cs-mt-state.h"
#define LOG "MF79U_CS_KCONNECT"
#define CS_AUDIO_LOG LOG
#define COMMAND_ID 0xffd1U
#define COMMAND_MAGIC 0x43534d54U
struct command {u32 magic,action;};
static callback original;
static volatile u32 *slot;
static struct cs_mt_state call;
static u32 cc_task,asc_task,umm_task;
static volatile u32 cleared,mm_release_sent,answer_window=1;
static int ram(u32 a,u32 n) {return n && a>=0xc0000000U && a<=0xc3bc0000U-n;}
static int match(u32 a,const u8 *wanted,u32 n) {
    u8 actual[8];if(n>8 || probe_kernel_read(actual,(const void *)a,n))return 0;
    for(u32 i=0;i<n;i++)if(actual[i]!=wanted[i])return 0;
    return 1;
}
#ifdef CS_I2S_PCM_TEST
#include "cs-i2s-pcm-candidate.h"
#else
#include "cs-dsp-tone-candidate.h"
#endif
static void publish(u32 previous) {
    if(previous!=call.stage) {
        printk("<6>" LOG " mt_state=%u previous=%u answer_budget=%u\n",call.stage,previous,call.budget);
    }
    cs_status_state=call.stage;
}
static int mm_release(void) {
    if(mm_release_sent)return 0;
    if(((u32 (*)(void))0xbf437bc1U)()!=cc_task)return -71;
    u8 *body=__kmalloc_node(4U,0xd0U,-1);
    if(!body)return -12;
    for(u32 i=0;i<4U;i++)body[i]=0;
    body[0]=3;body[2]=1; /* Exact CC CS normal clearing, BF356C9C. */
    int result=((int (*)(u32,void *,u32,u32))0xbf438315U)(0xaa3eU,body,4U,umm_task);
    if(result){kfree(body);cs_status_errors++;}else mm_release_sent=1;
    printk("<6>" LOG " mm_request=aa3e bytes=4 sim=0 queue_result=%d route=oss_umm\n",result);
    return result;
}
static int mm_cc_released(void) {
    u32 context=0;u8 protocol=3,reference=255;
    if(!mm_release_sent || probe_kernel_read(&context,(const void *)0xbf600bacU,4) ||
       !cs_audio_ram(context,0x68U) ||
       probe_kernel_read(&protocol,(const void *)(context+0x15U),1) ||
       probe_kernel_read(&reference,(const void *)(context+0x65U),1))return 0;
    if(protocol==3U || reference)return 0;
    printk("<6>" LOG " mm_cc_service_released=1 references=0 active_protocol=%u\n",protocol);
    return 1;
}
static int transmit(const struct cs_mt_packet *p) {
    u32 type=p->bytes[1];
    if(p->bytes[0]!=0x83U || (p->length!=2U && p->length!=5U && p->length!=6U) ||
       (type!=1U && type!=8U && type!=7U && type!=0x25U && type!=0x2dU && type!=0x2aU) ||
       (type==7U && (!call.budget || call.stage!=CS_MT_ANSWER_PENDING)))return -71;
    u32 *envelope=__kmalloc_node(12U,0xd0U,-1);
    u8 *wire=__kmalloc_node(p->length,0xd0U,-1);
    if(!envelope || !wire){kfree(envelope);kfree(wire);cs_status_errors++;return -12;}
    for(u32 i=0;i<p->length;i++)wire[i]=p->bytes[i];
    envelope[0]=0x100U;envelope[1]=p->length;envelope[2]=(u32)wire;
    int result=((int (*)(u32,void *,u32,u32))0xbf438315U)(0xaad4U,envelope,12U,asc_task);
    if(result){kfree(wire);kfree(envelope);cs_status_errors++;}else cs_status_sent++;
    printk("<6>" LOG " tx_type=%02x wire_length=%u queue_result=%d\n",type,p->length,result);
    return result;
}
static int enqueue(u32 action) {
    struct command *c=__kmalloc_node(sizeof(*c),0xd0U,-1);
    if(!c)return -12;
    c->magic=COMMAND_MAGIC;c->action=action;
    int result=((int (*)(u32,void *,u32,u32))0xbf438315U)(COMMAND_ID,c,sizeof(*c),cc_task);
    if(result)kfree(c);
    return result;
}
static int control(void *object,struct cs_kobj_attribute *attr,const char *buffer,u32 length) {
    (void)object;(void)attr;
    if(length!=5U || buffer[0]!='s' || buffer[1]!='t' || buffer[2]!='o' || buffer[3]!='p' || buffer[4]!='\n')return -22;
    answer_window=0;
    int result=enqueue(1);return result?result:(int)length;
}
static struct cs_kobj_attribute control_attribute={{"control",0200,0},(void *)0,(void *)control};
static void observe(u32 phase,u32 id,void *payload,u32 length,void *work) {
    u32 previous=call.stage;cs_status_events++;
    if(cs_status_events<=128U)printk("<6>" LOG " event=%u phase=%u id=%04x length=%u\n",cs_status_events,phase,id,length);
    if(phase==1U && id==COMMAND_ID && length==sizeof(struct command) && ram((u32)payload,length)) {
        struct command *c=payload;
        if(c->magic==COMMAND_MAGIC) {
            if(c->action==1U) {
                struct cs_mt_packet p;
                if(cs_mt_hangup(&call,&p)) {
                    if(transmit(&p)){call.stage=CS_MT_MM_CLEARING;mm_release();}
                } else if(call.stage==CS_MT_RELEASING || call.stage==CS_MT_DISCONNECTING || call.stage==CS_MT_MM_CLEARING) {
                    call.stage=CS_MT_MM_CLEARING;mm_release();
                } else if(!call.stage)cleared=1;
            }
            if(c->action==2U && call.stage==CS_MT_MM_CLEARING && mm_cc_released()) {call.stage=0;cleared=1;}
        }
    } else if(phase==1U && id==0xaa3fU && length==4U && ram((u32)payload,4U) && call.stage) {
        u8 connection=255;unsigned short reason=0xffff;
        if(!probe_kernel_read(&connection,payload,1) && !(connection&1U)) {
            probe_kernel_read(&reason,(const u8 *)payload+2,2);
            printk("<6>" LOG " mm_release_indication=1 mm_release_reason=%u\n",reason);
            call.stage=0;cleared=1;
        }
    } else if(phase==1U && id==0xaa45U && length==20U && ram((u32)payload,20U)) {
        u32 size=0,pointer=0;u8 connection=255,header[2];
        if(!probe_kernel_read(&connection,payload,1) && !connection &&
           !probe_kernel_read(&size,(const u8 *)payload+12U,4) &&
           !probe_kernel_read(&pointer,(const u8 *)payload+16U,4) && size>=2U && size<=2048U &&
           ram(pointer,size) && !probe_kernel_read(header,(const void *)pointer,2) && header[0]==3U) {
            u32 type=header[1]>>2;
            printk("<6>" LOG " message_type=%02x decoded_body_length=%u representation=b03_model\n",type,size);
            struct cs_mt_packet p[3];int n=cs_mt_receive(&call,header[0],type,answer_window,p);
            for(int i=0;i<n;i++)if(transmit(&p[i])){call.stage=CS_MT_MM_CLEARING;break;}
            if(call.stage==CS_MT_MM_CLEARING)mm_release();
        }
    }
    publish(previous);original(phase,id,payload,length,work);
}
static int expiry(void *unused) {
    (void)unused;u32 stop_sent_for=0xffffffffU;
    unsigned long long started=cs_monotonic_ns(),next=started+1000000000ULL;
    u32 warned=0,observed_state=0,elapsed_seconds=0;
    unsigned long long state_since=started;
    for(;;) {
        if(kthread_should_stop())return 0;
#ifdef CS_I2S_PCM_TEST
        usleep_range(1000,1500);
#else
        msleep(10);
#endif
        unsigned long long now=cs_monotonic_ns();u32 state=cs_status_state;
        if(state!=observed_state){observed_state=state;state_since=now;}
        cs_audio_step(state==CS_MT_CONNECTED,now);
        if(now+60000000000ULL>=started+(unsigned long long)CS_WATCH_SECONDS*1000000000ULL)answer_window=0;
        if(cleared)break;
        if(now<next)continue;
        next=now+1000000000ULL;elapsed_seconds++;
        if(state==CS_MT_MM_CLEARING)enqueue(2);
        u32 seconds=state==CS_MT_CONNECTED?10U:(state==CS_MT_ANSWER_PENDING?25U:5U);
        if(state && now-state_since>=(unsigned long long)seconds*1000000000ULL && stop_sent_for!=state) {
            int result=enqueue(1);
            printk("<6>" LOG " timeout_stage=%u stop_queue_result=%d\n",state,result);
            if(!result)stop_sent_for=state;
        }
        if(now>=started+(unsigned long long)CS_WATCH_SECONDS*1000000000ULL) {
            answer_window=0;
            if(!state)break;
            if(!warned){warned=1;printk("<4>" LOG " clearing_unconfirmed=1 callback_retained=1\n");}
        }
    }
    cs_audio_restore();cs_status_armed=0;
    int restored=__sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
    sysfs_remove_file(cs_status_object,&control_attribute.attr);cs_status_remove();
    printk("<6>" LOG " expired seconds=%u callback_restored=%u call_idle=%u pinned_until_reboot=1\n",
        elapsed_seconds,restored,call.stage==0);
    return 0;
}
int init_module(void) {
    static const u8 stub[8]={0x38,0xb5,0x14,0x46,0xa1,0xf5,0x33,0x43};
    static const u8 send[8]={0x2d,0xe9,0xf3,0x41,0x80,0x46,0x0d,0x46};
    if(!match(0xbf30053cU,stub,8) || !match(0xbf438314U,send,8) || !cs_audio_layout() ||
       *(const volatile u32 *)0xbf59e3c0U!=0xbf55a954U || *(const volatile u32 *)0xbf59e3bcU!=39U ||
       *(const volatile u8 *)0xbf59e7e1U!=1U || *(const volatile u8 *)0xbf59e8e3U!=1U)return -19;
    u32 list=*(const volatile u32 *)0xbf5bcd88U;
    if(!ram(list,39U*4U) || (list&3U))return -71;
    cc_task=((const volatile u32 *)list)[9];asc_task=((const volatile u32 *)list)[38];umm_task=((const volatile u32 *)list)[5];
    static const u8 cc_name[3]={'C','C',0},asc_name[4]={'A','S','C',0},umm_name[4]={'U','M','M',0};
    if(!ram(cc_task,0xbcU) || !ram(asc_task,0xbcU) || !ram(umm_task,0xbcU) ||
       !match(cc_task+16U,cc_name,3) || !match(asc_task+16U,asc_name,4) || !match(umm_task+16U,umm_name,4) ||
       *(const volatile u32 *)0xbf55e8bcU!=cc_task || *(const volatile u32 *)0xbf55f0e4U!=asc_task ||
       *(const volatile u32 *)0xbf55e874U!=umm_task || *(const volatile u32 *)0xbf55e88cU!=umm_task ||
       *(const volatile u32 *)(cc_task+8U)!=1U || *(const volatile u32 *)(asc_task+8U)!=1U ||
       *(const volatile u32 *)(umm_task+8U)!=1U || *(const volatile u8 *)(cc_task+0x9aU)!=1U ||
       *(const volatile u8 *)(asc_task+0x9aU)!=2U || *(const volatile u8 *)(umm_task+0x9aU)!=2U ||
       *(const volatile u32 *)(asc_task+0x50U)!=0xbf47be95U ||
       *(const volatile u32 *)(umm_task+0x50U)!=0xbf4c8811U)return -71;
    slot=(volatile u32 *)(cc_task+0x50U);original=(callback)*slot;
    if((u32)original!=0xbf30053dU)return -16;
    int result=cs_status_create();if(result)return result;
    result=sysfs_create_file(cs_status_object,&control_attribute.attr);
    if(result){cs_status_remove();return result;}
    void *worker=kthread_create_on_node(expiry,(void *)0,-1,"mf79u_mt_expire");
    if(!worker || (u32)worker>=0xfffff001U)goto failed;
    if(!try_module_get(__this_module)){kthread_stop(worker);goto failed;}
    if(!__sync_bool_compare_and_swap(slot,(u32)original,(u32)observe)) {
        kthread_stop(worker);module_put(__this_module);goto failed;
    }
    cs_status_armed=1;
    printk("<6>" LOG " armed seconds=%u connect_budget=1 no_dial=1 answer_forbidden=0 pinned_until_reboot=1\n",CS_WATCH_SECONDS);
#ifdef CS_I2S_PCM_TEST
    printk("<6>" LOG " i2s_pcm_candidate=1 test_seconds=6 audio_compatibility_verified=0 monotonic_deadlines=1\n");
#else
    printk("<6>" LOG " dsp_audio_candidate=1 tone_seconds=6 audio_compatibility_verified=0 monotonic_deadlines=1\n");
#endif
    wake_up_process(worker);return 0;
failed:
    sysfs_remove_file(cs_status_object,&control_attribute.attr);cs_status_remove();return -16;
}
void cleanup_module(void) {}
