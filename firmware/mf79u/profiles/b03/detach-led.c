/* One-shot installation helper, not a firmware runtime dependency. */
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <sys/wait.h>
int main(void) {
    pid_t first=fork(); if(first<0)return 1;
    if(first>0){int status;if(waitpid(first,&status,0)<0)return 1;return WIFEXITED(status)?WEXITSTATUS(status):1;}
    if(setsid()<0)_exit(1);
    signal(SIGHUP,SIG_IGN);
    pid_t second=fork();if(second<0)_exit(1);if(second>0)_exit(0);
    if(chdir("/")<0)_exit(1);
    int fd=open("/dev/null",O_RDWR);if(fd<0)_exit(1);
    for(int i=0;i<3;i++)if(dup2(fd,i)<0)_exit(1);
    if(fd>2)close(fd);
    execl("/mnt/userdata/mf79u/.mf79u-net-led","mf79u-net-led",(char *)0);
    _exit(1);
}
