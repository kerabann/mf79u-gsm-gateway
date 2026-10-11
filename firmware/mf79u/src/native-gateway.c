/* Standalone B03 CP/IMS/SIP controller. Only owned child processes and queues
 * are stopped. SIM authentication stays in RAM; logs contain event names only.
 * PCM and operator codec implementation remain in the already tested binaries. */
#include "cp-ipc.h"
#include "cp-pdp.h"
#include "net-led-policy.h"
#include "cs-status.h"
#include "voice-backend-policy.h"
#include "cs-voice-protocol.h"
#include "voice-registration-policy.h"
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/msg.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

struct message {
    int32_t type, dst, src;
    uint16_t cmd, len;
    uint32_t magic;
    unsigned char payload[3496];
};
struct owned_queue { int id; int32_t key; time_t stamp; };
static struct owned_queue owned[16];
static int before[128], before_count, owned_count, response=-1, request=-1;
static struct mf79u_cp cp={.tx=-1,.rx=-1};
static pid_t ims=-1, sip=-1;
static pid_t cs_voice=-1;
static int sip_input=-1, sip_output=-1, ims_output=-1;
static int cs_input=-1,cs_output=-1,cs_ready,cs_suspended,cs_resume_requested;
static unsigned cs_epoch,cs_call_id,cs_sequence;
static struct mf79u_voice_policy voice;
static enum mf79u_voice_backend notified_backend;
static int clearing_requested,loss_notified;
static int registered, active_call, codec_factory, frontend, wb_advertised;
static int voice_ready, eps_state=-1, cs_state=-1;
static int vowifi_had_tunnel, vowifi_registration_rejected;
static unsigned long vowifi_ims_generation;
static struct mf79u_cs_status cs_status;
static char last_registration[128];
static int last_system=-1,last_subsystem=-1,last_capability=-1;
/* Compile-time overrides are used only by the isolated lifecycle fixture. */
#ifndef MF79U_IMS_TIMEOUT
#define MF79U_IMS_TIMEOUT 60
#endif
#ifndef MF79U_RADIO_INTERVAL
#define MF79U_RADIO_INTERVAL 3
#endif
#ifndef MF79U_IMS_RETRY
#define MF79U_IMS_RETRY 900
#endif
static volatile sig_atomic_t stopping;
static time_t started;
static enum voice_mode requested_mode,effective_mode;
static int requested_usb,effective_usb;
static int radio_profile,auto_fallback;
static const char *registration_phase="starting",*fallback_reason="";
static time_t promotion_at;
static const char *gateway_config="/mnt/userdata/mf79u/gateway.ini";
static int voice_enabled(void) {
    FILE *f=fopen(gateway_config,"r");if(!f)return 0;
    char line[1200];int enabled=0;
    while(fgets(line,sizeof(line),f)) {
        line[strcspn(line,"\r\n")]=0;
        if(!strncmp(line,"role=",5)) {enabled=!strcmp(line+5,"TRUNK") || !strcmp(line+5,"SERVER");break;}
    }
    memset(line,0,sizeof(line));fclose(f);return enabled;
}

/* Persistent, explicit test guard. PBX/client auto-answer must never issue ATA.
 * Read at the action boundary so it can be armed without a controller restart.
 * An existing unreadable/invalid marker also blocks charged call operations. */
#ifndef MF79U_RING_ONLY_FILE
#define MF79U_RING_ONLY_FILE "/mnt/userdata/mf79u/native-ring-only"
#endif
#ifndef MF79U_CS_ONLY_FILE
#define MF79U_CS_ONLY_FILE "/mnt/userdata/mf79u/native-cs-only"
#endif
/* Reversible test policy, independent of SIP role and ring-only protection.
 * Unknown marker accessibility fails closed: never start IMS in that case. */
static int cs_only(void) {
    return effective_mode==VOICE_CS || access(MF79U_CS_ONLY_FILE,F_OK)==0 || errno!=ENOENT;
}
static void read_voice_mode(void) {
    FILE *f=fopen(gateway_config,"r");if(!f)return;
    char line[1200];enum voice_mode next=VOICE_AUTO;int usb=0;
    while(fgets(line,sizeof(line),f)) {
        line[strcspn(line,"\r\n")]=0;
        if(!strncmp(line,"voice_mode=",11)){if(voice_mode_parse(line+11,&next))next=VOICE_VOLTE;}
        if(!strncmp(line,"vowifi_uplink=",14))usb=!strcmp(line+14,"USB");
    }
    memset(line,0,sizeof(line));fclose(f);requested_mode=next;requested_usb=usb;
}
static int ring_only(void) {
    return access(MF79U_RING_ONLY_FILE,F_OK)==0 || errno!=ENOENT;
}
static int call_action_allowed(int ready,int enabled,int guarded) {
    return ready && enabled && !guarded;
}

static time_t monotonic(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec;
}
#include "vowifi-runtime.h"
static void event(const char *s) {
    printf("NATIVE_GATEWAY elapsed=%ld event=%s\n",(long)(monotonic()-started),s);
}
static void interrupted(int s) { (void)s; stopping=1; }
static int send_sip(const char *text);
static int query_ims(const char *command);
static void reconcile_voice(void);
static void cs_line(const char *line);
static int send_cs(const char *action,unsigned id,const char *argument) {
    if(cs_input<0 || !cs_epoch)return -1;
    char text[128];int n=snprintf(text,sizeof(text),"%s %u %u%s%s\n",action,cs_epoch,id,argument?" ":"",argument?argument:"");
    int result=n>0 && n<(int)sizeof(text) && write(cs_input,text,(size_t)n)==n?0:-1;
    memset(text,0,sizeof(text));return result;
}
static void cellular_ended(enum mf79u_voice_backend backend) {
    if(voice.owner!=backend)return;
    active_call=0;clearing_requested=loss_notified=0;cs_call_id=0;
    mf79u_voice_ended(&voice);
    if(backend==MF79U_VOICE_CS)mf79u_led_notify((const unsigned char *)"^CEND: 8",8);
    send_sip("ENDED");reconcile_voice();
}
static void hangup_owned(void) {
    if(clearing_requested || voice.owner==MF79U_VOICE_NONE)return;
    clearing_requested=1;
    if(voice.owner==MF79U_VOICE_CS)send_cs("HANGUP",cs_call_id,NULL);
    else {query_ims("ATH");query_ims("AT+CHUP");}
}
static void reconcile_voice(void) {
    struct mf79u_voice_inputs in={voice_enabled(),cs_only(),voice_ready,
        cs_state==1 || cs_state==5,cs_voice>0 && cs_epoch && !cs_suspended && ims<0,effective_mode!=VOICE_VOLTE && effective_mode!=VOICE_VOWIFI && cs_ready};
    mf79u_voice_reconcile(&voice,&in,(unsigned long)monotonic());
    if(voice.end_call && !loss_notified){hangup_owned();send_sip("ENDED");loss_notified=1;}
    enum mf79u_voice_backend usable=voice.end_call?MF79U_VOICE_NONE:voice.selected;
    if(usable!=notified_backend) {
        send_sip(usable==MF79U_VOICE_IMS?"READY":usable==MF79U_VOICE_CS?"BACKEND cs":"NOT_READY");
        notified_backend=usable;
    }
}
static void publish(const char *state) {
    int ready=voice.selected!=MF79U_VOICE_NONE && !voice.end_call;
    int signaling=cs_voice>0 && cs_epoch && !cs_suspended && ims<0;
    if(ready && strcmp(state,"stopped"))state="ready";
    FILE *f=fopen("/dev/.mf79u-native-status.tmp","w");if(!f)return;
    fprintf(f,"{\"version\":\"0.9\",\"pid\":%ld,\"state\":\"%s\",\"hostRelayRequired\":false,"
        "\"imsReady\":%s,\"voiceReady\":%s,\"voiceBackend\":\"%s\",\"callBackend\":\"%s\","
        "\"smsOnly\":%s,\"cellularRegistered\":%s,\"epsRegistration\":%d,\"csRegistration\":%d,"
        "\"sipPid\":%ld,\"csPid\":%ld,\"ringOnly\":%s,\"csOnly\":%s,"
        "\"csSignalingReady\":%s,\"csCallState\":\"%s\",\"csAudioReady\":%s,"
        "\"imsAccess\":\"%s\",\"vowifiUplink\":\"%s\",\"vowifiTunnelReady\":%s,\"voiceMode\":\"%s\",\"effectiveVoiceMode\":\"%s\",\"registrationMode\":\"%s\",\"registrationState\":\"%s\",\"fallbackReason\":\"%s\",\"volteRetrySeconds\":%ld}\n",
        (long)getpid(),state,voice_ready?"true":"false",ready?"true":"false",
        mf79u_voice_name(ready?voice.selected:MF79U_VOICE_NONE),mf79u_voice_name(voice.owner),
        sip>0 && !ready?"true":"false",eps_state==1 || eps_state==5 || cs_state==1 || cs_state==5?"true":"false",
        eps_state,cs_state,(long)(sip>0?sip:0),(long)(cs_voice>0?cs_voice:0),ring_only()?"true":"false",cs_only()?"true":"false",
        signaling || cs_status.armed?"true":"false",voice.owner==MF79U_VOICE_CS?"active":mf79u_cs_state_name(cs_status.state),
        cs_ready && signaling?"true":"false",ims>0?(ims_wifi?"WIFI":"LTE"):"NONE",effective_usb?"USB":"WIFI",vowifi_tunnel_ready()?"true":"false",voice_mode_name(requested_mode),voice_mode_name(effective_mode),
        (ims_wifi || effective_mode==VOICE_VOWIFI)?"VOWIFI":radio_profile==2?"CS":radio_profile==1?"VOLTE":"unknown",registration_phase,fallback_reason,
        (long)(auto_fallback && promotion_at>monotonic()?promotion_at-monotonic():0));
    fclose(f);rename("/dev/.mf79u-native-status.tmp","/dev/.mf79u-native-status.json");
}
static void poll_cs_status(void) {
    struct mf79u_cs_status next={0};
    if(!cs_only() || !ring_only() || !voice_enabled() || mf79u_cs_status_read(&next))
        memset(&next,0,sizeof(next));
    if(next.state!=cs_status.state) {
        /* Slot8 is reserved for this TI0 CS prototype; never feed the IMS event
         * parser or send SIP READY/CONNECTED before a CS audio backend exists. */
        const char *line=next.state==1?"^DSCI: 8,1,4":"^CEND: 8";
        mf79u_led_notify((const unsigned char *)line,strlen(line));
        event(next.state==1?"cs_incoming_alerting":next.state==2?"cs_call_releasing":"cs_call_idle");
    }
    int changed=next.armed!=cs_status.armed || next.state!=cs_status.state;
    cs_status=next;
    if(changed)publish(voice_ready?"ready":ims>0?"registering":"sms_only");
}
static int inventory(int capture) {
    FILE *f=fopen("/proc/sysvipc/msg","r");if(!f)return -1;
    char line[256];fgets(line,sizeof(line),f);
    while(fgets(line,sizeof(line),f)) {
        int32_t key;int id;
        if(sscanf(line,"%d %d",&key,&id)!=2)continue;
        if(capture) {
            if(before_count>=128){fclose(f);return -1;}
            before[before_count++]=id;
            if(key==0x701e || key==0x700f || key==5181 || key==-2130378751) {
                fclose(f);errno=EBUSY;return -1;
            }
        } else {
            int existing=0;
            for(int i=0;i<before_count;i++)if(before[i]==id)existing=1;
            for(int i=0;i<owned_count;i++)if(owned[i].id==id)existing=1;
            if(existing || id==response || id==cp.rx)continue;
            if(key!=0x701e && key!=5181 && key!=-2130378751 && key!=0)continue;
            struct msqid_ds ds;
            if(msgctl(id,IPC_STAT,&ds) || owned_count>=16) {fclose(f);return -1;}
            if(ds.msg_perm.uid || ds.msg_perm.cuid)continue;
            owned[owned_count++]=(struct owned_queue){id,key,ds.msg_ctime};
        }
    }
    fclose(f);return 0;
}
static int cleanup_queues(void) {
    int result=0;
    for(int i=0;i<owned_count;i++) {
        struct msqid_ds ds;
        if(msgctl(owned[i].id,IPC_STAT,&ds)) {
            if(errno!=EINVAL && errno!=EIDRM)result=-1;
            continue;
        }
        if((int32_t)ds.msg_perm.__key!=owned[i].key ||
           ds.msg_ctime!=owned[i].stamp || ds.msg_perm.uid || ds.msg_perm.cuid) {result=-1;continue;}
        int live=0;pid_t users[]={ds.msg_lspid,ds.msg_lrpid};
        for(unsigned j=0;j<2;j++)if(users[j] && users[j]!=getpid()) {
            errno=0;if(!kill(users[j],0) || errno!=ESRCH)live=1;
        }
        if(live || msgctl(owned[i].id,IPC_RMID,NULL))result=-1;
    }
    return result;
}
static int send_ims(uint16_t cmd,const char *text,size_t length,unsigned port) {
    if(request<0 || length>3488 || port<1 || port>4)return -1;
    struct message m={.type=1,.dst=0x701e,.src=0x700f,.cmd=cmd,.len=3496,.magic=0x3a3a3a3a};
    uint32_t count=(uint32_t)length;
    memcpy(m.payload,text,length);memcpy(m.payload+3488,&count,4);memcpy(m.payload+3492,&port,4);
    return msgsnd(request,&m,sizeof(m)-4,IPC_NOWAIT);
}
static int query_ims(const char *command) {
    char text[128];int n=snprintf(text,sizeof(text),"%s\r",command);
    if(n<0 || n>=(int)sizeof(text))return -1;
    return send_ims(0x1509,text,(size_t)n,1);
}
static int send_sip(const char *text) {
    if(sip_input<0)return 0;
    size_t size=strlen(text);
    return write(sip_input,text,size)==(ssize_t)size && write(sip_input,"\n",1)==1?0:-1;
}
static int number(const char *text) {
    if(*text=='+')text++;
    size_t n=strlen(text);if(n<3 || n>32)return 0;
    for(size_t i=0;i<n;i++)if(!isdigit((unsigned char)text[i]))return 0;
    return 1;
}
static int cp_allowed(const char *s) {
    const char *allowed[]={"AT^CARDMODE","AT+CFUN?","AT+CEREG?","AT+CGREG?","AT+CREG?",
        "AT+CPIN?","AT+COPS?","AT+CEN?","AT+CNEM?","AT+CGSN","AT+CIMI",
        "AT+CRSM=176,28589,0,0,4","AT+ZMODE?","AT+CSMS?","AT+CSTA?","AT^ZCSVOICESPT",
        "AT+ZPDPACT=0,\"IPV4V6\",\"ims\",0,1,1","AT+CGCONTRDP=5","AT+ZPDPDEACT=5",
        "AT+CEREG=2","AT+ZIMSSTATE=0","AT+ZIMSSTATE=1","AT+ZSCA?","AT+ZSMP?","AT+ZTPMR?"};
    for(unsigned i=0;i<sizeof(allowed)/sizeof(allowed[0]);i++)if(!strcmp(s,allowed[i]))return 1;
    if(!strncmp(s,"AT+ZTPMR=",9)) {
        char *end;long ref=strtol(s+9,&end,10);
        return end!=s+9 && !*end && ref>=0 && ref<=255;
    }
    if(!strncmp(s,"AT^MBAU=\"",9) && strlen(s)==77 && s[41]=='"' && s[42]==',' && s[43]=='"' && s[76]=='"') {
        for(int i=9;i<76;i++)if(i!=41 && i!=42 && i!=43 && !isxdigit((unsigned char)s[i]))return 0;
        return 1;
    }
    if(!strncmp(s,"AT+ZNUMTYPE=\"",13)) {
        char copy[40];size_t n=strlen(s+13);
        if(n<2 || n>=sizeof(copy) || s[13+n-1]!='"')return 0;
        memcpy(copy,s+13,n-1);copy[n-1]=0;return number(copy);
    }
    return 0;
}
static const char *cp_tag(const char *s) {
    if(!strncmp(s,"AT+ZTPMR=",9))return "sms_reference_update";
    if(!strncmp(s,"AT^MBAU=",8))return "sim_aka";
    if(!strncmp(s,"AT+ZNUMTYPE=",12))return "number_type";
    if(!strncmp(s,"AT+ZPDPACT=",11))return "ims_bearer_start";
    if(!strncmp(s,"AT+CGCONTRDP=",13))return "ims_bearer_details";
    if(!strncmp(s,"AT+ZIMSSTATE=",13))return "ims_state";
    if(!strcmp(s,"AT+CEREG=2"))return "registration_events";
    return s; /* Remaining allowlisted strings contain command names only. */
}
#include "ims-sms-native.h"
static void native_event(char *text) {
    if(strstr(text,"+CMT:") || strstr(text,"+CMTI:"))event("ims_sms_delivery_indication");
    if(strstr(text,"+CDS:") || strstr(text,"+CDSI:"))event("ims_sms_report_indication");
    mf79u_led_notify((unsigned char*)text,strlen(text));
    if(strstr(text,"+CVMOD: 3"))frontend=1;
    if(strstr(text,"+ZIMSAMRW: 1"))wb_advertised=1;
    char *save=NULL;
    for(char *line=strtok_r(text,"\r\n",&save);line;line=strtok_r(NULL,"\r\n",&save)) {
        unsigned index,direction,state;
        if(sscanf(line,"^DSCI: %u,%u,%u",&index,&direction,&state)==3) {
            if(direction<=1 && state<=6)printf("CELLULAR_STATE direction=%u state=%u\n",direction,state);
            (void)index;(void)direction;
            if(state<=5 && (!voice_ready || !voice_enabled())) {
                query_ims("ATH");query_ims("AT+CHUP");
                event("voice_call_blocked");continue;
            }
            reconcile_voice();
            if((state==4 || state==5) && !active_call) {
                if(!mf79u_voice_admit(&voice,MF79U_VOICE_IMS)){query_ims("ATH");query_ims("AT+CHUP");continue;}
                active_call=1;send_sip("INCOMING");
            } else if(state==6)cellular_ended(MF79U_VOICE_IMS);
            else if(mf79u_voice_event_current(&voice,MF79U_VOICE_IMS)) {
                if(state==3)send_sip("ALERT");
                else if(state==0)send_sip("CONNECTED");
            }
        } else if(!strncmp(line,"^CONN:",6)) {
            if(mf79u_voice_event_current(&voice,MF79U_VOICE_IMS))send_sip("CONNECTED");
        } else if(!strncmp(line,"^CEND:",6))cellular_ended(MF79U_VOICE_IMS);
    }
}
static int ims_messages(void) {
    if(response<0)return 0;
    struct message m;ssize_t n;
    while((n=msgrcv(response,&m,sizeof(m)-4,0,IPC_NOWAIT))>=0) {
        uint32_t length,port;
        if(n!=(ssize_t)sizeof(m)-4 || m.magic!=0x3a3a3a3a || m.src!=0x701e || m.dst!=0x700f)return -1;
        memcpy(&length,m.payload+3488,4);memcpy(&port,m.payload+3492,4);
        if(length>3488 || port<1 || port>4)return -1;
        char text[3489];memcpy(text,m.payload,length);text[length]=0;
        if(m.cmd==0x150a){sms_ims_event(text,port);native_event(text);memset(text,0,sizeof(text));}
        else if(m.cmd==0x150c) {
            while(length && (text[length-1]=='\r' || text[length-1]=='\n' || !text[length-1]))text[--length]=0;
            /* IMS-local PDU mode and manual MT acknowledgement do not change
             * the vendor cellular SMS service. No CP transmit fallback. */
            if(!strcmp(text,"AT+CMGF=0") || (ims_wifi && !strcmp(text,"AT+CSMS?"))) {
                const char *answer=!strcmp(text,"AT+CSMS?")?"\r\n+CSMS: 1,1,1,1\r\n\r\nOK\r\n":"AT+CMGF=0\r\n\r\nOK\r\n";
                if(send_ims(0x150b,answer,strlen(answer),port))return -1;
                event("ims_sms_local_configuration");continue;
            }
            if(!cp_allowed(text)) {
                /* A rejected IMS SMS fallback must not tear down voice/IMS. */
                if(ims_wifi && effective_mode==VOICE_VOWIFI &&
                   (!strncmp(text,"AT+ZMGS=",8) || !strncmp(text,"AT+CMGS=",8) || !strncmp(text,"AT+CMSS=",8))) {
                    const char *answer="\r\n+CMS ERROR: 331\r\n";
                    if(send_ims(0x150b,answer,strlen(answer),port))return -1;
                    sms_rejected++;event("ims_cp_fallback_blocked");memset(text,0,sizeof(text));continue;
                }
                event("cp_operation_rejected");return -1;
            }
            char reply[8192];int wifi_bearer=ims_wifi && (!strcmp(text,"AT+ZPDPACT=0,\"IPV4V6\",\"ims\",0,1,1") || !strcmp(text,"AT+CGCONTRDP=5") || !strcmp(text,"AT+ZPDPDEACT=5"));
            int count=wifi_bearer?vowifi_bearer(text,reply,sizeof(reply)):mf79u_cp_query(&cp,text,reply,sizeof(reply),6);
            if(!wifi_bearer && count>0 && !strcmp(text,"AT+ZPDPACT=0,\"IPV4V6\",\"ims\",0,1,1") && cp.pdp_received && cp.pdp[0]==0) {
                char details[4096];
                int fetched=mf79u_cp_query(&cp,"AT+CGCONTRDP=5",details,sizeof(details),6);
                count=fetched>0?mf79u_pdp_translate(details,reply,sizeof(reply)):-1;
                memset(details,0,sizeof(details));
                if(count>0)event("ims_bearer_verified");
            }
            if(count<0 || send_ims(0x150b,reply,(size_t)count,port)) {
                printf("CP_FAILURE tag=%s errno=%d reply_bytes=%d reply_cmd=0x%04x reply_src=0x%x\n",
                       cp_tag(text),errno,count,cp.reply_cmd,(unsigned)cp.reply_src);
                if(cp.pdp_received)printf("CP_PDP_RESPONSE result=%d cid=%d\n",cp.pdp[0],cp.pdp[1]);
                event("cp_transaction_failed");return -1;
            }
            printf("CP_COMPLETED tag=%s bytes=%d ok=%d\n",cp_tag(text),count,strstr(reply,"\r\nOK\r\n")!=NULL);
            /* Neither the command nor AKA reply is printed or written to disk. */
            if((!strcmp(text,"AT+ZIMSSTATE=0") || !strcmp(text,"AT+ZIMSSTATE=1")) && strstr(reply,"\r\nOK\r\n")) {
                registered=text[strlen(text)-1]=='1';
                event(registered?"ims_registered":"ims_unregistered");
                if(!registered) {
                    voice_ready=0;reconcile_voice();publish("sms_only");
                }
            }
            memset(reply,0,sizeof(reply));memset(text,0,sizeof(text));
        } else {event("ipc_operation_rejected");return -1;}
    }
    return errno==ENOMSG?0:-1;
}
static void sip_line(const char *line) {
    if(!strncmp(line,"DIAL ",5) && number(line+5)) {
        reconcile_voice();enum mf79u_voice_backend backend=voice.selected;
        if(!call_action_allowed(backend!=MF79U_VOICE_NONE && !voice.end_call,voice_enabled(),ring_only()) ||
           !mf79u_voice_admit(&voice,backend)){send_sip("ENDED");event("outgoing_call_blocked");return;}
        int failed=0;
        if(backend==MF79U_VOICE_CS) {
            if(cs_sequence==UINT32_MAX)failed=1;
            else {cs_call_id=++cs_sequence;failed=send_cs("DIAL",cs_call_id,line+5);}
        } else {
            char text[48];snprintf(text,sizeof(text),"ATD%s;",line+5);
            failed=query_ims(text);memset(text,0,sizeof(text));
        }
        if(failed){cellular_ended(backend);event("cellular_dial_failed");return;}
        active_call=1;clearing_requested=loss_notified=0;
        if(backend==MF79U_VOICE_CS)mf79u_led_notify((const unsigned char *)"^DSCI: 8,0,2",12);
        event(backend==MF79U_VOICE_CS?"cs_outgoing_call":"outgoing_call");
    } else if(!strcmp(line,"HANGUP")) {
        hangup_owned();event("call_ended");
    } else if(!strcmp(line,"ANSWER")) {
        reconcile_voice();
        if(call_action_allowed(voice.owner!=MF79U_VOICE_NONE && !voice.end_call,voice_enabled(),ring_only())) {
            if(voice.owner==MF79U_VOICE_CS)send_cs("ANSWER",cs_call_id,NULL);else query_ims("ATA");
            event("call_answered");
        } else {hangup_owned();send_sip("ENDED");event("voice_answer_blocked");}
    }
    else if(!strcmp(line,"GATEWAY_DISABLED"))event("sip_disabled");
    else if(!strcmp(line,"GATEWAY_LISTENING"))event("sip_listening");
    else if(!strcmp(line,"GATEWAY_READY"))event("sip_ready");
    else if(!strcmp(line,"SIP_CONNECTED")){event("sip_connected");send_sip("STATS");}
    else if(!strcmp(line,"SIP_MEDIA_CONNECTED"))event("sip_media_connected");
    else if(!strcmp(line,"SIP_INCOMING_FORWARDED"))event("incoming_forwarded");
    else if(!strcmp(line,"REJECT_PEER"))event("sip_untrusted_peer");
    else if(!strcmp(line,"GATEWAY_RELOADED"))event("sip_reloaded");
    else {
        unsigned code;unsigned long received,sent,rx_nonzero,tx_nonzero;
        if(sscanf(line,"SIP_ENDED %u",&code)==1)printf("SIP_RESULT code=%u\n",code);
        if(sscanf(line,"PCM_STATS received=%lu sent=%lu received_nonzero=%lu sent_nonzero=%lu",&received,&sent,&rx_nonzero,&tx_nonzero)==4)
            printf("PCM_COUNTERS received=%lu sent=%lu received_nonzero=%lu sent_nonzero=%lu\n",received,sent,rx_nonzero,tx_nonzero);
    }
}
static void cs_line(const char *line) {
    struct mf79u_cs_event e;
    if(mf79u_cs_event_parse(line,&e)){event("cs_protocol_rejected");return;}
    if(e.kind==CSV_HELLO) {
        if(cs_epoch){event("cs_duplicate_hello_rejected");return;}
        /* HELLO is emitted only after driver quiescence and socket release.
         * Restart cannot resurrect/replay the previous SIP dialog. */
        cellular_ended(MF79U_VOICE_CS);
        cs_epoch=e.epoch;cs_call_id=cs_sequence=0;cs_ready=0;cs_suspended=1;
        cs_resume_requested=0;event("cs_adapter_started");return;
    }
    if(e.epoch!=cs_epoch)return;
    if(e.kind==CSV_READY){
        if(cs_resume_requested!=1 || ims>0){event("cs_unrequested_ready_rejected");return;}
        cs_ready=1;cs_suspended=0;event("cs_media_ready");reconcile_voice();return;
    }
    if(e.kind==CSV_NOT_READY || e.kind==CSV_SUSPENDED) {
        cs_ready=0;
        if(e.kind==CSV_NOT_READY)cs_resume_requested=0;
        if(e.kind==CSV_SUSPENDED){cs_suspended=1;cs_resume_requested=0;}
        reconcile_voice();return;
    }
    if(e.kind==CSV_INCOMING) {
        reconcile_voice();
        if(e.id<=cs_sequence || !mf79u_voice_admit(&voice,MF79U_VOICE_CS)) {
            send_cs("HANGUP",e.id,NULL);return;
        }
        cs_call_id=cs_sequence=e.id;active_call=1;clearing_requested=loss_notified=0;
        int fd=open("/dev/.mf79u-incoming-caller",O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);
        if(fd>=0){fchmod(fd,0600);if(write(fd,e.caller,strlen(e.caller))!=(ssize_t)strlen(e.caller))unlink("/dev/.mf79u-incoming-caller");close(fd);}
        else unlink("/dev/.mf79u-incoming-caller");
        mf79u_led_notify((const unsigned char *)"^DSCI: 8,1,4",12);
        memset(e.caller,0,sizeof(e.caller));send_sip("INCOMING");event("cs_incoming_call");return;
    }
    if(voice.owner!=MF79U_VOICE_CS || e.id!=cs_call_id)return;
    if(e.kind==CSV_ENDED)cellular_ended(MF79U_VOICE_CS);
    else if(mf79u_voice_event_current(&voice,MF79U_VOICE_CS)) {
        if(e.kind==CSV_ALERT)send_sip("ALERT");
        else if(e.kind==CSV_CONNECTED){mf79u_led_notify((const unsigned char *)"^CONN: 8",8);send_sip("CONNECTED");}
    }
}
struct lines {char data[2048];size_t used;};
static struct lines sip_lines, ims_lines,cs_lines;
static int read_lines(int fd,struct lines *buffer,int metadata) {
    char data[512];ssize_t n=read(fd,data,sizeof(data));
    if(n<0 && (errno==EAGAIN || errno==EINTR))return 0;
    if(n<=0)return -1;
    for(ssize_t i=0;i<n;i++) {
        if(data[i]=='\n') {
            buffer->data[buffer->used]=0;
            if(metadata==2)cs_line(buffer->data);
            else if(metadata==1) {
                if(!strcmp(buffer->data,"OPERATOR WB/NB factory enabled result=1"))codec_factory=1;
                int capability;
                if(sscanf(buffer->data,"SMS registration capability result=%d",&capability)==1 && (capability==0 || capability==1))
                    printf("SMS_IMS_CAPABILITY advertised=%d\n",capability);
                if(strstr(buffer->data," SIP method MESSAGE "))event("ims_sip_message_observed");
                if(ims_wifi){
                    const char *safe[]={"USERSPACE ESP transport ready result=","USERSPACE ESP SA installed result=","ESP transport initialization failed errno result=","ESP raw send failed errno result=","ESP protected peer selectors unmatched result=","ESP IPv4 fragments sent result="};
                    for(unsigned j=0;j<sizeof(safe)/sizeof(safe[0]);j++)if(!strncmp(buffer->data,safe[j],strlen(safe[j]))){char *end;long value=strtol(buffer->data+strlen(safe[j]),&end,10);if(!*end)printf("IMS_WIFI_TRANSPORT %s%ld\n",safe[j],value);}
                    char dir[32],method[32];unsigned length;if(sscanf(buffer->data,"%31s SIP method %31s bytes=%u",dir,method,&length)==3 && !strcmp(method,"REGISTER"))printf("IMS_WIFI_REGISTER bytes=%u\n",length);
                }
                unsigned registration_code;
                if(sscanf(buffer->data,"IMS REGISTER response code result=%u",&registration_code)==1 && ims_wifi && !registered && registration_code>=500 && registration_code<=599){
                    vowifi_registration_rejected=1;event("vowifi_registration_rejected");
                }
                char direction[32];unsigned code,bytes;
                if(sscanf(buffer->data,"%31s SIP response %u bytes=%u",direction,&code,&bytes)==3 && code>=100 && code<=699)
                    printf("IMS_SIP_RESPONSE code=%u bytes=%u\n",code,bytes);
            } else sip_line(buffer->data);
            buffer->used=0;
        } else if(buffer->used<sizeof(buffer->data)-1)buffer->data[buffer->used++]=data[i];
        else return -1;
    }
    return 0;
}
static int pump(unsigned milliseconds) {
    time_t deadline=monotonic()+milliseconds/1000;
    unsigned ticks=milliseconds/50+1;
    for(unsigned i=0;i<ticks;i++) {
        sms_poll();
        if(ims_messages())return -2;
        struct pollfd fds[]={{ims_output,POLLIN,0},{sip_output,POLLIN,0},{cs_output,POLLIN,0}};
        if(poll(fds,3,50)<0 && errno!=EINTR)return -1;
        for(int j=0;j<3;j++)if(fds[j].revents) {
            if(read_lines(fds[j].fd,j==0?&ims_lines:j==1?&sip_lines:&cs_lines,j==0?1:j==2?2:0))return j==0?-2:j==2?-3:-1;
        }
        if(ims>0 && waitpid(ims,NULL,WNOHANG)==ims){ims=-1;event("ims_process_exited");return -2;}
        if(sip>0 && waitpid(sip,NULL,WNOHANG)==sip){sip=-1;event("sip_process_exited");return -1;}
        if(cs_voice>0 && waitpid(cs_voice,NULL,WNOHANG)==cs_voice){cs_voice=-1;event("cs_process_exited");return -3;}
        if(stopping || (milliseconds>=1000 && monotonic()>=deadline))break;
    }
    return 0;
}
static int system_modes(const char *reply,int *system,int *subsystem) {
    const char *p=strstr(reply,"^SYSINFO:");if(!p)return -1;
    p+=9;
    for(int i=0;i<7;i++) {
        const char *end=p+strcspn(p,",\r\n");
        /* ZTE permits an empty lock-state (field 5). Preserve empty fields. */
        if(i!=5) {
            char *number_end;long value=strtol(p,&number_end,10);
            while(number_end<end && *number_end==' ')number_end++;
            if(number_end!=end || number_end==p || value<0 || value>999)return -1;
            if(i==3)*system=(int)value;else if(i==6)*subsystem=(int)value;
        }
        /* B03 reports only five fields while searching, with no radio mode.
         * Do not invent a subsystem or tear down IMS while awaiting service. */
        if(i==4 && (*end=='\r' || *end=='\n' || !*end) && *system==0) {
            *subsystem=-1;return 1;
        }
        if((i<6 && *end!=',') || (i==6 && *end==','))return -1;
        p=end+1;
    }
    return 0;
}
static int registration_state(const char *reply,const char *prefix) {
    const char *p=strstr(reply,prefix);int mode,state;
    if(!p || !strstr(reply,"\r\nOK\r\n") ||
       sscanf(p+strlen(prefix)," %d,%d",&mode,&state)!=2 || mode<0 || mode>5 || state<0 || state>10)return -1;
    return state;
}
static int network_status(void) {
    char reply[4096],registration[128],status[200];
    int system,subsystem,capability,ignore;
    if(mf79u_cp_query(&cp,"AT+CEREG?",reply,sizeof(reply),5)<0){event("cereg_query_failed");return -1;}
    int eps=registration_state(reply,"+CEREG:");if(eps<0){event("cereg_field_missing");return -1;}
    char *p=strstr(reply,"+CEREG:");if(!p){event("cereg_field_missing");return -1;}
    p=strchr(p,',');if(!p)return -1;p++;
    size_t length=strcspn(p,"\r\n");if(length>=sizeof(registration))return -1;
    memcpy(registration,p,length);registration[length]=0;
    if(mf79u_cp_query(&cp,"AT+CREG?",reply,sizeof(reply),5)<0){event("creg_query_failed");return -1;}
    int cs=registration_state(reply,"+CREG:");if(cs<0){event("creg_field_missing");return -1;}
    if(mf79u_cp_query(&cp,"AT^SYSINFO",reply,sizeof(reply),5)<0){event("sysinfo_query_failed");return -1;}
    int modes=system_modes(reply,&system,&subsystem);
    if(modes<0){event("sysinfo_field_missing");return -1;}
    if(mf79u_cp_query(&cp,"AT+CIREP?",reply,sizeof(reply),5)<0){event("cirep_query_failed");return -1;}
    p=strstr(reply,"+CIREP:");if(!p || sscanf(p,"+CIREP: %d,%d",&ignore,&capability)!=2){event("cirep_field_missing");return -1;}
    eps_state=eps;cs_state=cs;
    /* The vendor owns GSM/SMS. IMS notifications need a live private engine;
     * cellular registration and SIP MESSAGE do not require that engine. */
    if(request<0)return 0;
    int n=snprintf(status,sizeof(status),"\r\n+CEREG: %s\r\n",registration);
    if(n<0 || n>=(int)sizeof(status))return -1;
    if(strcmp(last_registration,registration)) {
        if(send_ims(0x150b,status,(size_t)n,1) || pump(100))return -1;
        strcpy(last_registration,registration);
    }
    if(modes>0 && last_subsystem!=-2) {
        event("waiting_for_radio_service");last_system=-1;last_subsystem=-2;
    }
    n=snprintf(status,sizeof(status),"\r\n^MODE: %d,%d\r\n",system,subsystem);
    if(!modes && (system!=last_system || subsystem!=last_subsystem)) {
        if(send_ims(0x150b,status,(size_t)n,1) || pump(100))return -1;
        last_system=system;last_subsystem=subsystem;
    }
    n=snprintf(status,sizeof(status),"\r\n+CIREPI: %d\r\n",capability);
    if(capability!=last_capability) {
        if(send_ims(0x150b,status,(size_t)n,1))return -1;
        last_capability=capability;
    }
    return 0;
}
static pid_t spawn_ims(const char *binary,const char *library) {
    int pipefd[2];if(pipe(pipefd))return -1;
    pid_t pid=fork();
    if(!pid) {
        int writer=fcntl(pipefd[1],F_DUPFD,10),null=open("/dev/null",O_RDWR);
        if(writer<0 || null<0)_exit(126);
        dup2(null,0);dup2(null,1);dup2(null,2);dup2(writer,3);
        for(int fd=4;fd<256;fd++)close(fd);
        if(ims_wifi && effective_usb)setenv("MF79U_VOWIFI_USB","1",1);else unsetenv("MF79U_VOWIFI_USB");
        if(ims_wifi)setenv("MF79U_IMS_INTERFACE","vowifi0",1);else unsetenv("MF79U_IMS_INTERFACE");
        setenv("LD_PRELOAD",library,1);setenv("MF79U_SOFTWARE_MEDIA","1",1);
        setenv("MF79U_PCM_NETWORK","1",1);setenv("MF79U_PCM_WIDEBAND","1",1);
        setenv("MF79U_AMR_PREFER_HIGH","1",1);setenv("MF79U_OPERATOR_CODECS","1",1);
        setenv("MF79U_OPERATOR_CODEC","auto",1);execl(binary,binary,(char*)NULL);_exit(127);
    }
    close(pipefd[1]);if(pid<0){close(pipefd[0]);return -1;}
    ims_output=pipefd[0];fcntl(ims_output,F_SETFL,O_NONBLOCK);return pid;
}
static pid_t spawn_sip(const char *binary,const char *config) {
    int in[2],out[2];if(pipe(in) || pipe(out))return -1;
    pid_t pid=fork();
    if(!pid) {
        dup2(in[0],0);dup2(out[1],1);int null=open("/dev/null",O_WRONLY);if(null<0)_exit(126);
        dup2(null,2);for(int fd=3;fd<256;fd++)close(fd);
        execl(binary,binary,"--config",config,"--wideband",(char*)NULL);_exit(127);
    }
    close(in[0]);close(out[1]);
    if(pid<0){close(in[1]);close(out[0]);return -1;}
    sip_input=in[1];sip_output=out[0];fcntl(sip_output,F_SETFL,O_NONBLOCK);return pid;
}
static pid_t spawn_cs(const char *binary) {
    int in[2],out[2];if(pipe(in))return -1;
    if(pipe(out)){close(in[0]);close(in[1]);return -1;}
    pid_t pid=fork();
    if(!pid) {
        dup2(in[0],0);dup2(out[1],1);int null=open("/dev/null",O_WRONLY);if(null<0)_exit(126);
        dup2(null,2);for(int fd=3;fd<256;fd++)close(fd);
        execl(binary,binary,"--owned-pipe",(char *)NULL);_exit(127);
    }
    close(in[0]);close(out[1]);
    if(pid<0){close(in[1]);close(out[0]);return -1;}
    cs_input=in[1];cs_output=out[0];fcntl(cs_input,F_SETFL,O_NONBLOCK);fcntl(cs_output,F_SETFL,O_NONBLOCK);
    cs_epoch=cs_sequence=cs_call_id=0;cs_ready=cs_suspended=cs_resume_requested=0;
    memset(&cs_lines,0,sizeof(cs_lines));return pid;
}
/* An idle adapter releases its PCM socket and hardware before SUSPENDED.
 * IMS must wait for that acknowledgement. No backend switch during a call. */
static int suspend_cs(void) {
    if(cs_voice<0)return 1;
    if(voice.owner!=MF79U_VOICE_NONE || !cs_epoch)return 0;
    if(cs_suspended)return 1;
    if(cs_resume_requested!=2 && !send_cs("SUSPEND",0,NULL))cs_resume_requested=2;
    return 0;
}
static void resume_cs(void) {
    if(cs_voice>0 && cs_epoch && ims<0 && (cs_state==1 || cs_state==5) &&
       cs_resume_requested!=1 && (cs_suspended || !cs_ready) && !send_cs("RESUME",0,"2"))
        cs_resume_requested=1;
}
static void stop_child(pid_t *pid) {
    if(*pid<1)return;
    kill(*pid,SIGTERM);kill(*pid,SIGCONT);
    for(int i=0;i<30;i++) {
        if(waitpid(*pid,NULL,WNOHANG)==*pid){*pid=-1;return;}
        usleep(100000);
    }
    kill(*pid,SIGKILL);waitpid(*pid,NULL,0);*pid=-1;
}
static void stop_cs_runtime(void) {
    cs_ready=0;reconcile_voice();send_cs("QUIT",0,NULL);stop_child(&cs_voice);
    if(cs_input>=0){close(cs_input);cs_input=-1;}
    if(cs_output>=0){close(cs_output);cs_output=-1;}
    cs_epoch=cs_sequence=cs_call_id=0;cs_suspended=cs_resume_requested=0;
    memset(&cs_lines,0,sizeof(cs_lines));
    /* A restarted adapter must prove driver quiescence with HELLO before a
     * new call or IMS startup; child exit alone is not that proof. */
}
/* Restart only IMS: preserve the SIP process, its registration and SMS queue. */
static int stop_ims_runtime(void) {
    int had_request=request>=0;
    sms_reset();
    voice_ready=registered=vowifi_registration_rejected=0;reconcile_voice();
    if(request>=0 && ims>0) {
        if(voice.owner==MF79U_VOICE_IMS){query_ims("ATH");query_ims("AT+CHUP");}
        query_ims("AT+CVMOD=0");
        (void)pump(500);
    }
    if(ims>0)inventory(0);
    stop_child(&ims);
    if(ims_output>=0){close(ims_output);ims_output=-1;}
    if(response>=0){msgctl(response,IPC_RMID,NULL);response=-1;}
    request=-1;cellular_ended(MF79U_VOICE_IMS);
    if(cleanup_queues()){event("queue_cleanup_refused");return -1;}
    owned_count=0;
    if(cp.rx>=0 && had_request) {
        char reply[4096];
        mf79u_cp_query(&cp,"AT+ZIMSSTATE=0",reply,sizeof(reply),5);
        if(!ims_wifi)mf79u_cp_query(&cp,"AT+ZPDPDEACT=5",reply,sizeof(reply),5);
        memset(reply,0,sizeof(reply));
    }
    codec_factory=frontend=wb_advertised=0;
    memset(&ims_lines,0,sizeof(ims_lines));last_registration[0]=0;
    last_system=last_subsystem=last_capability=-1;
    reconcile_voice();return 0;
}
static int start_ims_runtime(const char *binary,const char *library) {
    if(voice.owner!=MF79U_VOICE_NONE || !suspend_cs())return -1;
    response=msgget(0x700f,IPC_CREAT|IPC_EXCL|0600);
    if(response<0){event("response_queue_busy");return -1;}
    ims=spawn_ims(binary,library);if(ims<0){event("ims_start_failed");return -1;}
    for(int i=0;i<100;i++) {
        request=msgget(0x701e,0600);if(request>=0)break;
        usleep(50000);
    }
    if(inventory(0) || request<0 || pump(500) || !codec_factory){event("ims_initialisation_failed");return -1;}
    const char *setup[]={"AT+ZIMSAMRW=1","AT+CVMOD=3","AT+ZIMSAPN=\"ims\"","AT+AUTOSTART=1","AT+CFUN=1"};
    for(unsigned i=0;i<sizeof(setup)/sizeof(setup[0]);i++)if(query_ims(setup[i]) || pump(i==4 && !ims_wifi?8000:1000))return -1;
    sms_configure();if(pump(1000))return -1;
    event("waiting_for_ims");publish("registering");
    return network_status();
}
/* Checked B03 profiles: LTE 27 and GSM 13.
 * Only while idle with both media backends released. CFUN readback handles
 * delayed terminal replies; no failed command is treated as registration. */
static int radio_query(const char *command,const char *expected) {
    char reply[4096];int r=mf79u_cp_query(&cp,command,reply,sizeof(reply),8);
    int ok=r>=0 && strstr(reply,"\r\nOK\r\n") && (!expected || strstr(reply,expected));
    memset(reply,0,sizeof(reply));return ok?0:-1;
}
static int radio_cfun(int value) {
    (void)radio_query(value?"AT+CFUN=1":"AT+CFUN=0",NULL);
    return radio_query("AT+CFUN?",value?"+CFUN: 1":"+CFUN: 0");
}
static int switch_radio(int target) {
    if(ims>0 || voice.owner!=MF79U_VOICE_NONE || !suspend_cs())return -1;
    const char *profile=target==2?"^SYSCONFIG: 13,0,1,2":"^SYSCONFIG: 27,0,1,2";
    const char *voice_flag=target!=1?"+ZSET: \"VOICE_SUPPORT\",1":"+ZSET: \"VOICE_SUPPORT\",0";
    const char *open_flag=target!=1?"+ZSET: \"OPEN_VOICE_FLAG\",1":"+ZSET: \"OPEN_VOICE_FLAG\",0";
    if(!radio_query("AT^SYSCONFIG?",profile) &&
       !radio_query("AT+ZSET=\"VOICE_SUPPORT\"",voice_flag) &&
       !radio_query("AT+ZSET=\"OPEN_VOICE_FLAG\"",open_flag) && !radio_query("AT+CFUN?","+CFUN: 1"))return 0;
    if(radio_cfun(0))return -1;
    int fail=radio_query(target==2?"AT^SYSCONFIG=13,0,1,2":"AT^SYSCONFIG=27,0,1,2",NULL) ||
        radio_query(target!=1?"AT+ZSET=\"VOICE_SUPPORT\",1":"AT+ZSET=\"VOICE_SUPPORT\",0",NULL) ||
        radio_query(target!=1?"AT+ZSET=\"OPEN_VOICE_FLAG\",1":"AT+ZSET=\"OPEN_VOICE_FLAG\",0",NULL) ||
        radio_query("AT^SYSCONFIG?",profile) || radio_query("AT+ZSET=\"VOICE_SUPPORT\"",voice_flag) ||
        radio_query("AT+ZSET=\"OPEN_VOICE_FLAG\"",open_flag);
    int on=radio_cfun(1);return fail || on?-1:0;
}
int main(int argc,char **argv) {
    if(argc==2 && !strcmp(argv[1],"--selftest")) {
        if(call_action_allowed(1,1,1) || call_action_allowed(0,1,0) ||
           call_action_allowed(1,0,0) || !call_action_allowed(1,1,0))return 1;

        if(mf79u_pdp_selftest())return 1;
        const char *valid[]={"AT+CFUN?","AT+ZSCA?","AT+ZTPMR?","AT+ZTPMR=255","AT+ZNUMTYPE=\"+12345678\"",
            "AT^MBAU=\"0123456789abcdef0123456789abcdef\",\"0123456789ABCDEF0123456789ABCDEF\""};
        const char *invalid[]={"AT+CFUN=0","AT+CMGS=15","AT+ZMGS=15","AT+ZTPMR=256","AT+ZTPMR=1;ATH","ATD12345678;","AT+ZNUMTYPE=\"123;ATH\"",
            "AT+ZNUMTYPE=\"12\"","AT^MBAU=\"0123456789abcdef0123456789abcdef\",\"0123456789ABCDEF0123456789ABCDE\"",
            "AT^MBAU=\"x123456789abcdef0123456789abcdef\",\"0123456789ABCDEF0123456789ABCDEF\""};
        for(unsigned i=0;i<sizeof(valid)/sizeof(valid[0]);i++)if(!cp_allowed(valid[i]))return 1;
        for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++)if(cp_allowed(invalid[i]))return 1;
        int system,subsystem;
        if(system_modes("\r\n^SYSINFO: 2,2,0,5,1,,7\r\nOK\r\n",&system,&subsystem) || system!=5 || subsystem!=7 ||
            !system_modes("^SYSINFO: 2,2,0,,1,,7\r\n",&system,&subsystem))return 1;
        if(system_modes("\r\n^SYSINFO: 0,3,0,0,1\r\nOK\r\n",&system,&subsystem)!=1 || system!=0 || subsystem!=-1 ||
            system_modes("^SYSINFO: 0,3,0,0,1",&system,&subsystem)!=1 ||
            system_modes("^SYSINFO: 2,2,1,5,1,,7\r\n",&system,&subsystem) || system!=5 || subsystem!=7)return 1;
        const char *bad_modes[]={"^SYSINFO: 2,2,0,5,1\r\n", "^SYSINFO: 0,3,0,0\r\n",
            "^SYSINFO: 0,3,0,0,1,\r\n", "^SYSINFO: 0,3,0,x,1\r\n",
            "^SYSINFO: 0,3,0,0,x\r\n", "^SYSINFO: 0,3,0,0,\r\n",
            "^SYSINFO: 2,2,0,5,1,,x\r\n", "ERROR\r\n"};
        for(unsigned i=0;i<sizeof(bad_modes)/sizeof(bad_modes[0]);i++)
            if(system_modes(bad_modes[i],&system,&subsystem)>=0)return 1;
        if(registration_state("\r\n+CEREG: 2,5,\"00D3\",\"000052C4\",7\r\nOK\r\n","+CEREG:")!=5 ||
           registration_state("\r\n+CREG: 2,1\r\nOK\r\n","+CREG:")!=1 ||
           registration_state("\r\n+CEREG: 2,2\r\nOK\r\n","+CEREG:")!=2 ||
           registration_state("\r\n+CEREG: 2,5\r\nERROR\r\n","+CEREG:")!=-1 ||
           registration_state("\r\n+CEREG: 2,99\r\nOK\r\n","+CEREG:")!=-1)return 1;
        puts("PASS native CP: AKA framing, number classification, mutation rejection, searching/roaming/malformed SYSINFO");return 0;
    }
    if(argc!=5 && argc!=6) {
        fputs("Usage: mf79u-native-gateway IMS_BINARY MEDIA_LIBRARY SIP_BINARY GATEWAY_INI [CS_BINARY]\n",stderr);return 2;
    }
    gateway_config=argv[4];
    started=monotonic();setvbuf(stdout,NULL,_IONBF,0);
    signal(SIGINT,interrupted);signal(SIGTERM,interrupted);signal(SIGPIPE,SIG_IGN);
    int lock=open("/dev/.mf79u-native.lock",O_CREAT|O_RDWR,0600),result=1;
    if(lock<0 || flock(lock,LOCK_EX|LOCK_NB)){event("already_running");return 1;}
    fcntl(lock,F_SETFD,FD_CLOEXEC);
    int direct=getenv("MF79U_CP_DIRECT") && !strcmp(getenv("MF79U_CP_DIRECT"),"1");
    if(inventory(1) || (direct?mf79u_cp_open_direct(&cp):mf79u_cp_open(&cp))){event("cp_or_ims_busy");goto done;}
    /* LAN SIP registration and MESSAGE stay available even on GSM or while
     * IMS is rejected. Voice remains gated on validated IMS/frontend readiness. */
    sip=spawn_sip(argv[3],argv[4]);
    if(sip<0 || pump(1500) || send_sip("NOT_READY")){event("sip_start_failed");goto done;}
    if(argc==6){cs_voice=spawn_cs(argv[5]);if(cs_voice<0){event("cs_start_failed");goto done;}}
    if(sms_listen()){event("ims_sms_socket_failed");goto done;}
    event("local_cp_started");event("sip_sms_started");publish("sms_only");
    time_t next=0,retry=0,deadline=monotonic()+MF79U_IMS_TIMEOUT,cs_retry=0,radio_retry=0;
    read_voice_mode();effective_mode=requested_mode;effective_usb=requested_usb;
    for(;;) {
        if(stopping){result=0;break;}
        int pumped=pump(500);
        poll_cs_status();read_voice_mode();
        if(pumped==-1)goto done;
        if(pumped==-3) {
            event("cs_failed_sms_preserved");stop_cs_runtime();cs_retry=monotonic()+5;
        }
        if(argc==6 && cs_voice<0 && monotonic()>=cs_retry) {
            cs_voice=spawn_cs(argv[5]);cs_retry=monotonic()+5;
            if(cs_voice<0)event("cs_start_failed");
        }
        if(voice.owner==MF79U_VOICE_NONE && (effective_mode!=requested_mode || effective_usb!=requested_usb)) {
            if(effective_usb!=requested_usb && ims_wifi){if(stop_ims_runtime())goto done;vowifi_stop();ims_wifi=0;vowifi_had_tunnel=0;}
            effective_mode=requested_mode;effective_usb=requested_usb;auto_fallback=0;retry=promotion_at=0;
            fallback_reason="";vowifi_retry=0;deadline=monotonic()+MF79U_IMS_TIMEOUT;next=0;
            event("voice_mode_changed");
        }
        if(pumped==-2) {
            event("ims_failed_sms_preserved");
            if(stop_ims_runtime())goto done;
            auto_fallback=effective_mode==VOICE_AUTO;fallback_reason="ims_process_failed";
            retry=promotion_at=monotonic()+MF79U_IMS_RETRY;next=0;
        }
        reconcile_voice();
        if(monotonic()<next)continue;
        next=monotonic()+MF79U_RADIO_INTERVAL;
        int guarded=access(MF79U_CS_ONLY_FILE,F_OK)==0 || errno!=ENOENT;
        int wifi_available=vowifi_wifi_ready(voice.owner!=MF79U_VOICE_NONE);
        int vowifi_exit=0;
        if(vowifi_pid>1 && waitpid(vowifi_pid,&vowifi_exit,WNOHANG)==vowifi_pid){
            printf("VOWIFI_MANAGER_EXIT code=%d signal=%d\n",WIFEXITED(vowifi_exit)?WEXITSTATUS(vowifi_exit):-1,WIFSIGNALED(vowifi_exit)?WTERMSIG(vowifi_exit):0);
            event("vowifi_manager_exited");kill(-vowifi_pid,SIGKILL);vowifi_pid=-1;vowifi_stop();vowifi_had_tunnel=0;vowifi_schedule_retry();fallback_reason="vowifi_start_failed";
        }
        if(ims_wifi && !wifi_available)event("vowifi_wifi_unavailable");
        int wifi_wanted=!guarded && (effective_mode==VOICE_VOWIFI || (effective_mode==VOICE_AUTO && wifi_available && monotonic()>=vowifi_retry));
        if(voice.owner!=MF79U_VOICE_NONE && ims_wifi){
            if(ims_wifi && (!wifi_available || !vowifi_tunnel_ready())){voice_ready=0;reconcile_voice();}
            /* Existing calls retain their admitting access until cleanup. */
            publish(voice_ready?"ready":"registering");continue;
        }
        if(voice.owner!=MF79U_VOICE_NONE)wifi_wanted=0;
        if(wifi_wanted && wifi_available && (vowifi_pid>0 || ims>0 || monotonic()>=vowifi_retry)){
            if(ims>0 && !ims_wifi && stop_ims_runtime())goto done;
            ims_wifi=1;
            if(vowifi_pid<0 && monotonic()>=vowifi_retry){vowifi_start();fallback_reason="";registration_phase="connecting_vowifi";deadline=monotonic()+MF79U_IMS_TIMEOUT;}
            int tunnel_now=vowifi_tunnel_ready();
            if(!tunnel_now && vowifi_had_tunnel){
                vowifi_had_tunnel=0;
                event("vowifi_tunnel_lost");
                if(ims>0 && stop_ims_runtime())goto done;
                ims_wifi=1;vowifi_deadline=monotonic()+120;
                registration_phase="renewing_vowifi";
            }
            if(tunnel_now){
                unsigned long generation=0;
                FILE *gf=fopen("/dev/mf79u/vowifi/generation","r");
                if(gf){if(fscanf(gf,"%lu",&generation)!=1)generation=0;fclose(gf);}
                if(generation && vowifi_ims_generation && generation!=vowifi_ims_generation){
                    event("vowifi_tunnel_replaced");
                    if(ims>0 && stop_ims_runtime())goto done;
                    ims_wifi=1;
                    memset(&vowifi_choices,0,sizeof(vowifi_choices));
                    (void)vowifi_tunnel_ready();
                }
                vowifi_ims_generation=generation;
                vowifi_had_tunnel=1;
                if(ims<0 && monotonic()>=vowifi_retry){registration_phase="registering_vowifi";if(start_ims_runtime(argv[1],argv[2])){if(stop_ims_runtime())goto done;vowifi_deadline=0;}deadline=monotonic()+MF79U_IMS_TIMEOUT;}
                if(ims>0 && registered && !voice_ready){
                    if(!query_ims("AT+CVMOD?") && !pump(1500) && !query_ims("AT+ZIMSAMRW?") && !pump(1000) && frontend && wb_advertised){voice_ready=1;vowifi_failures=0;vowifi_retry=0;registration_phase="ready";fallback_reason="";vowifi_pcscf_remember();event("vowifi_ready");}
                }
                if(voice_ready){reconcile_voice();publish("ready");continue;}
                if(ims>0 && !vowifi_registration_rejected && monotonic()<deadline){publish("registering");continue;}
                if(ims>0 && vowifi_pcscf_next(&vowifi_choices)){
                    if(stop_ims_runtime())goto done;
                    registration_phase="switching_vowifi_pcscf";deadline=monotonic()+MF79U_IMS_TIMEOUT;
                    event("vowifi_pcscf_failover");publish("registering");continue;
                }
            }else if(vowifi_pid>0 && monotonic()<vowifi_deadline){publish("registering");continue;}
            printf("VOWIFI_ATTEMPT_ENDED tunnel=%d registered=%d ims=%d\n",vowifi_tunnel_ready(),registered,ims>0);
            event("vowifi_attempt_ended");
            if(ims>0 && stop_ims_runtime())goto done;
            vowifi_stop();vowifi_had_tunnel=0;vowifi_schedule_retry();
            ims_wifi=0;fallback_reason="vowifi_registration_failed";
        }
        if(effective_mode==VOICE_VOWIFI && !guarded){
            if(ims>0 && stop_ims_runtime())goto done;
            vowifi_stop();ims_wifi=0;
            registration_phase=wifi_available?"vowifi_unavailable":effective_usb?"waiting_for_usb":"waiting_for_wifi";
            if(!wifi_available)fallback_reason=effective_usb?"usb_not_connected":"wifi_not_connected";
            voice_ready=0;reconcile_voice();publish("sms_only");continue;
        }
        if(ims_wifi){if(ims>0 && stop_ims_runtime())goto done;
            vowifi_stop();ims_wifi=0;retry=0;deadline=monotonic()+MF79U_IMS_TIMEOUT;}

        int target=voice_registration_target(guarded?VOICE_CS:effective_mode,auto_fallback,
            (unsigned long)monotonic(),(unsigned long)retry,(int)voice.owner);
        /* CS-only also remains fail-closed on a legacy installation without
         * the optional CS child. It must stop an idle IMS engine immediately. */
        if(target!=1 && ims>0 && voice.owner==MF79U_VOICE_NONE && stop_ims_runtime())goto done;
        if(argc==6 && voice.owner==MF79U_VOICE_NONE && target!=radio_profile) {
            registration_phase=target==2?"switching_to_cs":"switching_to_volte";publish("registering");
            if(ims>0 && stop_ims_runtime())goto done;
            if(!suspend_cs())continue;
            if(monotonic()<radio_retry)continue;
            if(switch_radio(target)) {
                registration_phase="radio_switch_failed";fallback_reason="radio_configuration_failed";
                radio_profile=0;radio_retry=monotonic()+15;
                publish("sms_only");continue;
            }
            radio_profile=target;eps_state=cs_state=-1;
            auto_fallback=effective_mode==VOICE_AUTO && target!=1;
            deadline=monotonic()+MF79U_IMS_TIMEOUT;
            registration_phase=target==2?"registering_cs":"registering_volte";
            event(target==2?"cs_radio_selected":"volte_radio_selected");
        }
        if(network_status()) {
            event("network_state_unavailable");eps_state=cs_state=-1;
            /* A failing status query must not extend the VoLTE registration
             * attempt indefinitely. Radio switching still requires checked
             * CFUN/profile commands and CS readiness still requires CREG. */
            if(target==1 && !voice_ready && monotonic()>=deadline && voice.owner==MF79U_VOICE_NONE) {
                if(stop_ims_runtime())goto done;
                auto_fallback=effective_mode==VOICE_AUTO;fallback_reason="network_state_unavailable";
                retry=promotion_at=monotonic()+MF79U_IMS_RETRY;deadline=retry;
                registration_phase="volte_unavailable";
            }
            voice_ready=0;reconcile_voice();publish("sms_only");continue;
        }
        if(target!=1) {
            if(cs_state==1 || cs_state==5){resume_cs();registration_phase=cs_ready?"ready":"starting_cs";}
            else registration_phase="registering_cs";
            reconcile_voice();publish("sms_only");continue;
        }
        if(ims>0 && eps_state!=1 && eps_state!=5 && voice.owner==MF79U_VOICE_NONE) {
            if(stop_ims_runtime())goto done;
            auto_fallback=effective_mode==VOICE_AUTO;fallback_reason="lte_service_lost";
            retry=promotion_at=monotonic()+MF79U_IMS_RETRY;
        }
        if(ims<0 && !cs_only() && (eps_state==1 || eps_state==5) && monotonic()>=retry &&
           voice.owner==MF79U_VOICE_NONE && (argc==5 || cs_voice>0) && suspend_cs()) {
            auto_fallback=0;registration_phase="registering_volte";event("lte_ims_attempt");
            int attempt=start_ims_runtime(argv[1],argv[2]);deadline=monotonic()+MF79U_IMS_TIMEOUT;
            if(attempt) {
                event("ims_failed_sms_preserved");if(stop_ims_runtime())goto done;
                auto_fallback=effective_mode==VOICE_AUTO;fallback_reason="ims_start_failed";
                retry=promotion_at=monotonic()+MF79U_IMS_RETRY;
            }
        }
        if(ims>0 && registered && !voice_ready) {
            if(!query_ims("AT+CVMOD?") && !pump(1500) &&
               !query_ims("AT+ZIMSAMRW?") && !pump(1000) && frontend && wb_advertised) {
                voice_ready=1;reconcile_voice();registration_phase="ready";fallback_reason="";
                event("autonomous_control_ready");
            }else event("frontend_not_ready_sms_preserved");
        }
        if(!voice_ready && monotonic()>=deadline && voice.owner==MF79U_VOICE_NONE) {
            event("registration_timeout_sms_preserved");if(stop_ims_runtime())goto done;
            auto_fallback=effective_mode==VOICE_AUTO;
            fallback_reason=(eps_state==1 || eps_state==5)?"volte_registration_timeout":"lte_registration_timeout";
            retry=promotion_at=monotonic()+MF79U_IMS_RETRY;deadline=retry;
            registration_phase="volte_unavailable";
        }
        if(voice_ready)registration_phase="ready";
        reconcile_voice();publish(voice_ready?"ready":ims>0?"registering":"sms_only");
    }
 done:
    sms_close();
    event("stopping");hangup_owned();send_sip("NOT_READY");
    if(stop_ims_runtime())result=1;
    vowifi_stop();stop_cs_runtime();mf79u_voice_ended(&voice);voice.selected=MF79U_VOICE_NONE;active_call=0;
    send_sip("QUIT");stop_child(&sip);
    if(sip_input>=0){close(sip_input);sip_input=-1;}
    if(sip_output>=0){close(sip_output);sip_output=-1;}
    mf79u_cp_close(&cp);registered=voice_ready=0;publish("stopped");
    event("stopped");if(lock>=0)close(lock);return result;
}
