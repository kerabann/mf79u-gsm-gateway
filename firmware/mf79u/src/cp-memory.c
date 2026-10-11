#include "cp-memory.h"
#include <errno.h>
#include <string.h>
static int word(mf79u_phys_read_fn read,void *ctx,uint32_t address,
                uint32_t start,uint32_t end,uint32_t *value) {
    if(address<start || address>end-4 || (address&3)){errno=ERANGE;return -1;}
    unsigned char bytes[4];if(read(ctx,address,bytes,4))return -1;
    *value=(uint32_t)bytes[0]|((uint32_t)bytes[1]<<8)|((uint32_t)bytes[2]<<16)|((uint32_t)bytes[3]<<24);
    return 0;
}
int mf79u_arm_translate(mf79u_phys_read_fn read,void *ctx,uint32_t pgd,
                       uint32_t va,uint32_t start,uint32_t end,uint32_t *pa) {
    if(!read || !pa || end<start || end-start<16384 || (pgd&16383) || pgd<start || pgd>end-16384){errno=EINVAL;return -1;}
    uint32_t first,physical;
    if(word(read,ctx,pgd+(va>>20)*4,start,end,&first))return -1;
    switch(first&3) {
    case 1: {
        uint32_t second,table=first&0xfffffc00U;
        if(word(read,ctx,table+((va>>12)&255)*4,start,end,&second))return -1;
        switch(second&3) {
        case 1:physical=(second&0xffff0000U)|(va&0xffffU);break;
        case 2:case 3:physical=(second&0xfffff000U)|(va&0xfffU);break;
        default:errno=ENOENT;return -1;
        }
        break;
    }
    case 2:
        if(first&(1U<<18)){errno=ENOTSUP;return -1;} /* Supersection unsupported. */
        physical=(first&0xfff00000U)|(va&0xfffffU);break;
    default:errno=ENOENT;return -1;
    }
    if(physical<start || physical>=end){errno=ERANGE;return -1;}
    *pa=physical;return 0;
}
