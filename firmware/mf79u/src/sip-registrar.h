/* One local account and one expiring, authenticated binding. No proxying.
 * Contacts are routed to their observed source, never an arbitrary Contact host.
 * SIP bodies, passwords, digests and subscriber numbers must not be logged. */
#ifndef MF79U_SIP_REGISTRAR_H
#define MF79U_SIP_REGISTRAR_H

static struct {
    char ip[16],call_id[256];
    unsigned port,cseq;
    long expires;
} sip_binding;
static struct {
    char value[33],ip[16];
    unsigned port,nc;
    long expires;
} sip_nonces[8];
static unsigned sip_nonce_next;
static pjsip_auth_srv sip_auth;
static pjsip_module sip_reg_module;

static long sip_now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec;}
static int sip_source_ip(pjsip_rx_data *r,char out[16]){
    struct in_addr address;
    return inet_pton(AF_INET,r->pkt_info.src_name,&address)==1 && inet_ntop(AF_INET,&address,out,16)!=NULL;
}
static int sip_server(void){return !strcmp(settings.role,"SERVER");}
static unsigned sip_binding_remaining(void){
    long n=sip_binding.expires-sip_now();
    return sip_server() && n>0?(unsigned)n:0;
}
static pj_status_t sip_local_credential(pj_pool_t *pool,const pj_str_t *realm,const pj_str_t *name,pjsip_cred_info *cred){
    (void)pool;
    if(pj_strcmp2(realm,"mf79u") || pj_strcmp2(name,settings.extension))return PJSIP_EAUTHACCNOTFOUND;
    cred->realm=pj_str("mf79u");cred->scheme=pj_str("digest");cred->username=pj_str(settings.extension);
    cred->data_type=PJSIP_CRED_DATA_PLAIN_PASSWD;cred->data=pj_str(settings.extension_password);
    return PJ_SUCCESS;
}
static void sip_reply(pjsip_rx_data *r,int code,const pjsip_hdr *headers){
    pjsip_endpt_respond(pjsua_get_pjsip_endpt(),&sip_reg_module,r,code,NULL,headers,NULL,NULL);
}
static void sip_challenge(pjsip_rx_data *r,pj_bool_t stale){
    unsigned char bytes[16];size_t used=0;
    int fd=open("/dev/urandom",O_RDONLY);if(fd<0){sip_reply(r,500,NULL);return;}
    while(used<sizeof(bytes)){
        ssize_t n=read(fd,bytes+used,sizeof(bytes)-used);
        if(n<0 && errno==EINTR)continue;
        if(n<=0)break;
        used+=(size_t)n;
    }
    close(fd);if(used!=sizeof(bytes)){sip_reply(r,500,NULL);return;}
    unsigned i=sip_nonce_next++%8;
    memset(&sip_nonces[i],0,sizeof(sip_nonces[i]));
    for(unsigned j=0;j<16;j++)snprintf(sip_nonces[i].value+j*2,3,"%02x",bytes[j]);
    if(!sip_source_ip(r,sip_nonces[i].ip)){sip_reply(r,403,NULL);return;}
    sip_nonces[i].port=(unsigned)r->pkt_info.src_port;sip_nonces[i].expires=sip_now()+90;
    char value_text[192];
    snprintf(value_text,sizeof(value_text),"Digest realm=\"mf79u\", nonce=\"%s\", algorithm=MD5, qop=\"auth\"%s",
             sip_nonces[i].value,stale?", stale=true":"");
    pjsip_hdr headers;pj_list_init(&headers);
    pj_str_t key=pj_str("WWW-Authenticate"),value=pj_str(value_text);
    pj_list_push_back(&headers,pjsip_generic_string_hdr_create(r->tp_info.pool,&key,&value));
    sip_reply(r,401,&headers);
}
/* The library verifies the digest; we additionally bind nonce to its source,
 * check the exact Request-URI, require qop/auth, and reject reused nonce counts. */
static int sip_authorise(pjsip_rx_data *r){
    pjsip_authorization_hdr *h=pjsip_msg_find_hdr(r->msg_info.msg,PJSIP_H_AUTHORIZATION,NULL);
    if(!h){sip_challenge(r,PJ_FALSE);return 0;}
    pjsip_digest_credential *d=&h->credential.digest;
    if(pj_stricmp2(&h->scheme,"Digest") || pj_strcmp2(&d->realm,"mf79u") ||
       pj_strcmp2(&d->username,settings.extension) || pj_stricmp2(&d->qop,"auth") ||
       !d->cnonce.slen || d->nc.slen!=8){sip_reply(r,403,NULL);return 0;}
    unsigned nc=0;
    for(int j=0;j<8;j++){
        unsigned char c=(unsigned char)d->nc.ptr[j];unsigned v;
        if(c>='0'&&c<='9')v=c-'0';else if(c>='a'&&c<='f')v=c-'a'+10;
        else if(c>='A'&&c<='F')v=c-'A'+10;else{sip_reply(r,403,NULL);return 0;}
        nc=(nc<<4)|v;
    }
    int found=-1;
    for(unsigned i=0;i<8;i++)if(!pj_strcmp2(&d->nonce,sip_nonces[i].value) &&
       !strcmp(sip_nonces[i].ip,r->pkt_info.src_name) && sip_nonces[i].port==(unsigned)r->pkt_info.src_port &&
       sip_nonces[i].expires>sip_now()){found=(int)i;break;}
    if(found<0 || !nc || nc<=sip_nonces[found].nc){sip_challenge(r,PJ_TRUE);return 0;}
    char uri[512];int n=pjsip_uri_print(PJSIP_URI_IN_REQ_URI,r->msg_info.msg->line.req.uri,uri,sizeof(uri));
    if(n<=0 || d->uri.slen!=n || memcmp(d->uri.ptr,uri,(size_t)n)){sip_reply(r,403,NULL);return 0;}
    int code=403;
    if(pjsip_auth_srv_verify(&sip_auth,r,&code)!=PJ_SUCCESS){sip_reply(r,403,NULL);return 0;}
    sip_nonces[found].nc=nc;return 1;
}
static pj_bool_t sip_local_request(pjsip_rx_data *r){
    if(!sip_server())return PJ_FALSE;
    pjsip_msg *msg=r->msg_info.msg;
    int reg=msg->line.req.method.id==PJSIP_REGISTER_METHOD;
    int invite=msg->line.req.method.id==PJSIP_INVITE_METHOD;
    if(!reg && !invite)return PJ_FALSE;
    if(invite && r->msg_info.to->tag.slen)return PJ_FALSE; /* existing dialog */
    struct in_addr ip;
    if(inet_pton(AF_INET,r->pkt_info.src_name,&ip)!=1){sip_reply(r,403,NULL);return PJ_TRUE;}
    /* Fixed work per request and bounded challenges protect the small device. */
    static long second;static unsigned requests;
    long now=sip_now();if(now!=second){second=now;requests=0;}
    if(++requests>24){sip_reply(r,503,NULL);return PJ_TRUE;}
    if(!sip_authorise(r))return PJ_TRUE;
    if(invite){
        if(!sip_binding_remaining() || strcmp(sip_binding.ip,r->pkt_info.src_name) ||
           sip_binding.port!=(unsigned)r->pkt_info.src_port){sip_reply(r,480,NULL);return PJ_TRUE;}
        return PJ_FALSE; /* authenticated, registered client -> normal SIM bridge */
    }
    pjsip_uri *to=pjsip_uri_get_uri(r->msg_info.to->uri);
    if(!PJSIP_URI_SCHEME_IS_SIP(to) || pj_strcmp2(&((pjsip_sip_uri*)to)->user,settings.extension)){
        sip_reply(r,403,NULL);return PJ_TRUE;
    }
    pjsip_contact_hdr *contact=pjsip_msg_find_hdr(msg,PJSIP_H_CONTACT,NULL);
    pjsip_expires_hdr *expires=pjsip_msg_find_hdr(msg,PJSIP_H_EXPIRES,NULL);
    unsigned ttl=expires?expires->ivalue:300;
    if(contact){
        if(pjsip_msg_find_hdr(msg,PJSIP_H_CONTACT,contact->next)){sip_reply(r,400,NULL);return PJ_TRUE;}
        if(contact->expires!=PJSIP_EXPIRES_NOT_SPECIFIED)ttl=contact->expires;
        if(contact->star && ttl){sip_reply(r,400,NULL);return PJ_TRUE;}
        if(!contact->star){
            pjsip_uri *uri=pjsip_uri_get_uri(contact->uri);
            if(!PJSIP_URI_SCHEME_IS_SIP(uri)){sip_reply(r,400,NULL);return PJ_TRUE;}
        }
    }
    if(ttl && ttl<60){
        pjsip_hdr headers;pj_list_init(&headers);
        pj_str_t key=pj_str("Min-Expires"),value=pj_str("60");
        pj_list_push_back(&headers,pjsip_generic_string_hdr_create(r->tp_info.pool,&key,&value));
        sip_reply(r,423,&headers);return PJ_TRUE;
    }
    if(ttl>3600)ttl=3600;
    char cid[256];pj_str_t id=r->msg_info.cid->id;
    if(id.slen<=0 || id.slen>255){sip_reply(r,400,NULL);return PJ_TRUE;}
    memcpy(cid,id.ptr,(size_t)id.slen);cid[id.slen]=0;
    unsigned seq=(unsigned)r->msg_info.cseq->cseq;
    if(sip_binding_remaining() && !strcmp(sip_binding.call_id,cid) && seq<=sip_binding.cseq){
        sip_reply(r,500,NULL);return PJ_TRUE;
    }
    if(contact){
        if(ttl){
            if(!sip_source_ip(r,sip_binding.ip)){sip_reply(r,403,NULL);return PJ_TRUE;}
            sip_binding.port=(unsigned)r->pkt_info.src_port;sip_binding.expires=now+ttl;
            strcpy(sip_binding.call_id,cid);sip_binding.cseq=seq;
        }else memset(&sip_binding,0,sizeof(sip_binding));
    }
    pjsip_hdr headers;pj_list_init(&headers);
    unsigned remaining=sip_binding_remaining();
    if(remaining){
        char dest[160];snprintf(dest,sizeof(dest),"sip:%s@%s:%u;transport=%s",settings.extension,sip_binding.ip,sip_binding.port,!strcmp(settings.transport,"TCP")?"tcp":"udp");
        pjsip_contact_hdr *out=pjsip_contact_hdr_create(r->tp_info.pool);
        out->uri=pjsip_parse_uri(r->tp_info.pool,dest,strlen(dest),0);out->expires=remaining;
        pj_list_push_back(&headers,out);
    }
    pjsip_expires_hdr *e=pjsip_expires_hdr_create(r->tp_info.pool,(int)remaining);pj_list_push_back(&headers,e);
    sip_reply(r,200,&headers);status_file();return PJ_TRUE;
}
static void sip_binding_reset(void){
    memset(&sip_binding,0,sizeof(sip_binding));memset(sip_nonces,0,sizeof(sip_nonces));sip_nonce_next=0;
}
static int sip_registrar_init(void){
    sip_binding_reset();
    if(!sip_server())return 0;
    pj_pool_t *pool=pjsua_pool_create("local-registrar",1024,1024);pj_str_t realm=pj_str("mf79u");
    if(pjsip_auth_srv_init(pool,&sip_auth,&realm,sip_local_credential,0)!=PJ_SUCCESS)return 1;
    sip_reg_module=(pjsip_module){.name={"mf79u-registrar",15},.id=-1,
        .priority=PJSIP_MOD_PRIORITY_UA_PROXY_LAYER-1,.on_rx_request=sip_local_request};
    return pjsip_endpt_register_module(pjsua_get_pjsip_endpt(),&sip_reg_module)!=PJ_SUCCESS;
}
static int sip_local_source(pjsip_rx_data *r){
    return sip_binding_remaining() && !strcmp(sip_binding.ip,r->pkt_info.src_name) &&
           sip_binding.port==(unsigned)r->pkt_info.src_port;
}
static int sip_local_target(char *target,size_t size){
    if(!sip_binding_remaining())return 0;
    snprintf(target,size,"sip:%s@%s:%u;transport=%s",settings.extension,sip_binding.ip,sip_binding.port,!strcmp(settings.transport,"TCP")?"tcp":"udp");
    return 1;
}
#endif
