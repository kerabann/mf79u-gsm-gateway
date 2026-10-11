#include "net-led-policy.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
/* The B03 uClibc loader exports sscanf, not glibc's __isoc99_sscanf alias. */
extern int mf79u_scanf(const char *,const char *,...) __asm__("sscanf");

void mf79u_led_clear(struct mf79u_led_calls *c){
    for(unsigned i=0;i<8;i++){c->state[i]=-1;c->direction[i]=0;}
    c->anonymous_ring=0;
}
int mf79u_led_parse(const void *text,size_t size,struct mf79u_led_event *event){
    if(!text || !size || size>3488)return 0;
    char line[256];size_t n=size<sizeof(line)-1?size:sizeof(line)-1;
    memcpy(line,text,n);line[n]=0;
    char *s=line;while(*s=='\r' || *s=='\n')s++;
    struct mf79u_led_event e={.magic=MF79U_LED_MAGIC,.id=1,.direction=0,.state=-1};
    if(!strncmp(s,"^DSCI:",6)){
        if(mf79u_scanf(s+6," %d,%d,%d",&e.id,&e.direction,&e.state)!=3)return 0;
    }else if(!strncmp(s,"^ORIG:",6)){
        if(mf79u_scanf(s+6," %d",&e.id)!=1)return 0;
        e.state=2;
    }else if(!strncmp(s,"^CONN:",6)){
        if(mf79u_scanf(s+6," %d",&e.id)!=1)return 0;
        e.state=0;
    }else if(!strncmp(s,"^CEND:",6)){
        if(mf79u_scanf(s+6," %d",&e.id)!=1)return 0;
        e.state=6;
    }else if(!strncmp(s,"RING\r",5) || !strcmp(s,"RING") || !strncmp(s,"+CRING: VOICE",13)){
        /* RING has no call index. Never invent slot 1: DSCI may use slot 6. */
        e.id=0;e.direction=1;e.state=4;
    }else return 0;
    if(e.id<0 || e.id>8 || e.direction<0 || e.direction>1 || e.state<0 || e.state>6 ||
       (e.id==0 && (e.direction!=1 || e.state!=4)))return 0;
    *event=e;return 1;
}
int mf79u_led_apply(struct mf79u_led_calls *c,const struct mf79u_led_event *e){
    if(e->magic!=MF79U_LED_MAGIC || e->id<0 || e->id>8 || e->direction<0 || e->direction>1 || e->state<0 || e->state>6)return -1;
    if(e->id==0){
        if(e->direction!=1 || e->state!=4)return -1;
        for(unsigned i=0;i<8;i++)if(c->direction[i]==1 && (c->state[i]==4 || c->state[i]==5))return 0;
        c->anonymous_ring=1;return 0;
    }
    c->anonymous_ring=0;
    c->state[e->id-1]=e->state==6?-1:e->state;c->direction[e->id-1]=e->direction;return 0;
}
unsigned mf79u_led_color(int registered,const struct mf79u_led_calls *c){
    /* Every live call state, including ringing and held, is green. */
    if(c->anonymous_ring)return 2;
    for(unsigned i=0;i<8;i++)
        if(c->state[i]>=0 && c->state[i]<=5)return 2;
    return registered?4:1; /* RGB mask: red=1, green=2, blue=4. */
}
unsigned mf79u_led_service_color(int registered,int ims_ready,const struct mf79u_led_calls *c){
    unsigned color=mf79u_led_color(registered,c);
    /* Preserve no-service/call priorities. Yellow is registered GSM/SMS-only idle. */
    return color==4 && !ims_ready?3:color;
}

unsigned mf79u_led_access_color(int registered,int ims_ready,int wifi_ready,const struct mf79u_led_calls *c){
    unsigned color=mf79u_led_service_color(registered,ims_ready,c);
    return wifi_ready && color!=2?5:color;
}
unsigned mf79u_led_mode_color(int registered,int ims_ready,int wifi_ready,int vowifi_only,const struct mf79u_led_calls *c){
    unsigned color=mf79u_led_access_color(registered,ims_ready,wifi_ready,c);
    /* Cellular SMS registration does not admit voice in VoWiFi Only. */
    return vowifi_only && color!=2?(wifi_ready?5:1):color;
}
int mf79u_led_registration(const char *network,const char *main_state){
    if(strcmp(main_state,"modem_init_complete"))return 0;
    const char *known[]={"LTE","LTE Advanced","LTE_CA","FDD LTE","TDD LTE","GSM","GPRS","EDGE","UMTS","WCDMA","HSDPA","HSUPA","HSPA","HSPA+","TD-SCDMA"};
    for(unsigned i=0;i<sizeof(known)/sizeof(known[0]);i++)if(!strcmp(network,known[i]))return 1;
    return 0; /* NO_SERVICE, LIMITED_SERVICE, empty and unknown fail closed. */
}
void mf79u_led_notify(const void *text,size_t size){
    int saved=errno;
    if(!text || !size || size>3488)return;
    int fd=socket(AF_UNIX,SOCK_DGRAM,0);
    if(fd>=0){
        struct sockaddr_un peer={.sun_family=AF_UNIX};strcpy(peer.sun_path,MF79U_LED_SOCKET);
        const char *p=text;size_t start=0;
        for(size_t i=0;i<=size;i++){
            if(i<size && p[i]!='\r' && p[i]!='\n')continue;
            struct mf79u_led_event e;
            if(i>start && mf79u_led_parse(p+start,i-start,&e))
                (void)sendto(fd,&e,sizeof(e),MSG_DONTWAIT,(struct sockaddr*)&peer,sizeof(peer));
            start=i+1;
        }
        close(fd);
    }
    errno=saved;
}
int mf79u_led_selftest(void){
    struct mf79u_led_calls c;struct mf79u_led_event e;
    mf79u_led_clear(&c);
    if(mf79u_led_color(0,&c)!=1 || mf79u_led_color(1,&c)!=4)return 1;
    if(mf79u_led_service_color(1,0,&c)!=3 || mf79u_led_service_color(1,1,&c)!=4 ||
       mf79u_led_service_color(0,0,&c)!=1 || mf79u_led_service_color(0,1,&c)!=1)return 13;
    if(mf79u_led_access_color(0,1,1,&c)!=5 || mf79u_led_access_color(1,1,1,&c)!=5 || mf79u_led_access_color(1,1,0,&c)!=4)return 30;
    if(mf79u_led_mode_color(1,0,0,1,&c)!=1 || mf79u_led_mode_color(1,1,0,1,&c)!=1 || mf79u_led_mode_color(0,1,1,1,&c)!=5 || mf79u_led_mode_color(1,0,0,0,&c)!=3)return 32;
    const char *events[]={"\r\n^ORIG: 1,0\r\n","\r\n^DSCI: 1,0,3,0,0,\"synthetic\",129\r\n","\r\n^CONN: 1,0\r\n","\r\n^DSCI: 2,1,4,0,0,\"synthetic\",129\r\n","\r\n^CONN: 2,0\r\n","\r\n^CEND: 1,0,101\r\n","\r\n^CEND: 2,0,101\r\n"};
    const unsigned colors[]={2,2,2,2,2,2,4};
    for(unsigned i=0;i<sizeof(colors)/sizeof(colors[0]);i++){
        if(!mf79u_led_parse(events[i],strlen(events[i]),&e) || mf79u_led_apply(&c,&e) || mf79u_led_color(1,&c)!=colors[i])return 2+(int)i;
        if(mf79u_led_color(0,&c)!=(colors[i]==4?1:2))return 10;
        if(mf79u_led_access_color(0,1,1,&c)!=(colors[i]==4?5:2))return 31;
        if(mf79u_led_mode_color(1,0,0,1,&c)!=(colors[i]==4?1:2))return 33;
        if(mf79u_led_service_color(1,0,&c)!=(colors[i]==4?3:colors[i]) ||
           mf79u_led_service_color(1,1,&c)!=colors[i])return 14;
    }
    if(mf79u_led_parse("^DSCI: 9,1,4",13,&e) || mf79u_led_parse("ATD123;",7,&e) || mf79u_led_parse("OK",2,&e))return 11;
    if(!mf79u_led_registration("LTE","modem_init_complete") || !mf79u_led_registration("GSM","modem_init_complete") || mf79u_led_registration("LIMITED_SERVICE","modem_init_complete") || mf79u_led_registration("LTE","modem_waitpin"))return 12;
    /* Regression: RING plus indexed DSCI must not leave a phantom call 1. */
    mf79u_led_clear(&c);
    const char *incoming[]={"RING","^DSCI: 6,1,4","RING","^DSCI: 6,1,6","^CEND: 6,0,101","RING","^CONN: 7,0","^CEND: 7,0,101"};
    const unsigned incoming_colors[]={2,2,2,4,4,2,2,4};
    for(unsigned i=0;i<sizeof(incoming_colors)/sizeof(incoming_colors[0]);i++)
        if(!mf79u_led_parse(incoming[i],strlen(incoming[i]),&e) || mf79u_led_apply(&c,&e) || mf79u_led_color(1,&c)!=incoming_colors[i])return 20+(int)i;
    return 0;
}
