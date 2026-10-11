/* Allowlisted local AT_CTL helper. Separate owned CP reply queue, no response logging. */
#include "cp-ipc.h"
#include <ctype.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static struct mf79u_cp cp;
static void cleanup(int signum) { mf79u_cp_close(&cp); _exit(128+signum); }
static int valid(const char *s) {
    if(strlen(s)!=15)return 0;
    int sum=0;
    for(int i=0;i<15;i++){if(!isdigit((unsigned char)s[i]))return 0;int n=s[i]-'0';if(i%2){n*=2;if(n>9)n-=9;}sum+=n;}
    return sum%10==0;
}
static int read_imei(char *out) {
    char reply[4096];int n=mf79u_cp_query(&cp,"AT+READIMEI?",reply,sizeof(reply),5);
    if(n<0 || !strstr(reply,"\r\nOK\r\n"))return -1;
    char *found=NULL;
    for(char *p=reply;*p;){if(isdigit((unsigned char)*p)){size_t len=strspn(p,"0123456789");if(len==15){if(found)return -1;found=p;}p+=len;}else p++;}
    if(!found)return -1;
    memcpy(out,found,15);out[15]=0;memset(reply,0,sizeof(reply));return 0;
}
int main(int argc,char **argv) {
    if(argc!=2 || (strcmp(argv[1],"read") && strcmp(argv[1],"write")))return 2;
    char wanted[32]={0},before[16]={0},after[16]={0};int write=!strcmp(argv[1],"write");
    if(write){if(!fgets(wanted,sizeof(wanted),stdin))return 2;wanted[strcspn(wanted,"\r\n")]=0;if(!valid(wanted))return 2;}
    if(mf79u_cp_open(&cp))return 3;
    signal(SIGTERM,cleanup);signal(SIGINT,cleanup);signal(SIGALRM,cleanup);alarm(20);
    int result=3;
    if(!read_imei(before)) {
        if(!write){puts(before);result=0;}
        else if(!strcmp(before,wanted)){puts("VERIFIED");result=0;}
        else {
            char command[48],reply[4096];snprintf(command,sizeof(command),"AT+MODIMEI=%s",wanted);
            int n=mf79u_cp_query(&cp,command,reply,sizeof(reply),5);memset(command,0,sizeof(command));
            if(n>=0 && strstr(reply,"\r\nOK\r\n") && !read_imei(after) && !strcmp(wanted,after)){puts("VERIFIED");result=0;}
            else result=4; /* Never automatically retry an uncertain NV write. */
            memset(reply,0,sizeof(reply));
        }
    }
    mf79u_cp_close(&cp);memset(wanted,0,sizeof(wanted));memset(before,0,sizeof(before));memset(after,0,sizeof(after));return result;
}
