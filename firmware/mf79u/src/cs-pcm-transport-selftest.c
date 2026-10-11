/* Exercises the real B03 sysfs binary path; all payloads are synthetic. */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
static void fail(const char *s) {perror(s);exit(1);}
static ssize_t transfer(int fd,void *p,size_t n,int writing) {
    if(lseek(fd,0,SEEK_SET)!=0)fail("seek");
    return writing?write(fd,p,n):read(fd,p,n);
}
int main(void) {
    const char *base="/sys/mf79u_pcm_probe/";char path[128],info[128]={0};
    snprintf(path,sizeof(path),"%spcm_info",base);int fd=open(path,O_RDONLY);
    if(fd<0)fail("info open");
    ssize_t n=read(fd,info,sizeof(info)-1);close(fd);
    if(n<=0 || strcmp(info,"MF79U_CS_PCM 1 1 8000 160 320\n"))fail("info contract");
    snprintf(path,sizeof(path),"%spcm_rx",base);int rx=open(path,O_RDONLY);
    snprintf(path,sizeof(path),"%spcm_tx",base);int tx=open(path,O_WRONLY);
    if(rx<0 || tx<0)fail("PCM open");
    unsigned char sent[320],got[320];uint32_t random=0x379c81a5;
    errno=0;if(transfer(rx,got,320,0)!=-1 || errno!=EAGAIN)fail("empty RX");
    memset(sent,0,sizeof(sent));errno=0;
    if(transfer(tx,sent,319,1)!=-1 || errno!=EINVAL)fail("short frame rejected");
    for(unsigned frame=0;frame<1000;frame++) {
        for(unsigned i=0;i<320;i++) {
            random^=random<<13;random^=random>>17;random^=random<<5;
            sent[i]=frame==0?0:(frame==1?255:(unsigned char)random);
        }
        if(transfer(tx,sent,320,1)!=320)fail("frame write");
        if(transfer(rx,got,320,0)!=320)fail("frame read");
        if(memcmp(sent,got,320))fail("binary roundtrip mismatch");
        errno=0;if(transfer(rx,got,320,0)!=-1 || errno!=EAGAIN)fail("consumed RX");
    }
    memset(sent,0,sizeof(sent));memset(got,0,sizeof(got));close(rx);close(tx);
    puts("{\"passed\":true,\"frames\":1000,\"binary_bytes\":320000,\"nul_and_high_bit\":true,\"repeated_seek\":true,\"empty_eagain\":true,\"wrong_size_einval\":true,\"synthetic_only\":true}");
    return 0;
}
