#include <assert.h>
/* Container-only CP/IMS/SIP lifecycle fixture. Never run on the modem. */
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/msg.h>
#include <unistd.h>
#include <poll.h>
#include <sys/socket.h>
#include <netinet/in.h>
struct message {int32_t type,dst,src;uint16_t cmd,len;uint32_t magic;unsigned char payload[3496];};
static int cp_queue=-1;
static void cp_stop(int sig){(void)sig;if(cp_queue>=0)msgctl(cp_queue,IPC_RMID,NULL);_exit(0);}
static int exists(const char *p){return !access(p,F_OK);}
static void ims_send(int q,unsigned cmd,const char *text){
 struct message m={.type=1,.src=0x701e,.dst=0x700f,.cmd=cmd,.len=3496,.magic=0x3a3a3a3a};
 uint32_t len=(uint32_t)strlen(text),port=1;memcpy(m.payload,text,len);memcpy(m.payload+3488,&len,4);memcpy(m.payload+3492,&port,4);
 if(msgsnd(q,&m,sizeof(m)-4,0))exit(5);
}
int main(int argc,char **argv){
 if(!exists("/tmp/MF79U_ISOLATED_FIXTURE"))return 90;
 if(strstr(argv[0],"test-sip")) {
  char line[128];setvbuf(stdout,NULL,_IONBF,0);puts("GATEWAY_LISTENING");
  while(fgets(line,sizeof(line),stdin)) {
   FILE *events=fopen("/tmp/sip-events","a");if(events){fputs(line,events);fclose(events);}
   if(!strncmp(line,"DIAL ",5) || !strcmp(line,"ANSWER\n") || !strcmp(line,"HANGUP\n")){fputs(line,stdout);continue;}
   if(!strcmp(line,"QUIT\n"))break;
   if(!strcmp(line,"READY\n")) {
   puts("GATEWAY_READY");
   if(exists("/tmp/test-call"))puts("DIAL 1234567");
   if(exists("/tmp/guard-test")){puts("DIAL 1234567");puts("ANSWER");}
  }
  if(!strcmp(line,"ENDED\n")){FILE *f=fopen("/tmp/call-ended","w");if(f){fputs("yes",f);fclose(f);}}}
  return 0;
 }
 if(strstr(argv[0],"test-cs")) {
  unsigned epoch=(unsigned)getpid(),sequence=0,call=0;int pcm=-1,announced=0;
  setvbuf(stdout,NULL,_IONBF,0);printf("CS_HELLO %u\nCS_SUSPENDED %u\n",epoch,epoch);
  char line[128];
  for(;;) {
   struct pollfd p={0,POLLIN,0};if(poll(&p,1,50)>0) {
    if(!fgets(line,sizeof(line),stdin))break;
    char action[24];unsigned seen,id;if(sscanf(line,"%23s %u %u",action,&seen,&id)!=3 || seen!=epoch)return 7;
    FILE *f=fopen("/tmp/cs-commands","a");if(f){fprintf(f,"%s %u\n",action,id);fclose(f);}
    if(!strcmp(action,"RESUME")) {
     /* A legacy physical GSM driver rejects a fourth RAT argument. */
     char extra;assert(sscanf(line,"%23s %u %u %c",action,&seen,&id,&extra)==3);
     if(pcm<0) {
      pcm=socket(AF_INET,SOCK_DGRAM,0);struct sockaddr_in addr={.sin_family=AF_INET,.sin_port=htons(46001),.sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
      if(pcm<0 || bind(pcm,(struct sockaddr *)&addr,sizeof(addr))){if(pcm>=0)close(pcm);
     pcm=-1;printf("CS_NOT_READY %u\n",epoch);continue;}
     }
     printf("CS_READY %u\n",epoch);
    } else if(!strcmp(action,"SUSPEND")) {
     if(call)return 8;
     if(pcm>=0)close(pcm);
     pcm=-1;printf("CS_SUSPENDED %u\n",epoch);
    } else if(!strcmp(action,"DIAL")) {
     if(pcm<0 || call || id<=sequence)return 9;
     call=sequence=id;printf("CS_ALERT %u %u\nCS_CONNECTED %u %u\n",epoch,id,epoch,id);
    } else if(!strcmp(action,"ANSWER")) {
     if(id!=call || !call)return 10;
     printf("CS_CONNECTED %u %u\n",epoch,id);
    } else if(!strcmp(action,"HANGUP")) {
     if(id==call){call=0;printf("CS_ENDED %u %u\nCS_CONNECTED %u %u\n",epoch,id,epoch,id);}
    } else if(!strcmp(action,"QUIT"))break;
   }
   if(pcm>=0 && !announced && exists("/tmp/cs-incoming")) {
    announced=1;call=++sequence;printf("CS_INCOMING %u %u anonymous\n",epoch,call);
   }
   if(exists("/tmp/cs-crash"))return 11;
  }
  if(pcm>=0)close(pcm);
  return 0;
 }
 if(strstr(argv[0],"test-ims")) {
  int request=msgget(0x701e,IPC_CREAT|IPC_EXCL|0600),response=msgget(0x700f,0600);if(request<0 || response<0)return 3;
  dprintf(3,"OPERATOR WB/NB factory enabled result=1\n");
  ims_send(response,0x150a,"\r\n+CVMOD: 3\r\n+ZIMSAMRW: 1\r\n");
  int accepted=0,access_gate=0,stage=0;struct message m;
  int non3gpp=exists("/tmp/ims-non3gpp-gated");
  for(;;){
   if(exists("/tmp/ims-crash"))return 4;
   if(!non3gpp && !accepted && exists("/tmp/ims-accept")){ims_send(response,0x150c,"AT+ZIMSSTATE=1");accepted=1;}
   ssize_t n=msgrcv(request,&m,sizeof(m)-4,0,IPC_NOWAIT);
   if(n<0 && errno!=ENOMSG && errno!=EINTR)return 6;
   if(non3gpp && n>=0 && m.cmd==0x150b) {
    if(!strncmp((char *)m.payload,"\r\n+CEREG: 1\r\n",13))access_gate|=1;
    if(!strncmp((char *)m.payload,"\r\n^MODE: 17,7\r\n",15))access_gate|=2;
    if(!strncmp((char *)m.payload,"\r\n+CIREPI: 1\r\n",14))access_gate|=4;
    if(stage==1 && strstr((char *)m.payload,"+CEREG: 2,1")) {
     stage=2;ims_send(response,0x150c,"AT+CGREG?");
    } else if(stage==2 && strstr((char *)m.payload,"+CGREG: 2,1")) {
     stage=3;ims_send(response,0x150c,"AT+ZPDPACT=0,\"IPV4V6\",\"ims\",0,1,1");
    } else if(stage==3 && strstr((char *)m.payload,"+ZPDPACT: 5,\"IP\",\"10.77.0.2\"")) {
     stage=4;ims_send(response,0x150c,"AT+ZIMSSTATE=1");accepted=1;
     FILE *f=fopen("/tmp/non3gpp-admitted","w");if(f){fputs("authenticated_bearer",f);fclose(f);}
    }
   }
   if(non3gpp && access_gate==7 && !stage) {
    stage=1;ims_send(response,0x150c,"AT+CEREG?");
   }
   if(n>=0 && m.cmd==0x1509 &&
      (!memcmp(m.payload,"ATA\r",4) || !memcmp(m.payload,"ATD",3))) {
    FILE *f=fopen("/tmp/charged-command","w");if(f){fputs("forbidden",f);fclose(f);}
   }
   usleep(10000);
  }
 }
 if(argc!=2 || strcmp(argv[1],"cp"))return 2;
 int q=msgget(0x100f,IPC_CREAT|IPC_EXCL|0600);if(q<0)return 1;
 cp_queue=q;signal(SIGTERM,cp_stop);signal(SIGINT,cp_stop);
 puts("FIXTURE_CP_READY");fflush(stdout);
 int profile=27,fun=1,voice=0,open_voice=0;
 for(;;){
  struct message m;if(msgrcv(q,&m,sizeof(m)-4,0,0)<0)return 7;
  int destination=m.src,replyq=msgget(destination,0600);if(replyq<0)return 8;
  char reply[256];char command[3497];memcpy(command,m.payload,3496);command[3496]=0;command[strcspn(command,"\r\n")]=0;
  int lte=profile==27 && fun && exists("/tmp/radio-lte"),short_reply=exists("/tmp/radio-search"),non3gpp=exists("/tmp/ims-non3gpp-gated");const char *text="\r\nOK\r\n";
  if(!strncmp(command,"AT+CEREG?",9))text=exists("/tmp/cp-status-error")?"\r\nERROR\r\n":non3gpp?"\r\n+CEREG: 2,4\r\nOK\r\n":lte?"\r\n+CEREG: 2,5,\"00D3\",\"000052C4\",7\r\nOK\r\n":"\r\n+CEREG: 2,2\r\nOK\r\n";
  else if(!strncmp(command,"AT+CREG?",8))text=non3gpp?"\r\n+CREG: 2,4\r\nOK\r\n":short_reply?"\r\n+CREG: 2,2\r\nOK\r\n":"\r\n+CREG: 2,5\r\nOK\r\n";
  else if(!strncmp(command,"AT^SYSINFO",10))text=short_reply?"\r\n^SYSINFO: 0,0,0,0,1\r\nOK\r\n":lte?"\r\n^SYSINFO: 2,2,1,5,1,,7\r\nOK\r\n":"\r\n^SYSINFO: 2,3,1,3,1,,3\r\nOK\r\n";
  else if(!strncmp(command,"AT+CIREP?",9))text=lte?"\r\n+CIREP: 0,1\r\nOK\r\n":"\r\n+CIREP: 0,0\r\nOK\r\n";
  else if(!strcmp(command,"AT+CFUN=0"))fun=0;
  else if(!strcmp(command,"AT+CFUN=1"))fun=1;
  else if(!strcmp(command,"AT+CFUN?")){snprintf(reply,sizeof(reply),"\r\n+CFUN: %d\r\nOK\r\n",fun);text=reply;}
  else if(!strcmp(command,"AT^SYSCONFIG=14,0,1,2"))profile=14;
  else if(!strcmp(command,"AT^SYSCONFIG=13,0,1,2"))profile=13;
  else if(!strcmp(command,"AT^SYSCONFIG=27,0,1,2"))profile=27;
  else if(!strcmp(command,"AT^SYSCONFIG?")){snprintf(reply,sizeof(reply),"\r\n^SYSCONFIG: %d,0,1,2\r\nOK\r\n",profile);text=reply;}
  else if(!strcmp(command,"AT+ZSET=\"VOICE_SUPPORT\",1"))voice=1;
  else if(!strcmp(command,"AT+ZSET=\"VOICE_SUPPORT\",0"))voice=0;
  else if(!strcmp(command,"AT+ZSET=\"OPEN_VOICE_FLAG\",1"))open_voice=1;
  else if(!strcmp(command,"AT+ZSET=\"OPEN_VOICE_FLAG\",0"))open_voice=0;
  else if(!strcmp(command,"AT+ZSET=\"VOICE_SUPPORT\"")){snprintf(reply,sizeof(reply),"\r\n+ZSET: \"VOICE_SUPPORT\",%d\r\nOK\r\n",voice);text=reply;}
  else if(!strcmp(command,"AT+ZSET=\"OPEN_VOICE_FLAG\"")){snprintf(reply,sizeof(reply),"\r\n+ZSET: \"OPEN_VOICE_FLAG\",%d\r\nOK\r\n",open_voice);text=reply;}
  m=(struct message){.type=1,.src=0x100f,.dst=destination,.cmd=0x152f,.len=(uint16_t)strlen(text),.magic=0x3a3a3a3a};memcpy(m.payload,text,m.len);
  if(msgsnd(replyq,&m,16+m.len,0))return 9;
 }
}
