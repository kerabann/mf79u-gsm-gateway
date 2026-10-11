/* Read-only statistics of unclassified, pointer-bounded B03 shared SRAM.
 * No samples or hashes leave the kernel. Periodicity is only a search hint;
 * concurrent DSP writes and unknown sample rate prevent PCM classification.
 */
#ifndef CS_DSP_PCM_METADATA_H
#define CS_DSP_PCM_METADATA_H
#include "../build/cs-dsp-pcm-windows.h"
struct cs_pcm_observation {u32 last,seen,samples,changed,nonzero,period[3];};
static struct cs_pcm_observation cs_pcm_observations[CS_PCM_WINDOW_COUNT];
static int cs_pcm_layout_valid(void) {
    for(u32 i=0;i<CS_PCM_WINDOW_COUNT;i++) {
        u32 value=0;
        if(!metadata_read(&value,cs_pcm_windows[i][0],4) || value!=cs_pcm_windows[i][1])return 0;
    }
    return 1;
}
static u32 cs_pcm_period(const short *data,u32 count,u32 lag) {
    int energy=0,positive=0,negative=0;
    for(u32 i=lag;i<count;i++) {
        int a=data[i]>>8,b=data[i-lag]>>8,c=data[i-lag/2U]>>8;
        energy+=a*a;positive+=a*b;negative+=a*c;
    }
    /* DC values do not satisfy the negative half-period condition. Bounds:
     * <=160 samples scaled to signed8, so all arithmetic fits signed32. */
    return energy>256 && positive*5>=energy*4 && negative*5<=-energy*4;
}
static void sample_pcm_metadata(u32 tick) {
    for(u32 index=0;index<CS_PCM_WINDOW_COUNT;index++) {
        short data[160];u32 count=cs_pcm_windows[index][2],hash=2166136261U,nonzero=0;
        const volatile u16 *p=(const volatile u16 *)cs_pcm_windows[index][1];
        for(u32 i=0;i<count;i++) {
            u16 word=p[i];data[i]=(short)word;nonzero|=word;
            hash=(hash^word)*16777619U;
        }
        struct cs_pcm_observation *o=&cs_pcm_observations[index];
        o->changed+=o->seen && o->last!=hash;o->last=hash;o->seen=1;
        o->samples++;o->nonzero+=!!nonzero;
        for(u32 i=0;i<3;i++)o->period[i]+=cs_pcm_period(data,count,8U<<i);
        if(tick%50U==0U) {
            printk("<6>MF79U_CS_CHANNEL pcm_window index=%u address=%08x halfwords=%u samples=%u changed_min=%u nonzero_samples=%u period8=%u period16=%u period32=%u contents_logged=0 hash_logged=0 writes=0 pcm_unverified=1\n",
                index,cs_pcm_windows[index][1],count,o->samples,o->changed,o->nonzero,o->period[0],o->period[1],o->period[2]);
            o->samples=o->changed=o->nonzero=0;
            for(u32 i=0;i<3;i++)o->period[i]=0;
        }
    }
}
#endif
