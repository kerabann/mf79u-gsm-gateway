/* SPDX-License-Identifier: GPL-2.0-only
 * Test our binary PCM attributes in RAM. No CP, DSP, radio or call access. */
typedef unsigned int u32;
typedef unsigned char u8;
extern int printk(const char *,...);
extern long probe_kernel_read(void *,const void *,unsigned long);
extern void msleep(unsigned int);
#define CS_STATUS_OBJECT_NAME "mf79u_pcm_probe"
#include "cs-kernel-status.h"
#define CS_PCM_SELF_LOOP 1
#include "cs-pcm-stream.h"
int init_module(void) {
    int result=cs_status_create();if(result)return result;
    result=cs_pcm_create();if(result){cs_status_remove();return result;}
    cs_pcm_start();
    printk("<6>MF79U_CS_PCM_LOOP loaded=1 no_cp_io=1 no_calls=1\n");
    return 0;
}
void cleanup_module(void) {
    cs_pcm_stop();cs_pcm_remove();cs_status_remove();
    printk("<6>MF79U_CS_PCM_LOOP unloaded=1 buffers_cleared=1\n");
}
