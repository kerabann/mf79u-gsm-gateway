#include "amr-rate-policy.h"
#include <arpa/inet.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <unistd.h>

static char *trim(char *s){
    while(*s==' ' || *s=='\t')s++;
    size_t n=strlen(s);while(n && (s[n-1]==' ' || s[n-1]=='\t' || s[n-1]=='\r'))s[--n]=0;
    return s;
}
static int number(const char *s,unsigned max,unsigned *n){
    if(!*s)return 0;
    unsigned value=0;
    for(;*s;s++){if(*s<'0' || *s>'9' || value>max/10)return 0;
        value=value*10+(unsigned)(*s-'0');if(value>max)return 0;}
    *n=value;return 1;
}
static int modes(char *s,uint16_t *mask){
    unsigned result=0,n;char *next;
    do{next=strchr(s,',');if(next)*next++=0;
        if(!number(trim(s),8,&n) || (result&(1u<<n)))return 0;
        result|=1u<<n;s=next;
    }while(s);
    *mask=(uint16_t)result;return result!=0;
}
static unsigned highest(unsigned mask){unsigned n=8;while(n && !(mask&(1u<<n)))n--;return n;}
static const unsigned rates[]={4750,5150,5900,6700,7400,7950,10200,12200};
static const unsigned wb_rates[]={6600,8850,12650,14250,15850,18250,19850,23050,23850};
static const char *codec_names[]={"unknown","AMR","AMR-WB","PCMU","PCMA","G722","EVS","opus","G729","telephone-event","CN","GSM","G723","iLBC","speex","L16","AMR-WB+"};
static void rtpmap(struct mf79u_amr_codec *c,const char *value){
    if(c->map_seen++){c->invalid=1;return;}
    for(unsigned i=1;i<sizeof(codec_names)/sizeof(codec_names[0]);i++){
        size_t n=strlen(codec_names[i]);if(strncasecmp(value,codec_names[i],n) || value[n]!='/')continue;
        char clock[16];const char *end=strchr(value+n+1,'/');size_t len=end?(size_t)(end-value-n-1):strlen(value+n+1);
        unsigned rate,channels=1;
        if(!len || len>=sizeof(clock))break;
        memcpy(clock,value+n+1,len);clock[len]=0;
        if(!number(clock,192000,&rate) || !rate || (end && (!number(end+1,8,&channels) || !channels)))break;
        c->mapped=(unsigned char)i;c->rtp_clock=rate;
        if(i<=2){
            if(rate!=(i==1?8000u:16000u) || channels!=1)c->invalid=1;
            if(i==2 && !c->mode_set)c->modes=511;
        }
        return;
    }
    c->invalid=1;
}
static void fmtp(struct mf79u_amr_codec *c,char *s){
    if(c->fmtp++){c->invalid=1;return;}
    char *next;unsigned align_seen=0,mode_seen=0;
    do{next=strchr(s,';');if(next)*next++=0;
        char *entry=trim(s),*value=strchr(entry,'=');unsigned n;
        if(!value){c->invalid=1;return;}*value++=0;entry=trim(entry);value=trim(value);
        if(!strcasecmp(entry,"mode-set")){
            if(mode_seen++ || !modes(value,&c->modes))c->invalid=1;
            c->mode_set=1;
        }else if(!strcasecmp(entry,"octet-align")){
            if(align_seen++ || !number(value,1,&n))c->invalid=1;
            else c->align=(unsigned char)n;
        }else if(!strcasecmp(entry,"crc") || !strcasecmp(entry,"robust-sorting") || !strcasecmp(entry,"interleaving")){
            if(!number(value,0,&n))c->invalid=1;
        }else if(!strcasecmp(entry,"channels")){
            if(!number(value,1,&n) || n!=1)c->invalid=1;
        }
        s=next;
    }while(s);
}
static int unicast(uint32_t address){unsigned n=ntohl(address);return n && n!=0xffffffffu && (n>>24)<224;}
static void parse_sdp(struct mf79u_amr_sdp *out,char *body){
    memset(out,0,sizeof(*out));for(unsigned i=0;i<128;i++)out->codec[i].modes=255;
    uint32_t session_address=0;unsigned audio=0,section=0,invalid=0;
    char *save=NULL;
    for(char *line=strtok_r(body,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
        line=trim(line);
        if(!strncmp(line,"m=",2)){
            char *words=NULL,*media=strtok_r(line+2," \t",&words);
            char *port=strtok_r(NULL," \t",&words),*transport=strtok_r(NULL," \t",&words);
            section=media && !strcmp(media,"audio");
            if(!section)continue;
            if(audio++){invalid=1;continue;}
            out->address=session_address;
            if(!port || !number(port,65535,&out->port) || !out->port || !transport || strcmp(transport,"RTP/AVP"))invalid=1;
            char *pt;unsigned n,count=0;
            while((pt=strtok_r(NULL," \t",&words))){
                if(!number(pt,127,&n) || out->codec[n].listed){invalid=1;break;}
                out->codec[n].listed=1;count++;
                if(n==0 || n==8 || n==9 || n==3 || n==13){
                    out->codec[n].mapped=n==0?3:n==8?4:n==9?5:n==3?11:10;
                    out->codec[n].rtp_clock=8000;
                }
            }
            if(!count)invalid=1;
        }else if(!strncmp(line,"c=",2)){
            struct in_addr address;
            if(strncmp(line,"c=IN IP4 ",9) || inet_pton(AF_INET,line+9,&address)!=1 || !unicast(address.s_addr)){
                if(!audio || section)invalid=1;
                continue;
            }
            if(!audio)session_address=address.s_addr;
            else if(section)out->address=address.s_addr;
        }else if(section && (!strcmp(line,"a=inactive") || !strcmp(line,"a=recvonly") || !strcmp(line,"a=sendonly"))){
            invalid=1;
        }else if(section && (!strncmp(line,"a=rtpmap:",9) || !strncmp(line,"a=fmtp:",7))){
            int map=!strncmp(line,"a=rtpmap:",9);char *value=line+(map?9:7),*space=strpbrk(value," \t");unsigned pt;
            if(!space){invalid=1;continue;}*space++=0;
            if(!number(value,127,&pt)){invalid=1;continue;}
            struct mf79u_amr_codec *c=out->codec+pt;space=trim(space);
            if(map)rtpmap(c,space);
            else fmtp(c,space);
        }
    }
    for(unsigned pt=0;pt<128;pt++)if(out->codec[pt].mapped==1 && (out->codec[pt].modes&256))out->codec[pt].invalid=1;
    out->valid=audio==1 && !invalid && out->address && out->port;
}
static unsigned negotiated(const struct mf79u_amr_policy *p,unsigned pt){
    if(!p->active || !p->leg[0].valid || !p->leg[1].valid)return 0;
    const struct mf79u_amr_codec *a=p->leg[0].codec+pt,*b=p->leg[1].codec+pt;
    if(!a->listed || !b->listed || (a->mapped!=1 && a->mapped!=2) || a->mapped!=b->mapped || a->invalid || b->invalid || a->align!=b->align)return 0;
    const struct mf79u_amr_codec *offer=p->leg[p->offer_side].codec+pt,*answer=p->leg[!p->offer_side].codec+pt;
    if(offer->mode_set && (!answer->mode_set || offer->modes!=answer->modes))return 0;
    return answer->modes;
}
struct codec_offer_scratch {char packet[7001],parsed[7001],body[7001],headers[7001];struct mf79u_amr_sdp s;};
static size_t codec_offer_impl(const void *buffer,size_t length,void *copy,size_t capacity,unsigned preferred,struct codec_offer_scratch *scratch){
    if(!buffer || !copy || length>7000 || length<7 || memcmp(buffer,"INVITE ",7) || memchr(buffer,0,length))return 0;
    char *packet=scratch->packet,*parsed=scratch->parsed,*body=scratch->body;memcpy(packet,buffer,length);packet[length]=0;
    char *start=strstr(packet,"\r\n\r\n");if(!start)return 0;
    size_t header=(size_t)(start-packet),body_length=length-header-4;
    *start=0;char *source=start+4;unsigned declared=0,seen=0,type=0;
    char *headers=scratch->headers;memcpy(headers,packet,header+1);char *save=NULL;
    for(char *line=strtok_r(headers,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
        char *value=strchr(line,':');if(!value)continue;*value++=0;
        if(!strcasecmp(trim(line),"Content-Length") || !strcasecmp(trim(line),"l")){
            if(seen++ || !number(trim(value),7000,&declared))return 0;
        }else if(!strcasecmp(trim(line),"Content-Type") || !strcasecmp(trim(line),"c"))type=!strcasecmp(trim(value),"application/sdp");
    }
    if(seen!=1 || !type || declared!=body_length)return 0;
    memcpy(parsed,source,body_length+1);struct mf79u_amr_sdp *s=&scratch->s;parse_sdp(s,parsed);if(!s->valid)return 0;
    int wb=-1,nb=-1;
    for(unsigned pt=0;pt<128;pt++){
        const struct mf79u_amr_codec *c=s->codec+pt;if(!c->listed || c->invalid)continue;
        int *best=c->mapped==1?&nb:c->mapped==2?&wb:NULL;if(!best)continue;
        if(*best<0 || highest(c->modes)>highest(s->codec[*best].modes) ||
           (highest(c->modes)==highest(s->codec[*best].modes) && c->modes>s->codec[*best].modes))*best=(int)pt;
    }
    if(wb<0 && nb<0)return 0;
    /* Forced preferences are useful to validate each actual media backend.
     * Fall back to normal ordering when the requested family is not offered. */
    if(preferred==2 && nb>=0){wb=-1;}
    unsigned keep[128]={0};if(wb>=0)keep[wb]=1;if(nb>=0)keep[nb]=1;
    for(unsigned pt=0;pt<128;pt++)if(s->codec[pt].listed && s->codec[pt].mapped==9)keep[pt]=1;
    size_t used=0;save=NULL;unsigned section=0;
    for(char *line=strtok_r(source,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
        line=trim(line);
        if(!strncmp(line,"m=",2))section=!strncmp(line,"m=audio ",8);
        if(section && !strncmp(line,"m=audio ",8)){
            int n=snprintf(body+used,sizeof(scratch->body)-used,"m=audio %u RTP/AVP",s->port);if(n<0 || (size_t)n>=sizeof(scratch->body)-used)return 0;used+=(size_t)n;
            int order[]={wb,nb};for(unsigned i=0;i<2;i++)if(order[i]>=0){n=snprintf(body+used,sizeof(scratch->body)-used," %d",order[i]);if(n<0 || (size_t)n>=sizeof(scratch->body)-used)return 0;used+=(size_t)n;}
            for(unsigned pt=0;pt<128;pt++)if(keep[pt] && s->codec[pt].mapped==9){n=snprintf(body+used,sizeof(scratch->body)-used," %u",pt);if(n<0 || (size_t)n>=sizeof(scratch->body)-used)return 0;used+=(size_t)n;}
            if(used+2>=sizeof(scratch->body))return 0;
            memcpy(body+used,"\r\n",2);used+=2;continue;
        }
        if(section && (!strncmp(line,"a=rtpmap:",9) || !strncmp(line,"a=fmtp:",7))){
            const char *v=line+(!strncmp(line,"a=rtpmap:",9)?9:7);const char *space=strpbrk(v," \t");char num[8];unsigned pt;
            if(!space || space-v>=(ptrdiff_t)sizeof(num))return 0;
            memcpy(num,v,(size_t)(space-v));num[space-v]=0;
            if(!number(num,127,&pt))return 0;
            if(!keep[pt])continue;
        }
        size_t n=strlen(line);if(n+2>=sizeof(scratch->body)-used)return 0;memcpy(body+used,line,n);used+=n;memcpy(body+used,"\r\n",2);used+=2;
    }
    size_t written=0;save=NULL;
    for(char *line=strtok_r(packet,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
        line=trim(line);char *colon=strchr(line,':');int replace=0;
        if(colon){char key[32];size_t n=(size_t)(colon-line);if(n<sizeof(key)){memcpy(key,line,n);key[n]=0;replace=!strcasecmp(trim(key),"Content-Length") || !strcasecmp(trim(key),"l");}}
        int n=replace?snprintf((char*)copy+written,capacity-written,"Content-Length: %u\r\n",(unsigned)used):snprintf((char*)copy+written,capacity-written,"%s\r\n",line);
        if(n<0 || (size_t)n>=capacity-written)return 0;
        written+=(size_t)n;
    }
    if(used+2>capacity-written)return 0;
    memcpy((char*)copy+written,"\r\n",2);written+=2;memcpy((char*)copy+written,body,used);return written+used;
}
size_t mf79u_codec_offer(const void *buffer,size_t length,void *copy,size_t capacity,unsigned preferred){
    if(!buffer || !copy || length>7000 || length<7 || memcmp(buffer,"INVITE ",7))return 0;
    struct codec_offer_scratch *scratch=calloc(1,sizeof(*scratch));if(!scratch)return 0;
    size_t result=codec_offer_impl(buffer,length,copy,capacity,preferred,scratch);
    volatile unsigned char *wipe=(void*)scratch;for(size_t i=0;i<sizeof(*scratch);i++)wipe[i]=0;
    free(scratch);return result;
}
static void report_sdp(const struct mf79u_amr_policy *p,int tx,int fd){
    if(fd<0)return;
    char text[160];const struct mf79u_amr_sdp *s=p->leg+tx;
    unsigned unknown=0;
    for(unsigned pt=0;pt<128;pt++)if(s->codec[pt].listed){
        if(!s->codec[pt].mapped){unknown++;continue;}
        const struct mf79u_amr_codec *c=s->codec+pt;unsigned mask=negotiated(p,pt);
        int n=snprintf(text,sizeof(text),"SDP_AUDIO side=%s codec=%s pt=%u rtp_clock=%u\n",tx?"TX":"RX",codec_names[c->mapped],pt,c->rtp_clock);
        if(n>0 && n<(int)sizeof(text))(void)write(fd,text,(size_t)n);
        if(c->mapped>2)continue;
        n=snprintf(text,sizeof(text),"AMR_SDP side=%s family=%s pt=%u modes=0x%02x align=%u valid=%u negotiated=0x%02x prefer_bps=%u enabled=%u\n",
            tx?"TX":"RX",c->mapped==2?"WB":"NB",pt,c->modes,c->align,s->valid && !c->invalid,mask,mask?(c->mapped==2?wb_rates:rates)[highest(mask)]:0,p->enabled);
        if(n>0 && n<(int)sizeof(text))(void)write(fd,text,(size_t)n);
    }
    if(unknown){int n=snprintf(text,sizeof(text),"SDP_AUDIO side=%s unknown_payloads=%u\n",tx?"TX":"RX",unknown);
        if(n>0 && n<(int)sizeof(text))(void)write(fd,text,(size_t)n);}
}
static void observe_packet(struct mf79u_amr_policy *p,int tx,char *packet,size_t length,int fd){
    if(memchr(packet,0,length))return;
    char *body=strstr(packet,"\r\n\r\n");if(!body)return;*body=0;body+=4;
    char *save=NULL,*first=strtok_r(packet,"\n",&save);if(!first)return;
    int invite=!strncmp(first,"INVITE ",7),end=!strncmp(first,"BYE ",4) || !strncmp(first,"CANCEL ",7);
    int response=!strncmp(first,"SIP/2.0 ",8) && first[8]>='1' && first[8]<='2';
    int ack=!strncmp(first,"ACK ",4);if(!invite && !response && !end && !ack)return;
    char *id=NULL;unsigned seq=0,seq_seen=0,content=0,declared=0,len_seen=0,invalid=0;
    for(char *line=strtok_r(NULL,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
        line=trim(line);char *value=strchr(line,':');if(!value)continue;*value++=0;value=trim(value);
        if(!strcasecmp(line,"Call-ID") || !strcasecmp(line,"i")){if(id)invalid=1;id=value;}
        else if(!strcasecmp(line,"CSeq")){
            char *space=strpbrk(value," \t");if(seq_seen++ || !space){invalid=1;continue;}*space++=0;
            if(!number(value,2147483647,&seq) || (!end && strcmp(trim(space),ack?"ACK":"INVITE")))invalid=1;
        }else if(!strcasecmp(line,"Content-Type") || !strcasecmp(line,"c"))content=!strcasecmp(value,"application/sdp");
        else if(!strcasecmp(line,"Content-Length") || !strcasecmp(line,"l")){
            if(len_seen++ || !number(value,7000,&declared))invalid=1;
        }
    }
    if(invalid || !id || !*id || strlen(id)>=sizeof(p->call_id) || !seq_seen)return;
    if(end && !strcmp(id,p->call_id)){
        char text[100];int n=snprintf(text,sizeof(text),"AMR_CMR eligible=%lu changed=%lu enabled=%u\n",p->eligible,p->changed,p->enabled);
        if(fd>=0 && n>0 && n<(int)sizeof(text))(void)write(fd,text,(size_t)n);
        unsigned enabled=p->enabled;memset(p,0,sizeof(*p));p->enabled=enabled;return;
    }
    if(invite && (strcmp(id,p->call_id) || seq!=p->cseq)){
        unsigned enabled=p->enabled;memset(p,0,sizeof(*p));p->enabled=enabled;p->cseq=seq;strcpy(p->call_id,id);
    }
    if(strcmp(id,p->call_id) || seq!=p->cseq || !content || !len_seen || declared!=strlen(body))return;
    struct mf79u_amr_sdp s;parse_sdp(&s,body);
    if(!p->have_offer){p->offer_side=(unsigned)tx;p->have_offer=1;}
    if(!memcmp(&s,p->leg+tx,sizeof(s)))return; /* ESP injection / receive and SIP retransmissions */
    p->leg[tx]=s;p->active=p->leg[0].valid && p->leg[1].valid;
    report_sdp(p,tx,fd);
}
void mf79u_amr_observe(struct mf79u_amr_policy *p,int tx,const void *data,size_t length,int fd){
    if(length<20 || length>7000 || (tx!=0 && tx!=1))return;
    const char *s=data;
    if(memcmp(s,"SIP/2.0 ",8) && memcmp(s,"INVITE ",7) && memcmp(s,"BYE ",4) && memcmp(s,"CANCEL ",7) && memcmp(s,"ACK ",4))return;
    char *packet=malloc(length+1);if(!packet)return;
    memcpy(packet,data,length);packet[length]=0;observe_packet(p,tx,packet,length,fd);free(packet);
}
static unsigned bit(const unsigned char *p,size_t n){return (p[n/8]>>(7-n%8))&1;}
static int valid_payload(const unsigned char *p,size_t n,unsigned align,unsigned wb){
    static const unsigned bits[16]={95,103,118,134,148,159,204,244,39,0,0,0,0,0,0,0};
    static const unsigned wb_bits[16]={132,177,253,285,317,365,397,461,477,40,0,0,0,0,0,0};
    size_t cursor=align?8:4,speech=0;unsigned count=0,more=1;
    if(n<2 || (align && (p[0]&15)))return 0;
    while(more){
        if(++count>64 || cursor+6>n*8)return 0;
        more=bit(p,cursor++);unsigned ft=0;
        for(unsigned i=0;i<4;i++)ft=ft*2+bit(p,cursor++);
        cursor++;if(ft>(wb?9u:8u) && ft!=15 && !(wb && ft==14))return 0;
        unsigned speech_bits=wb?wb_bits[ft]:bits[ft];
        if(align){if(cursor+2>n*8 || bit(p,cursor) || bit(p,cursor+1))return 0;cursor+=2;speech+=((speech_bits+7)/8)*8;}
        else speech+=speech_bits;
    }
    return (cursor+speech+7)/8==n;
}
int mf79u_amr_rewrite(struct mf79u_amr_policy *p,unsigned local_port,uint32_t peer_ip,unsigned peer_port,
                     const void *data,size_t length,void *copy,size_t capacity){
    if(!p->enabled || !p->active || length<14 || length>capacity || local_port!=p->leg[1].port ||
       peer_port!=p->leg[0].port || peer_ip!=p->leg[0].address)return 0;
    const unsigned char *rtp=data;if((rtp[0]>>6)!=2)return 0;
    unsigned pt=rtp[1]&127,mask=negotiated(p,pt);if(!mask)return 0;
    size_t offset=12+(rtp[0]&15)*4,end=length;if(offset>end)return 0;
    if(rtp[0]&0x10){if(offset+4>end)return 0;size_t words=(size_t)rtp[offset+2]*256+rtp[offset+3];offset+=4+words*4;if(offset>end)return 0;}
    if(rtp[0]&0x20){unsigned padding=rtp[length-1];if(!padding || padding>end-offset)return 0;end-=padding;}
    if(!valid_payload(rtp+offset,end-offset,p->leg[1].codec[pt].align,p->leg[1].codec[pt].mapped==2))return 0;
    unsigned mode=highest(mask);p->eligible++;
    if(rtp[offset]>>4==mode)return 0;
    memcpy(copy,data,length);((unsigned char*)copy)[offset]=(unsigned char)((rtp[offset]&15)|(mode<<4));
    p->changed++;return 1;
}
