/* Read-only packet metadata; never print or persist payload/authentication. */
#include <arpa/inet.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
static unsigned word(const unsigned char*p){return p[0]*256u+p[1];}
int main(void){
 char text[64];struct in_addr vip;FILE*f=fopen("/dev/mf79u/vowifi/address","r");if(!f)return 1;int ok=fgets(text,sizeof(text),f)!=NULL;fclose(f);if(!ok)return 1;text[strcspn(text,"\r\n")]=0;if(inet_pton(AF_INET,text,&vip)!=1)return 1;
 int fd=socket(AF_PACKET,SOCK_DGRAM,htons(ETH_P_ALL));if(fd<0)return 1;struct timeval timeout={.tv_sec=1};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
 time_t end=time(NULL)+35;unsigned seen=0;
 while(time(NULL)<end && seen<60){unsigned char b[4096];int n=recv(fd,b,sizeof(b),0);if(n<20 || b[0]>>4!=4 || (memcmp(b+12,&vip,4)&&memcmp(b+16,&vip,4)))continue;unsigned h=(b[0]&15)*4;if(h<20 || n<(int)h+8)continue;
  const char*dir=memcmp(b+16,&vip,4)?"TX":"RX";printf("PACKET %s protocol=%u bytes=%d",dir,b[9],n);
  if(b[9]==1){printf(" icmp_type=%u code=%u",b[h],b[h+1]);if(n>=(int)h+8+28){unsigned ih=(b[h+8]&15)*4;if(ih>=20 && n>=(int)h+8+(int)ih+8)printf(" inner_protocol=%u inner_source_port=%u inner_destination_port=%u",b[h+8+9],word(b+h+8+ih),word(b+h+8+ih+2));}}
  if(b[9]==17){printf(" source_port=%u destination_port=%u",word(b+h),word(b+h+2));unsigned off=h+8;if(n>=(int)off+11 && !memcmp(b+off,"SIP/2.0 ",8))printf(" sip_code=%u",(b[off+8]-'0')*100u+(b[off+9]-'0')*10u+b[off+10]-'0');if(n>=(int)off+9 && !memcmp(b+off,"REGISTER ",9))printf(" register=1");}
  if(b[9]==6 && n>=(int)h+20){unsigned total=word(b+2),sum=6u+total-h;for(unsigned i=12;i<20;i+=2)sum+=word(b+i);if(total<=(unsigned)n){for(unsigned i=h;i+1<total;i+=2)sum+=word(b+i);if((total-h)&1)sum+=b[total-1]*256u;while(sum>>16)sum=(sum&65535u)+(sum>>16);unsigned th=(b[h+12]>>4)*4;printf(" source_port=%u destination_port=%u flags=%u tcp_checksum_valid=%u payload_bytes=%u",word(b+h),word(b+h+2),b[h+13],sum==65535u,total-h-th);if(total>=h+th+9 && !memcmp(b+h+th,"REGISTER ",9)){printf(" register=1");for(unsigned j=h+th;j+sizeof("P-Access-Network-Info:")-1<total;j++)if(!strncasecmp((char*)b+j,"P-Access-Network-Info:",sizeof("P-Access-Network-Info:")-1)){unsigned a=j+sizeof("P-Access-Network-Info:")-1;while(a<total && b[a]==' ')a++;printf(" access_wlan=%u access_cellular=%u",a+10<=total&&!memcmp(b+a,"IEEE-802.11",10),a+5<=total&&!memcmp(b+a,"3GPP-",5));break;}}}else printf(" truncated=1");}
  puts("");fflush(stdout);memset(b,0,sizeof(b));seen++;
 }
 close(fd);return 0;
}
