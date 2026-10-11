/* Loopback-only raw UDP delivery test. No modem/SIM/operator traffic. */
#include <arpa/inet.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
static void put16(unsigned char *p,unsigned x){p[0]=x>>8;p[1]=x;}
int main(void){
    int receive=socket(AF_INET,SOCK_DGRAM,0),raw=socket(AF_INET,SOCK_RAW,IPPROTO_RAW);
    if(receive<0 || raw<0){perror("open loopback test socket");return 1;}
    struct sockaddr_in local={.sin_family=AF_INET,.sin_addr={.s_addr=htonl(0x7f000001)}};
    if(bind(receive,(void*)&local,sizeof(local))){perror("bind loopback test");return 1;}
    socklen_t len=sizeof(local);getsockname(receive,(void*)&local,&len);
    int one=1;struct timeval timeout={.tv_sec=2};
    setsockopt(raw,IPPROTO_IP,IP_HDRINCL,&one,sizeof(one));setsockopt(receive,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    unsigned char packet[36]={0};packet[0]=0x45;put16(packet+2,36);packet[8]=64;packet[9]=17;
    struct in_addr peer={.s_addr=htonl(0x7f000002)};
    memcpy(packet+12,&peer,4);memcpy(packet+16,&local.sin_addr,4);
    put16(packet+20,5101);memcpy(packet+22,&local.sin_port,2);put16(packet+24,16);
    memcpy(packet+28,"ESP_TEST",8);
    if(sendto(raw,packet,sizeof(packet),0,(void*)&local,sizeof(local))!=sizeof(packet)){perror("inject loopback UDP");return 1;}
    unsigned char out[32];struct sockaddr_in from;len=sizeof(from);
    ssize_t received=recvfrom(receive,out,sizeof(out),0,(void*)&from,&len);close(raw);close(receive);
    if(received!=8 || memcmp(out,"ESP_TEST",8) || from.sin_addr.s_addr!=peer.s_addr || ntohs(from.sin_port)!=5101){
        puts("Loopback UDP injection failed");return 1;}
    puts("PASS loopback UDP injection with preserved peer address/port");return 0;
}
