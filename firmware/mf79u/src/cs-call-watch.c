/* B03 passive CCAPP receiver. No AT sender, dial, answer or media activation.
 * libatext.so atCcapp_RecvDsciInd 0x818c -> 0x158d, dst 0x1023,
 * 64-byte payload: u32 id/direction/state/type, followed by caller bytes.
 * atCcapp_RecvZvoicechnlInd 0x7b5c -> 0x1590, 4 x u32.
 * Never consume a pre-existing queue; never print/store caller bytes. */
#include "net-led-policy.h"
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/msg.h>
#include <time.h>
#include <unistd.h>
struct message {
    int32_t type,dst,src;
    uint16_t cmd,len;
    uint32_t magic;
    unsigned char payload[3496];
};
static volatile sig_atomic_t stopping;
static void stop(int sig){(void)sig;stopping=1;}
static int decode(const struct message *m,ssize_t n,struct mf79u_led_event *e){
    if(n!=80 || m->magic!=0x3a3a3a3a || m->dst!=0x1023 ||
       m->src!=0x100f || m->cmd!=0x158d || m->len!=64)return 0;
    uint32_t fields[4];memcpy(fields,m->payload,sizeof(fields));
    if(fields[0]<1 || fields[0]>8 || fields[1]>1 || fields[2]>6)return 0;
    *e=(struct mf79u_led_event){MF79U_LED_MAGIC,(int)fields[0],(int)fields[1],(int)fields[2]};
    return 1;
}
int main(int argc,char **argv){
    if(argc==2 && !strcmp(argv[1],"--selftest")){
        struct message m={.dst=0x1023,.src=0x100f,.cmd=0x158d,.len=64,.magic=0x3a3a3a3a};
        uint32_t fields[]={6,1,4,0};memcpy(m.payload,fields,sizeof(fields));
        struct mf79u_led_event e;
        if(!decode(&m,80,&e) || e.id!=6 || e.direction!=1 || e.state!=4)return 1;
        if(decode(&m,79,&e))return 1;
        m.len=63;if(decode(&m,80,&e))return 1;m.len=64;
        fields[0]=9;memcpy(m.payload,fields,sizeof(fields));if(decode(&m,80,&e))return 1;
        fields[0]=1;fields[2]=7;memcpy(m.payload,fields,sizeof(fields));if(decode(&m,80,&e))return 1;
        puts("PASS CS DSCI framing, indexed incoming, malformed/range rejection");return 0;
    }
    if(argc!=2)return 2;
    char *end;long seconds=strtol(argv[1],&end,10);
    if(*end || seconds<1 || seconds>1800)return 2;
    if(access("/mnt/userdata/mf79u/native-ring-only",F_OK)){
        fputs("Requires persistent ring-only guard\n",stderr);return 1;
    }
    int queue=msgget(0x1023,IPC_CREAT|IPC_EXCL|0600);
    if(queue<0){perror("Exclusive CCAPP queue");return 1;}
    signal(SIGTERM,stop);signal(SIGINT,stop);setvbuf(stdout,NULL,_IONBF,0);
    puts("CS_WATCH_READY passive=1 dial=0 answer=0 caller_logging=0");
    time_t deadline=time(NULL)+seconds;unsigned incoming=0,ended=0,connected=0,channels=0;
    int result=0;
    while(!stopping && time(NULL)<deadline){
        struct message m;ssize_t n=msgrcv(queue,&m,sizeof(m)-sizeof(int32_t),0,IPC_NOWAIT);
        if(n<0){if(errno!=ENOMSG && errno!=EINTR){result=1;break;}usleep(50000);continue;}
        struct mf79u_led_event e;
        if(decode(&m,n,&e)){
            printf("CS_CALL id=%d direction=%d state=%d\n",e.id,e.direction,e.state);
            if(e.direction==1 && (e.state==4 || e.state==5))incoming++;
            if(e.state==6)ended++;
            if(e.state==0)connected++;
            char text[64];int len=snprintf(text,sizeof(text),"^DSCI: %d,%d,%d",e.id,e.direction,e.state);
            mf79u_led_notify(text,(size_t)len);
        }else if(n==32 && m.magic==0x3a3a3a3a && m.dst==0x1023 && m.src==0x100f && m.cmd==0x1590 && m.len==16){
            uint32_t f[4];memcpy(f,m.payload,sizeof(f));
            printf("CS_CHANNEL op=%u active=%u codec=%u path=%u\n",f[0],f[1],f[2],f[3]);channels++;
        }else printf("CS_OTHER cmd=0x%04x length=%u bytes=%ld\n",m.cmd,m.len,(long)n);
        memset(&m,0,sizeof(m));
    }
    if(msgctl(queue,IPC_RMID,NULL))result=1;
    printf("CS_WATCH_DONE incoming=%u ended=%u connected=%u channels=%u\n",incoming,ended,connected,channels);
    return result;
}
