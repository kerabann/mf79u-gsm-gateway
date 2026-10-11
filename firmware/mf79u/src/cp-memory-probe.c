#define _FILE_OFFSET_BITS 64
#include "cp-memory.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/sysmacros.h>
#include <unistd.h>

/* Exact CP getter bytes from SHA256 ab0f783a...d261; instruction verification
 * must pass before reading the two known single-byte policy fields. */
static const unsigned char signature[8]={0x01,0x4b,0x93,0xf8,0x5d,0x03,0x70,0x47};
#define NODE "/dev/.mf79u-cp-memory-ro"
#define RAM_START 0x20440000U
#define RAM_END   0x24000000U
#define PGD      0x20444000U
static int physical(void *ctx,uint32_t address,void *data,size_t length) {
    if(address<RAM_START || length>RAM_END-RAM_START || address>RAM_END-length){errno=ERANGE;return -1;}
    ssize_t n=pread(*(int *)ctx,data,length,address);
    if(n!=(ssize_t)length){if(n>=0)errno=EIO;return -1;}
    return 0;
}
static int cp_read(int fd,uint32_t va,void *data,size_t length) {
    if(va<0xbf000000U || length>6397096U || va>0xbf000000U+6397096U-length){errno=ERANGE;return -1;}
    unsigned char *out=data;
    while(length) {
        uint32_t pa;size_t count=4096-(va&4095);if(count>length)count=length;
        if(mf79u_arm_translate(physical,&fd,PGD,va,RAM_START,RAM_END,&pa) || physical(&fd,pa,out,count))return -1;
        va+=(uint32_t)count;out+=count;length-=count;
    }
    return 0;
}
int main(void) {
    struct stat st;
    if(!stat(NODE,&st) || errno!=ENOENT){fputs("CP_MEMORY node_exists_or_unreadable\n",stderr);return 1;}
    if(mknod(NODE,S_IFCHR|0600,makedev(1,1))){printf("CP_MEMORY node_create_errno=%d\n",errno);return 1;}
    int fd=open(NODE,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);int saved=errno;
    if(fd<0){unlink(NODE);printf("CP_MEMORY open_errno=%d\n",saved);return 2;}
    unsigned char bytes[8],voice,open_voice;int result=2;
    if(cp_read(fd,0xbf3e527cU,bytes,sizeof(bytes))){printf("CP_MEMORY code_read_errno=%d\n",errno);goto done;}
    if(memcmp(bytes,signature,sizeof(bytes))){puts("CP_MEMORY code_signature_mismatch");goto done;}
    if(cp_read(fd,0xbf59e484U+0x35d,&voice,1) || cp_read(fd,0xbf59e484U+0x45f,&open_voice,1)){
        printf("CP_MEMORY flags_read_errno=%d\n",errno);goto done;
    }
    if(voice>1 || open_voice>1){puts("CP_MEMORY flag_range_mismatch");goto done;}
    printf("CP_MEMORY code_signature=verified voice_support=%u open_voice=%u readonly=1\n",voice,open_voice);result=0;
done:close(fd);if(unlink(NODE)){puts("CP_MEMORY node_cleanup_failed");return 1;}return result;
}
