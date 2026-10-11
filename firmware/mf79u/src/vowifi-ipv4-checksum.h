#ifndef MF79U_VOWIFI_IPV4_CHECKSUM_H
#define MF79U_VOWIFI_IPV4_CHECKSUM_H
#include <stddef.h>
static unsigned mf79u_ip_word(const unsigned char *p){return p[0]*256u+p[1];}
static unsigned mf79u_ip_sum(const unsigned char *p,size_t n){unsigned s=0;while(n>1){s+=mf79u_ip_word(p);p+=2;n-=2;}if(n)s+=*p*256u;return s;}
static unsigned mf79u_ip_finish(unsigned sum){while(sum>>16)sum=(sum&65535u)+(sum>>16);return (~sum)&65535u;}
/* AF_PACKET sees CHECKSUM_PARTIAL before bridge TX offload. Complete checksums
 * before userspace ESP encapsulation; never interpret a partial IP fragment. */
static int mf79u_vowifi_checksum(unsigned char *p,size_t n,size_t *length){
 if(n<20 || p[0]>>4!=4)return 0;unsigned h=(p[0]&15)*4,total=mf79u_ip_word(p+2);
 if(h<20 || h>total || total>n)return 0;*length=total;
 p[10]=p[11]=0;unsigned check=mf79u_ip_finish(mf79u_ip_sum(p,h));p[10]=check>>8;p[11]=check;
 if(mf79u_ip_word(p+6)&0x3fff)return 1;
 unsigned bytes=total-h,offset;
 if(p[9]==6){if(bytes<20 || (p[h+12]>>4)*4<20 || (p[h+12]>>4)*4>bytes)return 0;offset=16;}
 else if(p[9]==17){if(bytes<8 || mf79u_ip_word(p+h+4)!=bytes)return 0;offset=6;}
 else return 1;
 p[h+offset]=p[h+offset+1]=0;
 check=mf79u_ip_finish(mf79u_ip_sum(p+12,8)+p[9]+bytes+mf79u_ip_sum(p+h,bytes));
 if(p[9]==17 && !check)check=65535;
 p[h+offset]=check>>8;p[h+offset+1]=check;return 1;
}
#endif
