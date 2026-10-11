#include "caller-id.h"
#include <string.h>
#include <strings.h>
#include <ctype.h>

static int phone_uri(const char *s,size_t len,char out[40]){
    for(size_t i=0;i+4<=len;i++){
        if((i && s[i-1]!='<' && s[i-1]!=' ' && s[i-1]!='\t') ||
           (strncasecmp(s+i,"sip:",4) && strncasecmp(s+i,"tel:",4)))continue;
        char candidate[40];int tel=!strncasecmp(s+i,"tel:",4);size_t p=i+4,n=0,digits=0;
        if(p<len && s[p]=='+'){candidate[n++]='+' ;p++;}
        while(p<len && s[p]>='0' && s[p]<='9' && n<33){candidate[n++]=s[p++];digits++;}
        if(digits<3 || p>=len || (tel?(s[p]!=';' && s[p]!='>' && s[p]!=' ' && s[p]!='\t'):(s[p]!='@')))continue;
        candidate[n]=0;strcpy(out,candidate);return 1;
    }return 0;
}
int mf79u_caller_id(const void *packet,size_t length,char out[40]){
    const char *s=packet;char asserted[40]={0},from[40]={0};int privacy=0,duplicate_pai=0;
    strcpy(out,"anonymous");if(!s || length<7 || length>7000 || memcmp(s,"INVITE ",7) || memchr(s,0,length))return 0;
    for(size_t off=0;off<length;){
        const char *end=memchr(s+off,'\n',length-off);if(!end)break;
        size_t n=(size_t)(end-s-off);if(n && s[off+n-1]=='\r')n--;if(!n)break;
        const char *colon=memchr(s+off,':',n);
        if(colon){size_t key=(size_t)(colon-s-off),vlen=n-key-1;const char *v=colon+1;
            if(key==7 && !strncasecmp(s+off,"Privacy",7)){
                for(size_t i=0;i<vlen;i++)if(i+2<=vlen && (i==0 || v[i-1]==' ' || v[i-1]=='\t' || v[i-1]==';') && !strncasecmp(v+i,"id",2) && (i+2==vlen || v[i+2]==' ' || v[i+2]=='\t' || v[i+2]==';'))privacy=1;
            }else if(key==19 && !strncasecmp(s+off,"P-Asserted-Identity",19)){
                /* Ambiguous asserted identities fail closed. */
                if(asserted[0])duplicate_pai=1;else phone_uri(v,vlen,asserted);
            }else if((key==4 && !strncasecmp(s+off,"From",4)) || (key==1 && !strncasecmp(s+off,"f",1))){phone_uri(v,vlen,from);}
        }off=(size_t)(end-s)+1;
    }
    if(privacy || duplicate_pai)return 0;
    if(asserted[0])strcpy(out,asserted);else if(from[0])strcpy(out,from);else return 0;
    return 1;
}
