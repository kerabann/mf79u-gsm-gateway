#!/usr/bin/env python3
"""Run the actual PCM bridge with virtual time, sysfs and loopback PCM2.

No device, sockets, root privileges or speech recordings are used.
"""
from pathlib import Path
import hashlib,json,subprocess,tempfile

BASE=Path(__file__).resolve().parent
source=BASE/'src/cs-pcm-bridge.c'
fixture=r'''
#define _DARWIN_C_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#include <sys/socket.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include <assert.h>
static uint64_t now=1000,next_frame;
static unsigned frames,writes,packets;
static int never_online,signal_stop,queued;
static unsigned char echo[644];
static const unsigned char *last_tx;
static int fake_clock(clockid_t id,struct timespec *t) {
    assert(id==CLOCK_MONOTONIC);now++;
    if(signal_stop && now>=46000){signal_stop=0;raise(SIGTERM);}
    t->tv_sec=now/1000;t->tv_nsec=(now%1000)*1000000;return 0;
}
static int fake_sleep(const struct timespec *t,struct timespec *remain) {
    (void)remain;now+=(uint64_t)t->tv_sec*1000+t->tv_nsec/1000000;return 0;
}
static uid_t fake_uid(void){return 0;}
static int fake_open(const char *path,int flags,...) {
    (void)flags;
    if(!strcmp(path,"/dev/.mf79u-cs-pcm.lock"))return 10;
    if(!strcmp(path,"/sys/mf79u_cs_mo/pcm_rx"))return 11;
    if(!strcmp(path,"/sys/mf79u_cs_mo/pcm_tx"))return 12;
    assert(!strcmp(path,"/sys/mf79u_cs_mo/pcm_info"));return 13;
}
static int fake_flock(int fd,int flags){assert(fd==10 && flags==(LOCK_EX|LOCK_NB));return 0;}
static off_t fake_seek(int fd,off_t n,int whence){assert(fd>=11 && fd<=13 && !n && whence==SEEK_SET);return 0;}
static int fake_close(int fd){
    assert(fd>=10 && fd<=14);
    if(last_tx)for(unsigned i=0;i<320;i++)assert(last_tx[i]==0);
    return 0;
}
static int fake_socket(int family,int type,int proto){assert(family==AF_INET && type==SOCK_DGRAM && !proto);return 14;}
static int fake_bind(int fd,const struct sockaddr *a,socklen_t n){(void)a;assert(fd==14 && n==sizeof(struct sockaddr_in));return 0;}
static int fake_fcntl(int fd,int command,...){assert(fd==14 && command==F_SETFL);return 0;}
static ssize_t fake_read(int fd,void *out,size_t size){
    if(fd==13){
        const char *s=never_online || now>=46000?"MF79U_CS_PCM 1 0 8000 160 320\n":"MF79U_CS_PCM 1 1 8000 160 320\n";
        assert(size>=strlen(s));memcpy(out,s,strlen(s));return (ssize_t)strlen(s);
    }
    assert(fd==11 && size==320);
    if(now<next_frame){errno=EAGAIN;return -1;}
    next_frame=now+20;frames++;
    int16_t *p=out;for(unsigned i=0;i<160;i++)p[i]=(i&1)?4000:-4000;
    return 320;
}
static ssize_t fake_write(int fd,const void *data,size_t size){assert(fd==12 && size==320);last_tx=data;writes++;return 320;}
static ssize_t fake_send(int fd,const void *data,size_t size,int flags,const struct sockaddr *a,socklen_t n){
    (void)flags;(void)a;assert(fd==14 && n==sizeof(struct sockaddr_in) && size==644);
    assert(!memcmp(data,"PCM2",4));memcpy(echo,data,size);queued=1;packets++;return 644;
}
static ssize_t fake_recv(int fd,void *data,size_t size,int flags,struct sockaddr *a,socklen_t *n){
    (void)flags;assert(fd==14 && size==644 && *n==sizeof(struct sockaddr_in));
    if(!queued){errno=EAGAIN;return -1;}
    queued=0;memcpy(data,echo,644);
    struct sockaddr_in peer={.sin_family=AF_INET,.sin_port=htons(43210),.sin_addr={htonl(INADDR_LOOPBACK)}};
    memcpy(a,&peer,sizeof(peer));return 644;
}
#define main bridge_main
#define clock_gettime fake_clock
#define nanosleep fake_sleep
#define geteuid fake_uid
#define open fake_open
#define flock fake_flock
#define lseek fake_seek
#define close fake_close
#define socket fake_socket
#define bind fake_bind
#define fcntl fake_fcntl
#define read fake_read
#define write fake_write
#define sendto fake_send
#define recvfrom fake_recv
'''
fixture+='#include "'+str(source)+'"\n'
fixture+=r'''
#undef main
int main(int argc,char **argv){
    assert(argc==2);
    int bounded=!strcmp(argv[1],"bounded");
    never_online=!strcmp(argv[1],"never_online");
    signal_stop=!strcmp(argv[1],"signal");
    char *args[]={"fixture",bounded?"--udp":"--stream",NULL};
    int result=bridge_main(2,args);
    assert(result==(bounded || never_online));
    if(never_online){assert(frames==0 && now>=91000 && now<91100);}
    else if(bounded){assert(frames>1300 && frames<1600 && now<32000);}
    else{assert(frames>2000 && now>=46000 && now<46100);}
    assert(packets==frames && (!frames || writes>=frames));
    printf("PASS mode=%s virtual_ms=%llu frames=%u external_samples=320\n",argv[1],(unsigned long long)now,frames);
}
'''
with tempfile.TemporaryDirectory(prefix='cs-pcm-stream-') as temp:
    c=Path(temp)/'fixture.c';exe=Path(temp)/'fixture';c.write_text(fixture)
    subprocess.run(['cc','-std=c11','-O1','-Wall','-Wextra','-Werror',
                    '-fsanitize=undefined',str(c),'-o',str(exe)],check=True,timeout=30)
    cases=[]
    for mode in ('stream','signal','never_online','bounded'):
        result=subprocess.run([str(exe),mode],capture_output=True,text=True,check=True,timeout=10)
        line=result.stdout.splitlines()[-1];assert line.startswith('PASS ');print(line)
        cases.append({'mode':mode,'result':line})
report={'passed':True,'device_access':False,'synthetic_pcm_only':True,
        'actual_bridge_code':True,'sanitizers':['undefined'],
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':cases}
(BASE/'build/cs-pcm-stream-fixture.json').write_text(json.dumps(report,indent=2)+'\n')
