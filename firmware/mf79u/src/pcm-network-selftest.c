/* Synthetic static ARM test. No native process, SIM, CP or calls. */
#include "ims-software-media.h"
#include <arpa/inet.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <sys/socket.h>
#include <unistd.h>
int mf79u_media_selftest(void);
int mf79u_media_wb_selftest(void);
int main(void){
    setenv("MF79U_PCM_NETWORK","1",1);mf79u_media_enable();
    int source=socket(AF_INET,SOCK_DGRAM,0),sink=socket(AF_INET,SOCK_DGRAM,0);
    struct timeval timeout={.tv_sec=1};setsockopt(sink,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    struct sockaddr_in dest={.sin_family=AF_INET,.sin_addr.s_addr=htonl(INADDR_LOOPBACK),.sin_port=htons(46001)};
    struct sockaddr_in output=dest;output.sin_port=htons(46000);
    if(source<0 || sink<0 || bind(sink,(struct sockaddr*)&output,sizeof(output)))return 1;
    if(mf79u_media_register(255,2))return 2;
    uint32_t config[5]={8000,1,160,16,0};
    if(mf79u_media_ioctl(255,0x40147605,config) || mf79u_media_ioctl(255,0x7601,NULL) || mf79u_media_ioctl(255,0x7603,NULL))return 3;
    unsigned char packet[324],readback[320];memcpy(packet,"PCM1",4);
    for(unsigned i=4;i<324;i++)packet[i]=(i*17)&255;
    for(int i=0;i<3;i++)if(sendto(source,packet,sizeof(packet),0,(struct sockaddr*)&dest,sizeof(dest))!=324)return 4;
    if(mf79u_media_read(255,readback,320)!=320 || memcmp(readback,packet+4,320))return 5;
    if(mf79u_media_write(255,readback,320)!=320)return 6;
    unsigned char received[324];if(recv(sink,received,sizeof(received),0)!=324 || memcmp(received,packet,324))return 7;
    for(int i=0;i<2;i++)if(mf79u_media_read(255,readback,320)!=320 || memcmp(readback,packet+4,320))return 12;
    memset(packet,'X',4);sendto(source,packet,sizeof(packet),0,(struct sockaddr*)&dest,sizeof(dest));
    if(mf79u_media_read(255,readback,320)!=320)return 8;
    for(int i=0;i<160;i++){
        short expected;memcpy(&expected,packet+4+2*i,2);expected=expected*3/4;
        short actual;memcpy(&actual,readback+2*i,2);if(actual!=expected)return 9;
    }
    config[0]=16000;config[2]=320;if(mf79u_media_ioctl(255,0x40147605,config)>=0)return 10;
    mf79u_media_close(255);
    setenv("MF79U_PCM_WIDEBAND","1",1);mf79u_media_enable();
    if(mf79u_media_register(255,2) || mf79u_media_ioctl(255,0x40147605,config) ||
       mf79u_media_ioctl(255,0x7601,NULL) || mf79u_media_ioctl(255,0x7603,NULL))return 13;
    unsigned char wide[644],wide_out[640],wide_received[644];memcpy(wide,"PCM2",4);
    for(unsigned i=4;i<644;i++)wide[i]=(i*11)&255;
    for(unsigned i=0;i<3;i++)if(sendto(source,wide,sizeof(wide),0,(struct sockaddr*)&dest,sizeof(dest))!=644)return 14;
    if(mf79u_media_read(255,wide_out,640)!=640 || memcmp(wide_out,wide+4,640))return 15;
    if(mf79u_media_write(255,wide_out,640)!=640 || recv(sink,wide_received,644,0)!=644 || memcmp(wide_received,wide,644))return 16;
    mf79u_media_close(255);close(source);close(sink);
    unsetenv("MF79U_PCM_WIDEBAND");mf79u_media_enable();
    if(mf79u_media_selftest())return 11;
    if(mf79u_media_wb_selftest())return 17;
    puts("PCM network selftest=0; NB+WB bidirectional samples, malformed packet, rate guard, NB+WB codecs verified");return 0;
}
