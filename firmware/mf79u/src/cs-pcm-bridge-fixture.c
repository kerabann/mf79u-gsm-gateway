/* Link-only syscall fixture for the actual bridge. Generates synthetic 8 kHz
 * PCM in RAM; never opens real sysfs audio or accesses modem hardware. */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <math.h>
extern int __real_open(const char *,int,...);
extern ssize_t __real_read(int,void *,size_t);
extern ssize_t __real_write(int,const void *,size_t);
extern off_t __real_lseek(int,off_t,int);
extern int __real_close(int);
static uint64_t start,next;
static unsigned got,frames,measured;
static double energy,matched;
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
int __wrap_open(const char *path,int flags,...){
    if(!strcmp(path,"/sys/mf79u_cs_mo/pcm_rx"))return 1000;
    if(!strcmp(path,"/sys/mf79u_cs_mo/pcm_tx"))return 1001;
    if(!strcmp(path,"/sys/mf79u_cs_mo/pcm_info"))return 1002;
    if(flags&O_CREAT){va_list ap;va_start(ap,flags);int mode=va_arg(ap,int);va_end(ap);return __real_open(path,flags,mode);}
    return __real_open(path,flags);
}
off_t __wrap_lseek(int fd,off_t offset,int whence){if(fd>=1000 && fd<=1002)return offset==0 && whence==SEEK_SET?0:-1;return __real_lseek(fd,offset,whence);}
int __wrap_close(int fd){if(fd>=1000 && fd<=1002)return 0;return __real_close(fd);}
ssize_t __wrap_read(int fd,void *data,size_t size){
    if(fd==1002){if(!start){start=ns();next=start;}char text[64];int n=snprintf(text,sizeof(text),"MF79U_CS_PCM 1 %d 8000 160 320\n",ns()-start<8000000000ULL);if(size<(size_t)n)return -1;memcpy(data,text,(size_t)n);return n;}
    if(fd!=1000)return __real_read(fd,data,size);
    if(size!=320){errno=EINVAL;return -1;}
    if(ns()<next){errno=EAGAIN;return -1;}next+=20000000ULL;
    static const int16_t tone[16]={0,3061,5657,7391,8000,7391,5657,3061,0,-3061,-5657,-7391,-8000,-7391,-5657,-3061};
    unsigned char *out=data;for(unsigned i=0;i<160;i++){uint16_t v=(uint16_t)tone[i&15];out[2*i]=(unsigned char)v;out[2*i+1]=(unsigned char)(v>>8);}frames++;return 320;
}
ssize_t __wrap_write(int fd,const void *data,size_t size){
    if(fd!=1001)return __real_write(fd,data,size);
    if(size!=320){errno=EINVAL;return -1;}got++;
    if(ns()-start>3500000000ULL){
        const unsigned char *p=data;double real=0,imag=0,e=0;
        for(unsigned i=0;i<160;i++){int16_t v=(int16_t)((unsigned)p[2*i]|(unsigned)p[2*i+1]<<8);double a=2*3.14159265358979323846*500*i/8000;e+=(double)v*v;real+=v*cos(a);imag+=v*sin(a);}
        energy+=e;matched+=2*(real*real+imag*imag)/160;measured++;
    }
    return 320;
}
__attribute__((destructor)) static void result(void){
    double fraction=energy?matched/energy:0;
    printf("{\"passed\":%s,\"source_frames\":%u,\"returned_frames\":%u,\"late_frames\":%u,\"echo_tone_energy\":%.6f,\"late_rms\":%.2f,\"synthetic_only\":true,\"real_bridge_code\":true}\n",frames>=390 && got>=390 && measured>=200 && fraction>.65?"true":"false",frames,got,measured,fraction,measured?sqrt(energy/(measured*160)):0);
}
