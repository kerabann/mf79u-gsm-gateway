/* SIP endpoint on the modem LAN. Cellular control/media live in the native
 * controller and its selected IMS/CS backend. No credentials/audio logged. */
#include <pjsua-lib/pjsua.h>
#include <pjmedia/plc.h>
#include <pjmedia-codec/opus.h>
#include "pcm-queue.h"
#include "sip-settings.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#ifdef MF79U_DIAGNOSTIC_FAULTS
#include "diagnostic-fault.h"
#endif

/* Compile-time separation for the physical CS media diagnostic. Production
 * defaults preserve the existing sockets, status path and caller-ID file. */
#ifndef MF79U_SIP_STATUS_BASE
#define MF79U_SIP_STATUS_BASE "/dev/.mf79u-gateway-status"
#endif
#ifndef MF79U_SIP_CALLER_FILE
#define MF79U_SIP_CALLER_FILE "/dev/.mf79u-incoming-caller"
#endif
#ifndef MF79U_SIP_PCM_RX
#define MF79U_SIP_PCM_RX 46000
#define MF79U_SIP_PCM_PEER 46001
#endif
#ifndef MF79U_SIP_RTP_PORT
#define MF79U_SIP_RTP_PORT 12000
#endif
static pjsua_call_id call=PJSUA_INVALID_ID;
static pjsua_acc_id account;
static pjsua_conf_port_id pcm_slot;
static int from_sim, ready, rx=-1, tx=-1, stopping, released;
static const char *cellular_backend="none";
static int sip_active;
static volatile sig_atomic_t interrupted;
static unsigned long frames_in,frames_out,nonzero_in,nonzero_out;
static time_t call_started;
static struct mf79u_pcm_queue downlink;
static pjmedia_plc *downlink_plc;
static pj_mutex_t *pcm_lock;
static struct sockaddr_in native_pcm;
static struct sip_settings settings;
static const char *settings_path="/mnt/userdata/mf79u/gateway.ini";
static char active_codec[16]="";
static char local_ip[16];
static char server_ips[8][16];static unsigned server_ip_count;
static volatile sig_atomic_t reload_requested;
static int sip_server(void);
static unsigned sip_binding_remaining(void);
static void signal_reload(int s){(void)s;reload_requested=1;}
static void status_file(void){
    pjsua_acc_info ai;memset(&ai,0,sizeof(ai));if(sip_active)pjsua_acc_get_info(account,&ai);
    FILE *f=fopen(MF79U_SIP_STATUS_BASE ".tmp","w");if(!f)return;
    fprintf(f,"{\"version\":\"0.8\",\"running\":true,\"pid\":%ld,\"imsReady\":%s,\"voiceReady\":%s,\"voiceBackend\":\"%s\",\"activeCall\":%s,\"role\":\"%s\",\"registerMode\":%s,\"registered\":%s,\"localRegistered\":%s,\"localRegistrationExpires\":%u,\"registrationCode\":%d,\"codec\":\"%s\"}\n",(long)getpid(),ready && !strcmp(cellular_backend,"ims")?"true":"false",ready?"true":"false",cellular_backend,call!=PJSUA_INVALID_ID?"true":"false",settings.role,settings.registration?"true":"false",ai.status==200?"true":"false",sip_binding_remaining()?"true":"false",sip_binding_remaining(),ai.status,active_codec);
    fclose(f);rename(MF79U_SIP_STATUS_BASE ".tmp",MF79U_SIP_STATUS_BASE ".json");
}
#include "sip-registrar.h"
static void registration_changed(pjsua_acc_id id){(void)id;status_file();}
static void transport_changed(pjsip_transport *transport,pjsip_transport_state state,const pjsip_transport_state_info *info){
    if(transport->key.type==PJSIP_TRANSPORT_TLS && state==PJSIP_TP_STATE_DISCONNECTED && info && info->status==PJSIP_TLS_ECERTVERIF)
        puts("SIP_TLS_CERTIFICATE_REJECTED"); /* No certificate contents or credentials. */
}
static int trusted_peer(const char *ip){
    char peers[256];strcpy(peers,settings.trusted_peers);char *save=NULL;
    for(char *p=strtok_r(peers,",",&save);p;p=strtok_r(NULL,",",&save))if(!strcmp(p,ip))return 1;
    for(unsigned i=0;i<server_ip_count;i++)if(!strcmp(ip,server_ips[i]))return 1;
    return 0;
}
#include "sip-sms.h"
static unsigned pcm_rate=8000,pcm_samples=160,pcm_bytes=320;
#ifdef MF79U_SIP_PCM_LEVELS
/* Diagnostic build only: aggregate levels, never sample/packet contents. */
struct pcm_levels {unsigned frames,peak,active,samples;uint64_t energy;};
static struct pcm_levels to_sip_levels,from_sip_levels;
static void pcm_level(struct pcm_levels *s,const char *leg,const void *buffer){
    const int16_t *data=buffer;
    for(unsigned i=0;i<pcm_samples;i++){
        int v=data[i];unsigned a=(unsigned)(v<0?-v:v);
        if(a>s->peak)s->peak=a;
        if(a>64)s->active++;
        s->energy+=(int64_t)v*v;
    }
    s->samples+=pcm_samples;
    if(++s->frames==50){
        printf("PCM_LEVEL leg=%s frames=%u samples=%u peak=%u active=%u energy=%llu\n",leg,s->frames,s->samples,s->peak,s->active,(unsigned long long)s->energy);
        memset(s,0,sizeof(*s));
    }
}
#endif

static void signal_stop(int s){(void)s;interrupted=1;}
static pj_status_t pcm_get(pjmedia_port *port,pjmedia_frame *frame){
    (void)port;
    unsigned char data[644];
    memset(frame->buf,0,pcm_bytes);frame->size=pcm_bytes;frame->type=PJMEDIA_FRAME_TYPE_AUDIO;
    pj_mutex_lock(pcm_lock);
    for(int i=0;i<32;i++){
        ssize_t n=recv(rx,data,sizeof(data),MSG_DONTWAIT);
        if(n<0)break;
        if(n==(ssize_t)pcm_bytes+4 && !memcmp(data,pcm_rate==16000?"PCM2":"PCM1",4)){
            mf79u_pcm_push(&downlink,data+4);frames_out++;
            for(unsigned j=4;j<pcm_bytes+4;j++)if(data[j]){nonzero_out++;break;}
        }
    }
    int got=mf79u_pcm_pop(&downlink,frame->buf);
    if(got==1)pjmedia_plc_save(downlink_plc,frame->buf);
    else if(got<0)pjmedia_plc_generate(downlink_plc,frame->buf);
    pj_mutex_unlock(pcm_lock);
#ifdef MF79U_SIP_PCM_LEVELS
    pcm_level(&to_sip_levels,"to_sip",frame->buf);
#endif
    return PJ_SUCCESS;
}
static pj_status_t pcm_put(pjmedia_port *port,pjmedia_frame *frame){
    (void)port;
    if(frame->type!=PJMEDIA_FRAME_TYPE_AUDIO || frame->size!=pcm_bytes)return PJ_SUCCESS;
#ifdef MF79U_SIP_PCM_LEVELS
    pcm_level(&from_sip_levels,"from_sip",frame->buf);
#endif
    unsigned char data[644];memcpy(data,pcm_rate==16000?"PCM2":"PCM1",4);memcpy(data+4,frame->buf,pcm_bytes);
    if(sendto(tx,data,pcm_bytes+4,MSG_DONTWAIT,(struct sockaddr*)&native_pcm,sizeof(native_pcm))==(ssize_t)pcm_bytes+4){
        frames_in++;for(unsigned i=4;i<pcm_bytes+4;i++)if(data[i]){nonzero_in++;break;}
    }
    return PJ_SUCCESS;
}
static void state_changed(pjsua_call_id id,pjsip_event *event){
    (void)event;pjsua_call_info ci;if(pjsua_call_get_info(id,&ci)!=PJ_SUCCESS)return;
    if(ci.state==PJSIP_INV_STATE_CONFIRMED){puts("SIP_CONNECTED");if(from_sim)puts("ANSWER");}
    if(ci.state==PJSIP_INV_STATE_DISCONNECTED && id==call){
        printf("SIP_ENDED %u\n",ci.last_status);
        if(!released)puts("HANGUP");
        call=PJSUA_INVALID_ID;from_sim=0;released=0;call_started=0;
        pj_mutex_lock(pcm_lock);
        printf("PCM_QUEUE received=%lu played=%lu underflows=%lu overflows=%lu high_water=%u\n",downlink.received,downlink.played,downlink.underflows,downlink.overflows,downlink.high_water);
        memset(&downlink,0,sizeof(downlink));
        downlink.samples=pcm_samples;
        pj_mutex_unlock(pcm_lock);
        active_codec[0]=0;
    }
    status_file();
}
static void media_changed(pjsua_call_id id){
    pjsua_call_info ci;if(pjsua_call_get_info(id,&ci)!=PJ_SUCCESS)return;
    if(ci.media_status==PJSUA_CALL_MEDIA_ACTIVE){
        if(pjsua_conf_connect(ci.conf_slot,pcm_slot)==PJ_SUCCESS &&
           pjsua_conf_connect(pcm_slot,ci.conf_slot)==PJ_SUCCESS)puts("SIP_MEDIA_CONNECTED");
        pjsua_stream_info info;
        if(pjsua_call_get_stream_info(id,0,&info)==PJ_SUCCESS && info.type==PJMEDIA_TYPE_AUDIO){
            pjmedia_codec_info *fmt=&info.info.aud.fmt;
            /* The codec name is whitelisted; never log SDP or peer details. */
            const char *names[]={"opus","G722","PCMA","PCMU","G729"};strcpy(active_codec,"unknown");
            for(unsigned i=0;i<5;i++)if(!pj_stricmp2(&fmt->encoding_name,names[i]))strcpy(active_codec,names[i]);
            printf("SIP_AUDIO codec=%s sample_rate=%u wire_pcm_rate=%u\n",active_codec,fmt->clock_rate,pcm_rate);
            status_file();
        }
    }
}
static void incoming(pjsua_acc_id acc,pjsua_call_id id,pjsip_rx_data *rdata){
    (void)acc;
    if((sip_server() && !sip_local_source(rdata)) || (!sip_server() && !trusted_peer(rdata->pkt_info.src_name))){
        pjsua_call_answer(id,403,NULL,NULL);puts("REJECT_PEER");return;
    }
    if(!ready || stopping){pjsua_call_answer(id,503,NULL,NULL);return;}
    if(call!=PJSUA_INVALID_ID){pjsua_call_answer(id,486,NULL,NULL);return;}
    pjsip_uri *uri=pjsip_uri_get_uri(rdata->msg_info.msg->line.req.uri);
    if(!PJSIP_URI_SCHEME_IS_SIP(uri)){pjsua_call_answer(id,484,NULL,NULL);return;}
    pj_str_t user=((pjsip_sip_uri*)uri)->user;
    char number[40];if(user.slen<3 || user.slen>33){pjsua_call_answer(id,484,NULL,NULL);return;}
    memcpy(number,user.ptr,(size_t)user.slen);number[user.slen]=0;
    if(!sip_phone(number)){pjsua_call_answer(id,484,NULL,NULL);puts("REJECT_DESTINATION");return;}
    call=id;from_sim=0;released=0;call_started=time(NULL);
    printf("DIAL %s\n",number);status_file();
}
static int initialise(void){
    sip_active=0;
    if(!strcmp(settings.role,"DISABLED"))return 0;
    server_ip_count=0;struct addrinfo hints={.ai_family=AF_INET,.ai_socktype=SOCK_DGRAM},*addresses=NULL;
    if(!sip_server() && getaddrinfo(settings.server,NULL,&hints,&addresses)==0){
        for(struct addrinfo *a=addresses;a&&server_ip_count<8;a=a->ai_next)if(inet_ntop(AF_INET,&((struct sockaddr_in*)a->ai_addr)->sin_addr,server_ips[server_ip_count],16))server_ip_count++;
        freeaddrinfo(addresses);
    }

    pj_status_t st=pjsua_create();if(st!=PJ_SUCCESS)return 1;
    strcpy(local_ip,settings.bind);
    if(!sip_server() && !strcmp(settings.bind,"0.0.0.0")){
        if(!server_ip_count)return 13;
        int fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0)return 13;
        struct sockaddr_in peer={.sin_family=AF_INET,.sin_port=htons(settings.port)},source; socklen_t size=sizeof(source);
        inet_pton(AF_INET,server_ips[0],&peer.sin_addr);
        int ok=!connect(fd,(struct sockaddr*)&peer,sizeof(peer)) && !getsockname(fd,(struct sockaddr*)&source,&size) && inet_ntop(AF_INET,&source.sin_addr,local_ip,sizeof(local_ip));
        close(fd);if(!ok)return 13; /* UDP connect only selects a route; no packet is sent. */
    }
    pjsua_config cfg;pjsua_config_default(&cfg);cfg.max_calls=1;cfg.thread_cnt=0;
    cfg.cb.on_incoming_call=incoming;cfg.cb.on_call_state=state_changed;cfg.cb.on_call_media_state=media_changed;cfg.cb.on_reg_state=registration_changed;
    cfg.cb.on_transport_state=transport_changed;
    cfg.cb.on_pager_status=sms_pager_status;
    pjsua_logging_config log;pjsua_logging_config_default(&log);log.level=0;log.console_level=0;log.msg_logging=PJ_FALSE;
    pjsua_media_config media;pjsua_media_config_default(&media);
    media.clock_rate=pcm_rate;media.snd_clock_rate=pcm_rate;media.channel_count=1;
    media.audio_frame_ptime=20;media.no_vad=PJ_TRUE;media.ec_tail_len=0;
    if(pjsua_init(&cfg,&log,&media)!=PJ_SUCCESS)return 2;
    if(sip_registrar_init())return 14;
    if(sms_init())return 15;
    pjsua_transport_config tc;pjsua_transport_config_default(&tc);tc.port=settings.local_port;
    tc.bound_addr=pj_str(local_ip);tc.public_addr=tc.bound_addr;
    tc.tls_setting.verify_server=PJ_TRUE;tc.tls_setting.ca_list_file=pj_str(settings.ca_file);
    tc.tls_setting.proto=PJ_SSL_SOCK_PROTO_TLS1_2|PJ_SSL_SOCK_PROTO_TLS1_3;
    pjsua_transport_id transport;
    if(pjsua_transport_create(!strcmp(settings.transport,"TLS")?PJSIP_TRANSPORT_TLS:!strcmp(settings.transport,"TCP")?PJSIP_TRANSPORT_TCP:PJSIP_TRANSPORT_UDP,&tc,&transport)!=PJ_SUCCESS)return 3;
    if(pjsua_start()!=PJ_SUCCESS)return 4;
    pjsua_set_null_snd_dev();
    pjsua_codec_info codecs[32];unsigned count=32;
    if(pjsua_enum_codecs(codecs,&count)!=PJ_SUCCESS)return 5;
    for(unsigned i=0;i<count;i++)pjsua_codec_set_priority(&codecs[i].codec_id,0);
    char order[64];strcpy(order,settings.codecs);char *save=NULL;unsigned priority=255,enabled=0;
    for(char *name=strtok_r(order,",",&save);name;name=strtok_r(NULL,",",&save)){
        const char *id=!strcmp(name,"OPUS")?"opus/48000/2":!strcmp(name,"G722")?"G722/16000/1":!strcmp(name,"PCMA")?"PCMA/8000/1":!strcmp(name,"PCMU")?"PCMU/8000/1":!strcmp(name,"G729")?"G729/8000/1":NULL;
        if(!id)return 6;
        pj_str_t codec=pj_str((char*)id);if(pjsua_codec_set_priority(&codec,(pj_uint8_t)priority--)!=PJ_SUCCESS)return 6;enabled++;
    }
    if(!enabled)return 6;
    pj_str_t opus=pj_str("opus/48000/2");pjmedia_codec_param op_param;
    if(pjsua_codec_get_param(&opus,&op_param)==PJ_SUCCESS){
        pjmedia_codec_opus_config op;pjmedia_codec_opus_get_config(&op);
        op.sample_rate=16000;op.channel_cnt=1;op.bit_rate=24000;op.complexity=3;op.frm_ptime=20;op.packet_loss=2;
        op_param.setting.vad=0;op_param.setting.plc=1;
        if(pjmedia_codec_opus_set_default_param(&op,&op_param)!=PJ_SUCCESS)return 6;
    }

    pjsua_acc_config ac;pjsua_acc_config_default(&ac);
    char identity[384],registrar[384],proxy[512];const char *scheme=!strcmp(settings.transport,"TLS")?"sips":"sip";
    if(sip_server()){
        snprintf(identity,sizeof(identity),"sip:%s@%s",settings.extension,local_ip);
    }else{
        snprintf(identity,sizeof(identity),"%s:%s@%s",scheme,settings.username,settings.server);
        snprintf(registrar,sizeof(registrar),"%s:%s:%u",scheme,settings.server,settings.port);
        if(settings.registration){ac.reg_uri=pj_str(registrar);ac.reg_retry_interval=30;ac.reg_first_retry_interval=5;}
        snprintf(proxy,sizeof(proxy),"%s;transport=%s;lr",registrar,!strcmp(settings.transport,"TLS")?"tls":!strcmp(settings.transport,"TCP")?"tcp":"udp");ac.proxy_cnt=1;ac.proxy[0]=pj_str(proxy);
        if(settings.password[0]){ac.cred_count=1;ac.cred_info[0].realm=pj_str(settings.realm);ac.cred_info[0].scheme=pj_str("digest");ac.cred_info[0].username=pj_str(settings.username);ac.cred_info[0].data_type=PJSIP_CRED_DATA_PLAIN_PASSWD;ac.cred_info[0].data=pj_str(settings.password);}
    }
    ac.id=pj_str(identity);ac.transport_id=transport;

    ac.allow_contact_rewrite=settings.registration?PJ_TRUE:PJ_FALSE;ac.allow_via_rewrite=settings.registration?PJ_TRUE:PJ_FALSE;
    ac.rtp_cfg.port=MF79U_SIP_RTP_PORT;ac.rtp_cfg.port_range=2;
    ac.rtp_cfg.bound_addr=pj_str(local_ip);ac.rtp_cfg.public_addr=ac.rtp_cfg.bound_addr;
    if(pjsua_acc_add(&ac,PJ_TRUE,&account)!=PJ_SUCCESS)return 7;
    rx=socket(AF_INET,SOCK_DGRAM|SOCK_NONBLOCK,0);tx=socket(AF_INET,SOCK_DGRAM,0);
    if(rx<0 || tx<0)return 8;
    struct sockaddr_in local={.sin_family=AF_INET,.sin_port=htons(MF79U_SIP_PCM_RX),.sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
    if(bind(rx,(struct sockaddr*)&local,sizeof(local)))return 9;
    native_pcm=(struct sockaddr_in){.sin_family=AF_INET,.sin_port=htons(MF79U_SIP_PCM_PEER),.sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
    pj_pool_t *pool=pjsua_pool_create("modem-pcm",2048,2048);
    if(pj_mutex_create_simple(pool,"pcm",&pcm_lock)!=PJ_SUCCESS)return 12;
    downlink.samples=pcm_samples;
    if(pjmedia_plc_create(pool,pcm_rate,pcm_samples,0,&downlink_plc)!=PJ_SUCCESS)return 11;
    pjmedia_port *port=PJ_POOL_ZALLOC_T(pool,pjmedia_port);pj_str_t name=pj_str("native-ims-pcm");
    pjmedia_port_info_init(&port->info,&name,PJMEDIA_SIG_CLASS_PORT_AUD('M','F'),pcm_rate,1,16,pcm_samples);
    port->get_frame=pcm_get;port->put_frame=pcm_put;
    if(pjsua_conf_add_port(pool,port,&pcm_slot)!=PJ_SUCCESS)return 10;
    sip_active=1;return 0;
}
static void close_sip(void){
    sms_close();
    if(sip_active)pjsua_destroy();
    if(rx>=0)close(rx);
    if(tx>=0)close(tx);
    rx=tx=-1;sip_active=0;
    memset(&downlink,0,sizeof(downlink));
}
static void command(const char *line){
    /* READY remains the compatible IMS command for older controllers. */
    if(!strcmp(line,"READY") || !strcmp(line,"BACKEND ims") || !strcmp(line,"BACKEND cs")){
        cellular_backend=!strcmp(line,"BACKEND cs")?"cs":"ims";
        ready=1;puts("GATEWAY_READY");status_file();return;
    }
    if(!strcmp(line,"NOT_READY") || !strcmp(line,"BACKEND none")){
        ready=0;cellular_backend="none";status_file();return;
    }
    if(!strcmp(line,"STATS")){
        printf("PCM_STATS received=%lu sent=%lu received_nonzero=%lu sent_nonzero=%lu\n",frames_out,frames_in,nonzero_out,nonzero_in);return;
    }
    if(!strcmp(line,"QUIT")){stopping=1;return;}
    if(call==PJSUA_INVALID_ID && !strcmp(line,"INCOMING")){
        if(!strcmp(settings.role,"DISABLED")){puts("HANGUP");return;}
        if(!ready)return;
        char target[384];
        if(sip_server()){
            if(!sip_local_target(target,sizeof(target))){puts("HANGUP");return;}
        }else snprintf(target,sizeof(target),"%s:%s@%s:%u",!strcmp(settings.transport,"TLS")?"sips":"sip",settings.incoming_user,settings.server,settings.port);
        pj_str_t uri=pj_str(target);
        char caller[40]="anonymous";struct stat caller_stat;
        FILE *f=NULL;if(!stat(MF79U_SIP_CALLER_FILE,&caller_stat) && time(NULL)-caller_stat.st_mtime>=0 && time(NULL)-caller_stat.st_mtime<=8)f=fopen(MF79U_SIP_CALLER_FILE,"r");
        if(f){if(!fgets(caller,sizeof(caller),f))strcpy(caller,"anonymous");fclose(f);}unlink(MF79U_SIP_CALLER_FILE);
        if(!sip_phone(caller))strcpy(caller,"anonymous");
        char from[384];snprintf(from,sizeof(from),"%s:%s@%s",!strcmp(settings.transport,"TLS")?"sips":"sip",caller,sip_server()?local_ip:settings.server);
        pjsua_msg_data msg;pjsua_msg_data_init(&msg);msg.local_uri=pj_str(from);
        pj_pool_t *identity_pool=pjsua_pool_create("caller-id",1024,1024);
        if(strcmp(caller,"anonymous")){
            pj_str_t key=pj_str("P-Asserted-Identity"),value=pj_str(from);
            pjsip_generic_string_hdr *h=pjsip_generic_string_hdr_create(identity_pool,&key,&value);pj_list_push_back(&msg.hdr_list,h);
        }else{pj_str_t key=pj_str("Privacy"),value=pj_str("id");pjsip_generic_string_hdr *h=pjsip_generic_string_hdr_create(identity_pool,&key,&value);pj_list_push_back(&msg.hdr_list,h);}

        from_sim=1;released=0;call_started=time(NULL);
        /* PJPROJECT 2.17 defaults to a real-time text stream as well as audio.
         * This gateway implements voice and separate SIP MESSAGE, not RTT.
         * The unused text offer also pushed full-codec Caller-ID INVITEs past
         * the USB LAN MTU, making voice setup depend on IP fragmentation. */
        pjsua_call_setting voice_call;pjsua_call_setting_default(&voice_call);
        voice_call.aud_cnt=1;voice_call.vid_cnt=0;voice_call.txt_cnt=0;
        if(pjsua_call_make_call(account,&uri,&voice_call,NULL,&msg,&call)!=PJ_SUCCESS){puts("HANGUP");call=PJSUA_INVALID_ID;from_sim=0;}
        else puts("SIP_INCOMING_FORWARDED");
        pj_pool_release(identity_pool);status_file();
        return;
    }
    if(call==PJSUA_INVALID_ID)return;
    if(!strcmp(line,"ALERT") && !from_sim)pjsua_call_answer(call,180,NULL,NULL);
    else if(!strcmp(line,"CONNECTED") && !from_sim)pjsua_call_answer(call,200,NULL,NULL);
    else if(!strcmp(line,"ENDED")){released=1;pjsua_call_hangup(call,487,NULL,NULL);}
}
int main(int argc,char **argv){
#ifdef MF79U_DIAGNOSTIC_FAULTS
    if(mf79u_diagnostic_fault_install())return 70;
#endif
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--version")){puts("MF79U SIP gateway 0.8; trunk or one-account registrar; SMS MESSAGE; Opus G722 PCMA PCMU G729; caller ID");return 0;}
        else if(!strcmp(argv[i],"--wideband")){pcm_rate=16000;pcm_samples=320;pcm_bytes=640;}
        else if(!strcmp(argv[i],"--config") && i+1<argc)settings_path=argv[++i];
        else return 2;
    }
    if(sip_load_settings(settings_path,&settings)){puts("GATEWAY_CONFIG_INVALID");return 2;}
    setvbuf(stdout,NULL,_IONBF,0);setvbuf(stdin,NULL,_IONBF,0);
    signal(SIGHUP,signal_reload);signal(SIGTERM,signal_stop);signal(SIGINT,signal_stop);
    int result=initialise();if(result){printf("GATEWAY_INIT_FAILED %d\n",result);pjsua_destroy();return result;}
    puts(sip_active?"GATEWAY_LISTENING":"GATEWAY_DISABLED");status_file();char line[128];
    while(!stopping && !interrupted){
        if(sip_active)pjsua_handle_events(20);else usleep(20000);
        sms_tick();
        if(reload_requested && call==PJSUA_INVALID_ID){
            reload_requested=0;struct sip_settings next;if(sip_load_settings(settings_path,&next)){puts("GATEWAY_CONFIG_INVALID");continue;}
            struct sip_settings previous=settings;
            close_sip();sip_binding_reset();settings=next;
            int result=initialise();if(result){printf("GATEWAY_RELOAD_FAILED %d\n",result);pjsua_destroy();if(rx>=0)close(rx);if(tx>=0)close(tx);rx=tx=-1;settings=previous;if(initialise())break;puts("GATEWAY_CONFIG_ROLLED_BACK");}
            else {puts("GATEWAY_RELOADED");}memset(&previous,0,sizeof(previous));status_file();
        }
        fd_set fds;FD_ZERO(&fds);FD_SET(0,&fds);struct timeval timeout={0};
        if(select(1,&fds,NULL,NULL,&timeout)>0){
            if(!fgets(line,sizeof(line),stdin))break;
            line[strcspn(line,"\r\n")]=0;command(line);
        }
        if(call_started && time(NULL)-call_started>=300){released=1;pjsua_call_hangup(call,487,NULL,NULL);puts("HANGUP");call_started=0;}
    }
    if(call!=PJSUA_INVALID_ID){released=1;puts("HANGUP");pjsua_call_hangup(call,487,NULL,NULL);}
    close_sip();unlink(MF79U_SIP_STATUS_BASE ".json");memset(&settings,0,sizeof(settings));return 0;
}
