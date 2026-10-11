/* Read-only B03 CP memory inspection through ARM short-descriptor page tables.
 * Never maps MMIO, modifies RAM, or consumes RPM/IPC messages. */
#ifndef MF79U_CP_MEMORY_H
#define MF79U_CP_MEMORY_H
#include <stdint.h>
#include <stddef.h>
typedef int (*mf79u_phys_read_fn)(void *,uint32_t,void *,size_t);
int mf79u_arm_translate(mf79u_phys_read_fn read,void *context,uint32_t pgd,
                       uint32_t virtual_address,uint32_t ram_start,uint32_t ram_end,
                       uint32_t *physical_address);
#endif
