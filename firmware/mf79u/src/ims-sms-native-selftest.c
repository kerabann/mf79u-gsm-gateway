#define _GNU_SOURCE
#include <assert.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#define MF79U_SMS_FORMAT_FIXTURE 1
#define MF79U_SMS_IMS_SOCKET "/tmp/mf79u-sms-native-test.sock"
#define MF79U_SMS_IMS_SPOOL "/tmp/mf79u-sms-native-test-spool"
enum {VOICE_VOWIFI=3};
static int effective_mode=3,requested_mode=3,ims_wifi=1,ims=10,registered=1,request=1,tunnel=1;
static time_t now=100;
static unsigned sent,at_port;
static char at[500];
static time_t monotonic(void){return now;}
static int vowifi_tunnel_ready(void){return tunnel;}
static int send_ims(uint16_t cmd,const char *p,size_t n,unsigned port){assert(cmd==0x1509 && n<sizeof(at));memset(at,0,sizeof(at));memcpy(at,p,n);at_port=port;sent++;return 0;}
static void event(const char *p){(void)p;}
#include "ims-sms-native.h"
static int connection(unsigned char op,const char *payload){int fd=socket(AF_UNIX,SOCK_SEQPACKET,0);assert(fd>=0);struct sockaddr_un a={.sun_family=AF_UNIX};strcpy(a.sun_path,MF79U_SMS_IMS_SOCKET);assert(!connect(fd,(struct sockaddr*)&a,sizeof(a)));char p[410]={'M','S','I','1',op};size_t n=strlen(payload);memcpy(p+5,payload,n);assert(send(fd,p,n+5,0)==(ssize_t)n+5);sms_poll();return fd;}
static void answer(int fd,unsigned char code){char p[512];ssize_t n=recv(fd,p,sizeof(p),0);assert(n>=5 && !memcmp(p,"MSI1",4) && p[4]==code);close(fd);}
int main(void){
 assert(!sms_listen());struct stat st;assert(!stat(MF79U_SMS_IMS_SOCKET,&st) && (st.st_mode&0777)==0600);
 sms_configure();assert(sms_configured && sms_stage==0);
 int status=connection(1,"");char metadata[400]={0};assert(recv(status,metadata,sizeof(metadata)-1,0)>5);close(status);assert(strstr(metadata+5,"\"ready\":true") && strstr(metadata+5,"\"fenced\":false"));
 const char *pdu="00010005812143F5000005E8329BFD06";
 int fd=connection(2,pdu);assert(sms_stage==1 && at_port==4 && !strcmp(at,"AT+CMGS=15\r"));unsigned before=sent;
 answer(connection(2,pdu),3);sms_ims_event("\r\nOK\r\n",4);assert(sms_stage==1 && sent==before);
 sms_ims_event("\r\n> ",1);assert(sms_stage==1);sms_ims_event("\r\n> ",4);assert(sms_stage==2 && sent==before+1 && at[strlen(pdu)]==0x1a);sms_ims_event("\r\n> ",4);assert(sent==before+1);
 sms_ims_event("\r\n+CMGS: 7\r\n\r\nOK\r\n",4);answer(fd,0);assert(!sms_stage && sms_confirmed==1);
 tunnel=0;before=sent;answer(connection(2,pdu),2);assert(sent==before);tunnel=1;
 fd=connection(2,pdu);sms_ims_event("\r\n> ",4);now+=50;sms_poll();answer(fd,7);assert(sms_fenced);before=sent;answer(connection(2,pdu),2);sms_ims_event("\r\n+CMGS: 8\r\n\r\nOK\r\n",4);assert(sms_fenced && sent==before);
 sms_configure();sms_ims_event("\r\nOK\r\n",4);assert(!sms_fenced);
 fd=connection(2,pdu);sms_ims_event("\r\n+CMS ERROR:331\r\n",4);answer(fd,6);assert(!sms_stage);
 const char *deliver="000405912143F500006201112143650005E8329BFD06";
 char indication[450];snprintf(indication,sizeof(indication),"\r\n+CMT: ,21\r\n%s\r\n",deliver);sms_ims_event(indication,1);assert(sms_received==1 && at_port==3 && !strcmp(at,"AT+CNMA=1\r"));
 DIR *d=opendir(MF79U_SMS_IMS_SPOOL);assert(d);struct dirent *e;unsigned files=0;while((e=readdir(d)))if(e->d_name[0]!='.'){char path[512];snprintf(path,sizeof(path),"%s/%s",MF79U_SMS_IMS_SPOOL,e->d_name);assert(!stat(path,&st) && (st.st_mode&0777)==0600);int x=open(path,O_RDONLY);char body[401]={0};assert(read(x,body,400)==(ssize_t)strlen(deliver) && !strcmp(body,deliver));close(x);unlink(path);files++;}closedir(d);assert(files==1);
 assert(!chmod(MF79U_SMS_IMS_SPOOL,0755));sms_ims_event(indication,1);assert(sms_received==1 && !strcmp(at,"AT+CNMA=2\r"));assert(!chmod(MF79U_SMS_IMS_SPOOL,0700));rmdir(MF79U_SMS_IMS_SPOOL);
 fd=connection(2,pdu);sms_reset();answer(fd,7);sms_close();puts("PASS native IMS SMS private channel, RP acknowledgement, durable MT, timeout fencing and no cellular fallback");return 0;
}
