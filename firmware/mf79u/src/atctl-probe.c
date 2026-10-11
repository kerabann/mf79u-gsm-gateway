/* Read-only FD2_VOLTE -> stock AT_CTL probe. Owns a newly created VOLTE queue. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/msg.h>
#include <unistd.h>
struct message {
    int32_t type,dst,src;
    uint16_t cmd,len;
    uint32_t magic;
    unsigned char payload[4096];
};
_Static_assert(sizeof(long)==4,"ARM32 required");
int main(int argc,char **argv) {
    if (argc!=2 || (strcmp(argv[1],"AT^CARDMODE") && strcmp(argv[1],"AT+ZPDPACT=?") &&
                     strcmp(argv[1],"AT+CFUN?"))) return 2;
    int rx=msgget(0x101e,IPC_CREAT|IPC_EXCL|0600);
    if (rx<0) { perror("create own VOLTE reply queue"); return 1; }
    int tx=msgget(0x100f,0600),result=1;
    if (tx<0) { perror("stock AT_CTL queue"); goto done; }
    struct message m={.type=1,.dst=0x100f,.src=0x101e,.cmd=0x150c,.len=3496,.magic=0x3a3a3a3a};
    uint32_t length=(uint32_t)strlen(argv[1])+1,port=1;
    memcpy(m.payload,argv[1],length-1);m.payload[length-1]='\r';
    memcpy(m.payload+3488,&length,4);memcpy(m.payload+3492,&port,4);
    if (msgsnd(tx,&m,16+3496,IPC_NOWAIT)) { perror("send stock query");goto done; }
    printf("SENT stock AT_CTL query=%s\n",argv[1]);fflush(stdout);
    for (int i=0;i<200;++i) {
        ssize_t n=msgrcv(rx,&m,sizeof(m)-4,0,IPC_NOWAIT);
        if (n>=0) {
            uint32_t count=m.len;
            if (n<16 || count>(uint32_t)n-16) { puts("malformed reply");goto done; }
            if (count==3496) {
                memcpy(&count,m.payload+3488,4);
                memcpy(&port,m.payload+3492,4);
                if (count>3488) { puts("malformed AT length");goto done; }
            }
            printf("RESPONSE cmd=0x%04x length=%u port=%u text=",m.cmd,count,port);
            for (unsigned j=0;j<count;++j) {
                unsigned c=m.payload[j];
                if (c>=32 && c<=126) putchar(c);else printf("\\x%02x",c);
            }
            putchar('\n'); result=0; break;
        }
        if (errno!=ENOMSG) { perror("receive"); goto done; }
        usleep(50000);
    }
    if (result) puts("NO_RESPONSE within 10 seconds");
done:
    if (msgctl(rx,IPC_RMID,NULL)) { perror("remove own reply queue");return 1; }
    return result;
}
