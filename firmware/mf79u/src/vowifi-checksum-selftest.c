#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "vowifi-ipv4-checksum.h"
int main(void){
 unsigned char tcp[45]={0x45,0,0,45,0,0,0,0,64,6,0,0,192,168,1,1,192,168,1,2,0x13,0xd8,0x13,0xc4,0,0,0,1,0,0,0,1,0x50,0x18,0x10,0,0xff,0xff,0,0,'H','E','L','L','O'};
 unsigned char udp[33]={0x45,0,0,33,0,0,0,0,64,17,0,0,192,168,1,1,192,168,1,2,0x13,0xd8,0x13,0xc4,0,13,0xff,0xff,'H','E','L','L','O'};
 size_t n=0;assert(mf79u_vowifi_checksum(tcp,sizeof(tcp),&n)&&n==45);assert(mf79u_ip_word(tcp+10)==0xf777 && mf79u_ip_word(tcp+36)==0x1144);assert(!memcmp(tcp+40,"HELLO",5));
 assert(mf79u_vowifi_checksum(udp,sizeof(udp),&n)&&n==33);assert(mf79u_ip_word(udp+10)==0xf778 && mf79u_ip_word(udp+26)==0x7152);assert(!memcmp(udp+28,"HELLO",5));
 assert(mf79u_vowifi_checksum(tcp,sizeof(tcp),&n)&&mf79u_ip_word(tcp+36)==0x1144);
 tcp[6]=0x20;tcp[36]=0xab;tcp[37]=0xcd;assert(mf79u_vowifi_checksum(tcp,sizeof(tcp),&n)&&mf79u_ip_word(tcp+36)==0xabcd);
 tcp[2]=1;assert(!mf79u_vowifi_checksum(tcp,sizeof(tcp),&n));udp[25]=12;assert(!mf79u_vowifi_checksum(udp,sizeof(udp),&n));
 puts("PASS IPv4 TCP/UDP offload normalization: known checksum vectors, odd payload, fragments, malformed lengths");return 0;
}
