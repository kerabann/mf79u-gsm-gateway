/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03, bounded ARM I2S self-loop diagnostic. No DSP commands, CC hooks,
 * SIM operations, external GPIO changes, DMA or IRQ handlers. Restore all
 * controls before init returns. Synthetic words only; never log sample bytes.
 */
typedef unsigned int u32;
typedef unsigned char u8;
extern int printk(const char *,...);
extern long probe_kernel_read(void *,const void *,unsigned long);
extern void msleep(unsigned int);
static const u32 addresses[]={0xf8440060U,0xf8a00014U,0xf8a00058U,0xf8a0005cU,
 0xf8a05004U,0xf8a05008U,0xf8a0500cU,0xf8a05014U,0xf8a05020U};
static u32 saved[9],flags[2];
static u32 get(u32 a){return *(const volatile u32 *)a;}
static void put(u32 a,u32 v){*(volatile u32 *)a=v;__asm__ volatile("dmb sy":::"memory");}
static void gate(u32 n,u32 hw,u32 sw){((void (*)(u32,u32))0xbf439151U)(n,hw);((void (*)(u32,u32))0xbf4391d1U)(n,sw);}
int init_module(void) {
 if(get(0xbf4f9650U)!=0xbf439151U || get(0xbf4f9654U)!=0xbf4391d1U || get(0xbf4f965cU)!=0xbf43930dU ||
    get(0xbf55cde4U)!=0xf8a00014U || get(0xbf55ce74U)!=0xf8a00014U ||
    get(0xf8a05000U)!=0x01030000U || get(0xf8a05004U) || get(0xf8a05014U))return -71;
 for(u32 i=0;i<9;i++)saved[i]=get(addresses[i]);
 for(u32 i=0;i<2;i++) {
  flags[i]=*(const volatile unsigned short *)(0xbf55c5a0U+(29U+2U*i)*0x48U+0x16U);
  if((flags[i]&255U)>1U || (flags[i]>>8)>1U)return -71;
 }
 gate(29,1,1);gate(31,1,1);
 ((void (*)(u32,u32))0xbf43930dU)(29,0);((void (*)(u32,u32))0xbf43930dU)(29,1);
 ((void (*)(u32,u32))0xbf43930dU)(31,0);((void (*)(u32,u32))0xbf43930dU)(31,1);
 put(0xf8a05014U,0);put(0xf8a05018U,0xffffU);
 put(0xf8a00014U,(get(0xf8a00014U)&~0xf0330U)|0x10f03U);
 put(0xf8a0005cU,get(0xf8a0005cU)&~0x10000U);put(0xf8a00058U,0x200019U);put(0xf8a0005cU,0x32U);put(0xf8a0005cU,0x10032U);
 /* ARM-local loop, no connection to Teak AFE. */
 put(0xf8440060U,saved[0]&~0x1f8U);
 put(0xf8a05008U,0x01ef4003U);put(0xf8a0500cU,0x70f03U);msleep(1);
 printk("<6>MF79U_CS_I2S_LOOP configured clock=%08x timing=%08x fifo=%08x status=%08x divisor=%08x/%08x\n",
  get(0xf8a00014U),get(0xf8a05008U),get(0xf8a0500cU),get(0xf8a05010U),get(0xf8a00058U),get(0xf8a0005cU));
 put(0xf8a05004U,7U);
 u32 rx_nonzero=0,rx_changed=0,last=0;
 for(u32 t=0;t<1000;t++) {
  for(u32 i=0;i<8;i++)put(0xf8a0501cU,0x12345678U);
  for(u32 i=0;i<8;i++){u32 v=get(0xf8a0501cU);if(v)rx_nonzero++;if(v!=last)rx_changed++;last=v;}
  if(t%250U==0)printk("<6>MF79U_CS_I2S_LOOP sample tick=%u process=%08x status=%08x irq=%08x frame=%08x rx_nonzero=%u rx_changed=%u\n",
   t,get(0xf8a05004U),get(0xf8a05010U),get(0xf8a05018U),get(0xf8a05020U),rx_nonzero,rx_changed);
  msleep(1);
 }
 put(0xf8a05004U,0);
 for(u32 i=4;i<9;i++)put(addresses[i],saved[i]);
 put(0xf8440060U,(get(0xf8440060U)&~0x1f8U)|(saved[0]&0x1f8U));put(0xf8a00058U,saved[2]);put(0xf8a0005cU,saved[3]);
 gate(29,flags[0]&255U,flags[0]>>8);gate(31,flags[1]&255U,flags[1]>>8);
 put(0xf8a00014U,(get(0xf8a00014U)&~0xf0f33U)|(saved[1]&0xf0f33U));
 u32 restored=1;for(u32 i=0;i<9;i++)if(get(addresses[i])!=saved[i])restored=0;
 printk("<6>MF79U_CS_I2S_LOOP completed=1 registers_restored=%u no_calls=1 no_dsp_commands=1\n",restored);
 return restored?0:-71;
}
void cleanup_module(void){printk("<6>MF79U_CS_I2S_LOOP unloaded\n");}
