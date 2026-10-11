/* Isolated native AT parser probe. A single explicitly enabled test dial has
 * one fixed authorized destination and an automatic native hangup watchdog. */
#include <errno.h>
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/msg.h>
#include <sys/select.h>
#include <time.h>
#include <unistd.h>
#include "net-led-policy.h"

struct message {
    int32_t type, dst, src;
    uint16_t cmd, len;
    uint32_t magic;
    unsigned char payload[3496];
};
_Static_assert(sizeof(long) == 4, "ARM32 IPC required");
_Static_assert(sizeof(struct message) == 3516, "native message layout");

static int allowed(const char *s,int test_call) {
    if(test_call==2 && !strcmp(s,"ATA"))return 1;
    if(test_call && (!strcmp(s,"ATDTEST_DESTINATION_E164;") || !strcmp(s,"ATDTEST_DESTINATION_LOCAL;") || !strcmp(s,"ATH") || !strcmp(s,"AT+CHUP")))return 1;
    const char *commands[] = {"AT+CLCC", "AT+CLCC=?", "AT+CVMOD?", "AT+CHLD=?",
        "AT+CVMOD=?", "AT+CVMOD=3", "AT+CVMOD=0", "AT+AUTOSTART=1",
        "AT+ZIMSAPN?", "AT+ZIMSAMRW?", "AT+ZIMSAMRW=0", "AT+ZIMSAMRW=1", "AT+CFUN=1", "AT+ZIMSAPN=\"ims\"",
        "AT+ZIMSTEST=\"NET_IMS_CAP\"", "AT+ZIMSTEST=\"NET_IMS_CAP\",1",
        "AT+ZIMSTEST=\"NET_IMS_CAP\",0"};
    for (unsigned i=0; i<sizeof(commands)/sizeof(commands[0]); ++i)
        if (!strcmp(s, commands[i])) return 1;
    return 0;
}
static int send_query(int request, const char *s) {
    struct message m = {.type=1, .dst=0x701e, .src=0x700f,
                        .cmd=0x1509, .len=3496, .magic=0x3a3a3a3a};
    uint32_t length=(uint32_t)strlen(s)+1, port=1;
    memcpy(m.payload, s, length-1); m.payload[length-1]='\r';
    memcpy(m.payload+3488, &length, 4); memcpy(m.payload+3492, &port, 4);
    return msgsnd(request, &m, sizeof(m)-sizeof(m.type), IPC_NOWAIT);
}
static int send_status(int request, const char *hex) {
    struct message m={.type=1,.dst=0x701e,.src=0x700f,
                      .cmd=0x150b,.len=3496,.magic=0x3a3a3a3a};
    size_t size=strlen(hex);
    if (size%2 || size>1024) return -1;
    uint32_t len=(uint32_t)size/2,port=1;
    for (unsigned i=0;i<len;++i) {
        unsigned value;
        if (sscanf(hex+i*2,"%2x",&value)!=1) return -1;
        m.payload[i]=(unsigned char)value;
    }
    if (strncmp((char*)m.payload,"\r\n+CEREG: ",10) &&
        strncmp((char*)m.payload,"\r\n+CREG: ",9) &&
        strncmp((char*)m.payload,"\r\n^MODE: ",9) &&
        strncmp((char*)m.payload,"\r\n+CIREPI: ",11)) return -1;
    memcpy(m.payload+3488,&len,4);memcpy(m.payload+3492,&port,4);
    return msgsnd(request,&m,sizeof(m)-4,IPC_NOWAIT);
}
static int send_reply(int request, const char *line) {
    unsigned port; int used=0;
    if (sscanf(line,"%u %n",&port,&used)!=1 || port<1 || port>4) return -1;
    const char *hex=line+used;
    size_t size=strlen(hex);
    if (size%2 || size>6976) return -1;
    for (size_t i=0;i<size;++i) if (!isxdigit((unsigned char)hex[i])) return -1;
    struct message m={.type=1,.dst=0x701e,.src=0x700f,
                      .cmd=0x150b,.len=3496,.magic=0x3a3a3a3a};
    uint32_t len=(uint32_t)size/2;
    for (unsigned i=0;i<len;++i) {
        unsigned value;
        if (sscanf(hex+i*2,"%2x",&value)!=1) return -1;
        m.payload[i]=(unsigned char)value;
    }
    memcpy(m.payload+3488,&len,4);memcpy(m.payload+3492,&port,4);
    return msgsnd(request,&m,sizeof(m)-4,IPC_NOWAIT);
}
static void hangup(int request){
    send_query(request,"ATH");send_query(request,"AT+CHUP");puts("SENT automatic test-call hangup");
}
static int session(int request, int response,int test_call) {
    char line[8192];
    int dial_used=0,active=0;struct timespec started={0};
    setvbuf(stdout, NULL, _IONBF, 0);
    puts("READY private IPC session; no automatic forwarding to CP");
    for (int ticks=0; test_call==2 || ticks<7200; ++ticks) {
        struct timespec now;clock_gettime(CLOCK_MONOTONIC,&now);
        if(active && now.tv_sec-started.tv_sec>=(test_call==2?300:30)){hangup(request);active=0;}
        fd_set fds; FD_ZERO(&fds); FD_SET(STDIN_FILENO, &fds);
        struct timeval timeout={.tv_sec=0, .tv_usec=50000};
        if (select(1, &fds, NULL, NULL, &timeout)>0) {
            if (!fgets(line, sizeof(line), stdin)) {if(active)hangup(request);return 0;}
            line[strcspn(line, "\r\n")]=0;
            if (!strcmp(line, "QUIT")) {if(active)hangup(request);return 0;}
            if (!strncmp(line,"REPLY ",6)) {
                if (send_reply(request,line+6)) puts("REJECT invalid reply");
                else puts("SENT CP reply to private IMS");
                continue;
            }
            if (!strncmp(line,"STATUS ",7)) {
                if (send_status(request,line+7)) puts("REJECT invalid status");
                else puts("SENT CP registration status to private IMS");
                continue;
            }
            if (!allowed(line,test_call)) { puts("REJECT unlisted command"); continue; }
            int dial=!strcmp(line,"ATDTEST_DESTINATION_E164;") || !strcmp(line,"ATDTEST_DESTINATION_LOCAL;");
            if(dial && dial_used && test_call!=2){puts("REJECT second test dial");continue;}
            if (send_query(request, line)) { perror("send"); return 1; }
            if(dial){dial_used=1;active=1;clock_gettime(CLOCK_MONOTONIC,&started);}
            if(test_call==2 && !strcmp(line,"ATA")){active=1;clock_gettime(CLOCK_MONOTONIC,&started);}
            if(!strcmp(line,"ATH") || !strcmp(line,"AT+CHUP"))active=0;
            printf("SENT %s\n", line);
        }
        struct message m;
        ssize_t n;
        while ((n=msgrcv(response,&m,sizeof(m)-4,0,IPC_NOWAIT))>=0) {
            if (n<3512) { puts("ERROR short message"); return 1; }
            uint32_t len,port;
            memcpy(&len,m.payload+3488,4); memcpy(&port,m.payload+3492,4);
            if (len>3488) { puts("ERROR invalid length"); return 1; }
            if(m.cmd==0x150a){
                mf79u_led_notify(m.payload,len);
                if(test_call==2 && len<3488){m.payload[len]=0;if(strstr((char*)m.payload,"^CEND:"))active=0;}
            }
            printf("MESSAGE cmd=0x%04x port=%u hex=",m.cmd,port);
            for (uint32_t j=0;j<len;++j) printf("%02x",m.payload[j]);
            putchar('\n');
        }
        if (errno!=ENOMSG) { perror("receive"); return 1; }
    }
    if(active)hangup(request);
    puts("Session timeout after 360 seconds"); return 0;
}
int main(int argc, char **argv) {
    int test_call=argc==3 && !strcmp(argv[1],"--session") && !strcmp(argv[2],"--allow-test-call");
    if(argc==3 && !strcmp(argv[1],"--session") && !strcmp(argv[2],"--gateway"))test_call=2;
    int interactive=(argc==2 || test_call) && !strcmp(argv[1],"--session");
    if ((!interactive && (argc!=2 || !allowed(argv[1],0)))) {
        fprintf(stderr, "Only constrained native commands are allowed\n");
        return 2;
    }
    int response = msgget(0x700f, IPC_CREAT | IPC_EXCL | 0600);
    if (response < 0) { perror("create private response queue"); return 1; }
    int request = msgget(0x701e, 0600);
    int result = 1;
    if (request < 0) { perror("private daemon queue"); goto done; }
    if (interactive) { result=session(request,response,test_call); goto done; }
    struct message m = {.type=1, .dst=0x701e, .src=0x700f,
                        .cmd=0x1509, .len=3496, .magic=0x3a3a3a3a};
    uint32_t length = (uint32_t)strlen(argv[1]) + 1, port = 1;
    memcpy(m.payload, argv[1], length - 1);
    m.payload[length - 1] = '\r';
    memcpy(m.payload + 3488, &length, 4);
    memcpy(m.payload + 3492, &port, 4);
    if (msgsnd(request, &m, sizeof(m) - sizeof(m.type), IPC_NOWAIT)) {
        perror("send"); goto done;
    }
    printf("request=%s private_queue=0x701e\n", argv[1]);
    for (int i=0; i<100; ++i) {
        ssize_t n = msgrcv(response, &m, sizeof(m)-sizeof(m.type), 0, IPC_NOWAIT);
        if (n >= 0) {
            uint32_t size=0;
            if (n < (ssize_t)(sizeof(m)-sizeof(m.type))) {
                fprintf(stderr, "short native message: %zd\n", n); goto done;
            }
            memcpy(&size, m.payload+3488, 4);
            if (size > 3488) { fprintf(stderr, "invalid payload length\n"); goto done; }
            printf("cmd=0x%04x source=0x%x length=%u text=", m.cmd, m.src, size);
            for (uint32_t j=0; j<size; ++j) {
                unsigned c = m.payload[j];
                if (c >= 32 && c <= 126) putchar(c);
                else printf("\\x%02x", c);
            }
            putchar('\n');
            result=0;
            break;
        }
        if (errno != ENOMSG) { perror("receive"); goto done; }
        usleep(50000);
    }
    if (result) fprintf(stderr, "No private response within 5 seconds\n");
done:
    if (msgctl(response, IPC_RMID, NULL)) { perror("remove own queue"); return 1; }
    return result;
}
