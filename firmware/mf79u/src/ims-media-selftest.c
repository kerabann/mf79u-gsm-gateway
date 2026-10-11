/* Synthetic media test through the real modem's uClibc loader. */
#include <dlfcn.h>
#include <stdio.h>
extern void __uClibc_main(int(*)(int,char**),int,char**,void*,void*,void*,void*);
int main(int argc,char **argv){
    if(argc!=1 && argc!=2)return 2;
    void *handle=dlopen(argc==2?argv[1]:"/dev/.mf79u-ims-userspace-ipsec.so",RTLD_NOW);
    if(!handle){printf("RAM library load failed: %s\n",dlerror());return 1;}
    int (*test)(void)=dlsym(handle,"mf79u_media_selftest");
    if(!test){puts("Media selftest unavailable");return 1;}
    int result=test();printf("ARM software media selftest result=%d\n",result);
    int (*wb)(void)=dlsym(handle,"mf79u_media_wb_selftest");
    if(!result)result=wb?wb():1;
    printf("ARM software WB media selftest result=%d\n",result);
    int (*g722)(void)=dlsym(handle,"mf79u_vendor_codecs_selftest");
    if(!result)result=g722?g722():1;
    printf("ARM vendor G722 ABI media selftest result=%d\n",result);dlclose(handle);return result;
}
__attribute__((naked,noreturn)) void _start(void){
    __asm__ volatile("ldr r1, [sp], #4\nmov r2, sp\nmov r4, sp\nldr r0, =main\nmov r3, #0\n"
                     "bic sp, sp, #7\nsub sp, sp, #16\nstr r3, [sp]\nstr r3, [sp, #4]\nstr r4, [sp, #8]\n"
                     "bl __uClibc_main\nmov r0, #1\nmov r7, #1\nsvc #0\n");
}
