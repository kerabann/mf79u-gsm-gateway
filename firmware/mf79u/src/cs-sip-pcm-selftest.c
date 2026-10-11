/* Synthetic on-device SIP/PBX media test. No modem audio or call-control IO. */
#define _POSIX_C_SOURCE 200809L
#include <sys/socket.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <errno.h>
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
int main(void){
    int fd=socket(AF_INET,SOCK_DGRAM,0);struct sockaddr_in local={.sin_family=AF_INET,.sin_port=htons(46011),.sin_addr={htonl(INADDR_LOOPBACK)}},peer=local;peer.sin_port=htons(46010);
    if(fd<0 || bind(fd,(struct sockaddr *)&local,sizeof(local)) || fcntl(fd,F_SETFL,O_NONBLOCK)){perror("PCM socket");return 1;}
    unsigned char tx[644],rx[645];int16_t sine[320];double cos500[320],sin500[320];
    for(unsigned i=0;i<320;i++){double a=2*3.14159265358979323846*500*i/16000;sine[i]=(int16_t)(8000*sin(a));cos500[i]=cos(a);sin500[i]=sin(a);}
    memcpy(tx,"PCM2",4);memcpy(tx+4,sine,640);
    unsigned sent=0,received=0,late=0,bad=0;double energy=0,match=0;uint64_t start=ns(),next=start;
    puts("SIP_PCM_SYNTH_READY");fflush(stdout);
    while(ns()-start<8000000000ULL){
        uint64_t now=ns();
        if(now>=next){if(sendto(fd,tx,644,0,(struct sockaddr *)&peer,sizeof(peer))==644)sent++;next+=20000000ULL;if(now-next>200000000ULL && now>next)next=now+20000000ULL;}
        for(unsigned budget=0;budget<32;budget++){
            struct sockaddr_in from;socklen_t nfrom=sizeof(from);ssize_t n=recvfrom(fd,rx,sizeof(rx),0,(struct sockaddr *)&from,&nfrom);
            if(n<0){if(errno!=EAGAIN){perror("PCM receive");return 1;}break;}
            if(n!=644 || memcmp(rx,"PCM2",4) || from.sin_addr.s_addr!=local.sin_addr.s_addr){bad++;continue;}
            received++;
            if(now-start<3500000000ULL)continue;
            double re=0,im=0,e=0;
            for(unsigned i=0;i<320;i++) {int16_t v=(int16_t)((unsigned)rx[4+2*i]|(unsigned)rx[5+2*i]<<8);e+=(double)v*v;re+=v*cos500[i];im+=v*sin500[i];}
            energy+=e;match+=2*(re*re+im*im)/320;late++;
        }
        struct timespec pause={0,1000000};nanosleep(&pause,NULL);
    }
    double fraction=energy?match/energy:0;int passed=sent>=350 && received>=300 && late>=150 && fraction>.65 && bad==0;
    printf("{\"passed\":%s,\"sent_frames\":%u,\"received_frames\":%u,\"late_frames\":%u,\"bad_packets\":%u,\"echo_tone_energy\":%.6f,\"late_rms\":%.2f,\"synthetic_only\":true}\n",passed?"true":"false",sent,received,late,bad,fraction,late?sqrt(energy/(late*320)):0);
    memset(tx,0,sizeof(tx));memset(rx,0,sizeof(rx));close(fd);return !passed;
}
