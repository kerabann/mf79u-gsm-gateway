/* Read USIM identity/EF_AD into RAM; generate protected ePDG client files.
 * Identifier and authentication material are never printed. */
#define _GNU_SOURCE
#include "cp-ipc.h"
#include <arpa/inet.h>
#include <ctype.h>
#include <fcntl.h>
#include <net/if.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>
#define DIR "/dev/mf79u/vowifi"
static void wipe(void *p,size_t n){volatile unsigned char *s=p;while(n--)*s++=0;}
static FILE *file(const char *name){char p[256];snprintf(p,sizeof(p),DIR "/%s",name);int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);return fd<0?NULL:fdopen(fd,"w");}
int main(void){
 const char *uplink=getenv("MF79U_VOWIFI_INTERFACE");if(!uplink)uplink="wlan0";if(strcmp(uplink,"wlan0") && strcmp(uplink,"bridge0"))return 1;
 umask(0077);if(mkdir(DIR,0700) && access(DIR,W_OK))return 1;
 struct mf79u_cp cp;char reply[1024],identity[17]={0},ad[16]={0};int result=1,mnc=0;
 if(mf79u_cp_open(&cp))return 1;
 if(mf79u_cp_query(&cp,"AT+CIMI",reply,sizeof(reply),6)>0 && strstr(reply,"\r\nOK\r\n")){
  for(char *p=reply;*p;p++)if(isdigit((unsigned char)*p)) {size_t n=strspn(p,"0123456789");if(n>=14 && n<=16){memcpy(identity,p,n);break;}p+=n-1;}
 }
 if(mf79u_cp_query(&cp,"AT+CRSM=176,28589,0,0,4",reply,sizeof(reply),6)>0){char *p=strstr(reply,"+CRSM:");unsigned a,b;if(p && (sscanf(p,"+CRSM: %u,%u,%15[0-9a-fA-F]",&a,&b,ad)==3 || sscanf(p,"+CRSM: %u,%u,\"%15[0-9a-fA-F]",&a,&b,ad)==3) && a==144 && b==0 && strlen(ad)==8){int n=ad[7]-'0';if(n==2 || n==3)mnc=n;}}
 mf79u_cp_close(&cp);wipe(reply,sizeof(reply));printf("VOWIFI_SIM_IDENTITY available=%d mnc_length=%d\n",!!*identity,mnc);if(!*identity || !mnc)goto done;
 char domain[160],realm[120],nai[180];snprintf(realm,sizeof(realm),"wlan.mnc%.*s.mcc%.3s.3gppnetwork.org",mnc,identity+3,identity);
 /* 3GPP realm/domain MNC is padded to three decimal digits. */
 char mn[4];snprintf(mn,sizeof(mn),"%03u",(unsigned)strtoul(strndupa(identity+3,(size_t)mnc),NULL,10));
 snprintf(realm,sizeof(realm),"wlan.mnc%s.mcc%.3s.3gppnetwork.org",mn,identity);
 snprintf(domain,sizeof(domain),"epdg.epc.mnc%s.mcc%.3s.pub.3gppnetwork.org",mn,identity);
 snprintf(nai,sizeof(nai),"0%s@%s",identity,realm);
 struct addrinfo hints={.ai_family=AF_INET,.ai_socktype=SOCK_DGRAM},*ai=NULL;char peer[INET_ADDRSTRLEN]={0};
 printf("VOWIFI_EPDG domain=%s\n",domain);int dns_error=getaddrinfo(domain,"500",&hints,&ai);printf("VOWIFI_DNS result=%d\n",dns_error);if(dns_error)goto done;
 for(struct addrinfo *p=ai;p;p=p->ai_next){struct sockaddr_in *a=(void*)p->ai_addr;unsigned n=ntohl(a->sin_addr.s_addr);if((n>>24)==127 || n==0 || (n>>28)==14)continue;inet_ntop(AF_INET,&a->sin_addr,peer,sizeof(peer));break;}freeaddrinfo(ai);printf("VOWIFI_EPDG_ADDRESS valid=%d\n",!!*peer);if(!*peer)goto done;
 int fd=socket(AF_INET,SOCK_DGRAM,0);struct ifreq ifr={0};strcpy(ifr.ifr_name,uplink);if(fd<0)goto done;int e=ioctl(fd,SIOCGIFADDR,&ifr);close(fd);if(e)goto done;
 char local[INET_ADDRSTRLEN];inet_ntop(AF_INET,&((struct sockaddr_in*)&ifr.ifr_addr)->sin_addr,local,sizeof(local));
 FILE *f=file("strongswan.conf");if(!f)goto done;
 fprintf(f,"charon {\n threads = 16\n make_before_break = no\n mf79u_apn = ims\n install_routes = no\n routing_table = 0\n interfaces_use = %s,vowifi0\n plugins {\n vici { socket = unix://" DIR "/charon.vici }\n kernel-netlink { install_virtual_ip_on = vowifi0 }\n kernel-libipsec { allow_peer_ts = yes }\n p-cscf { enable { vowifi = yes } }\n }\n filelog { /dev/null { default = -1\n flush_line = yes } }\n syslog { daemon { default = -1 }\n auth { default = -1 } }\n}\n",uplink);fclose(f);
 f=file("swanctl.conf");if(!f)goto done;
 fprintf(f,"connections {\n vowifi {\n version = 2\n local_addrs = %s\n remote_addrs = %s\n vips = 0.0.0.0\n encap = yes\n mobike = no\n over_time = 120s\n rand_time = 60s\n proposals = aes128-sha256-modp2048,aes256-sha256-modp2048,aes128-sha1-modp2048,aes128-sha1-modp1024\n local { auth = eap-aka\n id = %s\n eap_id = %s }\n remote { auth = eap\n id = %s }\n children {\n vowifi { local_ts = dynamic\n remote_ts = 0.0.0.0/0\n esp_proposals = aes128-sha256,aes256-sha256,aes128-sha1,aes256-sha1\n updown = /mnt/userdata/mf79u/vowifi-updown.sh\n dpd_action = clear\n } }\n dpd_delay = 20s\n }\n}\n",local,peer,nai,nai,domain);fclose(f);
 f=file("epdg");if(!f)goto done;fprintf(f,"%s\n%s\n",domain,peer);fclose(f);puts("VOWIFI_CONFIG_READY");result=0;
 done: wipe(reply,sizeof(reply));wipe(identity,sizeof(identity));wipe(nai,sizeof(nai));return result;
}
