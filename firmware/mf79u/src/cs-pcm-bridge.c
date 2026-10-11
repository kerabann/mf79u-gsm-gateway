/* CS PCM adapter: hardware 8k/160 <-> unchanged PCM2 16k/320.
 * Single owned endpoint. No call control; no audio/number persistence. */
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
#include "pcm-resample.h"
#include "cs-pcm-clarity.h"
#ifdef MF79U_DIAGNOSTIC_FAULTS
#include "diagnostic-fault.h"
#endif
#ifndef CS_PCM_BASE
#define CS_PCM_BASE "/sys/mf79u_cs_mo"
#endif
#ifndef CS_PCM_UDP_LOCAL
#define CS_PCM_UDP_LOCAL 46001
#define CS_PCM_UDP_PEER 46000
#endif
static volatile sig_atomic_t stopping;
static void stop(int sig){(void)sig;stopping=1;}
static uint64_t millis(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000+t.tv_nsec/1000000;}
static void erase(void *p,size_t n){volatile unsigned char *b=p;while(n--)*b++=0;}
static ssize_t frame_io(int fd,void *p,int writing){
    if(lseek(fd,0,SEEK_SET))return -1;
    return writing?write(fd,p,320):read(fd,p,320);
}
static int ready(int fd){
    char info[80]={0};if(lseek(fd,0,SEEK_SET))return -1;
    ssize_t n=read(fd,info,sizeof(info)-1);if(n<=0)return -1;
    if(!strcmp(info,"MF79U_CS_PCM 1 1 8000 160 320\n"))return 1;
    if(!strcmp(info,"MF79U_CS_PCM 1 0 8000 160 320\n"))return 0;
    return -1;
}
int main(int argc,char **argv){
#ifdef MF79U_DIAGNOSTIC_FAULTS
    if(mf79u_diagnostic_fault_install())return 70;
#endif
    /* Preserve level metadata across an unexpected device/USB interruption. */
    setvbuf(stdout,NULL,_IOLBF,0);
    int diagnostic=argc==2 && !strcmp(argv[1],"--tone-echo");
    int compare=argc==2 && !strcmp(argv[1],"--compare-sip");
    int clarity=argc==2 && !strcmp(argv[1],"--stream-clarity");
    int streaming=argc==2 && (!strcmp(argv[1],"--stream") || clarity);
    if(!diagnostic && !compare && !streaming && !(argc==2 && !strcmp(argv[1],"--udp"))){fputs("usage: cs-pcm-bridge --tone-echo|--udp|--compare-sip|--stream|--stream-clarity\n",stderr);return 2;}
    if(geteuid()!=0){fputs("root required\n",stderr);return 2;}
    umask(077);int owner=open("/dev/.mf79u-cs-pcm.lock",O_CREAT|O_RDWR,0600);
    if(owner<0 || flock(owner,LOCK_EX|LOCK_NB)){perror("PCM ownership");return 1;}
    int rx=open(CS_PCM_BASE "/pcm_rx",O_RDONLY),tx=open(CS_PCM_BASE "/pcm_tx",O_WRONLY),info=open(CS_PCM_BASE "/pcm_info",O_RDONLY);
    if(rx<0 || tx<0 || info<0){perror("PCM endpoint");return 1;}
    int udp=-1;struct sockaddr_in peer={.sin_family=AF_INET,.sin_port=htons(CS_PCM_UDP_PEER),.sin_addr={htonl(INADDR_LOOPBACK)}};
    if(!diagnostic){
        struct sockaddr_in local=peer;local.sin_port=htons(CS_PCM_UDP_LOCAL);
        udp=socket(AF_INET,SOCK_DGRAM,0);
        if(udp<0 || bind(udp,(struct sockaddr *)&local,sizeof(local)) || fcntl(udp,F_SETFL,O_NONBLOCK)){perror("PCM2 exclusive bind");return 1;}
    }
    signal(SIGTERM,stop);signal(SIGINT,stop);
    int16_t narrow[160]={0},wide[320]={0},out[320]={0},delay[4][320]={{0}},incoming[8][320]={{0}};
    unsigned char packet[644]={0};struct mf79u_resample up={0},down={0};
    struct cs_pcm_clarity rx_clarity={0},tx_clarity={0};
    unsigned frames=0,txframes=0,rxnonzero=0,txnonzero=0,txfull=0,udp_rx=0,udp_tx=0,udp_drop=0,udp_bad=0,underrun=0,head=0,tail=0,phase=0;
    unsigned rx_peak=0,rx_active=0,peer_peak=0,peer_active=0;uint64_t rx_energy=0,peer_energy=0;
    uint64_t end=millis()+90000,active=0,next_info=0;int failure=0,finished=0;
    struct timespec pause={0,2000000};
    puts("CS_PCM_BRIDGE waiting=1 external_rate=16000 external_samples=320 speech_saved=0");fflush(stdout);
    while(!stopping && (!end || millis()<end)){
        uint64_t now=millis();
        if(now>=next_info){
            int online=ready(info);next_info=now+20;
            if(online<0){if(active){finished=1;break;}failure=1;break;}
            if(online && !active){active=now;end=streaming?0:now+30000;
                /* Streaming ends on endpoint clearing or the owning process'
                 * signal, without truncating a valid long conversation. The
                 * initial wait remains bounded even in streaming mode. */
                /* Two silence frames provide bounded scheduling headroom. */
                for(unsigned i=0;i<2;i++)if(frame_io(tx,narrow,1)==320)txframes++;
                puts("CS_PCM_BRIDGE online=1");fflush(stdout);
            }
            if(!online && active){finished=1;break;}
        }
        if(!active){nanosleep(&pause,NULL);continue;}
        if(udp>=0)for(unsigned budget=0;budget<16;budget++){
            struct sockaddr_in from;socklen_t size=sizeof(from);
            ssize_t n=recvfrom(udp,packet,sizeof(packet),MSG_TRUNC,(struct sockaddr *)&from,&size);
            if(n<0){if(errno!=EAGAIN && errno!=EINTR)failure=1;break;}
            /* Existing SIP uses an unbound TX socket: its source port is ephemeral. */
            if(n!=644 || from.sin_family!=AF_INET || from.sin_addr.s_addr!=peer.sin_addr.s_addr || memcmp(packet,"PCM2",4)){udp_bad++;continue;}
            if(tail-head==8){erase(incoming[head++&7],640);udp_drop++;}
            memcpy(incoming[tail++&7],packet+4,640);udp_rx++;
        }
        ssize_t n=frame_io(rx,narrow,0);
        if(n<0 && (errno==EAGAIN || errno==EINTR)){nanosleep(&pause,NULL);continue;}
        if(n!=320){if(ready(info)<=0){finished=1;break;}failure=1;break;}
        for(unsigned i=0;i<160;i++){
            int v=narrow[i];unsigned a=(unsigned)(v<0?-v:v);
            if(v)rxnonzero++;
            if(a>rx_peak)rx_peak=a;
            if(a>64)rx_active++;
            rx_energy+=(int64_t)v*v;
        }
        if(clarity)cs_pcm_clarity_apply(&rx_clarity,narrow);
        mf79u_upsample(&up,narrow,wide);
        if(diagnostic){
            static const int16_t sine[32]={0,1951,3827,5556,7071,8315,9239,9808,10000,9808,9239,8315,7071,5556,3827,1951,0,-1951,-3827,-5556,-7071,-8315,-9239,-9808,-10000,-9808,-9239,-8315,-7071,-5556,-3827,-1951};
            if(frames<100){for(unsigned i=0;i<320;i++){out[i]=sine[phase&31];phase+=frames<50?1:3;}}
            else memcpy(out,delay[frames&3],640);
            memcpy(delay[frames&3],wide,640);
        }else{
            memcpy(packet,"PCM2",4);memcpy(packet+4,wide,640);
            if(sendto(udp,packet,644,0,(struct sockaddr *)&peer,sizeof(peer))==644)udp_tx++;else udp_drop++;
            if(tail!=head){memcpy(out,incoming[head&7],640);erase(incoming[head++&7],640);}
            else{memset(out,0,640);underrun++;}
            for(unsigned i=0;i<320;i++){
                int v=out[i];unsigned a=(unsigned)(v<0?-v:v);
                if(a>peer_peak)peer_peak=a;
                if(a>64)peer_active++;
                peer_energy+=(int64_t)v*v;
            }
            if(compare){
                if(frames<150)memcpy(out,delay[frames&3],640);
                else if(frames<175){
                    static const int16_t marker[8]={0,7071,10000,7071,0,-7071,-10000,-7071};
                    for(unsigned i=0;i<320;i++)out[i]=marker[i&7];
                }
                memcpy(delay[frames&3],wide,640);
            }
        }
        mf79u_downsample(&down,out,narrow);
        if(clarity)cs_pcm_clarity_apply(&tx_clarity,narrow);
        for(unsigned i=0;i<160;i++)if(narrow[i])txnonzero++;
        n=frame_io(tx,narrow,1);if(n==320)txframes++;else if(n<0 && errno==EAGAIN)txfull++;else {if(ready(info)<=0){finished=1;break;}failure=1;break;}
        frames++;
        if(frames%50==0){
            printf("CS_PCM_BRIDGE window=%u rx_peak=%u rx_active=%u rx_energy=%llu peer_peak=%u peer_active=%u peer_energy=%llu mode=%s\n",frames/50,rx_peak,rx_active,(unsigned long long)rx_energy,peer_peak,peer_active,(unsigned long long)peer_energy,diagnostic?"tone_echo":compare && frames<=150?"local_echo":"sip");
            rx_peak=rx_active=peer_peak=peer_active=0;rx_energy=peer_energy=0;
        }
    }
    if(!finished && !stopping)failure=1;
    if(clarity && access("/dev/.mf79u-cs-clarity-test",F_OK)==0){
        /* Diagnostic metadata only; neither samples nor subscriber identities. */
        int stats=open("/dev/.mf79u-cs-clarity-result.json",O_CREAT|O_TRUNC|O_WRONLY|O_NOFOLLOW,0600);
        if(stats>=0){char b[256];int n=snprintf(b,sizeof(b),"{\"frames\":%u,\"rx_clipped\":%llu,\"tx_clipped\":%llu,\"speech_saved\":false}\n",frames,(unsigned long long)rx_clarity.clipped,(unsigned long long)tx_clarity.clipped);
            if(n>0 && n<(int)sizeof(b))(void)write(stats,b,(size_t)n);
            close(stats);}
    }
    erase(narrow,sizeof(narrow));erase(wide,sizeof(wide));erase(out,sizeof(out));erase(delay,sizeof(delay));erase(incoming,sizeof(incoming));erase(packet,sizeof(packet));erase(&up,sizeof(up));erase(&down,sizeof(down));erase(&rx_clarity,sizeof(rx_clarity));erase(&tx_clarity,sizeof(tx_clarity));
    printf("CS_PCM_BRIDGE stopped=1 mode=%s frames=%u tx_frames=%u rx_nonzero_samples=%u tx_nonzero_samples=%u tx_full_frames=%u udp_rx=%u udp_tx=%u udp_drop=%u udp_bad=%u udp_empty_frames=%u finished=%d failed=%d buffers_cleared=1\n",diagnostic?"tone_echo":"udp",frames,txframes,rxnonzero,txnonzero,txfull,udp_rx,udp_tx,udp_drop,udp_bad,underrun,finished,failure);
    close(rx);close(tx);close(info);if(udp>=0)close(udp);close(owner);return failure;
}
