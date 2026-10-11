/* Standalone uClibc ABI bootstrap. Calls only the public-fixture selftest. */
#include <dlfcn.h>
#include <stdio.h>
extern void __uClibc_main(int(*)(int,char**),int,char**,void*,void*,void*,void*);
int main(int argc,char **argv){
    (void)argv;if(argc!=1)return 2;
    void *handle=dlopen("/dev/.mf79u-ims-userspace-ipsec.so",RTLD_NOW);
    if(!handle){puts("Unable to load RAM ESP library");return 1;}
    int (*test)(void)=dlsym(handle,"mf79u_esp_crypto_selftest");
    if(!test){puts("Selftest symbol unavailable");return 1;}
    int result=test();printf("ARM crypto selftest result=%d\n",result);dlclose(handle);return result;
}
__attribute__((naked,noreturn)) void _start(void){
    __asm__ volatile("ldr r1, [sp], #4\nmov r2, sp\nmov r4, sp\nldr r0, =main\nmov r3, #0\n"
                     "bic sp, sp, #7\nsub sp, sp, #16\nstr r3, [sp]\nstr r3, [sp, #4]\nstr r4, [sp, #8]\n"
                     "bl __uClibc_main\nmov r0, #1\nmov r7, #1\nsvc #0\n");
}
