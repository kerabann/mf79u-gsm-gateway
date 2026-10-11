/* Observe only SIP method/status lines and IP protocol counts on the IMS NIC.
 * No headers, bodies, SIM identifiers or authentication material are emitted. */
#include <arpa/inet.h>
#include <errno.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <netpacket/packet.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
int main(int argc,char **argv) {
    if(argc!=3 || (strcmp(argv[1],"wan5") && strcmp(argv[1],"bridge0"))) return 2;
    char *end;long seconds=strtol(argv[2],&end,10);
    if(*end || seconds<1 || seconds>180) return 2;
    int fd=socket(AF_PACKET,SOCK_DGRAM,htons(ETH_P_ALL));
    if(fd<0){perror("packet socket");return 1;}
    struct sockaddr_ll addr={.sll_family=AF_PACKET,.sll_protocol=htons(ETH_P_ALL),
                             .sll_ifindex=(int)if_nametoindex(argv[1])};
    struct timeval timeout={.tv_sec=1};
    if(!addr.sll_ifindex || bind(fd,(struct sockaddr*)&addr,sizeof(addr)) ||
       setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout))) {
        perror("bind IMS interface");close(fd);return 1;
    }
    unsigned count[256]={0},frames=0,non_ip=0;unsigned char bytes[4096];
    setvbuf(stdout,NULL,_IONBF,0);puts("READY IMS metadata observer");
    time_t deadline=time(NULL)+seconds;
    while(time(NULL)<deadline) {
        struct sockaddr_ll from; socklen_t size=sizeof(from);
        ssize_t n=recvfrom(fd,bytes,sizeof(bytes),0,(struct sockaddr*)&from,&size);
        if(n<0){if(errno==EAGAIN || errno==EWOULDBLOCK || errno==EINTR)continue;
            if(errno==ENETDOWN){usleep(100000);continue;}
            perror("receive IMS metadata");close(fd);return 1;}
        frames++;
        if(n>=34 && bytes[0]>>4!=4 && bytes[12]==8 && bytes[13]==0) {
            memmove(bytes,bytes+14,(size_t)n-14);n-=14;
        }
        if(n<20 || bytes[0]>>4!=4){non_ip++;continue;}
        unsigned ihl=(bytes[0]&15)*4,proto=bytes[9];count[proto]++;
        if(ihl<20 || (unsigned)n<ihl+8 || proto!=17)continue;
        const unsigned char *data=bytes+ihl+8;size_t len=(size_t)n-ihl-8;
        const char *direction=from.sll_pkttype==PACKET_OUTGOING?"TX":"RX";
        unsigned src=(unsigned)bytes[ihl]*256+bytes[ihl+1],dst=(unsigned)bytes[ihl+2]*256+bytes[ihl+3];
        if(!strcmp(argv[1],"bridge0")){
            if(src!=5060 && dst!=5060 && src!=5080 && dst!=5080)continue;
            char a[INET_ADDRSTRLEN],b[INET_ADDRSTRLEN];
            if(inet_ntop(AF_INET,bytes+12,a,sizeof(a)) && inet_ntop(AF_INET,bytes+16,b,sizeof(b)))
                printf("%s USB SIP %s:%u > %s:%u bytes=%u\n",direction,a,src,b,dst,(unsigned)len);
        }
        if(len>=11 && !memcmp(data,"SIP/2.0 ",8) &&
           data[8]>='1' && data[8]<='6' && data[9]>='0' && data[9]<='9' &&
           data[10]>='0' && data[10]<='9')
            printf("%s SIP response %.3s\n",direction,data+8);
        else {
            const char *methods[]={"REGISTER","INVITE","ACK","BYE","CANCEL",
                                   "OPTIONS","SUBSCRIBE","NOTIFY","PRACK","UPDATE"};
            for(unsigned i=0;i<sizeof(methods)/sizeof(methods[0]);i++) {
                size_t m=strlen(methods[i]);
                if(len>m && !memcmp(data,methods[i],m) && data[m]==' ') {
                    printf("%s SIP method %s\n",direction,methods[i]);break;
                }
            }
        }
    }
    for(unsigned i=0;i<256;i++)if(count[i])printf("IP protocol=%u packets=%u\n",i,count[i]);
    printf("Frames=%u non_IPv4=%u\n",frames,non_ip);
    close(fd);return 0;
}
