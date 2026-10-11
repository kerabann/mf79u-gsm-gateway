/* Synthetic SIP/SDP/RTP only: no sockets, SIM, calls or speech recordings. */
#include "amr-rate-policy.h"
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"AMR policy test failed line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static void message(struct mf79u_amr_policy *p,int tx,const char *first,const char *id,unsigned seq,const char *method,const char *body){
    char sip[3000];int n=snprintf(sip,sizeof(sip),"%s\r\nCall-ID: %s\r\nCSeq: %u %s\r\nContent-Type: application/sdp\r\nContent-Length: %u\r\n\r\n%s",
        first,id,seq,method,(unsigned)strlen(body),body);
    CHECK(n>0 && n<(int)sizeof(sip));mf79u_amr_observe(p,tx,sip,(size_t)n,-1);
}
static void sdp(struct mf79u_amr_policy *p,int tx,const char *fmt,const char *codec,const char *transport){
    char body[2000];int n=snprintf(body,sizeof(body),"v=0\r\nc=IN IP4 10.0.0.%u\r\nm=audio %u %s 96 101\r\na=rtpmap:96 %s\r\na=rtpmap:101 telephone-event/8000\r\n%s%s%s",
        tx?2:1,tx?50000:40000,transport,codec,*fmt?"a=fmtp:96 ":"",fmt,*fmt?"\r\n":"");
    CHECK(n>0 && n<(int)sizeof(body));message(p,tx,tx?"SIP/2.0 200 OK":"INVITE sip:synthetic SIP/2.0","synthetic-call",1,"INVITE",body);
}
static void setbit(unsigned char *p,size_t *cursor,unsigned value){if(value)p[*cursor/8]|=1u<<(7-*cursor%8);(*cursor)++;}
static size_t rtp_kind(unsigned char out[256],unsigned align,unsigned ft,unsigned multi,unsigned wb){
    static const unsigned bits[]={95,103,118,134,148,159,204,244,39,0,0,0,0,0,0,0};
    static const unsigned wb_bits[]={132,177,253,285,317,365,397,461,477,40,0,0,0,0,0,0};
    memset(out,0,256);out[0]=0x80;out[1]=96;out[12]=0xf0;size_t cursor=align?8:4;
    for(unsigned frame=0;frame<=multi;frame++){
        setbit(out+12,&cursor,frame<multi);
        for(int i=3;i>=0;i--)setbit(out+12,&cursor,(ft>>i)&1);
        setbit(out+12,&cursor,1);if(align)cursor+=2;
    }
    unsigned frame_bits=wb?wb_bits[ft]:bits[ft];
    cursor+=(multi+1)*(align?((frame_bits+7)/8)*8:frame_bits);return 12+(cursor+7)/8;
}
static size_t rtp(unsigned char out[256],unsigned align,unsigned ft,unsigned multi){return rtp_kind(out,align,ft,multi,0);}
static int rewrite(struct mf79u_amr_policy *p,const void *in,size_t n,void *out){
    return mf79u_amr_rewrite(p,50000,inet_addr("10.0.0.1"),40000,in,n,out,256);
}
static void changed_only(const unsigned char *before,const unsigned char *after,size_t n,size_t offset,unsigned mode){
    for(size_t i=0;i<n;i++)CHECK(after[i]==(i==offset?(unsigned char)((before[i]&15)|(mode<<4)):before[i]));
}
static struct mf79u_amr_policy negotiated(const char *offer,const char *answer,unsigned align){
    struct mf79u_amr_policy p={.enabled=1};char fmt[200];
    snprintf(fmt,sizeof(fmt),"octet-align=%u%s%s",align,*offer?"; mode-set=":"",offer);sdp(&p,0,fmt,"AMR/8000","RTP/AVP");
    snprintf(fmt,sizeof(fmt),"octet-align=%u%s%s",align,*answer?"; mode-set=":"",answer);sdp(&p,1,fmt,"AMR/8000","RTP/AVP");return p;
}
int main(void){
    {
        const char *body="v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio 40000 RTP/AVP 0 9 100 112 117 103\r\n"
            "a=rtpmap:100 AMR/8000\r\na=fmtp:100 mode-set=0,1,2,3,4,5,6,7\r\n"
            "a=rtpmap:112 AMR-WB/16000\r\na=fmtp:112 mode-set=0,1,2,3,4,5,6,7,8\r\n"
            "a=rtpmap:117 AMR-WB/16000\r\na=fmtp:117 mode-set=0,1,2\r\na=rtpmap:103 telephone-event/16000\r\n";
        char in[3000],out[3000];int n=snprintf(in,sizeof(in),"INVITE sip:synthetic SIP/2.0\r\nCall-ID: synthetic-call\r\nCSeq: 1 INVITE\r\nContent-Type: application/sdp\r\nContent-Length: %u\r\n\r\n%s",(unsigned)strlen(body),body);
        size_t length=mf79u_codec_offer(in,(size_t)n,out,sizeof(out)-1,0);CHECK(length);out[length]=0;
        CHECK(strstr(out,"m=audio 40000 RTP/AVP 112 100 103\r\n"));CHECK(!strstr(out,"a=rtpmap:117"));CHECK(!strstr(out,"a=fmtp:117"));
        struct mf79u_amr_policy observed={0};mf79u_amr_observe(&observed,0,out,length,-1);
        CHECK(observed.leg[0].valid && observed.leg[0].codec[112].modes==511 && !observed.leg[0].codec[117].listed);
        length=mf79u_codec_offer(in,(size_t)n,out,sizeof(out)-1,1);CHECK(length);out[length]=0;CHECK(strstr(out,"m=audio 40000 RTP/AVP 112 100 103\r\n"));
        length=mf79u_codec_offer(in,(size_t)n,out,sizeof(out)-1,2);CHECK(length);out[length]=0;CHECK(strstr(out,"m=audio 40000 RTP/AVP 100 103\r\n"));
        CHECK(!mf79u_codec_offer(in,(size_t)n,out,20,0));
        for(size_t cut=0;cut<(size_t)n;cut++)CHECK(!mf79u_codec_offer(in,cut,out,sizeof(out),0));
        char *a=strstr(in,"a=fmtp:112 mode-set=");CHECK(a);a[19]='9';
        length=mf79u_codec_offer(in,(size_t)n,out,sizeof(out)-1,0);CHECK(length);out[length]=0;CHECK(strstr(out,"m=audio 40000 RTP/AVP 117 100 103\r\n"));
        puts("Operator WB 23.85 / NB fallback profile selection tests passed");
    }
    /* Inspect operator codec names without persisting arbitrary SDP text. */
    {
        struct mf79u_amr_policy observed={.enabled=1};int logs[2];CHECK(!pipe(logs));
        const char *body="v=0\r\nc=IN IP4 10.0.0.1\r\nm=audio 40000 RTP/AVP 96 97 9 98\r\na=rtpmap:96 EVS/16000\r\na=rtpmap:97 AMR-WB+/72000\r\na=rtpmap:98 private-synthetic/16000\r\n";
        char sip[1500],result[1500];int length=snprintf(sip,sizeof(sip),"INVITE sip:synthetic SIP/2.0\r\nCall-ID: sensitive-synthetic\r\nCSeq: 1 INVITE\r\nContent-Type: application/sdp\r\nContent-Length: %u\r\n\r\n%s",(unsigned)strlen(body),body);
        CHECK(length>0 && length<(int)sizeof(sip));mf79u_amr_observe(&observed,0,sip,(size_t)length,logs[1]);close(logs[1]);
        ssize_t count=read(logs[0],result,sizeof(result)-1);CHECK(count>0);result[count]=0;close(logs[0]);
        CHECK(strstr(result,"codec=EVS pt=96 rtp_clock=16000"));
        CHECK(strstr(result,"codec=AMR-WB+ pt=97 rtp_clock=72000"));
        CHECK(strstr(result,"codec=G722 pt=9 rtp_clock=8000"));
        CHECK(strstr(result,"unknown_payloads=1"));
        CHECK(!strstr(result,"sensitive") && !strstr(result,"private-synthetic") && !strstr(result,"10.0.0.1"));
    }
    unsigned char in[256],out[256],saved[256];size_t n=rtp(in,0,1,0);
    struct mf79u_amr_policy p={.enabled=1};CHECK(!rewrite(&p,in,n,out));
    sdp(&p,0,"mode-set=1,7","AMR/8000","RTP/AVP");CHECK(!rewrite(&p,in,n,out));
    sdp(&p,1,"mode-set=1,7","AMR/8000","RTP/AVP");CHECK(rewrite(&p,in,n,out));changed_only(in,out,n,12,7);
    CHECK(p.eligible==1 && p.changed==1);CHECK(!rewrite(&p,out,n,saved));CHECK(p.eligible==2 && p.changed==1);
    CHECK(!mf79u_amr_rewrite(&p,50001,inet_addr("10.0.0.1"),40000,in,n,out,256));
    CHECK(!mf79u_amr_rewrite(&p,50000,inet_addr("10.0.0.3"),40000,in,n,out,256));
    CHECK(!mf79u_amr_rewrite(&p,50000,inet_addr("10.0.0.1"),40001,in,n,out,256));
    CHECK(!mf79u_amr_rewrite(&p,50000,inet_addr("10.0.0.1"),40000,in,n,out,n-1));
    p.enabled=0;CHECK(!rewrite(&p,in,n,out));p.enabled=1;
    /* Retransmissions keep counters; another call's BYE cannot reset this call. */
    sdp(&p,1,"mode-set=1,7","AMR/8000","RTP/AVP");CHECK(p.changed==1);
    message(&p,0,"BYE sip:synthetic SIP/2.0","other-call",1,"BYE","");CHECK(p.active);
    message(&p,0,"BYE sip:synthetic SIP/2.0","synthetic-call",1,"BYE","");CHECK(!p.active && p.enabled);
    CHECK(!rewrite(&p,in,n,out));
    for(unsigned align=0;align<2;align++){
        p=negotiated("","",align);
        for(unsigned ft=0;ft<16;ft++)if(ft<=8 || ft==15){
            n=rtp(in,align,ft,0);memcpy(saved,in,n);CHECK(rewrite(&p,in,n,out));changed_only(in,out,n,12,7);CHECK(!memcmp(in,saved,n));
            CHECK(!rewrite(&p,in,n-1,out));n=rtp(in,align,ft,1);CHECK(rewrite(&p,in,n,out));changed_only(in,out,n,12,7);
        }
        n=rtp(in,align,1,0);size_t payload=n-12;memmove(in+24,in+12,payload);memset(in+12,0,12);
        in[0]=0xb1;in[16]=0x10;in[19]=1;n+=16;memset(in+n-4,0,4);in[n-1]=4;
        CHECK(rewrite(&p,in,n,out));changed_only(in,out,n,24,7);
        in[n-1]=255;CHECK(!rewrite(&p,in,n,out));in[n-1]=4;in[19]=255;CHECK(!rewrite(&p,in,n,out));
    }
    n=rtp(in,0,1,0);
    p=negotiated("","0,2,4,6",0);CHECK(rewrite(&p,in,n,out));changed_only(in,out,n,12,6);
    p=negotiated("1,7","1",0);CHECK(!rewrite(&p,in,n,out));
    p=negotiated("1,7","",0);CHECK(!rewrite(&p,in,n,out));
    const char *bad[]={"mode-set=8","mode-set=1,1","mode-set=1,","mode-set=1; mode-set=7","octet-align=2","crc=1","robust-sorting=1","interleaving=1","channels=2"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++){
        p=(struct mf79u_amr_policy){.enabled=1};sdp(&p,0,bad[i],"AMR/8000","RTP/AVP");sdp(&p,1,bad[i],"AMR/8000","RTP/AVP");CHECK(!rewrite(&p,in,n,out));
    }
    p=(struct mf79u_amr_policy){.enabled=1};sdp(&p,0,"","AMR-WB/16000","RTP/AVP");sdp(&p,1,"","AMR-WB/16000","RTP/AVP");CHECK(!rewrite(&p,in,n,out));
    for(unsigned align=0;align<2;align++){
        char fmt[80];snprintf(fmt,sizeof(fmt),"octet-align=%u",align);
        p=(struct mf79u_amr_policy){.enabled=1};sdp(&p,0,fmt,"AMR-WB/16000","RTP/AVP");sdp(&p,1,fmt,"AMR-WB/16000","RTP/AVP");
        for(unsigned ft=0;ft<16;ft++)if(ft<=9 || ft>=14){
            n=rtp_kind(in,align,ft,1,1);CHECK(rewrite(&p,in,n,out));changed_only(in,out,n,12,8);CHECK(!rewrite(&p,in,n-1,out));
        }
    }
    p=(struct mf79u_amr_policy){.enabled=1};sdp(&p,0,"mode-set=0,1,2","AMR-WB/16000","RTP/AVP");sdp(&p,1,"mode-set=0,1,2","AMR-WB/16000","RTP/AVP");
    n=rtp_kind(in,0,1,0,1);CHECK(rewrite(&p,in,n,out));changed_only(in,out,n,12,2);
    sdp(&p,1,"mode-set=0,1,2","AMR/8000","RTP/AVP");CHECK(!rewrite(&p,in,n,out));
    n=rtp(in,0,1,0);
    p=(struct mf79u_amr_policy){.enabled=1};sdp(&p,0,"","AMR/8000","RTP/SAVP");sdp(&p,1,"","AMR/8000","RTP/SAVP");CHECK(!rewrite(&p,in,n,out));
    p=negotiated("","",0);sdp(&p,1,"octet-align=1","AMR/8000","RTP/AVP");CHECK(!rewrite(&p,in,n,out));
    p=negotiated("","",1);n=rtp(in,1,1,0);in[12]|=1;CHECK(!rewrite(&p,in,n,out));in[12]&=0xf0;in[13]|=1;CHECK(!rewrite(&p,in,n,out));
    p=negotiated("","",0);n=rtp(in,0,1,0);in[1]=101;CHECK(!rewrite(&p,in,n,out));in[1]=96;in[0]=0x40;CHECK(!rewrite(&p,in,n,out));
    p=negotiated("","",0);n=rtp(in,0,1,0);
    message(&p,0,"INVITE sip:synthetic SIP/2.0","synthetic-call",2,"INVITE","");CHECK(!rewrite(&p,in,n,out));
    /* Malformed/truncated SIP stays disabled, including embedded NUL bytes. */
    p=(struct mf79u_amr_policy){.enabled=1};
    const char *malformed="INVITE sip:x SIP/2.0\r\nCall-ID: synthetic-call\r\nCSeq: 1 INVITE\r\nContent-Type: application/sdp\r\nContent-Length: 1\r\n\r\nv=0\r\n";
    mf79u_amr_observe(&p,0,malformed,strlen(malformed),-1);CHECK(!p.active);
    for(size_t cut=0;cut<strlen(malformed);cut++)mf79u_amr_observe(&p,0,malformed,cut,-1);
    puts("AMR NB+WB SDP negotiation / endpoint / BE+OA CMR-only / truncation selftests passed");return 0;
}
