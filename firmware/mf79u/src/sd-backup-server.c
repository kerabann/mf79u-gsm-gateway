/* Temporary read-only SD transfer. Binds USB LAN, accepts only the Mac peer,
 * authenticates with a per-run token, and appends the device SHA256 per range.
 * Never mounts, opens for writing, or modifies the card. */
#define _FILE_OFFSET_BITS 64
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/fs.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include "sha256-min.h"

static volatile sig_atomic_t stopping;
static void stop(int signal_number) { (void)signal_number; stopping=1; }
static uint64_t unpack(const unsigned char *p) {
    uint64_t n=0;for(int i=0;i<8;i++)n=(n<<8)|p[i];return n;
}
static void pack(unsigned char *p,uint64_t n) {
    for(int i=7;i>=0;i--){p[i]=(unsigned char)n;n>>=8;}
}
static int transfer(int fd,void *data,size_t count,int sending) {
    unsigned char *p=data;
    while(count && !stopping) {
        ssize_t n=sending?send(fd,p,count,MSG_NOSIGNAL):recv(fd,p,count,0);
        if(n<0 && errno==EINTR)continue;
        if(n<=0)return -1;
        p+=n;count-=(size_t)n;
    }
    return count?-1:0;
}
static int range(int card,int peer,uint64_t size,const char *token) {
    unsigned char request[48],header[32],buffer[65536],digest[32];
    if(transfer(peer,request,sizeof(request),0) || memcmp(request,token,32))return -1;
    uint64_t offset=unpack(request+32),length=unpack(request+40),current;
    if(!length || length>32*1024*1024 || offset%512 || length%512 ||
       offset>size || length>size-offset || ioctl(card,BLKGETSIZE64,&current) || current!=size)return -1;
    if(lseek(card,(off_t)offset,SEEK_SET)!=(off_t)offset)return -1;
    memcpy(header,"MF79USD1",8);pack(header+8,size);pack(header+16,offset);pack(header+24,length);
    if(transfer(peer,header,sizeof(header),1))return -1;
    sd_sha256 hash;sd_hash_init(&hash);
    uint64_t left=length;
    while(left && !stopping) {
        size_t count=left<sizeof(buffer)?(size_t)left:sizeof(buffer);
        ssize_t n=read(card,buffer,count);
        if(n<0 && errno==EINTR)continue;
        if(n<=0)return -1;
        sd_hash_update(&hash,buffer,(size_t)n);
        if(transfer(peer,buffer,(size_t)n,1))return -1;
        left-=(uint64_t)n;
    }
    if(left)return -1;
    sd_hash_final(&hash,digest);
    return transfer(peer,digest,sizeof(digest),1);
}
int main(int argc,char **argv) {
    if(argc==2 && !strcmp(argv[1],"--selftest")) {
        unsigned sizes[]={0,3,55,56,64,65,65536,1048576};
        unsigned char data[65536],digest[32];for(unsigned i=0;i<sizeof(data);i++)data[i]=(unsigned char)(i*17+13);
        for(unsigned test=0;test<sizeof(sizes)/sizeof(sizes[0]);test++) {
            sd_sha256 hash;sd_hash_init(&hash);unsigned left=sizes[test];
            while(left){unsigned n=left<sizeof(data)?left:sizeof(data);sd_hash_update(&hash,data,n);left-=n;}
            sd_hash_final(&hash,digest);printf("%u ",sizes[test]);
            for(unsigned i=0;i<32;i++)printf("%02x",digest[i]);
            putchar('\n');
        }
        return 0;
    }
    if(argc!=2 || strlen(argv[1])!=32 || strspn(argv[1],"0123456789abcdef")!=32)return 2;
    struct sigaction action={.sa_handler=stop};sigemptyset(&action.sa_mask);
    sigaction(SIGTERM,&action,NULL);sigaction(SIGINT,&action,NULL);signal(SIGPIPE,SIG_IGN);
    setpriority(PRIO_PROCESS,0,10);
    int card=open("/dev/mmcblk0",O_RDONLY|O_CLOEXEC),server=-1,result=1;
    uint64_t size;struct stat info;
    if(card<0 || fstat(card,&info) || !S_ISBLK(info.st_mode) || ioctl(card,BLKGETSIZE64,&size) || !size)goto done;
    server=socket(AF_INET,SOCK_STREAM,0);if(server<0)goto done;
    int yes=1;setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
    struct sockaddr_in address={.sin_family=AF_INET,.sin_port=htons(18191)};
    inet_pton(AF_INET,"192.168.0.1",&address.sin_addr);
    if(bind(server,(struct sockaddr*)&address,sizeof(address)) || listen(server,1))goto done;
    printf("SD_BACKUP_READY pid=%ld bytes=%llu\n",(long)getpid(),(unsigned long long)size);fflush(stdout);
    time_t activity=time(NULL);
    while(!stopping && time(NULL)-activity<300) {
        struct pollfd ready={.fd=server,.events=POLLIN};int available=poll(&ready,1,1000);
        if(available<0 && errno==EINTR)continue;
        if(available<0)goto done;
        if(!available)continue;
        struct sockaddr_in remote;socklen_t length=sizeof(remote);
        int peer=accept(server,(struct sockaddr*)&remote,&length);if(peer<0)continue;
        struct in_addr permitted;inet_pton(AF_INET,"192.168.0.169",&permitted);
        if(remote.sin_addr.s_addr!=permitted.s_addr){close(peer);continue;}
        struct timeval timeout={30,0};setsockopt(peer,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
        setsockopt(peer,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
        if(range(card,peer,size,argv[1]))puts("SD_BACKUP_RANGE_FAILED");
        close(peer);activity=time(NULL);
    }
    result=0;
done:
    if(server>=0)close(server);
    if(card>=0)close(card);
    return result;
}
