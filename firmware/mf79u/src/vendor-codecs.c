/* B03's verified ARM32 codec-factory ABI. Only the private RAM executable's
 * writable callback table is changed; no instructions, NV or flash writes.
 * G.722 uses the audited PJPROJECT encoder/decoder, not a hardware ioctl.
 * Keep these ABI declarations separate from newer PJMEDIA public structs. */
#include "vendor-codecs.h"
#include "ims-software-media.h"
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include "g722_enc.h"
#include "g722_dec.h"
struct vstring {char *ptr;int length;};
struct vinfo {unsigned type,pt;struct vstring name;unsigned rate,channels;};
struct vframe {unsigned type;void *buf;unsigned size;uint64_t timestamp;unsigned bit_info;};
struct vcodec;
struct vops {
    int (*init)(struct vcodec*,void*);
    int (*open)(struct vcodec*,void*);
    int (*close)(struct vcodec*);
    int (*modify)(struct vcodec*,const void*);
    int (*parse)(struct vcodec*,void*,unsigned,const uint64_t*,unsigned*,struct vframe*);
    int (*encode)(struct vcodec*,const struct vframe*,unsigned,struct vframe*);
    int (*decode)(struct vcodec*,const struct vframe*,unsigned,struct vframe*);
    int (*recover)(struct vcodec*,unsigned,struct vframe*);
};
struct vcodec {struct vcodec *next,*prev;void *data,*factory;const struct vops *ops;};
struct vfactory_ops {
    int (*test)(void*,const struct vinfo*);
    int (*param)(void*,const struct vinfo*,void*);
    int (*enumerate)(void*,unsigned*,struct vinfo*);
    int (*allocate)(void*,const struct vinfo*,struct vcodec**);
    int (*release)(void*,struct vcodec*);
};
_Static_assert(sizeof(struct vinfo)==24,"B03 codec info ABI");
_Static_assert(sizeof(struct vcodec)==20,"B03 codec ABI");
_Static_assert(sizeof(struct vframe)==32 && offsetof(struct vframe,timestamp)==16,"B03 frame ABI");
struct gstate {g722_enc_t enc;g722_dec_t dec;short last[320];unsigned decoded,encoded,lost;int active;};
static struct vfactory_ops stock;static int logfd=-1;
static void put32(unsigned char *p,uint32_t value){memcpy(p,&value,4);}
static void put16(unsigned char *p,uint16_t value){memcpy(p,&value,2);}
static unsigned read32(const unsigned char *p){uint32_t value;memcpy(&value,p,4);return value;}
static int is_g722(const struct vinfo *i){return i && i->type==1 && i->pt==9 && i->rate==16000 && i->channels==1 && i->name.length==4 && !memcmp(i->name.ptr,"G722",4);}
static int g_init(struct vcodec *c,void *pool){(void)c;(void)pool;return 0;}
static int g_open(struct vcodec *c,void *param){
    unsigned char *p=param;struct gstate *s=c->data;
    if(!p || read32(p)!=16000 || read32(p+4)!=1)return 70004;
    memset(s,0,sizeof(*s));if(g722_enc_init(&s->enc) || g722_dec_init(&s->dec))return 70004;
    s->active=1;return 0;
}
static int g_close(struct vcodec *c){
    struct gstate *s=c->data;
    if(s->active){char line[120];int n=snprintf(line,sizeof(line),"MEDIA_G722 encoded=%u decoded=%u concealed=%u sample_rate=16000\n",s->encoded,s->decoded,s->lost);
        if(logfd>=0 && n>0 && n<(int)sizeof(line))(void)write(logfd,line,(size_t)n);}
    s->active=0;g722_enc_deinit(&s->enc);g722_dec_deinit(&s->dec);return 0;
}
static int g_modify(struct vcodec *c,const void *param){(void)c;(void)param;return 0;}
static int g_parse(struct vcodec *c,void *packet,unsigned size,const uint64_t *ts,unsigned *count,struct vframe *frames){
    (void)c;if(!packet || !ts || !count || !frames || !size || size%160 || size/160>*count)return 70004;
    *count=size/160;
    for(unsigned i=0;i<*count;i++)frames[i]=(struct vframe){.type=1,.buf=(unsigned char*)packet+i*160,.size=160,.timestamp=*ts+i*320};
    return 0;
}
static int g_encode(struct vcodec *c,const struct vframe *in,unsigned capacity,struct vframe *out){
    struct gstate *s=c->data;if(!s->active || !in || !out || !in->buf || !out->buf || in->size!=640 || capacity<160)return 70004;
    short pcm[320];memcpy(pcm,in->buf,sizeof(pcm));
    /* PJ's G.722 core expects 14-bit PCM. Preserve the caller's buffer. */
    for(unsigned i=0;i<320;i++)pcm[i]/=4;
    pj_size_t size=capacity;if(g722_enc_encode(&s->enc,pcm,320,out->buf,&size) || size!=160)return 70004;
    out->size=(unsigned)size;out->type=1;out->timestamp=in->timestamp;s->encoded++;return 0;
}
static int g_decode(struct vcodec *c,const struct vframe *in,unsigned capacity,struct vframe *out){
    struct gstate *s=c->data;if(!s->active || !in || !out || !in->buf || !out->buf || in->size!=160 || capacity<640)return 70004;
    pj_size_t samples=320;if(g722_dec_decode(&s->dec,in->buf,in->size,out->buf,&samples) || samples!=320)return 70004;
    short *pcm=out->buf;
    for(unsigned i=0;i<320;i++){int value=pcm[i]*4;pcm[i]=(short)(value>32767?32767:value<-32768?-32768:value);}
    memcpy(s->last,pcm,640);out->size=640;out->type=1;out->timestamp=in->timestamp;s->decoded++;return 0;
}
static int g_recover(struct vcodec *c,unsigned capacity,struct vframe *out){
    struct gstate *s=c->data;if(!s->active || !out || !out->buf || capacity<640)return 70004;
    for(unsigned i=0;i<320;i++)s->last[i]=(short)(s->last[i]*3/4);
    memcpy(out->buf,s->last,640);out->type=1;out->size=640;s->lost++;return 0;
}
static const struct vops gops={g_init,g_open,g_close,g_modify,g_parse,g_encode,g_decode,g_recover};
static int f_param(void *f,const struct vinfo *i,void *param){
    unsigned char *p=param;
    if(is_g722(i)){
        memset(p,0,556);put32(p,16000);put32(p+4,1);put32(p+8,64000);put32(p+12,64000);
        put16(p+20,20);p[24]=16;p[25]=9;p[32]=1;p[33]=8;return 0;
    }
    int result=stock.param(f,i,param);
    if(!result && i->rate==16000 && i->name.length==6 && !memcmp(i->name.ptr,"AMR-WB",6)){
        /* Native AMR open chooses the nearest permitted mode when an answer
         * restricts mode-set; incoming network CMR can still lower it. */
        put32(p+8,23850);
    }
    return result;
}
static int f_allocate(void *f,const struct vinfo *i,struct vcodec **out){
    if(!is_g722(i))return stock.allocate(f,i,out);
    struct vcodec *c=calloc(1,sizeof(*c));if(!c)return 70007;
    c->data=calloc(1,sizeof(struct gstate));if(!c->data){free(c);return 70007;}
    c->factory=f;c->ops=&gops;*out=c;return 0;
}
static int f_release(void *f,struct vcodec *c){
    if(c && c->ops==&gops){g_close(c);memset(c->data,0,sizeof(struct gstate));free(c->data);free(c);return 0;}
    return stock.release(f,c);
}
int mf79u_vendor_codecs_enable(int fd){
    char path[256];ssize_t n=readlink("/proc/self/exe",path,sizeof(path)-1);
    if(n<0 || n>=(ssize_t)sizeof(path)-1)return 0;
    path[n]=0;const char *name=strrchr(path,'/');
    if(!name || strcmp(name+1,".mf79u-volte-private"))return 0;
    struct vfactory_ops *ops=(void*)(uintptr_t)0xc667c;
    const uint32_t expected[]={0x6344d,0x63bb1,0x63cd9,0x626d1,0x62c21};
    if(memcmp(ops,expected,sizeof(expected)))return 0;
    stock=*ops;logfd=fd;
    ops->param=f_param; /* Keep stock AMR-WB/NB enumeration and allocation. */
    return 1;
}
int mf79u_vendor_codecs_selftest(void){
    struct vinfo info={.type=1,.pt=9,.name={"G722",4},.rate=16000,.channels=1};
    unsigned char param[564];memset(param,0xa5,sizeof(param));
    if(f_param(NULL,&info,param) || read32(param)!=16000 || read32(param+8)!=64000 || param[25]!=9)return 1;
    for(unsigned i=556;i<sizeof(param);i++)if(param[i]!=0xa5)return 2;
    struct vcodec *c=NULL;if(f_allocate(NULL,&info,&c) || g_open(c,param))return 3;
    short pcm[320],decoded[328];unsigned char coded[168];struct vframe frames[3];
    const short tone[8]={0,8485,-12000,8485,0,-8485,12000,-8485};
    uint64_t ts=123456;int result=0;unsigned spectral=0;
    for(unsigned k=0;k<16 && !result;k++){
        for(unsigned i=0;i<320;i++)pcm[i]=tone[i%8];
        memset(coded,0xa5,sizeof(coded));memset(decoded,0x5a,sizeof(decoded));
        struct vframe in={.type=1,.buf=pcm,.size=640,.timestamp=ts},out={.buf=coded};
        if(g_encode(c,&in,160,&out) || out.size!=160 || out.timestamp!=ts){result=4;break;}
        for(unsigned i=160;i<sizeof(coded);i++)if(coded[i]!=0xa5)result=5;
        if(memcmp(pcm,tone,16))result=6;
        unsigned count=3;if(g_parse(c,coded,160,&ts,&count,frames) || count!=1 || frames[0].timestamp!=ts){result=7;break;}
        out=(struct vframe){.buf=decoded};if(g_decode(c,frames,640,&out) || out.size!=640){result=8;break;}
        for(unsigned i=320;i<328;i++)if(decoded[i]!=0x5a5a)result=9;
        int64_t a=0,b=0,energy=0;
        const short sine[8]={0,707,-1000,707,0,-707,1000,-707},cosine[8]={1000,-707,0,707,-1000,707,0,-707};
        for(unsigned i=0;i<320;i++){a+=(int32_t)decoded[i]*sine[i%8];b+=(int32_t)decoded[i]*cosine[i%8];energy+=(int32_t)decoded[i]*decoded[i];}
        if(k>4 && energy && a*a+b*b>320*energy*100000)spectral++;
        ts+=320;
    }
    if(spectral<5 && !result)result=10;
    unsigned count=3;unsigned char twice[320];memcpy(twice,coded,160);memcpy(twice+160,coded,160);
    if(g_parse(c,twice,320,&ts,&count,frames) || count!=2 || frames[1].timestamp!=ts+320)result=11;
    if(!g_parse(c,twice,319,&ts,&count,frames))result=12;
    struct vframe output={.buf=decoded};if(!g_recover(c,639,&output) || g_recover(c,640,&output))result=13;
    f_release(NULL,c);return result;
}
/* Execute the stock RTP packetizer/parser with synthetic PCM, before main()
 * of a separately named private B03 copy. No IMS/CP/SIM initialization. */
int mf79u_vendor_amr_packet_selftest(void){
    char path[256];ssize_t n=readlink("/proc/self/exe",path,sizeof(path)-1);
    if(n<0 || n>=(ssize_t)sizeof(path)-1)return 1;
    path[n]=0;const char *name=strrchr(path,'/');
    if(!name || strcmp(name+1,".mf79u-native-codec-test"))return 2;
    const uint32_t expected[]={0x634c5,0x6351d,0x62b1d,0x63361,0x627c9,0x62c75,0x63899,0x63f31};
    if(memcmp((const void*)(uintptr_t)0xc6694,expected,sizeof(expected)))return 3;
    const struct vops *native=(const void*)(uintptr_t)0xc6694;
    _Alignas(8) unsigned char state[80]={0};struct vcodec c={.data=state,.ops=native};
    setenv("MF79U_PCM_WIDEBAND","1",1);mf79u_media_enable();
    short pcm[320],decoded[336];unsigned char packet[528],init[8]={0};struct vframe frames[16];
    for(unsigned family=0;family<2;family++){
        unsigned value=family?5:2,samples=family?320:160,max_mode=family?8:7;
        memset(state,0,sizeof(state));put32(state+4,family?16000:8000);put32(state+8,255);state[32]=state[33]=family?0:1;
        put32(init+4,value);if(mf79u_media_register(255,1) || mf79u_media_ioctl(255,0x40087602,init) || mf79u_media_ioctl(255,0x40047601,&value))return 4;
        for(unsigned mode=0;mode<=max_mode;mode++){
            put32(state+28,mode);
            for(unsigned i=0;i<samples;i++)pcm[i]=(short)((i%16)<8?8000:-8000);
            memset(packet,0xa5,sizeof(packet));memset(decoded,0x5a,sizeof(decoded));
            struct vframe in={.type=1,.buf=pcm,.size=samples*2,.timestamp=123456},out={.buf=packet};
            if(native->encode(&c,&in,512,&out) || !out.size || out.size>64)return 10+(int)mode;
            for(unsigned i=512;i<sizeof(packet);i++)if(packet[i]!=0xa5)return 20+(int)mode;
            unsigned count=16;uint64_t ts=in.timestamp;
            if(native->parse(&c,packet,out.size,&ts,&count,frames) || count!=1)return 30+(int)mode;
            out=(struct vframe){.buf=decoded};
            if(native->decode(&c,frames,samples*2,&out) || out.size!=samples*2)return 40+(int)mode;
            for(unsigned i=samples;i<336;i++)if(decoded[i]!=0x5a5a)return 50+(int)mode;
        }
        mf79u_media_close(255);
    }
    return 0;
}
