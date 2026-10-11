/* SIP MESSAGE <-> device-local SMS queue. No HTTP exposure or shell commands.
 * Keep operator I/O asynchronous and never log numbers or message bodies. */
#ifndef MF79U_SIP_SMS_H
#define MF79U_SIP_SMS_H
#include <sys/un.h>

static pjsip_module sms_module;
static char sms_pending[33];
static int sms_inflight,sms_ack_pending;
static long sms_last_poll,sms_last_attempt;
/* A provisional response keeps Linphone's MESSAGE transaction pending until
 * B03 confirms SEND_SMS. Transaction layer owns UDP retransmission/deduplication. */
static int sms_ipc(unsigned,const unsigned char*,size_t,unsigned char*,size_t*);
static struct sms_submission {
    char id[33];long started;
    pjsip_transaction *tsx;
    pjsip_tx_data *response;
} sms_submissions[8];
static void sms_submission_finish(struct sms_submission *s,int code){
    s->response->msg->line.status.code=code;
    s->response->msg->line.status.reason=*pjsip_get_status_text(code);
    pjsip_tx_data_invalidate_msg(s->response);
    if(s->tsx->state>=PJSIP_TSX_STATE_COMPLETED ||
       pjsip_tsx_send_msg(s->tsx,s->response)!=PJ_SUCCESS)
        pjsip_tx_data_dec_ref(s->response);
    pj_grp_lock_dec_ref(s->tsx->grp_lock);
    memset(s,0,sizeof(*s));
}
static void sms_close(void){
    for(unsigned i=0;i<8;i++)if(sms_submissions[i].tsx)
        sms_submission_finish(&sms_submissions[i],503);
}
static void sms_submission_tick(long now){
    for(unsigned i=0;i<8;i++){
        struct sms_submission *s=&sms_submissions[i];if(!s->tsx)continue;
        unsigned char reply[1];size_t size=0;
        int result=sms_ipc(5,(unsigned char*)s->id,32,reply,&size);
        if(result==0)sms_submission_finish(s,200);
        else if(result==6 || now-s->started>=20)sms_submission_finish(s,504);
    }
}

static void sms_put16(unsigned char *p,unsigned v){p[0]=(unsigned char)(v>>8);p[1]=(unsigned char)v;}
static unsigned sms_get16(const unsigned char *p){return ((unsigned)p[0]<<8)|p[1];}
static int sms_io(int fd,unsigned char *p,size_t n,int writing){
    while(n){ssize_t r=writing?send(fd,p,n,MSG_NOSIGNAL):recv(fd,p,n,0);
        if(r<0 && errno==EINTR)continue;
        if(r<=0)return -1;
        p+=r;n-=(size_t)r;
    }return 0;
}
static int sms_ipc(unsigned op,const unsigned char *data,size_t size,unsigned char *reply,size_t *length){
    if(size>8192)return -1;
    const char *path=getenv("MF79U_SMS_SOCKET");
    if(!path)path="/mnt/userdata/mf79u/sms-sip.sock";
    struct sockaddr_un address={.sun_family=AF_UNIX};
    if(strlen(path)>=sizeof(address.sun_path))return -1;
    strcpy(address.sun_path,path);
    int fd=socket(AF_UNIX,SOCK_STREAM,0);if(fd<0)return -1;
    struct timeval timeout={.tv_usec=200000};
    setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
    unsigned char header[9]={'M','S','M','1',(unsigned char)op};
    uint32_t n=htonl((uint32_t)size);memcpy(header+5,&n,4);
    int result=-1;
    if(connect(fd,(struct sockaddr*)&address,sizeof(address)) || sms_io(fd,header,9,1) ||
       (size && sms_io(fd,(unsigned char*)data,size,1)) || sms_io(fd,header,9,0))goto done;
    memcpy(&n,header+5,4);n=ntohl(n);
    if(memcmp(header,"MSM1",4) || n>*length || (n && sms_io(fd,reply,n,0)))goto done;
    *length=n;result=header[4];
done:
    close(fd);return result;
}
static void sms_reply(pjsip_rx_data *r,int code){
    pjsip_endpt_respond(pjsua_get_pjsip_endpt(),&sms_module,r,code,NULL,NULL,NULL,NULL);
}
/* CPIM outer metadata is never trusted for destination routing. Only its
 * inner MIME type/body is used; compose/read receipts must not send an SMS. */
static int sms_text(pjsip_msg_body *body,char out[2681],size_t *length){
    if(!body || !body->data || body->len==0 || body->len>4096)return 400;
    const char *source=body->data;size_t n=body->len;
    int plain=!pj_stricmp2(&body->content_type.type,"text") && !pj_stricmp2(&body->content_type.subtype,"plain");
    int cpim=!pj_stricmp2(&body->content_type.type,"message") && !pj_stricmp2(&body->content_type.subtype,"cpim");
    if(!plain && !cpim){
        if(!pj_stricmp2(&body->content_type.type,"application") &&
           (!pj_stricmp2(&body->content_type.subtype,"im-iscomposing+xml") || !pj_stricmp2(&body->content_type.subtype,"imdn+xml")))return 200;
        return 415;
    }
    if(memchr(source,0,n))return 400;
    if(cpim){
        char copy[4097];memcpy(copy,source,n);copy[n]=0;
        char *first=strstr(copy,"\r\n\r\n");size_t skip=4;
        if(!first){first=strstr(copy,"\n\n");skip=2;}if(!first)return 400;
        char *headers=first+skip,*second=strstr(headers,"\r\n\r\n");skip=4;
        if(!second){second=strstr(headers,"\n\n");skip=2;}if(!second)return 400;
        *second=0;int type=0;char *save=NULL;
        for(char *line=strtok_r(headers,"\r\n",&save);line;line=strtok_r(NULL,"\r\n",&save)){
            if(strncasecmp(line,"Content-Type:",13))continue;
            char *value=line+13;while(*value==' '||*value=='\t')value++;
            char *end=value+strcspn(value,"; \t");*end=0;
            if(!strcasecmp(value,"text/plain"))type=1;
            else if(!strcasecmp(value,"application/imdn+xml") || !strcasecmp(value,"application/im-iscomposing+xml"))type=2;
            else type=3;
        }
        if(type==2)return 200;
        if(type!=1)return 415;
        size_t offset=(size_t)(second+skip-copy);source=(const char*)body->data+offset;n=body->len-offset;
    }
    if(n==0)return 400;
    if(n>2680)return 413;
    memcpy(out,source,n);out[n]=0;*length=n;return 0;
}
static pj_bool_t sms_receive(pjsip_rx_data *r){
    if(pj_stricmp2(&r->msg_info.msg->line.req.method.name,"MESSAGE"))return PJ_FALSE;
    if(!sip_active)return PJ_FALSE;
    long now=sip_now();static long second;static unsigned count;
    if(now!=second){second=now;count=0;}
    if(++count>8){sms_reply(r,503);return PJ_TRUE;}
    if(sip_server()){
        if(!sip_authorise(r))return PJ_TRUE;
        if(!sip_local_source(r)){sms_reply(r,480);return PJ_TRUE;}
    }else if(!trusted_peer(r->pkt_info.src_name)){sms_reply(r,403);return PJ_TRUE;}
    pjsip_uri *uri=pjsip_uri_get_uri(r->msg_info.msg->line.req.uri);
    if(!PJSIP_URI_SCHEME_IS_SIP(uri) && !PJSIP_URI_SCHEME_IS_SIPS(uri)){sms_reply(r,484);return PJ_TRUE;}
    pj_str_t user=((pjsip_sip_uri*)uri)->user;
    char number[34];
    if(user.slen<1 || user.slen>33){sms_reply(r,484);return PJ_TRUE;}
    memcpy(number,user.ptr,(size_t)user.slen);number[user.slen]=0;
    char text[2681];size_t bytes=0;int code=sms_text(r->msg_info.msg->body,text,&bytes);
    if(code){sms_reply(r,code);return PJ_TRUE;}
    if(!sip_phone(number)){sms_reply(r,484);return PJ_TRUE;}
    pj_str_t cid=r->msg_info.cid->id;
    if(cid.slen<1 || cid.slen>255){sms_reply(r,400);return PJ_TRUE;}
    pj_md5_context context;unsigned char hash[16];char seq[32],id[33];
    snprintf(seq,sizeof(seq),":%ld",(long)r->msg_info.cseq->cseq);
    pj_md5_init(&context);pj_md5_update(&context,(const unsigned char*)cid.ptr,(unsigned)cid.slen);
    pj_md5_update(&context,(const unsigned char*)seq,(unsigned)strlen(seq));pj_md5_final(&context,hash);
    for(unsigned i=0;i<16;i++)snprintf(id+2*i,3,"%02x",hash[i]);
    unsigned char request[2749],reply[1];size_t length=0,phone=strlen(number);
    memcpy(request,id,32);sms_put16(request+32,(unsigned)phone);sms_put16(request+34,(unsigned)bytes);
    memcpy(request+36,number,phone);memcpy(request+36+phone,text,bytes);
    struct sms_submission *pending=NULL;
    for(unsigned i=0;i<8;i++)if(!sms_submissions[i].tsx){pending=&sms_submissions[i];break;}
    if(!pending){sms_reply(r,503);return PJ_TRUE;}
    pjsip_tx_data *response=NULL;pjsip_transaction *tsx=NULL;
    if(pjsip_endpt_create_response(pjsua_get_pjsip_endpt(),r,200,NULL,&response)!=PJ_SUCCESS){
        sms_reply(r,503);return PJ_TRUE;
    }
    if(pjsip_endpt_respond(pjsua_get_pjsip_endpt(),&sms_module,r,100,NULL,NULL,NULL,&tsx)!=PJ_SUCCESS){
        pjsip_tx_data_dec_ref(response);return PJ_TRUE;
    }
    pj_grp_lock_add_ref(tsx->grp_lock);
    pending->tsx=tsx;pending->response=response;pending->started=now;strcpy(pending->id,id);
    int result=sms_ipc(1,request,36+phone+bytes,reply,&length);
    if(result!=0)sms_submission_finish(pending,result==1?400:result==4?409:503);
    return PJ_TRUE;
}
static void sms_pager_status(pjsua_call_id id,const pj_str_t *to,const pj_str_t *body,void *token,
                             pjsip_status_code code,const pj_str_t *reason){
    (void)id;(void)to;(void)body;(void)reason;
    if(token!=sms_pending || code<200)return;
    sms_inflight=0;
    if(code<300)sms_ack_pending=1;
    else {sms_pending[0]=0;sms_last_attempt=sip_now();}
}
static void sms_tick(void){
    if(!sip_active)return;
    long now=sip_now();if(now==sms_last_poll)return;sms_last_poll=now;
    sms_submission_tick(now);
    unsigned char reply[8192];size_t length=sizeof(reply);
    if(sms_ack_pending){
        if(sms_ipc(3,(unsigned char*)sms_pending,32,reply,&length)==0){sms_ack_pending=0;sms_pending[0]=0;}
        return;
    }
    if(sms_inflight || now-sms_last_attempt<30)return;
    char target[512];
    if(sip_server()){
        if(!sip_local_target(target,sizeof(target)))return;
    }else snprintf(target,sizeof(target),"sip:%s@%s:%u",settings.incoming_user,settings.server,settings.port);
    if(sms_ipc(2,NULL,0,reply,&length)!=0 || !length)return;
    if(length<38)return;
    unsigned a=sms_get16(reply+32),b=sms_get16(reply+34),c=sms_get16(reply+36);
    if(a<1 || a>128 || b<1 || b>2680 || c>40 || 38+a+b+c!=length)return;
    char user[385];size_t at=0;const char *hex="0123456789ABCDEF";
    for(unsigned i=0;i<a;i++){
        unsigned char ch=reply[38+i];
        if((ch>='0'&&ch<='9')||(ch>='a'&&ch<='z')||(ch>='A'&&ch<='Z')||ch=='+'||ch=='-'||ch=='_'||ch=='.')user[at++]=(char)ch;
        else {user[at++]='%';user[at++]=hex[ch>>4];user[at++]=hex[ch&15];}
    }user[at]=0;
    char from[512];snprintf(from,sizeof(from),"sip:%s@%s:%u",user,local_ip,settings.local_port);
    pjsua_msg_data message;pjsua_msg_data_init(&message);message.local_uri=pj_str(from);
    pj_str_t dest=pj_str(target),mime=pj_str("text/plain"),text={(char*)reply+38+a,(pj_ssize_t)b};
    memcpy(sms_pending,reply,32);sms_pending[32]=0;sms_inflight=1;
    if(pjsua_im_send(account,&dest,&mime,&text,&message,sms_pending)!=PJ_SUCCESS){
        sms_inflight=0;sms_pending[0]=0;sms_last_attempt=now;
    }
}
static int sms_init(void){
    sms_inflight=0;sms_last_poll=0;
    sms_module=(pjsip_module){.name={"mf79u-sms",9},.id=-1,
        .priority=PJSIP_MOD_PRIORITY_UA_PROXY_LAYER-2,.on_rx_request=sms_receive};
    return pjsip_endpt_register_module(pjsua_get_pjsip_endpt(),&sms_module)!=PJ_SUCCESS;
}
#endif
