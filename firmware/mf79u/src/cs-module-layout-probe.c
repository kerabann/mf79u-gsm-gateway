/* SPDX-License-Identifier: GPL-2.0-only
 * Read-only B03 module-loader ABI anchors for a possible future boot observer.
 * No hooks, module notifications, DSP access or hardware writes.
 */
typedef unsigned int u32;
typedef unsigned char u8;
extern int printk(const char *,...);
extern void *__module_address(unsigned long);
int init_module(void) {
    u32 irq_flags;
    u32 core=0,size=0,init=0,state=0,valid=0;
    /* __module_address requires RCU/preemption protection. On this single-CPU
     * kernel IRQ exclusion prevents module-list removal during the bounded
     * reads. Never printk or sleep inside this critical section.
     */
    __asm__ volatile("mrs %0, cpsr\n\tcpsid i":"=r"(irq_flags)::"memory");
    const volatile u8 *module=(const volatile u8 *)__module_address(0xbf000000U);
    if((u32)module>=0xbf000000U && (u32)module<=0xbf800000U-328U &&
       module[12]=='c' && module[13]=='p' && module[14]=='k' && module[15]=='o' && !module[16]) {
        state=*(const volatile u32 *)module;
        init=*(const volatile u32 *)(module+188U);
        core=*(const volatile u32 *)(module+196U);
        size=*(const volatile u32 *)(module+204U);
        valid=!state && core==0xbf000000U && size==6397096U && init>=core && init<core+size;
    }
    __asm__ volatile("msr cpsr_c, %0"::"r"(irq_flags):"memory");
    printk("<6>MF79U_CS_MODULE_LAYOUT cp_structure=%08x state=%u init=%08x core=%08x size=%u layout_verified=%u no_hooks=1 no_dsp_access=1\n",
        (u32)module,state,init,core,size,valid);
    return valid?0:-19;
}
void cleanup_module(void) {printk("<6>MF79U_CS_MODULE_LAYOUT unloaded\n");}
