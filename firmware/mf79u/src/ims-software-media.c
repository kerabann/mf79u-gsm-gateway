/* B03 ioctl adapter to OpenCORE AMR-NB and optional loopback PCM network.
 * Only RAM handles created by this adapter are touched. No audio is logged. */
#include "ims-software-media.h"
#include <errno.h>
#include <stdint.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <interf_enc.h>
#include <interf_dec.h>
#include <dec_if.h>
#include <enc_if.h>
#include "pcm-queue.h"
#include "pcm-clock.h"
#include "pcm-resample.h"
struct media_handle {int kind,read_started,write_started,net_rx,net_tx;unsigned rate,frame;void *encoder,*decoder;
    int64_t read_deadline,write_deadline;struct mf79u_pcm_queue *input_queue;
    short last_pcm[320];unsigned concealed;unsigned long decoded[16],encoded[9],bad_frames;
    int encoder_wb,decoder_wb,dtx;struct mf79u_resample up,down;};
static struct media_handle handles[256];static int enabled,network,wideband;static volatile int locked;
static void lock(void){while(__sync_lock_test_and_set(&locked,1))usleep(200);}
static void unlock(void){__sync_lock_release(&locked);}
static unsigned get16(const unsigned char *p){return p[0]|(unsigned)p[1]<<8;}
static void set16(unsigned char *p,unsigned n){p[0]=n;p[1]=n>>8;}
static uint32_t get32(const unsigned char *p){uint32_t n;memcpy(&n,p,4);return n;}
void mf79u_media_enable(void){
    enabled=1;const char *s=getenv("MF79U_PCM_NETWORK");network=s && !strcmp(s,"1");
    s=getenv("MF79U_PCM_WIDEBAND");wideband=s && !strcmp(s,"1");
}
int mf79u_media_path(const char *path){
    if(!enabled)return 0;
    if(!strcmp(path,"/dev/amr_device"))return 1;
    if(!strcmp(path,"/dev/volte_device"))return 2;
    return 0;
}
int mf79u_media_register(int fd,int kind){
    if(fd<0 || fd>=256 || !kind){errno=EMFILE;return -1;}
    lock();handles[fd]=(struct media_handle){.kind=kind,.net_rx=-1,.net_tx=-1};unlock();return 0;
}
int mf79u_media_kind(int fd){return enabled && fd>=0 && fd<256?handles[fd].kind:0;}
void mf79u_media_close(int fd){
    if(!mf79u_media_kind(fd))return;
    lock();struct media_handle *h=handles+fd;
    char summary[400];int length=0;
    if(h->kind==1)length=snprintf(summary,sizeof(summary),"MEDIA_AMR decoded=%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu sid=%lu no_data=%lu bad=%lu\n",
        h->decoded[0],h->decoded[1],h->decoded[2],h->decoded[3],h->decoded[4],h->decoded[5],h->decoded[6],h->decoded[7],h->decoded[8],h->decoded[15],h->bad_frames);
    if(h->kind==1 && h->decoder_wb)length=snprintf(summary,sizeof(summary),"MEDIA_AMR_WB decoded=%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu sid=%lu lost=%lu no_data=%lu bad=%lu\n",
        h->decoded[0],h->decoded[1],h->decoded[2],h->decoded[3],h->decoded[4],h->decoded[5],h->decoded[6],h->decoded[7],h->decoded[8],h->decoded[9],h->decoded[14],h->decoded[15],h->bad_frames);
    if(h->input_queue){struct mf79u_pcm_queue *q=h->input_queue;
        length=snprintf(summary,sizeof(summary),"MEDIA_PCM received=%lu played=%lu underflows=%lu overflows=%lu high_water=%u\n",q->received,q->played,q->underflows,q->overflows,q->high_water);}
    if(length>0 && length<(int)sizeof(summary))(void)write(3,summary,(size_t)length);
    if(h->kind==1){
        length=snprintf(summary,sizeof(summary),"MEDIA_AMR_TX family=%s encoded=%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",h->encoder_wb?"WB":"NB",
            h->encoded[0],h->encoded[1],h->encoded[2],h->encoded[3],h->encoded[4],h->encoded[5],h->encoded[6],h->encoded[7],h->encoded[8]);
        if(length>0 && length<(int)sizeof(summary))(void)write(3,summary,(size_t)length);
    }
    if(h->encoder){if(h->encoder_wb)E_IF_exit(h->encoder);else Encoder_Interface_exit(h->encoder);}
    if(h->decoder){if(h->decoder_wb)D_IF_exit(h->decoder);else Decoder_Interface_exit(h->decoder);}
    if(h->net_rx>=0)close(h->net_rx);
    if(h->net_tx>=0)close(h->net_tx);
    if(h->input_queue)free(h->input_queue);
    memset(h,0,sizeof(*h));unlock();
}
static int valid_pcm(const unsigned char *p){
    unsigned rate=get32(p),channels=get32(p+4),frame=get32(p+8),bits=get32(p+12);
    return (rate==8000 || rate==16000) && channels==1 && frame==rate/50 && bits==16;
}
int mf79u_media_preopen(const void *config){
    if(!enabled)return 0;
    if(!config || !valid_pcm(config)){errno=EINVAL;return -1;}
    return 1;
}
int mf79u_media_resource(const void *request,void *response){
    if(!enabled || !request)return 0;
    const unsigned char *p=request;
    if(get32(p)!=5181 || get32(p+4)!=5184 || get32(p+8)!=1)return 0;
    if(response)memset(response,0,12);
    return 1;
}
int mf79u_media_ioctl(int fd,unsigned long request,void *argument){
    int result=-1;errno=EINVAL;lock();struct media_handle *h=handles+fd;
    unsigned char *p=argument;
    if(h->kind==2){
        switch(request){
        case 0x40147605:
            if(p && valid_pcm(p)){
                if(network && get32(p)!=8000 && !wideband){errno=ENOTSUP;break;}
                if(network && h->net_rx<0){
                    int input=socket(AF_INET,SOCK_DGRAM|SOCK_NONBLOCK,0),output=socket(AF_INET,SOCK_DGRAM,0);
                    struct sockaddr_in local={.sin_family=AF_INET,.sin_port=htons(46001),.sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
                    if(input<0 || output<0 || bind(input,(struct sockaddr*)&local,sizeof(local))){
                        if(input>=0)close(input);
                        if(output>=0)close(output);
                        break;
                    }
                    h->input_queue=calloc(1,sizeof(*h->input_queue));
                    if(!h->input_queue){close(input);close(output);break;}
                    h->input_queue->samples=wideband?320:160;
                    h->net_rx=input;h->net_tx=output;
                }
                h->rate=get32(p);h->frame=get32(p+8);result=0;
                {char summary[80];int n=snprintf(summary,sizeof(summary),"MEDIA_PCM_RATE native=%u wire=%u\n",h->rate,wideband?16000:8000);
                 if(n>0 && n<(int)sizeof(summary))(void)write(3,summary,(size_t)n);}
            }break;
        case 0x7601:h->read_started=1;h->read_deadline=0;result=0;break;
        case 0x7602:h->read_started=0;result=0;break;
        case 0x7603:h->write_started=1;h->write_deadline=0;result=0;break;
        case 0x7604:h->write_started=0;result=0;break;
        default:errno=ENOTTY;break;
        }
    }else if(h->kind==1){
        switch(request){
        case 0x40087602: /* byte DTX; codec family at offset 4: NB=2/WB=5 */
            if(!p)break;
            if(get32(p+4)!=2 && !(wideband && get32(p+4)==5)){errno=ENOTSUP;break;}
            if(h->encoder){if(h->encoder_wb)E_IF_exit(h->encoder);else Encoder_Interface_exit(h->encoder);}
            h->encoder_wb=get32(p+4)==5;h->dtx=p[0]!=0;
            h->encoder=h->encoder_wb?E_IF_init():Encoder_Interface_init(h->dtx);result=h->encoder?0:-1;break;
        case 0x40047601:
            if(!p)break;
            if(get32(p)!=2 && !(wideband && get32(p)==5)){errno=ENOTSUP;break;}
            if(h->decoder){if(h->decoder_wb)D_IF_exit(h->decoder);else Decoder_Interface_exit(h->decoder);}
            h->decoder_wb=get32(p)==5;h->decoder=h->decoder_wb?D_IF_init():Decoder_Interface_init();result=h->decoder?0:-1;break;
        case 0x40147604: /* codec0, mode4, output_size8, pcm_size10, in12, out16 */
            if(!p || !h->encoder || p[0]!=h->encoder_wb || get32(p+4)>(h->encoder_wb?8u:7u) || get16(p+10)!=(h->encoder_wb?640u:320u))break;
            {const short *in=(const short*)(uintptr_t)get32(p+12);
             unsigned char *out=(unsigned char*)(uintptr_t)get32(p+16);
             if(!in || !out)break;
             short input_copy[320];memcpy(input_copy,in,h->encoder_wb?640:320);
             int n=h->encoder_wb?E_IF_encode(h->encoder,(int)get32(p+4),input_copy,out,h->dtx):
                 Encoder_Interface_Encode(h->encoder,(enum Mode)get32(p+4),input_copy,out,0);
             if(n>=1 && n<=(h->encoder_wb?61:32)){h->encoded[get32(p+4)]++;set16(p+8,(unsigned)n);result=0;}}
            break;
        case 0x40107603: /* codec0, input_size4, input8, PCM output12 */
            if(!p || !h->decoder || p[0]!=h->decoder_wb || get16(p+4)!=(h->decoder_wb?61u:32u))break;
            {const unsigned char *in=(const unsigned char*)(uintptr_t)get32(p+8);
             short *out=(short*)(uintptr_t)get32(p+12);
             if(!in || !out || (in[0]&0x83))break;
             unsigned type=(in[0]>>3)&15;if(type>(h->decoder_wb?9u:8u) && type!=15 && !(h->decoder_wb && type==14))break;
             h->decoded[type]++;if(!(in[0]&4))h->bad_frames++;
             if(h->decoder_wb)D_IF_decode(h->decoder,in,out,!(in[0]&4));
             else Decoder_Interface_Decode(h->decoder,in,out,!(in[0]&4));
             result=0;}
            break;
        case 0x7608:if(h->encoder){if(h->encoder_wb)E_IF_exit(h->encoder);else Encoder_Interface_exit(h->encoder);h->encoder=NULL;}result=0;break;
        case 0x7607:if(h->decoder){if(h->decoder_wb)D_IF_exit(h->decoder);else Decoder_Interface_exit(h->decoder);h->decoder=NULL;}result=0;break;
        default:errno=ENOTTY;break;
        }
    }
    unlock();return result;
}
ssize_t mf79u_media_read(int fd,void *buffer,size_t size){
    lock();unsigned rate=handles[fd].rate;int active=handles[fd].read_started,input=handles[fd].net_rx;unlock();
    if(!active || !rate){usleep(20000);errno=EAGAIN;return -1;}
    if(!buffer || !size || size>4096 || size%2){errno=EINVAL;return -1;}
    mf79u_pcm_pace(&handles[fd].read_deadline,(unsigned)(size*1000000/(rate*2)));
    memset(buffer,0,size);
    if(input>=0 && size==rate/50*2){
        unsigned char data[644];short pcm[320];struct media_handle *h=handles+fd;unsigned wire_size=wideband?640:320;
        for(unsigned i=0;i<32;i++){
            ssize_t n=recv(input,data,sizeof(data),MSG_DONTWAIT);if(n<0)break;
            if(n==(ssize_t)wire_size+4 && !memcmp(data,wideband?"PCM2":"PCM1",4))mf79u_pcm_push(h->input_queue,data+4);
        }
        memset(pcm,0,sizeof(pcm));int got=mf79u_pcm_pop(h->input_queue,pcm);
        if(got==1){memcpy(h->last_pcm,pcm,wire_size);h->concealed=0;}
        else if(got<0){
            if(h->concealed<3){for(unsigned i=0;i<wire_size/2;i++){h->last_pcm[i]=h->last_pcm[i]*3/4;pcm[i]=h->last_pcm[i];}}
            h->concealed++;
        }
        if(wideband && rate==8000)mf79u_downsample(&h->down,pcm,buffer);
        else memcpy(buffer,pcm,size);
    }
    return (ssize_t)size;
}
ssize_t mf79u_media_write(int fd,const void *buffer,size_t size){
    lock();int active=handles[fd].write_started,output=handles[fd].net_tx;unsigned rate=handles[fd].rate;unlock();
    if(!active){usleep(20000);errno=EAGAIN;return -1;}
    if(!size || size>4096 || size%2){errno=EINVAL;return -1;}
    mf79u_pcm_pace(&handles[fd].write_deadline,rate?(unsigned)(size*1000000/(rate*2)):20000);
    if(output>=0 && size==rate/50*2 && buffer){
        _Alignas(2) unsigned char data[644];unsigned wire_size=wideband?640:320;memcpy(data,wideband?"PCM2":"PCM1",4);
        if(wideband && rate==8000)mf79u_upsample(&handles[fd].up,buffer,(short*)(void*)(data+4));
        else memcpy(data+4,buffer,size);
        struct sockaddr_in gateway={.sin_family=AF_INET,.sin_port=htons(46000),.sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
        sendto(output,data,wire_size+4,MSG_DONTWAIT,(struct sockaddr*)&gateway,sizeof(gateway));
    }
    return (ssize_t)size; /* No audio recordings. */
}
/* Public synthetic fixture: exercises recovered ARM32 layouts, canaries and
 * every NB rate against the direct OpenCORE interface. Never opens a radio. */
int mf79u_media_selftest(void){
    _Static_assert(sizeof(void*)==4,"B03 ARM32 pointers required");
    const int lengths[8]={13,14,16,18,20,21,27,32};
    short samples[160],oracle_input[160],decoded[176];unsigned char encoded[48],reference[32];
    unsigned char init[8]={0},enc[20]={0},dec[16]={0};
    uint32_t nb=2;memcpy(init+4,&nb,4);mf79u_media_enable();
    if(mf79u_media_register(255,1) || mf79u_media_ioctl(255,0x40087602,init) ||
       mf79u_media_ioctl(255,0x40047601,&nb))return 1;
    void *oracle=Encoder_Interface_init(0);if(!oracle){mf79u_media_close(255);return 2;}
    int failure=0;
    for(uint32_t mode=0;mode<8 && !failure;mode++)for(unsigned frame=0;frame<4;frame++){
        for(unsigned i=0;i<160;i++)samples[i]=((i+frame*13)%80)<40?12000:-12000;
        memset(encoded,0xa5,sizeof(encoded));memcpy(enc+4,&mode,4);set16(enc+10,320);
        uint32_t p=(uint32_t)(uintptr_t)samples;memcpy(enc+12,&p,4);
        p=(uint32_t)(uintptr_t)encoded;memcpy(enc+16,&p,4);
        memcpy(oracle_input,samples,sizeof(samples));
        int n=Encoder_Interface_Encode(oracle,(enum Mode)mode,oracle_input,reference,0);
        int rc=mf79u_media_ioctl(255,0x40147604,enc);
        if(rc || get16(enc+8)!=(unsigned)lengths[mode] || n!=lengths[mode] || memcmp(encoded,reference,(size_t)n)){
            printf("Synthetic NB mode=%u frame=%u adapter_rc=%d size=%u reference_size=%d equal=%d\n",mode,frame,rc,get16(enc+8),n,n>0 && n<=32?!memcmp(encoded,reference,(size_t)n):0);
            failure=10+(int)mode;break;}
        for(unsigned i=(unsigned)n;i<sizeof(encoded);i++)if(encoded[i]!=0xa5)failure=30;
        memset(decoded,0x5a,sizeof(decoded));set16(dec+4,32);
        p=(uint32_t)(uintptr_t)encoded;memcpy(dec+8,&p,4);
        p=(uint32_t)(uintptr_t)decoded;memcpy(dec+12,&p,4);
        if(mf79u_media_ioctl(255,0x40107603,dec)){failure=31;break;}
        for(unsigned i=160;i<176;i++)if(decoded[i]!=0x5a5a)failure=32;
        long energy=0;for(unsigned i=0;i<160;i++)energy+=decoded[i]<0?-decoded[i]:decoded[i];
        if(!energy)failure=33;
    }
    Encoder_Interface_exit(oracle);mf79u_media_close(255);if(failure)return failure;
    uint32_t config[5]={8000,1,160,16,0},resource[3]={5181,5184,1},response[3];
    unsigned char pcm[320];
    if(mf79u_media_register(255,2) || mf79u_media_preopen(config)!=1 ||
       mf79u_media_ioctl(255,0x40147605,config) || mf79u_media_resource(resource,response)!=1)failure=40;
    if(!failure && (mf79u_media_ioctl(255,0x7601,NULL) || mf79u_media_read(255,pcm,320)!=320))failure=41;
    if(!failure)for(unsigned i=0;i<320;i++)if(pcm[i])failure=42;
    if(!failure && (mf79u_media_ioctl(255,0x7603,NULL) || mf79u_media_write(255,pcm,320)!=320))failure=43;
    mf79u_media_close(255);return failure;
}
/* WB ABI: family=5, codec byte=1, PCM=640, decoder input buffer=61.
 * Derived from stock B03 at 0x62d46, 0x63304 and 0x63af8. */
int mf79u_media_wb_selftest(void){
    const unsigned lengths[9]={18,24,33,37,41,47,51,59,61};
    unsigned char init[8]={0},enc[20]={1},dec[16]={1},encoded[80],reference[80];
    short input[320],oracle_input[320],output[336];uint32_t family=5;int old_wide=wideband;
    enabled=1;wideband=1;memcpy(init+4,&family,4);
    if(mf79u_media_register(255,1) || mf79u_media_ioctl(255,0x40087602,init) ||
       mf79u_media_ioctl(255,0x40047601,&family)){wideband=old_wide;return 1;}
    void *oracle=E_IF_init();if(!oracle){mf79u_media_close(255);wideband=old_wide;return 2;}
    const short tone[8]={0,8485,-12000,8485,0,-8485,12000,-8485};
    const short sine[8]={0,707,-1000,707,0,-707,1000,-707};
    const short cosine[8]={1000,-707,0,707,-1000,707,0,-707};
    int failure=0;unsigned spectral_passed=0;
    for(uint32_t mode=0;mode<9 && !failure;mode++)for(unsigned frame=0;frame<12;frame++){
        for(unsigned i=0;i<320;i++)input[i]=tone[i%8];
        memcpy(oracle_input,input,sizeof(input));
        memset(encoded,0xa5,sizeof(encoded));memcpy(enc+4,&mode,4);set16(enc+10,640);
        uint32_t ptr=(uint32_t)(uintptr_t)input;memcpy(enc+12,&ptr,4);
        ptr=(uint32_t)(uintptr_t)encoded;memcpy(enc+16,&ptr,4);
        int n=E_IF_encode(oracle,(int)mode,oracle_input,reference,0);
        if(mf79u_media_ioctl(255,0x40147604,enc) || get16(enc+8)!=lengths[mode] || n!=(int)lengths[mode] || memcmp(encoded,reference,(size_t)n)){failure=10+(int)mode;break;}
        for(unsigned i=(unsigned)n;i<sizeof(encoded);i++)if(encoded[i]!=0xa5)failure=30;
        memset(output,0x5a,sizeof(output));set16(dec+4,61);
        ptr=(uint32_t)(uintptr_t)encoded;memcpy(dec+8,&ptr,4);
        ptr=(uint32_t)(uintptr_t)output;memcpy(dec+12,&ptr,4);
        if(mf79u_media_ioctl(255,0x40107603,dec)){failure=31;break;}
        for(unsigned i=320;i<336;i++)if(output[i]!=0x5a5a)failure=32;
        int64_t a=0,b=0,energy=0;
        for(unsigned i=0;i<320;i++){a+=(int32_t)output[i]*sine[i%8];b+=(int32_t)output[i]*cosine[i%8];energy+=(int32_t)output[i]*output[i];}
        if(!energy)failure=33;
        if(mode==8 && frame>4 && a*a+b*b>320*energy*100000) spectral_passed++;
    }
    E_IF_exit(oracle);mf79u_media_close(255);wideband=old_wide;
    if(!failure && !spectral_passed)failure=34;
    printf("WB ABI selftest modes=9 tone_6000Hz_passes=%u result=%d\n",spectral_passed,failure);return failure;
}
