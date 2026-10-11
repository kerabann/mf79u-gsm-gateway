/* RAM-only LD_PRELOAD observer. FD 3 carries only SIP method/status names
 * and IPsec call results. Never emits payloads, addresses, identities or keys.
 * Link without a GNU libc dependency: the target uses vendor uClibc. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>
#include "vendor-ipsec-uapi.h"
static int logfd=3;
static void metadata(const void *buffer,size_t len,int tx) {
    const char *s=buffer;char out[64];int n=0;
    if(len>=11 && !memcmp(s,"SIP/2.0 ",8) &&
       s[8]>='1' && s[8]<='6' && s[9]>='0' && s[9]<='9' && s[10]>='0' && s[10]<='9')
        n=snprintf(out,sizeof(out),"%s SIP response %.3s\n",tx?"TX":"RX",s+8);
    else {
        const char *methods[]={"REGISTER","INVITE","ACK","BYE","CANCEL","OPTIONS",
                               "SUBSCRIBE","NOTIFY","PRACK","UPDATE"};
        for(unsigned i=0;i<sizeof(methods)/sizeof(methods[0]);i++) {
            size_t m=strlen(methods[i]);
            if(len>m && !memcmp(s,methods[i],m) && s[m]==' ') {
                n=snprintf(out,sizeof(out),"%s SIP method %s\n",tx?"TX":"RX",methods[i]);break;
            }
        }
    }
    if(n>0 && n<(int)sizeof(out))write(logfd,out,(size_t)n);
}
ssize_t sendto(int fd,const void *b,size_t n,int flags,const struct sockaddr *a,socklen_t l) {
    ssize_t (*real)(int,const void*,size_t,int,const struct sockaddr*,socklen_t)=dlsym(RTLD_NEXT,"sendto");
    if(!real){errno=ENOSYS;return -1;}
    ssize_t r=real(fd,b,n,flags,a,l);int saved=errno;if(r>0)metadata(b,(size_t)r,1);errno=saved;return r;
}
ssize_t send(int fd,const void *b,size_t n,int flags) {
    ssize_t (*real)(int,const void*,size_t,int)=dlsym(RTLD_NEXT,"send");
    if(!real){errno=ENOSYS;return -1;}
    ssize_t r=real(fd,b,n,flags);int saved=errno;if(r>0)metadata(b,(size_t)r,1);errno=saved;return r;
}
ssize_t recvfrom(int fd,void *b,size_t n,int flags,struct sockaddr *a,socklen_t *l) {
    ssize_t (*real)(int,void*,size_t,int,struct sockaddr*,socklen_t*)=dlsym(RTLD_NEXT,"recvfrom");
    if(!real){errno=ENOSYS;return -1;}
    ssize_t r=real(fd,b,n,flags,a,l);int saved=errno;if(r>0)metadata(b,(size_t)r,0);errno=saved;return r;
}
ssize_t recv(int fd,void *b,size_t n,int flags) {
    ssize_t (*real)(int,void*,size_t,int)=dlsym(RTLD_NEXT,"recv");
    if(!real){errno=ENOSYS;return -1;}
    ssize_t r=real(fd,b,n,flags);int saved=errno;if(r>0)metadata(b,(size_t)r,0);errno=saved;return r;
}
static void result(const char *name,int r) {
    char out[64];int n=snprintf(out,sizeof(out),"%s result=%d\n",name,r);
    if(n>0 && n<(int)sizeof(out))write(logfd,out,(size_t)n);
}
int ipsec_set(int fd,void *config,int length) {
    /* uClibc RTLD_NEXT resolves libc sockets here, but does not reliably find
     * the earlier-loaded libsoftap. Resolve its existing handle explicitly. */
    void *handle=dlopen("/lib/libsoftap.so",RTLD_LAZY);
    int (*real)(int,void*,int)=handle?dlsym(handle,"ipsec_set"):NULL;
    if(!real || real==ipsec_set){if(handle)dlclose(handle);result("IPSEC_SET lookup failed",-1);errno=ENOSYS;return -1;}
    if(config && length==404){
        const struct vendor_ipsec_sa *sa=config;
        const char *dir=!memcmp(sa->direction,"out\0",4)?"out":!memcmp(sa->direction,"in\0",3)?"in":"unknown";
        const char *alg="unknown",*enc="unknown";
        const char *auths[]={"hmac-md5-96","hmac-sha-1-96","hmac(md5)","hmac(sha1)"};
        const char *encs[]={"null","aes-cbc","des-ede3-cbc","ecb(cipher_null)","cbc(aes)","cbc(des3_ede)"};
        for(unsigned i=0;i<sizeof(auths)/sizeof(auths[0]);i++)
            if(!memcmp(sa->authentication_algorithm,auths[i],strlen(auths[i])+1))alg=auths[i];
        for(unsigned i=0;i<sizeof(encs)/sizeof(encs[0]);i++)
            if(!memcmp(sa->encryption_algorithm,encs[i],strlen(encs[i])+1))enc=encs[i];
        char out[120];int n=snprintf(out,sizeof(out),"IPSEC SA direction=%s family=%u authentication=%s encryption=%s\n",dir,sa->family,alg,enc);
        if(n>0 && n<(int)sizeof(out))write(logfd,out,(size_t)n);
    }
    write(logfd,"IPSEC_SET begin\n",16);int r=real(fd,config,length);int saved=errno;
    result("IPSEC_SET",r);dlclose(handle);errno=saved;return r;
}
int system(const char *command) {
    int (*real)(const char*)=dlsym(RTLD_NEXT,"system");
    if(!real){errno=ENOSYS;return -1;}
    int xfrm=command && !strncmp(command,"ip xfrm ",8);
    if(xfrm)write(logfd,"XFRM_COMMAND begin\n",19);
    int r=real(command);int saved=errno;if(xfrm)result("XFRM_COMMAND",r);errno=saved;return r;
}
__attribute__((constructor)) static void ready(void) {
    int fd=fcntl(3,F_DUPFD,198);if(fd>=0)logfd=fd;
    write(logfd,"READY SIP metadata observer\n",28);
}
