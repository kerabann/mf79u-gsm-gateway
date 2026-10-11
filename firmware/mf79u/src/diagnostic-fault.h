/* Diagnostic-only crash address receipt. No core dump, memory contents,
 * numbers or credentials. B03 ramdump_on_user can reboot on a user fault. */
#ifndef MF79U_DIAGNOSTIC_FAULT_H
#define MF79U_DIAGNOSTIC_FAULT_H
#include <signal.h>
#include <stdint.h>
#include <string.h>
#ifdef __arm__
#include <ucontext.h>
#endif
#include <unistd.h>
static unsigned mf79u_fault_hex(char *out,uintptr_t value) {
    static const char hex[]="0123456789abcdef";
    for(unsigned i=0;i<8;i++)out[i]=hex[(value>>(28U-i*4U))&15U];
    return 8;
}
static unsigned mf79u_fault_field(char *out,const char *key,uintptr_t value) {
    unsigned n=0;while(*key)out[n++]=*key++;
    return n+mf79u_fault_hex(out+n,value);
}
static void mf79u_diagnostic_fault(int sig,siginfo_t *info,void *context) {
    char line[192];unsigned n=0;uintptr_t pc=0,lr=0,sp=0;
#ifdef __arm__
    ucontext_t *c=(ucontext_t *)context;
#if defined(__GLIBC__) && !defined(__USE_MISC)
    if(c){pc=c->uc_mcontext.__arm_pc;lr=c->uc_mcontext.__arm_lr;sp=c->uc_mcontext.__arm_sp;}
#else
    if(c){pc=c->uc_mcontext.arm_pc;lr=c->uc_mcontext.arm_lr;sp=c->uc_mcontext.arm_sp;}
#endif
#else
    (void)context;
#endif
    n+=mf79u_fault_field(line+n,"MF79U_DIAG_FAULT signal=",(unsigned)sig);
    n+=mf79u_fault_field(line+n," code=",info?(unsigned)info->si_code:0);
    n+=mf79u_fault_field(line+n," pc=",pc);
    n+=mf79u_fault_field(line+n," lr=",lr);
    n+=mf79u_fault_field(line+n," sp=",sp);
    n+=mf79u_fault_field(line+n," address=",info?(uintptr_t)info->si_addr:0);
    line[n++]='\n';
    /* Only async-signal-safe calls. Never resume the damaged process or
     * re-raise into B03's device-wide user-ramdump path. */
    (void)write(STDOUT_FILENO,line,n);_exit(128+sig);
}
static int mf79u_diagnostic_fault_install(void) {
    struct sigaction action;memset(&action,0,sizeof(action));
    action.sa_sigaction=mf79u_diagnostic_fault;action.sa_flags=SA_SIGINFO;
    sigemptyset(&action.sa_mask);
    const int signals[]={SIGSEGV,SIGBUS,SIGILL,SIGABRT,SIGFPE};
    for(unsigned i=0;i<sizeof(signals)/sizeof(signals[0]);i++)
        if(sigaction(signals[i],&action,0))return -1;
    return 0;
}
#endif
