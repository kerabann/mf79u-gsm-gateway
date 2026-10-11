#include "cp-memory.h"
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static unsigned char pgd[16384],table[1024];
static int reads;
static int read_fixture(void *ctx,uint32_t address,void *out,size_t length) {
    (void)ctx;reads++;
    if(length!=4){errno=EIO;return -1;}
    if(address>=0x20004000U && address<=0x20007ffcU){memcpy(out,pgd+address-0x20004000U,4);return 0;}
    if(address>=0x20008000U && address<=0x200083fcU){memcpy(out,table+address-0x20008000U,4);return 0;}
    errno=ERANGE;return -1;
}
static void set(unsigned char *where,uint32_t word) {
    where[0]=word;where[1]=word>>8;where[2]=word>>16;where[3]=word>>24;
}
static int translate(uint32_t va,uint32_t *pa) {
    return mf79u_arm_translate(read_fixture,NULL,0x20004000U,va,0x20000000U,0x22000000U,pa);
}
#define CHECK(x) do{if(!(x)){printf("FAIL line=%d\n",__LINE__);return 1;}}while(0)
int main(void) {
    uint32_t pa=0;
    /* Independent ARMv7 short descriptor examples, including real CP VA. */
    set(pgd+0xbf0*4,0x21000c02U);
    CHECK(!translate(0xbf001234U,&pa) && pa==0x21001234U);
    set(pgd+0xbf3*4,0x20008001U);set(table+0xe5*4,0x2054503eU);
    CHECK(!translate(0xbf3e527cU,&pa) && pa==0x2054527cU);
    set(table+0xe5*4,0x20a00001U);
    CHECK(!translate(0xbf3e527cU,&pa) && pa==0x20a0527cU);
    set(table+0xe5*4,0);CHECK(translate(0xbf3e527cU,&pa)<0 && errno==ENOENT);
    set(pgd+0xbf3*4,0xf8a00001U);reads=0;
    CHECK(translate(0xbf3e527cU,&pa)<0 && errno==ERANGE && reads==1);
    set(pgd+0xbf3*4,0xf8a00c02U);
    CHECK(translate(0xbf3e527cU,&pa)<0 && errno==ERANGE);
    set(pgd+0xbf3*4,0x21040c02U);
    CHECK(translate(0xbf3e527cU,&pa)<0 && errno==ENOTSUP);
    CHECK(mf79u_arm_translate(read_fixture,NULL,0x20004004U,0xbf3e527cU,0x20000000U,0x22000000U,&pa)<0 && errno==EINVAL);
    puts("PASS ARM section/small/large translations, missing entries, MMIO exclusion, supersection/alignment rejection");return 0;
}
