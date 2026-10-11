/* Diagnostic-only: one verified B03 enum, never general IMS memory. */
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv){if(argc!=2)return 2;char *end;long pid=strtol(argv[1],&end,10);if(*end || pid<2)return 2;char path[80],exe[256]={0};snprintf(path,sizeof(path),"/proc/%ld/exe",pid);if(readlink(path,exe,255)<1 || strcmp(exe,"/mnt/userdata/mf79u/.mf79u-volte-private"))return 2;snprintf(path,sizeof(path),"/proc/%ld/mem",pid);int fd=open(path,O_RDONLY);if(fd<0)return 1;unsigned format;int n=pread(fd,&format,4,0xcea14);close(fd);if(n!=4 || format>1)return 1;printf("{\"pduMode\":%s}\n",format==0?"true":"false");return 0;}
