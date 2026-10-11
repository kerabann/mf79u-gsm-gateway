#include "cp-pdp.h"
#include <arpa/inet.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

struct family {int seen;char address[INET6_ADDRSTRLEN],gateway[INET6_ADDRSTRLEN],dns[2][INET6_ADDRSTRLEN];};
static int address(const char *text,char *out,size_t capacity,int local) {
    unsigned bytes[32];unsigned n=0;const char *p=text;
    if(strchr(text,':')) {
        unsigned char raw[16];if(inet_pton(AF_INET6,text,raw)!=1)return 0;
        unsigned nonzero=0;for(unsigned i=0;i<16;i++)nonzero|=raw[i];if(local && !nonzero)return 0;
        return inet_ntop(AF_INET6,raw,out,capacity)?6:0;
    }
    while(*p && n<32) {
        if(*p<'0' || *p>'9')return 0;
        char *end;unsigned long value=strtoul(p,&end,10);
        if(end==p || value>255 || (*end && *end!='.'))return 0;
        bytes[n++]=(unsigned)value;if(!*end){p=end;break;}p=end+1;if(!*p)return 0;
    }
    if(*p)return 0;
    if(n==4 || (local && n==8)) {
        if(local && !(bytes[0]|bytes[1]|bytes[2]|bytes[3]))return 0;
        snprintf(out,capacity,"%u.%u.%u.%u",bytes[0],bytes[1],bytes[2],bytes[3]);return 4;
    }
    if(n==16 || (local && n==32)) {
        unsigned char raw[16];unsigned nonzero=0;
        for(unsigned i=0;i<16;i++){raw[i]=(unsigned char)bytes[i];nonzero|=bytes[i];}
        if(local && !nonzero)return 0;
        return inet_ntop(AF_INET6,raw,out,capacity)?6:0;
    }
    return 0;
}
int mf79u_pdp_translate(const char *details,char *reply,size_t capacity) {
    struct family v4={0},v6={0};int pcscf=0;
    if(!strstr(details,"\r\nOK\r\n"))goto invalid;
    const char *line=details;
    while((line=strstr(line,"+CGCONTRDP:"))) {
        line+=11;size_t size=strcspn(line,"\r\n");char row[2048];
        if(size>=sizeof(row))goto invalid;
        memcpy(row,line,size);row[size]=0;line+=size;
        char *fields[24];unsigned count=0;char *p=row;
        for(;;) {
            if(count>=24)goto invalid;
            while(*p==' ')p++;
            fields[count++]=p;
            char *end=strchr(p,',');if(end)*end=0;
            size_t n=strlen(p);while(n && p[n-1]==' ')p[--n]=0;
            if(n>=2 && p[0]=='"' && p[n-1]=='"'){p[n-1]=0;fields[count-1]=p+1;}
            if(!end)break;
            p=end+1;
        }
        if(count<8 || strcmp(fields[0],"5") || (strcasecmp(fields[2],"ims") && strncasecmp(fields[2],"ims.",4)))goto invalid;
        char ip[INET6_ADDRSTRLEN];int af=address(fields[3],ip,sizeof(ip),1);
        struct family *f=af==4?&v4:af==6?&v6:NULL;if(!f || f->seen)goto invalid;
        f->seen=1;strcpy(f->address,ip);
        if(!*fields[4])strcpy(f->gateway,af==4?"0.0.0.0":"::");
        else if(address(fields[4],f->gateway,sizeof(f->gateway),0)!=af)goto invalid;
        for(int i=0;i<2;i++) {
            if(!*fields[5+i])strcpy(f->dns[i],af==4?"0.0.0.0":"::");
            else if(address(fields[5+i],f->dns[i],sizeof(f->dns[i]),0)!=af)goto invalid;
        }
        for(unsigned i=7;i<count && i<9;i++)if(*fields[i] && address(fields[i],ip,sizeof(ip),1))pcscf=1;
    }
    if(!pcscf || (!v4.seen && !v6.seen))goto invalid;
    const char *type=v4.seen?(v6.seen?"IPV4V6":"IP"):"IPV6";
    char text[512];int n=snprintf(text,sizeof(text),"\r\n+ZPDPACT: 5,\"%s\"",type);
    struct family *families[]={&v4,&v6};
    for(unsigned i=0;i<2;i++)if(families[i]->seen) {
        struct family *f=families[i];
        int written=snprintf(text+n,sizeof(text)-(size_t)n,",\"%s\",\"%s\",\"%s\",\"%s\"",f->address,f->gateway,f->dns[0],f->dns[1]);
        if(written<0 || written>=(int)sizeof(text)-n)goto invalid;
        n+=written;
    }
    int end=snprintf(text+n,sizeof(text)-(size_t)n,"\r\nOK\r\n");if(end<0 || end>=(int)sizeof(text)-n)goto invalid;n+=end;
    if((size_t)n>=capacity){errno=EMSGSIZE;return -1;}memcpy(reply,text,(size_t)n+1);return n;
invalid: errno=EPROTO;return -1;
}
int mf79u_pdp_selftest(void) {
    const char *valid="\r\n+CGCONTRDP: 5,6,\"ims.mnc001.mcc001.gprs\",\"10.2.3.4.255.255.255.0\",,\"10.1.1.1\",\"10.1.1.2\",\"10.1.1.3\",\"10.1.1.4\"\r\nOK\r\n";
    char reply[512];if(mf79u_pdp_translate(valid,reply,sizeof(reply))<0 || !strstr(reply,"5,\"IP\",\"10.2.3.4\""))return 1;
    char copy[512];strcpy(copy,valid);*strstr(copy,"5,6")='4';if(mf79u_pdp_translate(copy,reply,sizeof(reply))>=0)return 1;
    strcpy(copy,valid);memcpy(strstr(copy,"ims."),"bad.",4);if(mf79u_pdp_translate(copy,reply,sizeof(reply))>=0)return 1;
    if(mf79u_pdp_translate("\r\n+CGCONTRDP: 5,6,ims,10.2.3.4,,10.1.1.1,10.1.1.2,,\r\nOK\r\n",reply,sizeof(reply))>=0)return 1;
    if(mf79u_pdp_translate("\r\n+CGCONTRDP: 5,6,ims,999.2.3.4,,10.1.1.1,10.1.1.2,10.1.1.3\r\nOK\r\n",reply,sizeof(reply))>=0)return 1;
    if(mf79u_pdp_translate("\r\n+CGCONTRDP: 5,6,ims,2001:db8::1,,2001:db8::2,,2001:db8::3\r\nOK\r\n",reply,sizeof(reply))<0 || !strstr(reply,"\"IPV6\""))return 1;
    return 0;
}
