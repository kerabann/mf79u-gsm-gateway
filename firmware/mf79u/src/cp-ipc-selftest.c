/* Synthetic IPC fixtures. Uses two IPC_PRIVATE queues; no stock AT_CTL access. */
#include "cp-ipc.h"
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/msg.h>
#include <sys/wait.h>
#include <unistd.h>
struct fixture {
    int32_t type,dst,src;uint16_t cmd,len;uint32_t magic;
    unsigned char payload[3496];
};
static int one(int scenario,int direct) {
    struct mf79u_cp cp={.tx=msgget(IPC_PRIVATE,IPC_CREAT|0600),
        .rx=msgget(IPC_PRIVATE,IPC_CREAT|0600),.key=0x1132,.request_cmd=direct?0x152e:0x152d};
    if(cp.rx<0 || cp.tx<0)return 1;
    pid_t child=fork();
    if(!child) {
        struct fixture m;
        if(msgrcv(cp.tx,&m,sizeof(m)-4,0,0)<0)_exit(2);
        uint32_t size,timeout;memcpy(&size,m.payload+3488,4);memcpy(&timeout,m.payload+3492,4);
        if(m.cmd!=(direct?0x152e:0x152d) || m.src!=cp.key || m.dst!=0x100f || size!=9 || timeout!=1 ||
           memcmp(m.payload,"AT+CFUN?\r",9))_exit(3);
        m=(struct fixture){.type=1,.src=0x100f,.dst=cp.key,.cmd=0x159b,.len=12,.magic=0x3a3a3a3a};
        if(msgsnd(cp.rx,&m,28,0))_exit(4); // Binary PDP notification precedes text.
        m.cmd=0x152f;
        if(scenario==1)m.magic=0;
        if(scenario==2)m.src=0x100e;
        if(scenario==3)m.len=100;
        else {const char *text=scenario==4?"\r\n+CME ERROR: 4\r\n":"\r\n+CFUN: 1\r\nOK\r\n";
            m.len=(uint16_t)strlen(text);memcpy(m.payload,text,m.len);}
        if(msgsnd(cp.rx,&m,16+(scenario==3?4:m.len),0))_exit(5);
        _exit(0);
    }
    char reply[80];int result=mf79u_cp_query(&cp,"AT+CFUN?",reply,scenario==5?8:sizeof(reply),1);
    int saved=errno,child_status;waitpid(child,&child_status,0);
    msgctl(cp.tx,IPC_RMID,NULL);mf79u_cp_close(&cp);
    if(!WIFEXITED(child_status) || WEXITSTATUS(child_status))return 1;
    if(scenario==0)return result==(int)strlen("\r\n+CFUN: 1\r\nOK\r\n") && strstr(reply,"+CFUN: 1")?0:1;
    if(scenario==4)return result>0 && strstr(reply,"+CME ERROR:")?0:1;
    return result==-1 && saved==(scenario==5?EMSGSIZE:EPROTO)?0:1;
}
static int pdp(int scenario) {
    struct mf79u_cp cp={.tx=msgget(IPC_PRIVATE,IPC_CREAT|0600),
        .rx=msgget(IPC_PRIVATE,IPC_CREAT|0600),.key=0x1132,.request_cmd=0x152d};
    if(cp.rx<0 || cp.tx<0)return 1;
    pid_t child=fork();
    if(!child) {
        struct fixture m;if(msgrcv(cp.tx,&m,sizeof(m)-4,0,0)<0)_exit(2);
        m=(struct fixture){.type=1,.src=0x100f,.dst=cp.key,.cmd=0x159b,.len=12,.magic=0x3a3a3a3a};
        int32_t words[]={scenario==1?1:scenario==3?2:0,scenario==2?4:5,0x7fffffff};
        memcpy(m.payload,words,12);if(msgsnd(cp.rx,&m,28,0))_exit(3);_exit(0);
    }
    char reply[80];int result=mf79u_cp_query(&cp,"AT+ZPDPACT=0,\"IPV4V6\",\"ims\",0,1,1",reply,sizeof(reply),1);
    int saved=errno,child_status;waitpid(child,&child_status,0);
    msgctl(cp.tx,IPC_RMID,NULL);mf79u_cp_close(&cp);
    if(!WIFEXITED(child_status) || WEXITSTATUS(child_status))return 1;
    if(scenario<2)return result>0 && strstr(reply,scenario?"ERROR":"OK")?0:1;
    return result==-1 && saved==EPROTO?0:1;
}
int main(void) {
    for(int route=0;route<2;route++)for(int i=0;i<6;i++)if(one(i,route)){printf("FAIL synthetic CP route=%d fixture=%d\n",route,i);return 1;}
    for(int i=0;i<4;i++)if(pdp(i)){printf("FAIL typed PDP fixture=%d\n",i);return 1;}
    puts("PASS synthetic CP IPC: wire ABI, typed PDP completion, terminal reply, malformed/foreign/oversized frames");
    return 0;
}
