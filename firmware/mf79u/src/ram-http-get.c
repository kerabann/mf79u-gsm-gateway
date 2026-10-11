/* Bounded USB-LAN transfer for old adbd. SHA256 is checked by the host. */
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
int main(int argc,char **argv){
 if(argc!=4 || (strncmp(argv[3],"/dev/.mf79u-",12) && strncmp(argv[3],"/mnt/userdata/mf79u/",sizeof("/mnt/userdata/mf79u/")-1)) || strchr(argv[2],'\r') || strchr(argv[2],'\n'))return 1;
 struct in_addr ip;if(inet_pton(AF_INET,argv[1],&ip)!=1)return 1;
 int s=socket(AF_INET,SOCK_STREAM,0);struct timeval t={10,0};setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&t,sizeof(t));setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&t,sizeof(t));
 struct sockaddr_in addr={.sin_family=AF_INET,.sin_port=htons(18089),.sin_addr=ip};if(connect(s,(struct sockaddr*)&addr,sizeof(addr)))return 2;
 char request[300];int n=snprintf(request,sizeof(request),"GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n",argv[2],argv[1]);if(n<0 || n>=(int)sizeof(request) || write(s,request,n)!=n)return 3;
 char header[2048];unsigned used=0;for(;used<sizeof(header)-1;){if(read(s,header+used,1)!=1)return 4;used++;if(used>=4&&!memcmp(header+used-4,"\r\n\r\n",4))break;}header[used]=0;if(!strstr(header," 200 "))return 5;
 int f=open(argv[3],O_WRONLY|O_CREAT|O_TRUNC,0700);if(f<0)return 6;char data[4096];unsigned total=0;
 while((n=read(s,data,sizeof(data)))>0){total+=(unsigned)n;if(total>12*1024*1024 || write(f,data,n)!=n){close(f);unlink(argv[3]);return 7;}}
 close(f);close(s);if(n<0){unlink(argv[3]);return 8;}printf("USB LAN transfer bytes=%u\n",total);return 0;
}
