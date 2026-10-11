#include "caller-id.h"
#include "ims-register-response.h"

/* RAM-only B03 IMS ESP transport. IPv4/UDP transport mode only.
 * Negotiated SAs and keys stay in this process; no key or SIP body logging.
 * AES/HMAC use the modem's existing OpenSSL 1.0.0, not a replacement cipher. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <net/if.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include "vowifi-access.h"
#include <string.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/time.h>
#include <sys/uio.h>
#include <unistd.h>
#include "esp-null.h"
#include "vendor-ipsec-uapi.h"
#include "ipv4-fragments.h"
#include "ims-software-media.h"
#include "amr-rate-policy.h"
#include "vendor-codecs.h"
#include <stdlib.h>

/* Stable OpenSSL 1.0.0 ARM32 AES_KEY layout and function interfaces. */
typedef struct {unsigned int rd_key[60];int rounds;} aes_key;
extern int AES_set_encrypt_key(const unsigned char*,int,aes_key*);
extern int AES_set_decrypt_key(const unsigned char*,int,aes_key*);
extern void AES_cbc_encrypt(const unsigned char*,unsigned char*,size_t,const aes_key*,unsigned char*,int);
extern const void *EVP_md5(void);
extern const void *EVP_sha1(void);
extern unsigned char *HMAC(const void*,const void*,int,const unsigned char*,size_t,unsigned char*,unsigned int*);
extern int RAND_bytes(unsigned char*,int);

struct association {
    int used,incoming,cbc,sha1,last_next_header;struct in_addr src,dst;uint16_t sport,dport;
    unsigned char auth_key[32];int auth_len;aes_key encrypt,decrypt;
    struct esp_null_sa esp;
};
static struct association sas[8];static volatile int locked;
static int logfd=3,txfd=-1,rxfd=-1,injectfd=-1,started;
static unsigned wan_mtu;static uint16_t ip_id;
static ssize_t (*original_sendto)(int,const void*,size_t,int,const struct sockaddr*,socklen_t);
static ssize_t (*original_send)(int,const void*,size_t,int);
static ssize_t (*original_recvfrom)(int,void*,size_t,int,struct sockaddr*,socklen_t*);
static ssize_t (*original_recv)(int,void*,size_t,int);
static int (*original_connect)(int,const struct sockaddr*,socklen_t);
static ssize_t (*original_writev)(int,const struct iovec*,int);
static int (*original_open)(const char*,int,...);
static int (*original_ioctl)(int,unsigned long,...);
static int (*original_close)(int);
static ssize_t (*original_read)(int,void*,size_t);
static ssize_t (*original_write)(int,const void*,size_t);
static int (*original_resource)(const void*,void*);
static int (*original_preopen)(const void*);
static int (*original_preclose)(void);
static int (*original_setschedparam)(pthread_t,int,const struct sched_param*);
static int (*original_stacksize)(pthread_attr_t*,size_t);
static void (*original_assert)(const char*,const char*,int,const char*);
static unsigned synthetic_codec_test;
static struct mf79u_amr_policy amr_policy;static volatile int amr_locked;
static void log_result(const char *,long);
static unsigned operator_codecs,operator_preferred;
int pthread_attr_setstacksize(pthread_attr_t *attr,size_t size){
    if(!original_stacksize)return ENOSYS;
    /* B03 gives PJMEDIA workers 32 KiB. The software wideband encoder and
     * SDP handling need more headroom than the original hardware codecs. */
    if((operator_codecs || synthetic_codec_test) && size<256*1024){
        log_result("SOFTWARE worker original stack bytes",(long)size);
        size=256*1024;
        log_result("SOFTWARE worker selected stack bytes",(long)size);
    }
    return original_stacksize(attr,size);
}
static void *native_pipeline_worker(void *result){
    *(int*)result=mf79u_vendor_amr_packet_selftest();return NULL;
}
static ssize_t select_operator_offer(void *buffer,size_t length,size_t capacity){
    if(!operator_codecs || length<7 || memcmp(buffer,"INVITE ",7))return (ssize_t)length;
    unsigned char *selected=malloc(7001);if(!selected)return (ssize_t)length;
    size_t n=mf79u_codec_offer(buffer,length,selected,7001,operator_preferred);
    if(n && n<=capacity){memcpy(buffer,selected,n);log_result("OPERATOR codec offer selected",operator_preferred);}
    else n=length;
    free(selected);return (ssize_t)n;
}
static void amr_lock(void){while(__sync_lock_test_and_set(&amr_locked,1))usleep(200);}
static void amr_unlock(void){__sync_lock_release(&amr_locked);}
static void lock(void){while(__sync_lock_test_and_set(&locked,1))usleep(250);}
static void unlock(void){__sync_lock_release(&locked);}
static void wipe(void *pointer,size_t len){volatile unsigned char *p=pointer;while(len--)*p++=0;}
static uint16_t get16(const unsigned char *s){return (uint16_t)s[0]<<8|s[1];}
static uint32_t get32(const unsigned char *s){return (uint32_t)s[0]<<24|(uint32_t)s[1]<<16|(uint32_t)s[2]<<8|s[3];}
static void put16(unsigned char *s,unsigned value){s[0]=value>>8;s[1]=value;}
static void log_result(const char *name,long result){char out[100];int n=snprintf(out,sizeof(out),"%s result=%ld\n",name,result);if(n>0 && n<(int)sizeof(out))write(logfd,out,(size_t)n);}
__attribute__((noreturn)) void __assert(const char *expression,const char *file,int line,const char *function){
    if(operator_codecs)log_result("NATIVE codec assertion line",line);
    if(synthetic_codec_test){log_result("NATIVE synthetic codec assertion line",line);_exit(92);}
    if(original_assert)original_assert(expression,file,line,function);
    _exit(91);
}
static void sip_metadata(const char *direction,const void *buffer,size_t len){
    const char *s=buffer;char out[100];int n=0;
    unsigned registration_code=mf79u_register_response(buffer,len);
    if(!strncmp(direction,"RX",2) && registration_code)log_result("IMS REGISTER response code",registration_code);
    if(!strncmp(direction,"RX",2) && len>=7 && !memcmp(s,"INVITE ",7)){
        char caller[40];mf79u_caller_id(buffer,len,caller);
        int fd=open("/dev/.mf79u-incoming-caller.tmp",O_WRONLY|O_CREAT|O_TRUNC,0600);
        if(fd>=0){size_t size=strlen(caller);if(write(fd,caller,size)==(ssize_t)size)rename("/dev/.mf79u-incoming-caller.tmp","/dev/.mf79u-incoming-caller");close(fd);}
    }

    if(len>=11 && !memcmp(s,"SIP/2.0 ",8) && s[8]>='1' && s[8]<='6' && s[9]>='0' && s[9]<='9' && s[10]>='0' && s[10]<='9')
        n=snprintf(out,sizeof(out),"%s SIP response %.3s bytes=%u\n",direction,s+8,(unsigned)len);
    else {const char *methods[]={"REGISTER","INVITE","ACK","BYE","CANCEL","OPTIONS","SUBSCRIBE","NOTIFY","PRACK","UPDATE","MESSAGE"};
        for(unsigned i=0;i<sizeof(methods)/sizeof(methods[0]);i++){
            size_t m=strlen(methods[i]);if(len>m && !memcmp(s,methods[i],m) && s[m]==' '){
                n=snprintf(out,sizeof(out),"%s SIP method %s bytes=%u\n",direction,methods[i],(unsigned)len);break;}
        }
    }
    if(n>0 && n<(int)sizeof(out)){
        write(logfd,out,(size_t)n);
        if(len>9 && !memcmp(s,"REGISTER ",9)) {
            int smsip=0;
            for(size_t i=0;i+13<=len;i++)if(!memcmp(s+i,"+g.3gpp.smsip",13)){smsip=1;break;}
            log_result("SMS registration capability",smsip);
        }
        if(len>=13 && !memcmp(s,"SIP/2.0 ",8) && s[8]>='4' && s[8]<='6'){
            const char *end=memchr(s+12,'\r',len-12);size_t words=end?(size_t)(end-s-12):0;
            int safe=words>0 && words<64;
            for(size_t i=0;i<words && safe;i++){
                char c=s[12+i];safe=(c>='a' && c<='z') || (c>='A' && c<='Z') || c==' ' || c=='-';
            }
            if(safe){n=snprintf(out,sizeof(out),"%s SIP error reason %.*s\n",direction,(int)words,s+12);if(n>0 && n<(int)sizeof(out))write(logfd,out,(size_t)n);}
            for(size_t off=0;off<len;){
                const char *line=s+off,*nl=memchr(line,'\n',len-off);size_t width=nl?(size_t)(nl-line):len-off;
                if(width>12 && !strncasecmp(line,"Retry-After:",12)){
                    size_t i=12;unsigned delay=0,digits=0;while(i<width && (line[i]==' ' || line[i]=='\t'))i++;
                    while(i<width && line[i]>='0' && line[i]<='9' && digits<5){delay=delay*10+(unsigned)(line[i++]-'0');digits++;}
                    if(digits && delay<=3600)log_result("SIP registration retry after seconds",delay);
                }
                off+=width+(nl?1:0);
            }
        }
        amr_lock();
        mf79u_amr_observe(&amr_policy,!strncmp(direction,"TX",2),buffer,len,logfd);amr_unlock();
    }
}
/* Touch only a validated RTP/AMR datagram on both SDP-negotiated endpoints.
 * Use a bounded copy; never mutate the vendor's original packet buffer. */
static const void *prefer_amr(int fd,const void *buffer,size_t len,const struct sockaddr *address,socklen_t address_len,
                              unsigned char copy[2048]){
    if(len<14 || len>2048 || !address || address_len<sizeof(struct sockaddr_in) || address->sa_family!=AF_INET)return buffer;
    if((((const unsigned char*)buffer)[0]>>6)!=2)return buffer;
    int type=0;socklen_t size=sizeof(type);if(getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&size) || type!=SOCK_DGRAM)return buffer;
    struct sockaddr_in local;size=sizeof(local);
    if(getsockname(fd,(struct sockaddr*)&local,&size) || local.sin_family!=AF_INET)return buffer;
    const struct sockaddr_in *peer=(const void*)address;amr_lock();
    int changed=mf79u_amr_rewrite(&amr_policy,ntohs(local.sin_port),peer->sin_addr.s_addr,ntohs(peer->sin_port),buffer,len,copy,2048);
    if(changed && amr_policy.changed==1)log_result("AMR first negotiated CMR preference applied",1);
    amr_unlock();return changed?copy:buffer;
}
/* Observe only named media devices and ioctl IDs; never argument buffers. */
int open(const char *path,int flags,...){
    mode_t mode=0;
    if(flags&O_CREAT){va_list arguments;va_start(arguments,flags);mode=va_arg(arguments,int);va_end(arguments);}
    if(!original_open){errno=ENOSYS;return -1;}
    int kind=mf79u_media_path(path);
    if(kind){int fd=original_open("/dev/null",O_RDWR);
        if(fd>=0 && mf79u_media_register(fd,kind)){original_close(fd);return -1;}
        log_result("SOFTWARE media device opened",kind);return fd;}
    int result=original_open(path,flags,mode),saved=errno;
    if(!strcmp(path,"/dev/amr_device") || !strcmp(path,"/dev/volte_device") || !strcmp(path,"/dev/voice_device")){
        log_result(path,result);if(result<0)log_result("MEDIA open errno",saved);
    }
    errno=saved;return result;
}
int ioctl(int fd,unsigned long request,...){
    va_list arguments;va_start(arguments,request);void *argument=va_arg(arguments,void*);va_end(arguments);
    if(!original_ioctl){errno=ENOSYS;return -1;}
    if(mf79u_media_kind(fd)){int result=mf79u_media_ioctl(fd,request,argument),saved=errno;
        log_result("SOFTWARE media ioctl",request);log_result("SOFTWARE media result",result);
        if(result<0)log_result("SOFTWARE media errno",saved);
        errno=saved;return result;}
    int result=original_ioctl(fd,request,argument),saved=errno;
    if(((request>>8)&255)==0x76){
        log_result("MEDIA ioctl request",request);log_result("MEDIA ioctl fd",fd);log_result("MEDIA ioctl return",result);
        if(result<0)log_result("MEDIA ioctl errno",saved);
    }
    errno=saved;return result;
}
int close(int fd){
    if(!original_close){errno=ENOSYS;return -1;}
    mf79u_media_close(fd);return original_close(fd);
}
ssize_t read(int fd,void *buffer,size_t size){
    if(mf79u_media_kind(fd)==2)return mf79u_media_read(fd,buffer,size);
    if(!original_read){errno=ENOSYS;return -1;}return original_read(fd,buffer,size);
}
ssize_t write(int fd,const void *buffer,size_t size){
    if(mf79u_media_kind(fd)==2)return mf79u_media_write(fd,buffer,size);
    if(!original_write){errno=ENOSYS;return -1;}return original_write(fd,buffer,size);
}
int audio_resource_request(const void *request,void *response){
    if(mf79u_media_resource(request,response)){log_result("SOFTWARE PCM resource owned",1);return 1;}
    if(!original_resource){errno=ENOSYS;return 0;}return original_resource(request,response);
}
int zDrvVolte_PreOpen(const void *config){
    int result=mf79u_media_preopen(config);
    if(result){log_result("SOFTWARE PCM preopen",result);return result>0?0:-1;}
    if(!original_preopen){errno=ENOSYS;return -1;}return original_preopen(config);
}
int zDrvVolte_PreClose(void){
    if(mf79u_media_path("/dev/volte_device")){log_result("SOFTWARE PCM preclose",0);return 0;}
    if(!original_preclose){errno=ENOSYS;return -1;}return original_preclose();
}
int pthread_setschedparam(pthread_t thread,int policy,const struct sched_param *parameters){
    if(!original_setschedparam)return ENOSYS;
    if(mf79u_media_path("/dev/volte_device")){
        struct sched_param normal={.sched_priority=0};
        int result=original_setschedparam(thread,SCHED_OTHER,&normal);
        log_result("SOFTWARE media thread normal scheduling",result);return result;
    }
    return original_setschedparam(thread,policy,parameters);
}
static unsigned sum_bytes(const unsigned char *p,size_t n){unsigned sum=0;while(n>=2){sum+=get16(p);p+=2;n-=2;}if(n)sum+=(unsigned)*p<<8;return sum;}
static uint16_t finish_sum(unsigned sum){while(sum>>16)sum=(sum&65535)+(sum>>16);return (uint16_t)~sum;}
static void ipv4_header(unsigned char *p,size_t total,unsigned proto,struct in_addr src,struct in_addr dst){
    memset(p,0,20);p[0]=0x45;put16(p+2,(unsigned)total);p[8]=64;p[9]=(unsigned char)proto;
    memcpy(p+12,&src,4);memcpy(p+16,&dst,4);put16(p+10,finish_sum(sum_bytes(p,20)));
}
static int digest(void *context,const unsigned char *data,size_t len,unsigned char out[32]){
    struct association *sa=context;unsigned int n=0;
    if(!HMAC(sa->sha1?EVP_sha1():EVP_md5(),sa->auth_key,sa->auth_len,data,len,out,&n))return -1;
    return (int)n;
}
static int cipher(void *context,int encrypt,const unsigned char iv[16],const unsigned char *in,size_t n,unsigned char *out){
    struct association *sa=context;unsigned char copy[16];memcpy(copy,iv,16);
    AES_cbc_encrypt(in,out,n,encrypt?&sa->encrypt:&sa->decrypt,copy,encrypt);
    if(!encrypt && sa->used && sa->incoming && n>=2)sa->last_next_header=out[n-1];
    wipe(copy,16);return 0;
}
static int random_iv(void *context,unsigned char *out,size_t n){(void)context;return n==16 && RAND_bytes(out,16)==1?0:-1;}
static int same_string(const char *field,size_t size,const char *wanted){size_t n=strlen(wanted);return n<size && !memcmp(field,wanted,n+1);}
static void log_mode(const char field[16]){
    size_t n=strnlen(field,16);if(n==16)return;
    for(size_t i=0;i<n;i++)if(!((field[i]>='a' && field[i]<='z') || (field[i]>='A' && field[i]<='Z') || field[i]=='-'))return;
    char out[64];int count=snprintf(out,sizeof(out),"ESP vendor mode=%.*s length=%u\n",(int)n,field,(unsigned)n);
    if(count>0 && count<(int)sizeof(out))write(logfd,out,(size_t)count);
}
static int unhex(const char *input,size_t capacity,unsigned char *output,size_t max){
    size_t len=strnlen(input,capacity);if(len==capacity || len%2 || len/2>max)return -1;
    for(size_t i=0;i<len/2;i++){
        unsigned value=0;
        for(unsigned j=0;j<2;j++){unsigned char c=input[i*2+j];unsigned x;
            if(c>='0' && c<='9')x=c-'0';else if(c>='a' && c<='f')x=c-'a'+10;
            else if(c>='A' && c<='F')x=c-'A'+10;else return -1;
            value=value*16+x;
        }
        output[i]=(unsigned char)value;
    }
    return (int)(len/2);
}
static void *receive_esp(void *unused){
    (void)unused;unsigned char packet[8192],udp[8192],injected[8212];
    for(;;){ssize_t n=original_recvfrom(rxfd,packet,sizeof(packet),0,NULL,NULL);
        if(n<0){if(errno!=EINTR && errno!=EAGAIN && errno!=EWOULDBLOCK)usleep(10000);continue;}
        if(n<52 || packet[0]>>4!=4 || packet[9]!=50)continue;
        unsigned ihl=(packet[0]&15)*4;size_t total=get16(packet+2);
        if(ihl<20 || total>(size_t)n || total<ihl+32 || (get16(packet+6)&0x3fff))continue;
        struct in_addr src,dst;memcpy(&src,packet+12,4);memcpy(&dst,packet+16,4);
        uint32_t spi=get32(packet+ihl);lock();struct association *sa=NULL;
        for(unsigned i=0;i<8;i++)if(sas[i].used && sas[i].incoming && sas[i].esp.spi==spi &&
            sas[i].src.s_addr==src.s_addr && sas[i].dst.s_addr==dst.s_addr){sa=&sas[i];break;}
        if(!sa){unlock();continue;}
        sa->last_next_header=-1;
        int size=sa->cbc?esp_cbc_decode(&sa->esp,packet+ihl,total-ihl,udp,sizeof(udp),digest,cipher,sa):
                         esp_null_decode(&sa->esp,packet+ihl,total-ihl,udp,sizeof(udp),digest,sa);
        if(size<8){int protocol=sa->last_next_header;unlock();
            if(protocol>=0 && protocol!=17)log_result("ESP authenticated unsupported next header",protocol);
            else log_result("ESP RX rejected integrity/replay/format",-1);
            continue;}
        log_result("ESP verified source port",get16(udp));log_result("ESP verified destination port",get16(udp+2));
        if(get16(udp)!=sa->sport || get16(udp+2)!=sa->dport || get16(udp+4)!=size){unlock();log_result("ESP RX rejected UDP selectors",-1);continue;}
        ipv4_header(injected,(size_t)size+20,17,src,dst);memcpy(injected+20,udp,(size_t)size);
        struct sockaddr_in target={.sin_family=AF_INET,.sin_addr=dst};
        ssize_t sent=original_sendto(injectfd,injected,(size_t)size+20,0,(struct sockaddr*)&target,sizeof(target));
        if(sent==size+20)sip_metadata("RX_ESP verified",udp+8,(size_t)size-8);
        else log_result("ESP UDP injection failed errno",errno);
        unlock();
    }
    return NULL;
}
static const char *ims_interface(void){const char *s=getenv("MF79U_IMS_INTERFACE");return s && !strcmp(s,"vowifi0")?"vowifi0":"wan5";}
static int raw_socket(int proto,int bind_wan){
    int fd=socket(AF_INET,SOCK_RAW,proto);if(fd<0)return -1;
    fcntl(fd,F_SETFD,FD_CLOEXEC);int one=1;
    if((proto==IPPROTO_RAW && setsockopt(fd,IPPROTO_IP,IP_HDRINCL,&one,sizeof(one))) ||
       (bind_wan && setsockopt(fd,SOL_SOCKET,SO_BINDTODEVICE,ims_interface(),strlen(ims_interface())+1))){int saved=errno;close(fd);errno=saved;return -1;}
    return fd;
}
static int start_transport(void){
    if(started)return 0;
    if(!original_sendto || !original_recvfrom){errno=ENOSYS;return -1;}
    int wifi=!strcmp(ims_interface(),"vowifi0");
    txfd=raw_socket(IPPROTO_RAW,1);rxfd=raw_socket(IPPROTO_ESP,!wifi);injectfd=raw_socket(IPPROTO_RAW,0);
    if(txfd<0 || rxfd<0 || injectfd<0)goto fail;
    if(wifi){
        /* SWu injects authenticated inner packets through local IP routing.
         * Receive on the assigned VIP; SO_BINDTODEVICE would discard this
         * loopback delivery. Source/destination/SPI/MAC checks remain below. */
        struct ifreq local={0};strcpy(local.ifr_name,ims_interface());
        if(ioctl(rxfd,SIOCGIFADDR,&local) || bind(rxfd,&local.ifr_addr,sizeof(struct sockaddr_in)))goto fail;
    }
    struct ifreq interface={0};strcpy(interface.ifr_name,ims_interface());
    if(ioctl(txfd,SIOCGIFMTU,&interface) || interface.ifr_mtu<576 || interface.ifr_mtu>65535)goto fail;
    wan_mtu=(unsigned)interface.ifr_mtu;ip_id=(uint16_t)getpid();log_result("ESP IMS interface MTU",wan_mtu);
    struct timeval timeout={.tv_sec=1};if(setsockopt(rxfd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout)))goto fail;
    pthread_t thread;if(pthread_create(&thread,NULL,receive_esp,NULL)){errno=EAGAIN;goto fail;}
    pthread_detach(thread);started=1;log_result("USERSPACE ESP transport ready",0);return 0;
fail: {int saved=errno;if(txfd>=0)close(txfd);if(rxfd>=0)close(rxfd);if(injectfd>=0)close(injectfd);
    txfd=rxfd=injectfd=-1;errno=saved;return -1;}
}
int ipsec_set(int fd,void *config,int length){
    if(fd<0 || !config || length!=404){errno=EINVAL;return -1;}
    const struct vendor_ipsec_sa *v=config;struct association value={0};unsigned char encryption_key[32]={0};int stage=1;
    stage=11;if(v->family!=1)goto unsupported;
    stage=12;if(!same_string(v->protocol,16,"esp"))goto unsupported;
    /* B03 passes the iproute2 transport-mode abbreviation "trans". */
    stage=13;if(!same_string(v->mode,16,"transport") && !same_string(v->mode,16,"trans")){log_mode(v->mode);goto unsupported;}
    stage=2;
    if(same_string(v->direction,8,"in"))value.incoming=1;else if(!same_string(v->direction,8,"out"))goto unsupported;
    stage=3;
    if(same_string(v->authentication_algorithm,16,"hmac-sha-1-96"))value.sha1=1;
    else if(!same_string(v->authentication_algorithm,16,"hmac-md5-96"))goto unsupported;
    stage=4;
    if(same_string(v->encryption_algorithm,16,"aes-cbc"))value.cbc=1;
    else if(!same_string(v->encryption_algorithm,16,"null"))goto unsupported;
    stage=5;
    if(!memchr(v->src4,0,32) || !memchr(v->dst4,0,32) || inet_pton(AF_INET,v->src4,&value.src)!=1 || inet_pton(AF_INET,v->dst4,&value.dst)!=1)goto unsupported;
    stage=6;
    value.auth_len=unhex(v->authentication_key_hex,64,value.auth_key,sizeof(value.auth_key));
    log_result("ESP authentication key bytes",value.auth_len);
    if(value.auth_len<16 || !v->spi)goto unsupported;
    stage=7;
    if(value.cbc){int bytes=unhex(v->encryption_key_hex,64,encryption_key,sizeof(encryption_key));
        log_result("ESP encryption key bytes",bytes);
        if(bytes!=16 || AES_set_encrypt_key(encryption_key,128,&value.encrypt) || AES_set_decrypt_key(encryption_key,128,&value.decrypt))goto unsupported;}
    wipe(encryption_key,sizeof(encryption_key));value.sport=v->sport;value.dport=v->dport;value.esp.spi=v->spi;value.used=1;
    lock();if(start_transport()){int saved=errno;unlock();wipe(&value,sizeof(value));log_result("ESP transport initialization failed errno",saved);errno=saved;return -1;}
    int slot=-1;for(unsigned i=0;i<8;i++)if(sas[i].used && sas[i].incoming==value.incoming &&
        ((sas[i].esp.spi==value.esp.spi && sas[i].src.s_addr==value.src.s_addr && sas[i].dst.s_addr==value.dst.s_addr) ||
         (sas[i].src.s_addr==value.src.s_addr && sas[i].dst.s_addr==value.dst.s_addr &&
          sas[i].sport==value.sport && sas[i].dport==value.dport))){slot=(int)i;break;}
    if(slot<0)for(unsigned i=0;i<8;i++)if(!sas[i].used){slot=(int)i;break;}
    if(slot<0){unlock();wipe(&value,sizeof(value));errno=ENOSPC;return -1;}
    wipe(&sas[slot],sizeof(sas[slot]));sas[slot]=value;unlock();wipe(&value,sizeof(value));
    log_result("USERSPACE ESP SA installed",slot);log_result("ESP SA source port",v->sport);log_result("ESP SA destination port",v->dport);return 0;
unsupported:
    wipe(encryption_key,sizeof(encryption_key));wipe(&value,sizeof(value));errno=ENOTSUP;log_result("USERSPACE ESP unsupported SA stage",stage);return -1;
}
int ipsec_del(int fd,void *config,int length){
    (void)fd;if(!config || length!=404){errno=EINVAL;return -1;}
    const struct vendor_ipsec_sa *v=config;int incoming=same_string(v->direction,8,"in");
    lock();for(unsigned i=0;i<8;i++)if(sas[i].used && sas[i].esp.spi==v->spi && sas[i].incoming==incoming)wipe(&sas[i],sizeof(sas[i]));unlock();
    log_result("USERSPACE ESP SA removed",0);return 0;
}
struct raw_destination {int flags;struct sockaddr_in address;};
static int emit_fragment(void *context,const unsigned char *packet,size_t len){
    struct raw_destination *destination=context;
    ssize_t n=original_sendto(txfd,packet,len,destination->flags,(void*)&destination->address,sizeof(destination->address));
    if(n==(ssize_t)len)return 0;
    if(n>=0)errno=EIO;
    return -1;
}
static ssize_t protected_send(int fd,const void *buffer,size_t len,int flags,const struct sockaddr *address,socklen_t address_len,int *handled){
    *handled=0;if(!address || address_len<sizeof(struct sockaddr_in) || address->sa_family!=AF_INET)return -1;
    int type=0;socklen_t size=sizeof(type);if(getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&size) || type!=SOCK_DGRAM)return -1;
    struct sockaddr_in local;size=sizeof(local);if(getsockname(fd,(struct sockaddr*)&local,&size) || local.sin_family!=AF_INET)return -1;
    const struct sockaddr_in *peer=(const void*)address;lock();struct association *sa=NULL;int protected_peer=0;
    for(unsigned i=0;i<8;i++)if(sas[i].used && !sas[i].incoming && sas[i].dst.s_addr==peer->sin_addr.s_addr){
        protected_peer=1;
        if((!local.sin_addr.s_addr || sas[i].src.s_addr==local.sin_addr.s_addr) &&
           sas[i].sport==ntohs(local.sin_port) && sas[i].dport==ntohs(peer->sin_port)){sa=&sas[i];break;}
    }
    if(!sa){unlock();if(protected_peer){*handled=1;errno=EACCES;log_result("ESP protected peer selectors unmatched",-1);}return -1;}*handled=1;
    if(len>7000){unlock();errno=EMSGSIZE;return -1;}
    unsigned char udp[7008],packet[7100];put16(udp,sa->sport);put16(udp+2,sa->dport);put16(udp+4,(unsigned)len+8);put16(udp+6,0);memcpy(udp+8,buffer,len);
    unsigned sum=sum_bytes((const void*)&sa->src,4)+sum_bytes((const void*)&sa->dst,4)+17+(unsigned)len+8+sum_bytes(udp,len+8);
    uint16_t check=finish_sum(sum);put16(udp+6,check?check:65535);
    int encoded=sa->cbc?esp_cbc_encode(&sa->esp,udp,len+8,packet+20,sizeof(packet)-20,digest,cipher,random_iv,sa):
                        esp_null_encode(&sa->esp,udp,len+8,packet+20,sizeof(packet)-20,digest,sa);
    if(encoded<0){unlock();errno=EIO;return -1;}
    ipv4_header(packet,(size_t)encoded+20,50,sa->src,sa->dst);
    struct raw_destination target={.flags=flags,.address={.sin_family=AF_INET,.sin_addr=sa->dst}};
    if(!++ip_id)++ip_id;
    int fragments=ipv4_emit_fragments(packet,(size_t)encoded+20,wan_mtu,ip_id,emit_fragment,&target),saved=errno;
    if(fragments>0){sip_metadata("TX_ESP protected",buffer,len);log_result("ESP IPv4 fragments sent",fragments);}
    else log_result("ESP raw send failed errno",saved);
    unlock();errno=saved;return fragments>0?(ssize_t)len:-1;
}
static ssize_t ims_sendto(int fd,const void *buffer,size_t len,int flags,const struct sockaddr *address,socklen_t size){
    char access[7100];size_t wire=0;
    if(!strcmp(ims_interface(),"vowifi0") && getenv("MF79U_VOWIFI_USB"))wire=vowifi_access_header_kind(buffer,len,NULL,access,sizeof(access),1);
    else if(!strcmp(ims_interface(),"vowifi0")){char node[13]={0};FILE *f=fopen("/dev/mf79u/wifi-node-id","r");if(f){if(fread(node,1,12,f)==12)wire=vowifi_access_header(buffer,len,node,access,sizeof(access));fclose(f);}}
    if(wire)buffer=access;else wire=len;
    int handled=0;ssize_t n=protected_send(fd,buffer,wire,flags,address,size,&handled);
    if(!handled && original_sendto)n=original_sendto(fd,buffer,wire,flags,address,size);
    return n==(ssize_t)wire?(ssize_t)len:n;
}
ssize_t sendto(int fd,const void *buffer,size_t len,int flags,const struct sockaddr *address,socklen_t size){
    unsigned char copy[2048];buffer=prefer_amr(fd,buffer,len,address,size,copy);
    ssize_t n=ims_sendto(fd,buffer,len,flags,address,size);int saved=errno;
    if(n>0)sip_metadata("TX",buffer,(size_t)n);
    errno=saved;return n;

}
ssize_t send(int fd,const void *buffer,size_t len,int flags){
    struct sockaddr_storage peer;socklen_t size=sizeof(peer);ssize_t n;unsigned char copy[2048];
    if(!getpeername(fd,(struct sockaddr*)&peer,&size)){
        buffer=prefer_amr(fd,buffer,len,(struct sockaddr*)&peer,size,copy);
        n=ims_sendto(fd,buffer,len,flags,(struct sockaddr*)&peer,size);return n;}
    if(!original_send){errno=ENOSYS;return -1;}n=original_send(fd,buffer,len,flags);int saved=errno;
    if(n>0)sip_metadata("TX",buffer,(size_t)n);
    errno=saved;return n;
}
int connect(int fd,const struct sockaddr *address,socklen_t size){
    if(!original_connect){errno=ENOSYS;return -1;}
    if(address && size>=sizeof(struct sockaddr_in) && address->sa_family==AF_INET){
        int type=0;socklen_t bytes=sizeof(type);
        if(!getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&bytes)){
            log_result("SOCKET connect type",type);log_result("SOCKET connect destination port",ntohs(((const struct sockaddr_in*)address)->sin_port));
            if(type==SOCK_STREAM){int protected_peer=0;lock();
                for(unsigned i=0;i<8;i++)if(sas[i].used && !sas[i].incoming &&
                    sas[i].dst.s_addr==((const struct sockaddr_in*)address)->sin_addr.s_addr)protected_peer=1;
                unlock();if(protected_peer){log_result("ESP TCP unsupported; refusing plaintext connection",-1);errno=EPROTONOSUPPORT;return -1;}}
        }
    }
    int result=original_connect(fd,address,size),saved=errno;log_result("SOCKET connect result",result);
    if(result<0)log_result("SOCKET connect errno",saved);
    errno=saved;return result;
}
ssize_t writev(int fd,const struct iovec *parts,int count){
    if(!original_writev){errno=ENOSYS;return -1;}
    int type=0;socklen_t size=sizeof(type);unsigned char buffer[7000];size_t total=0;
    if(parts && count>0 && count<=64 && !getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&size)){
        for(int i=0;i<count;i++){if(parts[i].iov_len>sizeof(buffer)-total){total=0;break;}
            memcpy(buffer+total,parts[i].iov_base,parts[i].iov_len);total+=parts[i].iov_len;}
        if(total){
            if(type==SOCK_DGRAM){struct sockaddr_storage peer;size=sizeof(peer);
                if(!getpeername(fd,(struct sockaddr*)&peer,&size)){
                    unsigned char copy[2048];const void *payload=prefer_amr(fd,buffer,total,(struct sockaddr*)&peer,size,copy);
                    return ims_sendto(fd,payload,total,0,(struct sockaddr*)&peer,size);}}
            sip_metadata("TX_WRITEV",buffer,total);
        }
    }
    return original_writev(fd,parts,count);
}
ssize_t recvfrom(int fd,void *buffer,size_t len,int flags,struct sockaddr *address,socklen_t *size){
    if(!original_recvfrom){errno=ENOSYS;return -1;}ssize_t n=original_recvfrom(fd,buffer,len,flags,address,size);int saved=errno;
    if(n>0){sip_metadata("RX",buffer,(size_t)n);n=select_operator_offer(buffer,(size_t)n,len);}
    errno=saved;return n;
}
ssize_t recv(int fd,void *buffer,size_t len,int flags){
    if(!original_recv){errno=ENOSYS;return -1;}ssize_t n=original_recv(fd,buffer,len,flags);int saved=errno;
    if(n>0){sip_metadata("RX",buffer,(size_t)n);n=select_operator_offer(buffer,(size_t)n,len);}
    errno=saved;return n;
}
__attribute__((constructor)) static void prepare(void){
    original_read=dlsym(RTLD_NEXT,"read");original_write=dlsym(RTLD_NEXT,"write");original_close=dlsym(RTLD_NEXT,"close");
    int fd=fcntl(3,F_DUPFD,198);if(fd>=0){logfd=fd;fcntl(logfd,F_SETFD,FD_CLOEXEC);}
    original_sendto=dlsym(RTLD_NEXT,"sendto");original_send=dlsym(RTLD_NEXT,"send");
    original_recvfrom=dlsym(RTLD_NEXT,"recvfrom");original_recv=dlsym(RTLD_NEXT,"recv");
    original_connect=dlsym(RTLD_NEXT,"connect");original_writev=dlsym(RTLD_NEXT,"writev");
    original_open=dlsym(RTLD_NEXT,"open");original_ioctl=dlsym(RTLD_NEXT,"ioctl");
    original_resource=dlsym(RTLD_NEXT,"audio_resource_request");
    original_preopen=dlsym(RTLD_NEXT,"zDrvVolte_PreOpen");original_preclose=dlsym(RTLD_NEXT,"zDrvVolte_PreClose");
    original_setschedparam=dlsym(RTLD_NEXT,"pthread_setschedparam");
    original_stacksize=dlsym(RTLD_NEXT,"pthread_attr_setstacksize");
    original_assert=dlsym(RTLD_NEXT,"__assert");
    const char *software=getenv("MF79U_SOFTWARE_MEDIA");
    if(software && !strcmp(software,"1")){mf79u_media_enable();log_result("SOFTWARE AMR-NB and silent PCM enabled",1);}
    const char *synthetic=getenv("MF79U_NATIVE_CODEC_TEST");
    if(synthetic && !strcmp(synthetic,"1")){
        synthetic_codec_test=1;
        int result=90;pthread_attr_t attr;pthread_t thread;
        if(!pthread_attr_init(&attr)){
            if(!pthread_attr_setstacksize(&attr,32768) && !pthread_create(&thread,&attr,native_pipeline_worker,&result))pthread_join(thread,NULL);
            pthread_attr_destroy(&attr);
        }
        log_result("NATIVE B03 AMR NB/WB packetizer pipeline test",result);_exit(result?1:0);
    }
    const char *codecs=getenv("MF79U_OPERATOR_CODECS");
    if(codecs && !strcmp(codecs,"1"))operator_codecs=mf79u_vendor_codecs_enable(logfd);
    const char *preferred=getenv("MF79U_OPERATOR_CODEC");
    operator_preferred=preferred && !strcmp(preferred,"amr-nb")?2:0;
    log_result("OPERATOR WB/NB factory enabled",operator_codecs);
    const char *prefer=getenv("MF79U_AMR_PREFER_HIGH");amr_policy.enabled=prefer && !strcmp(prefer,"1");
    log_result("AMR negotiated high-rate preference enabled",amr_policy.enabled);
    write(logfd,"READY userspace IMS ESP transport\n",34);
}
/* Exported only for the synthetic ARM ABI check; has no socket/radio access. */
int mf79u_esp_crypto_selftest(void){
    const unsigned char key[16]={0x06,0xa9,0x21,0x40,0x36,0xb8,0xa1,0x5b,0x51,0x2e,0x03,0xd5,0x34,0x12,0x00,0x06};
    const unsigned char iv[16]={0x3d,0xaf,0xba,0x42,0x9d,0x9e,0xb4,0x30,0xb4,0x22,0xda,0x80,0x2c,0x9f,0xac,0x41};
    const unsigned char expected[16]={0xe3,0x53,0x77,0x9c,0x10,0x79,0xae,0xb8,0x27,0x08,0x94,0x2d,0xbe,0x77,0x18,0x1a};
    struct association sa={0};unsigned char encrypted[16],plain[16],mac[32],iv_a[16],iv_b[16];
    if(AES_set_encrypt_key(key,128,&sa.encrypt) || AES_set_decrypt_key(key,128,&sa.decrypt))return 1;
    if(cipher(&sa,1,iv,(const void*)"Single block msg",16,encrypted) || memcmp(encrypted,expected,16) ||
       cipher(&sa,0,iv,encrypted,16,plain) || memcmp(plain,"Single block msg",16))return 2;
    sa.auth_len=16;memset(sa.auth_key,0x0b,16);
    const unsigned char hmac_expected[16]={0x92,0x94,0x72,0x7a,0x36,0x38,0xbb,0x1c,0x13,0xf4,0x8e,0xf8,0x15,0x8b,0xfc,0x9d};
    if(digest(&sa,(const void*)"Hi There",8,mac)!=16 || memcmp(mac,hmac_expected,16))return 3;
    if(random_iv(NULL,iv_a,16) || random_iv(NULL,iv_b,16) || !memcmp(iv_a,iv_b,16))return 4;
    wipe(&sa,sizeof(sa));wipe(mac,sizeof(mac));log_result("ARM AES/HMAC/RNG selftest passed",0);return 0;
}
