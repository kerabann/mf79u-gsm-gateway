#!/usr/bin/env python3
"""Exercise the actual PCM step/hold functions with simulated MMIO and CC state.

No device access. Hardware startup/restore and PCM transport are instrumented
boundaries; their real ABI and audio behavior still require the physical test.
"""
from pathlib import Path
import hashlib,json,subprocess,tempfile

BASE=Path(__file__).resolve().parent
source=(BASE/'src/cs-i2s-pcm-candidate.h').read_text()
def function(name):
    start=source.index('static void '+name+'(')
    begin=source.index('{',start);depth=1;end=begin+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]

fixture=r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define CS_I2S_USERSPACE_PCM 1
#define CS_I2S_ARM_ECHO_TEST 1
#define CS_I2S_ARM_TONE_TEST 1
#define CS_I2S_ARM1_TX_SWITCH 1
#define CS_I2S_ARM1_RX_ONLY 1
#define CS_I2S_ARM1_ECHO_TEST 1
#define CS_I2S_PORT_TONE_TEST 1
#define CS_AUDIO_LOG "fixture"
#define CS_I2S_CALL_ACTIVE() (stage!=0)
static u32 stage,cs_audio_started,cs_audio_done,cs_audio_media_done;
static u32 cs_port_tone_started,cs_i2s_failed,cs_echo_started,cs_arm1_tx_switched;
static u32 cs_i2s_last_rx,cs_i2s_rx,cs_i2s_rx_nonzero,cs_i2s_tx;
static u32 cs_rx_window_words,cs_rx_window_active,cs_rx_window_peak;
static u32 cs_echo_nonzero;
#ifndef CS_I2S_STREAMING_PCM
static u32 cs_i2s_phase;
#endif
static unsigned long long cs_audio_connected_at,cs_port_tone_at,cs_audio_play_at;
static u32 process[2],stops,restores,starts,pcm_rx,pcm_tx,silence,control_writes;
static int printk(const char *format,...) {(void)format;return 0;}
static unsigned long long cs_monotonic_ns(void) {return 10000000000ULL;}
static int cs_audio_channel(void) {return 1;}
static int cs_port_tone_start(void) {starts++;return 1;}
static int cs_i2s_start(void) {starts++;return 1;}
static void cs_pcm_stop(void) {stops++;}
static void cs_pcm_start(void) {starts++;}
static void cs_pcm_receive_word(u32 v) {(void)v;pcm_rx++;}
static u32 cs_pcm_transmit_word(void) {pcm_tx++;return 42;}
static void cs_audio_restore(void) {restores++;cs_audio_started=0;cs_audio_done=1;}
static u32 cs_i2s_read(u32 a) {
    u32 port=(a>=0xf8a06000U),off=a&0xfffU;
    if(off==4)return process[port];
    if(off==0x10)return (4U<<16)|(4U<<8);
    if(off==0x1c)return 0x00100020U;
    assert(0);return 0;
}
static void cs_i2s_write(u32 a,u32 v) {
    if((a&0xfffU)==4){control_writes++;process[a>=0xf8a06000U]=v;return;}
    assert((a&0xfffU)==0x1c);
    if(v==0)silence++;
}
static void reset(void) {
    stage=5;cs_audio_started=cs_port_tone_started=cs_echo_started=cs_arm1_tx_switched=1;
    cs_audio_done=cs_audio_media_done=0;cs_audio_connected_at=1000000000ULL;
    cs_port_tone_at=4000000000ULL;cs_audio_play_at=10000000000ULL;
    process[0]=6;process[1]=7;
    stops=restores=starts=pcm_rx=pcm_tx=silence=control_writes=0;
}
'''
fixture+=function('cs_audio_hold_silence')+'\n'+function('cs_audio_step')
fixture+=r'''
int main(void) {
    reset();cs_audio_step(1,31999999999ULL);
    assert(pcm_rx && pcm_tx && !stops && !restores);
#ifdef CS_I2S_STREAMING_PCM
    /* The real streaming branch must keep transporting speech well beyond
     * the diagnostic deadline, and close only on signaling. */
    for(u32 i=0;i<3600;i++)cs_audio_step(1,32000000000ULL+i*1000000000ULL);
    assert(!stops && !restores && !starts && !control_writes);
    assert(pcm_rx>10000 && pcm_tx>10000 && !silence);
    stage=6;cs_audio_step(0,4000000000000ULL);
    assert(stops==1 && !restores && silence);
    /* PCM and ARM1 TX start immediately; there is no diagnostic tone phase. */
    reset();cs_echo_started=cs_arm1_tx_switched=0;
    cs_audio_step(1,10000000001ULL);
    assert(cs_echo_started && cs_arm1_tx_switched && starts==1 && pcm_rx && pcm_tx);
#else
    for(u32 i=0;i<1000;i++)cs_audio_step(1,32000000000ULL+i*1000000ULL);
    assert(stops==1 && !restores && !starts && silence && !control_writes);
    assert(process[0]==6 && process[1]==7);
    for(stage=6;stage<=8;stage++)cs_audio_step(0,34000000000ULL);
    assert(stops==1 && !restores && !control_writes);
    stage=0;cs_audio_step(0,35000000000ULL);assert(restores==1);
#endif
    /* Remote clearing before the media deadline closes PCM exactly once. */
    reset();stage=6;cs_audio_step(0,15000000000ULL);
    assert(stops==1 && !restores && silence && !control_writes);
    stage=8;cs_audio_step(0,16000000000ULL);assert(stops==1 && !restores);
    stage=0;cs_audio_step(0,17000000000ULL);assert(restores==1);
    /* Pre-connect signaling must not arm or close the media path. */
    reset();cs_audio_started=cs_port_tone_started=0;stage=2;
    cs_audio_step(0,15000000000ULL);
    assert(!stops && !restores && !starts && !cs_audio_media_done && !control_writes);
    puts("PCM transport and clearing retain hardware until MM idle: passed");
}
'''
with tempfile.TemporaryDirectory(prefix='cs-audio-lifecycle-') as tmp:
    c=Path(tmp)/'test.c';exe=Path(tmp)/'test';c.write_text(fixture)
    results=[]
    for streaming in (False,True):
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',
                        *(['-DCS_I2S_STREAMING_PCM=1'] if streaming else []),str(c),'-o',str(exe)],check=True,timeout=30)
        result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=10)
        results.append({'streaming':streaming,'result':result.stdout.strip()})
report={'passed':True,'device_access':False,'hardware_behavior_verified':False,
        'sanitizer':'undefined',
        'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'checks':['deadline_keeps_clocks','stop_once','silence_during_clearing','close_only_mm_idle','remote_clearing','preconnect_no_media','streaming_no_media_deadline','streaming_immediate_pcm_and_arm1'],
        'results':results}
(BASE/'build/cs-audio-lifecycle-test.json').write_text(json.dumps(report,indent=2)+'\n')
print(result.stdout.strip())
