/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03, non-consuming RPMSG cursor sampler. No payloads, callbacks,
 * task hooks or writes. Optional TCH RAM metadata and checksum-bound DSP
 * control/status halfwords are separate from the default cursor sampler.
 * A sample is a lower bound
 * because the DSP can wrap multiple times between 20ms snapshots.
 */
typedef unsigned int u32;
typedef unsigned char u8;
typedef unsigned short u16;
#include "cs-channel-delta.h"
extern int printk(const char *,...);
extern void *kthread_create_on_node(int (*)(void *),void *,int,const char *,...);
extern int wake_up_process(void *);
extern int kthread_should_stop(void);
extern int kthread_stop(void *);
extern void msleep(unsigned int);
#ifndef CS_WATCH_SECONDS
#define CS_WATCH_SECONDS 600
#endif
#if defined(CS_WATCH_DSP_FRAME_METADATA) || defined(CS_WATCH_DSP_PCM_METADATA)
#define TCH_BUFFER_READ 1U
#else
#define TCH_BUFFER_READ 0U
#endif
static void *worker;
struct observation { struct cs_channel_snapshot last;u32 moved,sent,received,resets,invalid; };
static struct observation observations[2][64];
static u32 tables[2],counts[2];
#ifdef CS_WATCH_TCH_METADATA
extern long probe_kernel_read(void *,const void *,unsigned long);
/* l1g_tch.c's verified B03 globals. Read scalar state/configuration only;
 * never the DSP buffers, payloads, MMIO registers, or frame numbers. */
struct tch_metadata {
    u32 state,rate_mode,config_present;
    u8 channel[2],mode_12a,mode_131,amr[12];
};
static struct tch_metadata tch_last[2];
static u32 tch_changes[2],tch_reads_failed[2];
static int metadata_address(u32 p,u32 n) {
    return p && n<=0x200U &&
        ((p>=0xc0000000U && p<=0xc3bc0000U-n) ||
         (p>=0xbf59e000U && p<=0xbf619ba8U-n));
}
static int metadata_read(void *out,u32 p,u32 n) {
    return metadata_address(p,n) && !probe_kernel_read(out,(const void *)p,n);
}
#ifdef CS_WATCH_DSP_STATUS
/* B03's live pointer layout, also used by original CP halfword accesses.
 * Only AMR control words and the CSD RX status word; no frame bytes, IRQ
 * registers, commands, ACKs, or writes. Their speech relevance is unverified. */
static u16 dsp_last[8];
static u32 dsp_status_changes;
#ifdef CS_WATCH_DSP_PCM_METADATA
#include "cs-dsp-pcm-metadata.h"
#endif
#ifdef CS_WATCH_DSP_FRAME_METADATA
/* These exact SRAM ranges are the original CSD/TCH data interface. Reading
 * them never acknowledges a frame. Concurrent DSP writes can make a snapshot
 * inconsistent; change counts alone do not establish a speech frame format. */
struct frame_observation {u32 last,seen,samples,changes,nonzero;};
#ifdef CS_WATCH_DSP_SPEECH_CANDIDATES
#define TCH_BUFFER_COUNT 7U
static const u32 frame_starts[TCH_BUFFER_COUNT]={0xfad01348U,0xfad01318U,
    0xfad01376U,0xfad013a4U,0xfad013d4U,0xfad01404U,0xfad01434U};
static const u32 frame_lengths[TCH_BUFFER_COUNT]={46U,48U,46U,48U,48U,48U,54U};
#else
#define TCH_BUFFER_COUNT 2U
static const u32 frame_starts[TCH_BUFFER_COUNT]={0xfad01348U,0xfad0131aU};
static const u32 frame_lengths[TCH_BUFFER_COUNT]={46U,46U};
#endif
static struct frame_observation frame_observations[TCH_BUFFER_COUNT];
static void sample_frame_metadata(u32 tick) {
    for(u32 direction=0;direction<TCH_BUFFER_COUNT;++direction) {
        const volatile u16 *p=(const volatile u16 *)frame_starts[direction];
        u32 hash=2166136261U,nonzero=0;
        for(u32 i=0;i<frame_lengths[direction]/2U;++i) {
            u16 value=p[i];
            nonzero|=value;
            hash=(hash^(value&255U))*16777619U;
            hash=(hash^(value>>8))*16777619U;
        }
        struct frame_observation *o=&frame_observations[direction];
        if(o->seen && hash!=o->last)o->changes++;
        o->last=hash;o->seen=1;o->samples++;o->nonzero+=!!nonzero;
        if(tick%250U==0U) {
            printk("<6>MF79U_CS_CHANNEL tch_buffer direction=%u samples=%u bytes_per_sample=%u changes_min=%u nonzero_samples=%u contents_logged=0 hash_logged=0 writes=0 ownership_unverified=1\n",
                direction,o->samples,frame_lengths[direction],o->changes,o->nonzero);
            o->samples=o->changes=o->nonzero=0;
        }
    }
}
#endif
static void sample_dsp_status(u32 tick) {
    u16 now[8];
    const volatile u16 *ul=(const volatile u16 *)0xfad012feU;
    const volatile u16 *dl=(const volatile u16 *)0xfad0130eU;
    for(u32 i=0;i<3U;++i)now[i]=ul[i];
    for(u32 i=0;i<4U;++i)now[i+3U]=dl[i];
    now[7]=*(const volatile u16 *)0xfad01318U;
    u32 changed=0;
    for(u32 i=0;i<8U;++i){if(now[i]!=dsp_last[i])changed=1;dsp_last[i]=now[i];}
    dsp_status_changes+=changed;
    if(tick%250U==0U) {
        printk("<6>MF79U_CS_CHANNEL dsp_status samples=%u changes_min=%u ul_control=%04x,%04x,%04x dl_control=%04x,%04x,%04x,%04x rx_status=%04x payload_read=0 status_writes=0\n",
               tick,dsp_status_changes,now[0],now[1],now[2],now[3],now[4],now[5],now[6],now[7]);
        dsp_status_changes=0;
    }
}
static int dsp_status_layout_valid(void) {
#ifdef CS_WATCH_DSP_PCM_METADATA
    if(!cs_pcm_layout_valid())return 0;
#endif
    const u32 globals[4]={0xbf59f4c4U,0xbf59f4d4U,0xbf59f4dcU,0xbf59f4e4U};
    const u32 expected[4]={0xfad012feU,0xfad0130eU,0xfad01318U,0xfad01348U};
    for(u32 i=0;i<4U;++i) {
        u32 address=0;
        if(!metadata_read(&address,globals[i],4) || address!=expected[i])return 0;
    }
#ifdef CS_WATCH_DSP_SPEECH_CANDIDATES
    /* Exact BF3E9F4C pointer initialization; range lengths end at the next
     * pointer, so no padding or unrelated register area is sampled. These
     * candidates are unclassified. Never expose their bytes or hash. */
    const u32 candidate_slots[5]={0xbf59f4ecU,0xbf59f4f4U,0xbf59f4fcU,
        0xbf59f504U,0xbf59f50cU};
    for(u32 i=0;i<5U;++i) {
        u32 address=0;
        if(!metadata_read(&address,candidate_slots[i],4) ||
           address!=frame_starts[i+2U])return 0;
    }
#endif
    return 1;
}
#endif
static void sample_tch(u32 tick) {
    for(u32 connection=0;connection<2U;++connection) {
        if(!tick) {
            u32 ul_control=0,dl_control=0,ul_data=0,dl_data=0;
            metadata_read(&ul_control,0xbf59f4c4U+connection*4U,4);
            metadata_read(&dl_control,0xbf59f4d4U+connection*4U,4);
            metadata_read(&ul_data,0xbf59f4e4U+connection*4U,4);
            metadata_read(&dl_data,0xbf59f4dcU+connection*4U,4);
            /* Pointer values only. The pointed DSP buffers are not read. */
            printk("<6>MF79U_CS_CHANNEL layout connection=%u ul_control=%08x dl_control=%08x ul_data=%08x dl_data=%08x dsp_buffer_read=0\n",
                   connection,ul_control,dl_control,ul_data,dl_data);
        }
        struct tch_metadata now;u32 p=0,channel=0;
        /* Aggregate zero initialization generated a direct Thumb call to
         * B03's ARM memset. Volatile bytes prevent that unsafe libcall. */
        volatile u8 *zero=(volatile u8 *)&now;
        for(u32 i=0;i<sizeof(now);++i)zero[i]=0;
        if(!metadata_read(&now.rate_mode,0xbf5a7860U+connection*4U,4) ||
           !metadata_read(&now.state,0xbf5a7870U+connection*4U,4))tch_reads_failed[connection]++;
        if(metadata_read(&p,0xbf5a7720U+connection*4U,4) &&
           metadata_address(p,0x147U) &&
           metadata_read(&channel,p+0x120U,4) &&
           metadata_address(channel,10U) &&
           metadata_read(now.channel,channel+8U,2) &&
           metadata_read(&now.mode_12a,p+0x12aU,1) &&
           metadata_read(&now.mode_131,p+0x131U,1) &&
           metadata_read(now.amr,p+0x13bU,12))now.config_present=1;
        const u8 *a=(const u8 *)&now,*b=(const u8 *)&tch_last[connection];u32 changed=0;
        for(u32 i=0;i<sizeof(now);++i)if(a[i]!=b[i])changed=1;
        if(changed)tch_changes[connection]++;
        /* Bound printk even if metadata changes every sample. */
        if(tick%50U==0U && (tch_changes[connection] || tick%250U==0U)) {
            printk("<6>MF79U_CS_CHANNEL tch samples=%u connection=%u state=%u rate_mode=%u config_present=%u changes=%u read_failures=%u channel_8=%u channel_9=%u mode_12a=%u mode_131=%u config_13b=%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x payload_read=0\n",
                tick,connection,now.state,now.rate_mode,now.config_present,tch_changes[connection],tch_reads_failed[connection],now.channel[0],now.channel[1],now.mode_12a,now.mode_131,
                now.amr[0],now.amr[1],now.amr[2],now.amr[3],now.amr[4],now.amr[5],
                now.amr[6],now.amr[7],now.amr[8],now.amr[9],now.amr[10],now.amr[11]);
            tch_changes[connection]=0;tch_reads_failed[connection]=0;
        }
        tch_last[connection]=now;
    }
}
#endif
static void sample(u32 tick) {
    u32 active=0,moved=0;
    for(u32 direction=0;direction<2;++direction)for(u32 id=0;id<counts[direction];++id) {
        const volatile u32 *address=(const volatile u32 *)(tables[direction]+id*24U);
        struct cs_channel_snapshot now={address[0],address[1],address[2],address[3],address[4],address[5]};
        struct observation *o=&observations[direction][id];u32 sent,received;
        if(!cs_channel_valid(&now)) {if(now.flags&1U)o->invalid++;}
        else if(cs_channel_delta(&o->last,&now,&sent,&received)) {
            if(sent || received){o->moved++;moved++;}
            o->sent+=sent;o->received+=received;
        } else o->resets++;
        if(cs_channel_valid(&now))active++;
        o->last=now;
        if(tick%250U==0U && (o->moved || o->resets || o->invalid)) {
            printk("<6>MF79U_CS_CHANNEL nominal_seconds=%u direction=%u id=%u cursor_samples=%u producer_bytes_min=%u consumer_bytes_min=%u descriptor_changes=%u invalid=%u size=%u payload_read=0\n",
                   tick/50U,direction,id,o->moved,o->sent,o->received,o->resets,o->invalid,now.size);
            o->moved=o->sent=o->received=o->resets=o->invalid=0;
        }
    }
    if(tick && tick%250U==0U)
        printk("<6>MF79U_CS_CHANNEL heartbeat samples=%u active_descriptors=%u moved_this_sample=%u payload_read=0\n",tick,active,moved);
#ifdef CS_WATCH_TCH_METADATA
    sample_tch(tick);
#endif
#ifdef CS_WATCH_DSP_STATUS
    sample_dsp_status(tick);
#endif
#ifdef CS_WATCH_DSP_PCM_METADATA
    sample_pcm_metadata(tick);
#endif
#ifdef CS_WATCH_DSP_FRAME_METADATA
    sample_frame_metadata(tick);
#endif
}
static int observe(void *unused) {
    (void)unused;
    for(u32 tick=1;tick<=CS_WATCH_SECONDS*50U;++tick) {
        if(kthread_should_stop())return 0;
        msleep(20);sample(tick);
    }
    printk("<6>MF79U_CS_CHANNEL expired seconds=%u rpmsg_payload_read=0 tch_buffer_read=%u cursor_writes=0\n",CS_WATCH_SECONDS,TCH_BUFFER_READ);
    /* Retain the task until cleanup calls kthread_stop; otherwise its pointer
     * could become invalid before a later rmmod on this old kernel. */
    while(!kthread_should_stop())msleep(1000);
    return 0;
}
int init_module(void) {
    static const u8 code[8]={1,0x4b,0x93,0xf8,0x5d,3,0x70,0x47};
    for(u32 i=0;i<8;++i)if(((const volatile u8 *)0xbf3e527cU)[i]!=code[i])return -19;
#ifdef CS_WATCH_TCH_METADATA
    static const u8 tch_getter[8]={1,0x4b,0x53,0xf8,0x20,0x00,0x70,0x47};
    for(u32 i=0;i<8;++i)if(((const volatile u8 *)0xbf40a994U)[i]!=tch_getter[i])return -19;
#endif
#ifdef CS_WATCH_DSP_STATUS
    if(!dsp_status_layout_valid())return -19;
#endif
    const volatile u32 *r=(const volatile u32 *)0xbf55c214U;
    if(r[20]!=0xf83008c0U || r[21]!=0xf8300f80U || r[22]!=64U)return -71;
    tables[0]=r[20];tables[1]=r[21];counts[0]=counts[1]=64;
    sample(0);
    worker=kthread_create_on_node(observe,(void *)0,-1,"mf79u_cs_channels");
    if(!worker || (u32)worker>=0xfffff001U){worker=(void *)0;return -12;}
    printk("<6>MF79U_CS_CHANNEL armed seconds=%u interval_ms=20 registry_verified=1 rpmsg_payload_read=0 tch_buffer_read=%u cursor_writes=0 unloadable=1\n",CS_WATCH_SECONDS,TCH_BUFFER_READ);
    wake_up_process(worker);return 0;
}
void cleanup_module(void) {
    if(worker)kthread_stop(worker);
    printk("<6>MF79U_CS_CHANNEL unloaded rpmsg_payload_read=0 tch_buffer_read=%u cursor_writes=0\n",TCH_BUFFER_READ);
}
