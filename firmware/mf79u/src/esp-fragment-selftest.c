/* Synthetic loopback ESP-protocol fragments; no SIM/operator traffic. */
#include "ipv4-fragments.h"
#include <arpa/inet.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
struct destination {int fd;struct sockaddr_in target;};
static int emit(void *context,const unsigned char *packet,size_t len){
    struct destination *d=context;
    return sendto(d->fd,packet,len,0,(void*)&d->target,sizeof(d->target))==(ssize_t)len?0:-1;
}
int main(void){
    int receive=socket(AF_INET,SOCK_RAW,IPPROTO_ESP),raw=socket(AF_INET,SOCK_RAW,IPPROTO_RAW);
    if(receive<0 || raw<0){perror("open loopback fragment socket");return 1;}
    struct destination d={.fd=raw,.target={.sin_family=AF_INET,.sin_addr={.s_addr=htonl(0x7f000001)}}};
    if(bind(receive,(void*)&d.target,sizeof(d.target))){perror("bind loopback ESP receive");return 1;}
    int one=1;struct timeval timeout={.tv_sec=2};
    if(setsockopt(raw,IPPROTO_IP,IP_HDRINCL,&one,sizeof(one)) ||
       setsockopt(receive,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout)))return 1;
    unsigned char packet[2068]={0},out[4096];packet[0]=0x45;packet[8]=64;packet[9]=50;
    struct in_addr peer={.s_addr=htonl(0x7f000002)};
    memcpy(packet+12,&peer,4);memcpy(packet+16,&d.target.sin_addr,4);
    for(size_t i=20;i<sizeof(packet);i++)packet[i]=(unsigned char)i;
    memcpy(packet+20,"MF79_FRAG_TEST",14);
    int count=ipv4_emit_fragments(packet,sizeof(packet),600,0x7911,emit,&d);
    if(count!=4){perror("emit four ESP fragments");return 1;}
    ssize_t size=recv(receive,out,sizeof(out),0);close(raw);close(receive);
    if(size!=(ssize_t)sizeof(packet) || out[0]!=0x45 || out[9]!=50 ||
       (out[6]&0x3f) || out[7] || memcmp(out+12,packet+12,8) ||
       memcmp(out+20,packet+20,sizeof(packet)-20)){
        puts("Loopback ESP fragment reassembly failed");return 1;}
    puts("PASS four IPv4 fragments reassembled before raw ESP delivery");return 0;
}
