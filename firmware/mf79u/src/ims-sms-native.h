/* Owned SMS-over-IMS AT channel. No CP SMS submission, phone/body logging or
 * retries. Port 4 is exclusively SMS; port 3 acknowledges durable MT storage.
 * The existing B03 engine owns SIP MESSAGE / RP-DATA / RP-ACK and IMS security. */
#include <dirent.h>
#include <sys/socket.h>
#include <sys/un.h>
#ifndef MF79U_SMS_IMS_SOCKET
#define MF79U_SMS_IMS_SOCKET "/dev/.mf79u-sms-ims.sock"
#endif
#ifndef MF79U_SMS_IMS_SPOOL
#define MF79U_SMS_IMS_SPOOL "/mnt/userdata/mf79u/sms-ims-spool"
#endif
static int sms_listener=-1,sms_client=-1,sms_stage,sms_configured,sms_fenced;
static time_t sms_deadline;
static char sms_pdu[401],sms_incoming[401];
static unsigned sms_incoming_length,sms_sequence;
static unsigned sms_submitted,sms_confirmed,sms_received,sms_rejected;
static void sms_reply(unsigned char code) {
    unsigned char packet[5]={'M','S','I','1',code};
    if(sms_client>=0){(void)send(sms_client,packet,sizeof(packet),MSG_NOSIGNAL);close(sms_client);sms_client=-1;}
}
static int sms_at(const char *command,unsigned port) {
    char buffer[430];int n=snprintf(buffer,sizeof(buffer),"%s\r",command);
    int r=n>0 && n<(int)sizeof(buffer)?send_ims(0x1509,buffer,(size_t)n,port):-1;
    memset(buffer,0,sizeof(buffer));return r;
}
static int sms_available(void) {
    return effective_mode==VOICE_VOWIFI && requested_mode==VOICE_VOWIFI &&
        ims_wifi && ims>0 && registered && request>=0 && vowifi_tunnel_ready();
}
static int sms_hex(const char *p,size_t n) {
    if(n<4 || n>400 || (n&1))return 0;
    for(size_t i=0;i<n;i++)if(!isxdigit((unsigned char)p[i]))return 0;
    return 1;
}
static int sms_spool(const char *p) {
    if(mkdir(MF79U_SMS_IMS_SPOOL,0700) && errno!=EEXIST)return -1;
    struct stat st;
    if(lstat(MF79U_SMS_IMS_SPOOL,&st) || !S_ISDIR(st.st_mode) || st.st_uid || (st.st_mode&077))return -1;
    DIR *dir=opendir(MF79U_SMS_IMS_SPOOL);if(!dir)return -1;
    unsigned count=0;struct dirent *entry;
    while((entry=readdir(dir)))if(entry->d_name[0]!='.')count++;
    closedir(dir);if(count>=128)return -1;
    char temporary[256],target[256];
    snprintf(target,sizeof(target),"%s/%ld-%u.pdu",MF79U_SMS_IMS_SPOOL,(long)getpid(),++sms_sequence);
    snprintf(temporary,sizeof(temporary),"%s/.%ld-%u.tmp",MF79U_SMS_IMS_SPOOL,(long)getpid(),sms_sequence);
    int fd=open(temporary,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(fd<0)return -1;
    size_t n=strlen(p);int ok=write(fd,p,n)==(ssize_t)n && !fsync(fd);
    close(fd);
    if(!ok || rename(temporary,target)){unlink(temporary);return -1;}
    fd=open(MF79U_SMS_IMS_SPOOL,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if(fd<0)return -1;
    ok=!fsync(fd);close(fd);return ok?0:-1;
}
/* Called before native_event tokenizes/clears the private AT response. */
static void sms_ims_event(const char *text,unsigned port) {
    if(port==4) {
        if(sms_stage==3) {
            if(strstr(text,"\r\nOK\r\n")){sms_configured=1;sms_stage=0;event("ims_sms_pdu_ready");}
            else if(strstr(text,"ERROR")){sms_stage=0;sms_configured=0;event("ims_sms_configuration_failed");}
        }else if(sms_stage==1 && strstr(text,"> ")) {
            size_t n=strlen(sms_pdu);sms_pdu[n]=0x1a;
            if(send_ims(0x1509,sms_pdu,n+1,4)){sms_reply(7);sms_fenced=1;sms_stage=0;}
            else {sms_stage=2;sms_deadline=monotonic()+45;sms_submitted++;event("ims_sms_submitted");}
            memset(sms_pdu,0,sizeof(sms_pdu));
        }else if((sms_stage==1 || sms_stage==2) && strstr(text,"+CMGS:") && strstr(text,"\r\nOK\r\n")) {
            sms_confirmed++;sms_reply(0);sms_stage=0;event("ims_sms_rp_ack");
        }else if((sms_stage==1 || sms_stage==2) && strstr(text,"ERROR")) {
            sms_rejected++;sms_reply(6);sms_stage=0;memset(sms_pdu,0,sizeof(sms_pdu));event("ims_sms_submission_rejected");
        }
    }
    const char *line=text;
    while(*line) {
        while(*line=='\r' || *line=='\n')line++;
        size_t n=strcspn(line,"\r\n");if(!n)break;
        if((n>=5 && !memcmp(line,"+CMT:",5)) || (n>=5 && !memcmp(line,"+CDS:",5))) {
            const char *p=line+5,*end=line+n;
            for(const char *q=p;q<end;q++)if(*q==',')p=q+1;
            char *tail;unsigned long length=strtoul(p,&tail,10);
            while(tail<end && *tail==' ')tail++;
            sms_incoming_length=tail==end && length>0 && length<=176?(unsigned)length:0;
            memset(sms_incoming,0,sizeof(sms_incoming));
        }else if(sms_incoming_length && sms_hex(line,n)) {
            /* CMT/CDS PDU includes an SMSC length byte, then exactly TPDU len. */
            char sca[3]={line[0],line[1],0};unsigned long s=strtoul(sca,NULL,16);
            if(n==2*(1+s+sms_incoming_length)) {
                memcpy(sms_incoming,line,n);sms_incoming[n]=0;
                int saved=sms_spool(sms_incoming);
                if(!saved){sms_received++;event("ims_sms_durable_receive");}
                else event("ims_sms_storage_full_or_failed");
                /* CSMS=1 is an IMS-local policy. RP-ACK only after fsync. */
                if(sms_at(saved?"AT+CNMA=2":"AT+CNMA=1",3))event("ims_sms_ack_failed");
            }else event("ims_sms_invalid_pdu");
            sms_incoming_length=0;memset(sms_incoming,0,sizeof(sms_incoming));
        }
        line+=n;
    }
}
static void sms_reset(void) {
    if(sms_stage==1 || sms_stage==2)sms_reply(7);
    sms_stage=sms_configured=sms_fenced=0;sms_incoming_length=0;
    memset(sms_pdu,0,sizeof(sms_pdu));memset(sms_incoming,0,sizeof(sms_incoming));
}
static int sms_listen(void) {
    struct sockaddr_un address={.sun_family=AF_UNIX};
    snprintf(address.sun_path,sizeof(address.sun_path),"%s",MF79U_SMS_IMS_SOCKET);
    struct stat st;if(!lstat(address.sun_path,&st)) {
        if(!S_ISSOCK(st.st_mode) || st.st_uid)return -1;
        int check=socket(AF_UNIX,SOCK_SEQPACKET,0);
        if(check<0)return -1;
        int live=!connect(check,(struct sockaddr *)&address,sizeof(address));close(check);
        if(live || unlink(address.sun_path))return -1;
    }else if(errno!=ENOENT)return -1;
    sms_listener=socket(AF_UNIX,SOCK_SEQPACKET,0);if(sms_listener<0)return -1;
    if(bind(sms_listener,(struct sockaddr *)&address,sizeof(address)) || chmod(address.sun_path,0600) || listen(sms_listener,4))return -1;
    fcntl(sms_listener,F_SETFL,O_NONBLOCK);fcntl(sms_listener,F_SETFD,FD_CLOEXEC);return 0;
}
/* B03 CMGF is a forwarded configuration command without an AP terminal
 * response. Verify the owned child's actual G_IMS_CMGF enum after replying.
 * Fixed address is checked in stock B03 CmgsPduProc/DecAtReqCmgf2 disassembly;
 * this reads four bytes only, never writes memory or reads SMS/SIM material. */
static int sms_format_ready(void) {
#ifdef MF79U_SMS_FORMAT_FIXTURE
    return 1;
#else
    if(ims<1)return 0;
    char path[64];snprintf(path,sizeof(path),"/proc/%ld/mem",(long)ims);
    int fd=open(path,O_RDONLY);if(fd<0)return 0;
    uint32_t format=UINT32_MAX;ssize_t n=pread(fd,&format,sizeof(format),0xcea14);
    close(fd);return n==4 && format==0;
#endif
}
static void sms_poll(void) {
    if(!sms_configured && sms_stage==3 && sms_format_ready()) {
        sms_configured=1;if(sms_stage==3)sms_stage=0;event("ims_sms_pdu_ready");
    }
    if(sms_stage && monotonic()>=sms_deadline) {
        if(sms_stage!=3){sms_reply(7);sms_fenced=1;event("ims_sms_result_uncertain");}
        sms_stage=0;memset(sms_pdu,0,sizeof(sms_pdu));
    }
    int fd=accept(sms_listener,NULL,NULL);if(fd<0)return;
    fcntl(fd,F_SETFL,O_NONBLOCK);fcntl(fd,F_SETFD,FD_CLOEXEC);
    unsigned char packet[410];ssize_t n=recv(fd,packet,sizeof(packet),MSG_DONTWAIT|MSG_TRUNC);
    /* Local client writes immediately; allow its bounded packet to arrive on
     * the next pump tick, without blocking CP/voice. */
    if(n<0 && errno==EAGAIN) {
        struct pollfd p={fd,POLLIN,0};if(poll(&p,1,5)>0)n=recv(fd,packet,sizeof(packet),MSG_DONTWAIT|MSG_TRUNC);
    }
    if(n<5 || n>(ssize_t)sizeof(packet) || memcmp(packet,"MSI1",4)){close(fd);return;}
    if(packet[4]==1 && n==5) {
        char out[300];int size=snprintf(out,sizeof(out),"MSI1%c{\"ready\":%s,\"configured\":%s,\"fenced\":%s,\"formatVerified\":%s,\"submitted\":%u,\"confirmed\":%u,\"received\":%u,\"rejected\":%u}",0,
            sms_available() && sms_configured && !sms_fenced?"true":"false",sms_configured?"true":"false",sms_fenced?"true":"false",sms_format_ready()?"true":"false",sms_submitted,sms_confirmed,sms_received,sms_rejected);
        if(size>0 && size<(int)sizeof(out))(void)send(fd,out,(size_t)size,MSG_NOSIGNAL);
        close(fd);return;
    }
    unsigned char code=8;
    if(packet[4]==2 && sms_hex((const char *)packet+5,(size_t)n-5)) {
        if(!sms_available() || !sms_configured || sms_fenced)code=2;
        else if(sms_stage || sms_client>=0)code=3;
        else {
            char command[32],sca[3]={packet[5],packet[6],0};unsigned long s=strtoul(sca,NULL,16);
            size_t bytes=((size_t)n-5)/2;
            if(s<bytes-1) {
                memcpy(sms_pdu,packet+5,(size_t)n-5);sms_pdu[n-5]=0;
                snprintf(command,sizeof(command),"AT+CMGS=%u",(unsigned)(bytes-s-1));
                sms_stage=1;sms_deadline=monotonic()+10;sms_client=fd;
                if(sms_at(command,4)){sms_reply(2);sms_stage=0;memset(sms_pdu,0,sizeof(sms_pdu));}
                memset(packet,0,sizeof(packet));return;
            }
        }
    }
    unsigned char answer[5]={'M','S','I','1',code};
    (void)send(fd,answer,sizeof(answer),MSG_NOSIGNAL);close(fd);memset(packet,0,sizeof(packet));
}
static void sms_configure(void) {
    sms_reset();sms_stage=3;sms_deadline=monotonic()+8;
    if(sms_format_ready()){sms_configured=1;sms_stage=0;event("ims_sms_pdu_ready");}
    else if(sms_at("AT+CMGF=0",4)){sms_stage=0;event("ims_sms_configuration_failed");}
}
static void sms_close(void) {
    sms_reset();if(sms_client>=0){close(sms_client);sms_client=-1;}
    if(sms_listener>=0){close(sms_listener);sms_listener=-1;unlink(MF79U_SMS_IMS_SOCKET);}
}
