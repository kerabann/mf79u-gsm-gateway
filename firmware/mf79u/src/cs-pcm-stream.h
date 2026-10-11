/* Experimental root-only, bounded sysfs PCM transport. Exact B03 kobject ABI
 * is admitted by cs_status_create. Hardware thread never waits on userspace.
 * RX: worker produces, sysfs consumes; TX: sysfs produces, worker consumes. */
#ifndef MF79U_CS_PCM_STREAM_H
#define MF79U_CS_PCM_STREAM_H
#include "cs-pcm-spsc.h"
static struct cs_pcm_ring cs_pcm_rx,cs_pcm_tx;
static volatile u32 cs_pcm_rx_lock,cs_pcm_tx_lock,cs_pcm_online;
static u32 cs_pcm_rx_busy,cs_pcm_tx_busy,cs_pcm_tx_empty,cs_pcm_rx_frames,cs_pcm_tx_frames;
static u32 cs_pcm_files;
static int cs_pcm_take(volatile u32 *lock) {return __sync_bool_compare_and_swap(lock,0,1);}
static void cs_pcm_give(volatile u32 *lock) {__sync_lock_release(lock);}
static void cs_pcm_start(void) {
    cs_pcm_ring_clear(&cs_pcm_rx);cs_pcm_ring_clear(&cs_pcm_tx);
    __atomic_store_n(&cs_pcm_online,1,__ATOMIC_RELEASE);
    printk("<6>MF79U_CS_PCM ready=1 internal_rate=8000 frame_bytes=320 sip_rate=16000 spsc=1\n");
}
static void cs_pcm_stop(void) {
    __atomic_store_n(&cs_pcm_online,0,__ATOMIC_RELEASE);
    while(!cs_pcm_take(&cs_pcm_rx_lock))msleep(1);
    while(!cs_pcm_take(&cs_pcm_tx_lock))msleep(1);
    u32 dropped=cs_pcm_rx.dropped;
    cs_pcm_ring_clear(&cs_pcm_rx);cs_pcm_ring_clear(&cs_pcm_tx);
    cs_pcm_give(&cs_pcm_tx_lock);cs_pcm_give(&cs_pcm_rx_lock);
    printk("<6>MF79U_CS_PCM stopped=1 rx_frames=%u tx_frames=%u rx_dropped_words=%u rx_busy=%u tx_busy=%u tx_empty_words=%u buffers_cleared=1\n",
        cs_pcm_rx_frames,cs_pcm_tx_frames,dropped,cs_pcm_rx_busy,cs_pcm_tx_busy,cs_pcm_tx_empty);
}
static void cs_pcm_receive_word(u32 word) {
    if(__atomic_load_n(&cs_pcm_online,__ATOMIC_ACQUIRE))cs_pcm_spsc_push(&cs_pcm_rx,word);
}
static u32 cs_pcm_transmit_word(void) {
    u32 word=0;if(!__atomic_load_n(&cs_pcm_online,__ATOMIC_ACQUIRE))return 0;
    if(!cs_pcm_spsc_pop(&cs_pcm_tx,&word))cs_pcm_tx_empty++;
    return word;
}
static int cs_pcm_show(void *o,struct cs_kobj_attribute *a,char *buffer) {
    (void)o;(void)a;
    if(!cs_pcm_take(&cs_pcm_rx_lock)){cs_pcm_rx_busy++;return -11;}
    int result=-11;
    if(__atomic_load_n(&cs_pcm_online,__ATOMIC_ACQUIRE) && cs_pcm_spsc_read_frame(&cs_pcm_rx,(u8 *)buffer)) {
        cs_pcm_rx_frames++;result=320;
    }
    cs_pcm_give(&cs_pcm_rx_lock);return result;
}
static int cs_pcm_store(void *o,struct cs_kobj_attribute *a,const char *buffer,u32 length) {
    (void)o;(void)a;if(length!=320U)return -22;
    if(!cs_pcm_take(&cs_pcm_tx_lock)){cs_pcm_tx_busy++;return -11;}
    int result=-11;
    if(__atomic_load_n(&cs_pcm_online,__ATOMIC_ACQUIRE) && cs_pcm_spsc_write_frame(&cs_pcm_tx,(const u8 *)buffer)) {
        cs_pcm_tx_frames++;result=320;
#ifdef CS_PCM_SELF_LOOP
        /* Dedicated no-hardware ABI fixture, with one serialized producer. */
        for(u32 i=0;i<CS_PCM_FRAME_WORDS;i++)cs_pcm_receive_word(cs_pcm_transmit_word());
#endif
    }
    cs_pcm_give(&cs_pcm_tx_lock);return result;
}
static int cs_pcm_info(void *o,struct cs_kobj_attribute *a,char *buffer) {
    (void)o;(void)a;
    return scnprintf(buffer,128,"MF79U_CS_PCM 1 %u 8000 160 320\n",cs_pcm_online);
}
static struct cs_kobj_attribute cs_pcm_attributes[]={
    {{"pcm_rx",0400,0},cs_pcm_show,(void *)0},
    {{"pcm_tx",0200,0},(void *)0,(void *)cs_pcm_store},
    {{"pcm_info",0400,0},cs_pcm_info,(void *)0}
};
static void cs_pcm_remove(void) {
    while(cs_pcm_files)sysfs_remove_file(cs_status_object,&cs_pcm_attributes[--cs_pcm_files].attr);
}
static int cs_pcm_create(void) {
    for(u32 i=0;i<3U;i++) {
        int result=sysfs_create_file(cs_status_object,&cs_pcm_attributes[i].attr);
        if(result){cs_pcm_remove();return result;}cs_pcm_files++;
    }
    return 0;
}
#endif
