#ifndef MF79U_VOWIFI_RUNTIME_H
#define MF79U_VOWIFI_RUNTIME_H
#include <arpa/inet.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>
#include "vowifi-pcscf.h"
static struct vowifi_pcscf_choices vowifi_choices;
static char vowifi_preferred[INET_ADDRSTRLEN];
static pid_t vowifi_pid=-1;
static time_t vowifi_deadline,vowifi_retry;
static unsigned vowifi_failures;
static void vowifi_schedule_retry(void){
 time_t now=monotonic();if(vowifi_retry>now)return;
 unsigned seconds=vowifi_failures<4?(5u<<vowifi_failures):60u;
 if(vowifi_failures<4)vowifi_failures++;
 vowifi_retry=now+seconds;
}
static int ims_wifi;
static time_t vowifi_wifi_seen;
static char vowifi_local[INET_ADDRSTRLEN],vowifi_pcscf[INET_ADDRSTRLEN];
static int vowifi_address(const char *name,char *out){
 char path[128],text[64];snprintf(path,sizeof(path),"/dev/mf79u/vowifi/%s",name);FILE *f=fopen(path,"r");if(!f)return 0;
 int ok=fgets(text,sizeof(text),f)!=NULL;fclose(f);if(!ok)return 0;text[strcspn(text,"\r\n")]=0;
 struct in_addr addr;if(inet_pton(AF_INET,text,&addr)!=1 || !addr.s_addr)return 0;strcpy(out,text);return 1;
}
static int vowifi_tunnel_ready(void){
 if(vowifi_pid<2 || kill(vowifi_pid,0) || !vowifi_address("address",vowifi_local))return 0;
 if(!vowifi_choices.count){
  if(!vowifi_preferred[0]){FILE *f=fopen("/dev/mf79u/vowifi-pcscf-preferred","r");if(f){fgets(vowifi_preferred,sizeof(vowifi_preferred),f);fclose(f);vowifi_preferred[strcspn(vowifi_preferred,"\r\n")]=0;}}
  if(!vowifi_pcscf_load(&vowifi_choices,"/dev/mf79u/vowifi/pcscf-list",vowifi_preferred))return vowifi_address("mf79u-pcscf",vowifi_pcscf);
 }
 strcpy(vowifi_pcscf,vowifi_choices.address[vowifi_choices.current]);return 1;
}
static void vowifi_pcscf_remember(void){
 strcpy(vowifi_preferred,vowifi_pcscf);int f=open("/dev/mf79u/vowifi-pcscf-preferred",O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);if(f>=0){write(f,vowifi_preferred,strlen(vowifi_preferred));close(f);}
}
static int vowifi_wifi_ready(int active_call){
 if(effective_usb){
  FILE *f=fopen("/sys/class/net/usblan0/carrier","r");int carrier=0;if(f){carrier=fgetc(f)=='1';fclose(f);}
  return carrier && !access("/dev/mf79u/vowifi-usb-ready",R_OK);
 }

 /* Query the owned supplicant with a bounded wait; never stall CP/calls on
  * a stale control socket, and never treat an old DHCP lease as association. */
 char text[1024];int fd=socket(AF_UNIX,SOCK_DGRAM,0);if(fd<0)return 0;
 struct sockaddr_un local={.sun_family=AF_UNIX},peer={.sun_family=AF_UNIX};
 snprintf(local.sun_path,sizeof(local.sun_path),"/dev/mf79u/vowifi-wpa.%ld",(long)getpid());
 strcpy(peer.sun_path,"/dev/mf79u/wpa/wlan0");unlink(local.sun_path);
 struct timeval timeout=active_call?(struct timeval){.tv_usec=250000}:(struct timeval){.tv_sec=1};ssize_t n=-1;
 if(!setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout)) &&
    !bind(fd,(void*)&local,sizeof(local)) && !connect(fd,(void*)&peer,sizeof(peer)) &&
    send(fd,"STATUS",6,0)==6)n=recv(fd,text,sizeof(text)-1,0);
 if(getenv("MF79U_WIFI_DIAG") && !access("/dev/mf79u/vowifi/diagnostic-enabled",F_OK))printf("WIFI_QUERY bytes=%ld errno=%d\n",(long)n,n<0?errno:0);
 close(fd);unlink(local.sun_path);
 if(n<0)return vowifi_wifi_seen>0 && monotonic()-vowifi_wifi_seen<=30;
 text[n]=0;int ready=strstr(text,"wpa_state=COMPLETED") && strstr(text,"ip_address=");
 if(getenv("MF79U_WIFI_DIAG") && !access("/dev/mf79u/vowifi/diagnostic-enabled",F_OK))printf("WIFI_QUERY completed=%d address=%d\n",!!strstr(text,"wpa_state=COMPLETED"),!!strstr(text,"ip_address="));
 if(ready){
  const char *b=strstr(text,"bssid=");char node[13];unsigned j=0;
  if(b && (b==text || b[-1]=='\n')){b+=6;for(unsigned i=0;i<17 && b[i];i++){if(i%3==2){if(b[i]!=':')break;}else{char c=b[i];if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F')))break;if(j<12)node[j++]=c;}}}
  if(j==12){node[12]=0;int out=open("/dev/mf79u/wifi-node-id.next",O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);if(out>=0){if(write(out,node,12)==12)rename("/dev/mf79u/wifi-node-id.next","/dev/mf79u/wifi-node-id");close(out);}}
  vowifi_wifi_seen=monotonic();
 }else{vowifi_wifi_seen=0;unlink("/dev/mf79u/wifi-node-id");}
 return ready;
}
static int vowifi_start(void){
 if(vowifi_pid>0)return 0;
 memset(&vowifi_choices,0,sizeof(vowifi_choices));unlink("/dev/mf79u/vowifi/pcscf-list");
 unlink("/dev/mf79u/vowifi/address");unlink("/dev/mf79u/vowifi/mf79u-pcscf");
 pid_t p=fork();if(!p){setenv("MF79U_VOWIFI_INTERFACE",effective_usb?"bridge0":"wlan0",1);setsid();int fd=open("/dev/null",O_RDWR);if(fd<0)_exit(126);dup2(fd,0);dup2(fd,1);dup2(fd,2);for(int i=3;i<256;i++)close(i);execl("/mnt/userdata/mf79u/tools/busybox","busybox","sh","/mnt/userdata/mf79u/start-vowifi.sh",(char*)NULL);_exit(127);}if(p<0)return -1;vowifi_pid=p;vowifi_deadline=monotonic()+120;return 0;
}
static void vowifi_stop(void){
 if(vowifi_pid>1){pid_t group=vowifi_pid;kill(-group,SIGTERM);for(int i=0;i<100;i++){if(waitpid(vowifi_pid,NULL,WNOHANG)==vowifi_pid){vowifi_pid=-1;break;}usleep(100000);}if(vowifi_pid>1){kill(-vowifi_pid,SIGKILL);waitpid(vowifi_pid,NULL,0);vowifi_pid=-1;}kill(-group,SIGKILL);}
 pid_t cleanup=fork();if(!cleanup){execl("/mnt/userdata/mf79u/tools/busybox","busybox","sh","/mnt/userdata/mf79u/start-vowifi.sh","--cleanup-only",(char*)NULL);_exit(127);}if(cleanup>0){int done=0;for(int i=0;i<20;i++){if(waitpid(cleanup,NULL,WNOHANG)==cleanup){done=1;break;}usleep(100000);}if(!done){kill(cleanup,SIGKILL);waitpid(cleanup,NULL,0);}}
 unlink("/dev/mf79u/vowifi/address");unlink("/dev/mf79u/vowifi/mf79u-pcscf");memset(vowifi_local,0,sizeof(vowifi_local));memset(vowifi_pcscf,0,sizeof(vowifi_pcscf));
}
static int vowifi_bearer(const char *command,char *reply,size_t size){
 if(!vowifi_tunnel_ready())return -1;
 if(!strcmp(command,"AT+ZPDPACT=0,\"IPV4V6\",\"ims\",0,1,1"))return snprintf(reply,size,"\r\n+ZPDPACT: 5,\"IP\",\"%s\",\"0.0.0.0\",\"0.0.0.0\",\"0.0.0.0\"\r\nOK\r\n",vowifi_local);
 if(!strcmp(command,"AT+CGCONTRDP=5"))return snprintf(reply,size,"\r\n+CGCONTRDP: 5,6,\"ims\",\"%s.255.255.255.255\",,\"0.0.0.0\",\"0.0.0.0\",\"%s\"\r\nOK\r\n",vowifi_local,vowifi_pcscf);
 if(!strcmp(command,"AT+ZPDPDEACT=5"))return snprintf(reply,size,"\r\nOK\r\n");
 return -1;
}
#endif
