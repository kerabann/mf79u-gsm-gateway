#include <sys/ptrace.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){if(argc<2)return 1;pid_t pid=fork();if(!pid){ptrace(PTRACE_TRACEME,0,0,0);raise(SIGSTOP);execv(argv[1],argv+1);_exit(127);}int status;unsigned long history[40][4],counter=0;waitpid(pid,&status,0);ptrace(PTRACE_SETOPTIONS,pid,0,PTRACE_O_TRACESYSGOOD);while(1){ptrace(PTRACE_SYSCALL,pid,0,0);waitpid(pid,&status,0);if(WIFEXITED(status)||WIFSIGNALED(status))break;if(WSTOPSIG(status)==(SIGTRAP|0x80)){unsigned long r[18];if(!ptrace(PTRACE_GETREGS,pid,0,r)){unsigned n=counter++%40;history[n][0]=r[7];history[n][1]=r[0];history[n][2]=r[1];history[n][3]=r[2];}}else if(WSTOPSIG(status)!=SIGTRAP&&WSTOPSIG(status)!=SIGSTOP){ptrace(PTRACE_CONT,pid,0,WSTOPSIG(status));waitpid(pid,&status,0);break;}}for(unsigned i=counter>40?counter-40:0;i<counter;i++){unsigned long *h=history[i%40];printf("syscall=%lu r0=%ld r1=%lu r2=%lu\n",h[0],(long)h[1],h[2],h[3]);}printf("exit=%d signal=%d\n",WIFEXITED(status)?WEXITSTATUS(status):-1,WIFSIGNALED(status)?WTERMSIG(status):0);return 0;}
