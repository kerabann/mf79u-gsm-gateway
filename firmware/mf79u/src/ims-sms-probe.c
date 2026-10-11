/* Metadata-only local SMS readiness probe. Cannot submit an SMS. */
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
int main(int argc,char **argv){
 if(argc!=2 || strcmp(argv[1],"--status"))return 2;
 int fd=socket(AF_UNIX,SOCK_SEQPACKET,0);if(fd<0)return 1;
 struct sockaddr_un a={.sun_family=AF_UNIX};strcpy(a.sun_path,"/dev/.mf79u-sms-ims.sock");
 unsigned char p[4096]={'M','S','I','1',1};
 if(connect(fd,(struct sockaddr*)&a,sizeof(a)) || send(fd,p,5,0)!=5){close(fd);return 1;}
 struct timeval timeout={2,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
 ssize_t n=recv(fd,p,sizeof(p)-1,0);close(fd);
 if(n<6 || memcmp(p,"MSI1",4) || p[4])return 1;
 p[n]=0;puts((char*)p+5);return 0;
}
