/* Watch only our RAM IMS daemon's fatal signals; never inspect data memory.
 * A fatal tracee is stopped, allowing controlled termination instead of crash.
 * ARM32 Linux 3.4 ptrace ABI. */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#ifndef __WALL
#define __WALL 0x40000000
#endif
struct arm_regs {unsigned long r[18];};
static pid_t tids[64];static unsigned count;
static int index_of(pid_t tid){for(unsigned i=0;i<count;i++)if(tids[i]==tid)return (int)i;return -1;}
static void remove_tid(pid_t tid){int i=index_of(tid);if(i>=0)tids[i]=tids[--count];}
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    char *end;long value=strtol(argv[1],&end,10);if(*end || value<2)return 2;
    pid_t pid=(pid_t)value;char path[80],exe[128];
    snprintf(path,sizeof(path),"/proc/%d/exe",pid);
    ssize_t len=readlink(path,exe,sizeof(exe)-1);if(len<0)return 1;exe[len]=0;
    if(strcmp(exe,"/dev/.mf79u-volte-private"))return 2;
    setvbuf(stdout,NULL,_IONBF,0);
    snprintf(path,sizeof(path),"/proc/%d/task",pid);DIR *directory=opendir(path);
    if(!directory)return 1;
    struct dirent *entry;
    while((entry=readdir(directory))) {
        if(entry->d_name[0]=='.')continue;
        pid_t tid=(pid_t)strtol(entry->d_name,NULL,10);if(tid<2 || count>=64)continue;
        if(ptrace(PTRACE_ATTACH,tid,NULL,NULL)){perror("attach private IMS thread");continue;}
        int status;if(waitpid(tid,&status,__WALL)!=tid || !WIFSTOPPED(status))continue;
        tids[count++]=tid;
        ptrace(PTRACE_SETOPTIONS,tid,NULL,(void*)(long)PTRACE_O_TRACECLONE);
        ptrace(PTRACE_CONT,tid,NULL,NULL);
    }
    closedir(directory);printf("READY fatal-signal observer threads=%u\n",count);
    int freezing=0;time_t deadline=time(NULL)+240;
    while(count) {
        if(!freezing && time(NULL)>=deadline){kill(pid,SIGSTOP);freezing=1;puts("Observer timeout; stopping before detach");}
        int status;pid_t tid=waitpid(-1,&status,__WALL|WNOHANG);
        if(tid<0){if(errno==ECHILD)break;perror("wait private IMS");break;}
        if(!tid){usleep(10000);continue;}
        if(WIFEXITED(status)||WIFSIGNALED(status)){remove_tid(tid);continue;}
        if(!WIFSTOPPED(status))continue;
        unsigned event=(unsigned)status>>16;int sig=WSTOPSIG(status);
        if(event==PTRACE_EVENT_CLONE){
            unsigned long child=0;ptrace(PTRACE_GETEVENTMSG,tid,NULL,&child);
            if(child && index_of((pid_t)child)<0 && count<64)tids[count++]=(pid_t)child;
        }
        if(sig==SIGSEGV || sig==SIGABRT || sig==SIGBUS || sig==SIGILL || sig==SIGFPE) {
            struct arm_regs regs={0};ptrace(PTRACE_GETREGS,tid,NULL,&regs);
            printf("FATAL signal=%d tid=%d pc=%08lx lr=%08lx sp=%08lx\n",
                   sig,tid,regs.r[15],regs.r[14],regs.r[13]);
            kill(pid,SIGSTOP);freezing=1;
        }
        if(freezing){
            if(!ptrace(PTRACE_DETACH,tid,NULL,(void*)(long)SIGSTOP) || errno==ESRCH)remove_tid(tid);
        }else ptrace(PTRACE_CONT,tid,NULL,(void*)(long)((sig==SIGSTOP || sig==SIGTRAP)?0:sig));
    }
    if(freezing)puts("Private IMS stopped; use controlled termination with SIGTERM and SIGCONT");
    else puts("Private IMS exited without observed fatal signal");
    return 0;
}
