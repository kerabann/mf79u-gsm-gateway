#include "esp-null.h"
#include <string.h>
static uint32_t get32(const unsigned char *s){return (uint32_t)s[0]<<24|(uint32_t)s[1]<<16|(uint32_t)s[2]<<8|s[3];}
static void put32(unsigned char *s,uint32_t x){s[0]=x>>24;s[1]=x>>16;s[2]=x>>8;s[3]=x;}
static int encode(struct esp_null_sa *sa,const unsigned char *udp,size_t len,
                  unsigned char *out,size_t capacity,esp_digest_fn digest,
                  esp_cipher_fn cipher,esp_random_fn random,void *context) {
    if(!sa || !udp || !out || !digest || !sa->spi || len<8 || len>65500 ||
       sa->tx_sequence==UINT32_MAX)return -1;
    unsigned block=cipher?16:4,ivlen=cipher?16:0;
    size_t padding=(block-(len+2)%block)%block,total=8+ivlen+len+padding+2+12;
    if(total>capacity)return -1;
    put32(out,sa->spi);put32(out+4,sa->tx_sequence+1);
    unsigned char *body=out+8+ivlen;memcpy(body,udp,len);
    for(size_t i=0;i<padding;i++)body[len+i]=(unsigned char)(i+1);
    body[len+padding]=(unsigned char)padding;body[1+len+padding]=17;
    if(cipher && (!random || random(context,out+8,16) ||
                  cipher(context,1,out+8,body,len+padding+2,body)))return -1;
    unsigned char mac[32];if(digest(context,out,total-12,mac)<12)return -1;
    memcpy(out+total-12,mac,12);sa->tx_sequence++;
    return (int)total;
}
static int decode(struct esp_null_sa *sa,const unsigned char *packet,size_t len,
                  unsigned char *udp,size_t capacity,esp_digest_fn digest,
                  esp_cipher_fn cipher,void *context) {
    unsigned block=cipher?16:4,ivlen=cipher?16:0;
    if(!sa || !packet || !udp || !digest || len<32+ivlen || len>65535 ||
       (len-20-ivlen)%block || get32(packet)!=sa->spi)return -1;
    uint32_t seq=get32(packet+4);if(!seq)return -1;
    if(seq<=sa->rx_highest && (sa->rx_highest-seq>=64 ||
       (sa->rx_window & ((uint64_t)1<<(sa->rx_highest-seq)))))return -1;
    unsigned char mac[32];if(digest(context,packet,len-12,mac)<12)return -1;
    unsigned difference=0;for(unsigned i=0;i<12;i++)difference|=mac[i]^packet[len-12+i];
    if(difference)return -1;
    size_t body_len=len-20-ivlen;if(body_len>capacity)return -1;
    if(cipher){if(cipher(context,0,packet+8,packet+8+ivlen,body_len,udp))return -1;}
    else memcpy(udp,packet+8,body_len);
    unsigned padding=udp[body_len-2];
    if(udp[body_len-1]!=17 || padding>body_len-10)return -1;
    size_t udp_len=body_len-2-padding;if(udp_len<8)return -1;
    for(unsigned i=0;i<padding;i++)if(udp[udp_len+i]!=i+1)return -1;
    if(seq>sa->rx_highest){uint32_t delta=seq-sa->rx_highest;
        sa->rx_window=delta>=64?1:(sa->rx_window<<delta)|1;sa->rx_highest=seq;
    }else sa->rx_window|=(uint64_t)1<<(sa->rx_highest-seq);
    return (int)udp_len;
}
int esp_null_encode(struct esp_null_sa *s,const unsigned char *p,size_t n,unsigned char *o,
                    size_t c,esp_digest_fn d,void *x){return encode(s,p,n,o,c,d,NULL,NULL,x);}
int esp_null_decode(struct esp_null_sa *s,const unsigned char *p,size_t n,unsigned char *o,
                    size_t c,esp_digest_fn d,void *x){return decode(s,p,n,o,c,d,NULL,x);}
int esp_cbc_encode(struct esp_null_sa *s,const unsigned char *p,size_t n,unsigned char *o,
                   size_t c,esp_digest_fn d,esp_cipher_fn e,esp_random_fn r,void *x){
    if(!e || !r)return -1;
    return encode(s,p,n,o,c,d,e,r,x);
}
int esp_cbc_decode(struct esp_null_sa *s,const unsigned char *p,size_t n,unsigned char *o,
                   size_t c,esp_digest_fn d,esp_cipher_fn e,void *x){
    if(!e)return -1;
    return decode(s,p,n,o,c,d,e,x);
}
