/* Native AT_CTL client, using an exclusive application queue. Never opens rpm
 * devices or consumes another application's queue. No commands/responses logged.
 * ABI verified against B03 libatutils.so (send_app_req 0x1948, wait 0x1a9c)
 * and zte_mifi request handlers 0xf99a / 0xfa44, plus the MF79U SDK sources. */
#include "cp-ipc.h"
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <sys/msg.h>
#include <time.h>
#include <unistd.h>

struct message {
    int32_t type, dst, src;
    uint16_t cmd, len;
    uint32_t magic;
    unsigned char payload[3496];
};
_Static_assert(sizeof(long) == 4, "B03 IPC requires ARM32 long");
_Static_assert(sizeof(struct message) == 3516, "B03 IPC layout");

int mf79u_cp_open(struct mf79u_cp *cp) {
    cp->tx = cp->rx = -1;
    cp->key = 0;
    cp->reply_cmd = 0;
    cp->reply_src = 0;
    cp->request_cmd = 0x152d;
    cp->pdp_received=0;memset(cp->pdp,0,sizeof(cp->pdp));
    cp->tx = msgget(0x100f, 0600);
    if (cp->tx < 0) return -1;
    /* Same application range as the vendor's synchronous AT client. */
    for (int32_t key = 0x1132; key < 0x1233; ++key) {
        cp->rx = msgget(key, IPC_CREAT | IPC_EXCL | 0600);
        if (cp->rx >= 0) { cp->key = key; return 0; }
        if (errno != EEXIST) return -1;
    }
    errno = EBUSY;
    return -1;
}

int mf79u_cp_open_direct(struct mf79u_cp *cp) {
    int result=mf79u_cp_open(cp);
    /* B03 libatutils send_app_req's fifth argument selects 0x152d for 1,
     * 0x152e otherwise. zte_mifi fa44 creates a type-1 application channel.
     * No RPM descriptors or queues belonging to other clients are opened. */
    if(!result)cp->request_cmd=0x152e;
    return result;
}

void mf79u_cp_close(struct mf79u_cp *cp) {
    if (cp->rx >= 0) msgctl(cp->rx, IPC_RMID, NULL);
    cp->rx = cp->tx = -1;
    cp->key = 0;
}

static int terminal(const char *text) {
    return strstr(text, "\r\nOK\r\n") || strstr(text, "\r\nERROR\r\n") ||
           strstr(text, "\r\n+CME ERROR:") || strstr(text, "\r\n+CMS ERROR:");
}

int mf79u_cp_query(struct mf79u_cp *cp, const char *command,
                  char *reply, size_t capacity, unsigned timeout_seconds) {
    size_t length = strlen(command);
    if (cp->rx < 0 || !length || length >= MF79U_AT_BYTES - 1 ||
        capacity < 2 || timeout_seconds < 1 || timeout_seconds > 30 ||
        strpbrk(command, "\r\n")) { errno = EINVAL; return -1; }
    struct message m = {.type=1, .dst=0x100f, .src=cp->key,
                        .cmd=cp->request_cmd?cp->request_cmd:0x152d, .len=3496, .magic=0x3a3a3a3a};
    uint32_t wire_length = (uint32_t)length + 1, timeout = timeout_seconds;
    memcpy(m.payload, command, length);
    m.payload[length] = '\r';
    memcpy(m.payload + 3488, &wire_length, 4);
    memcpy(m.payload + 3492, &timeout, 4);
    if (msgsnd(cp->tx, &m, sizeof(m)-4, IPC_NOWAIT)) return -1;
    struct timespec now, started;
    clock_gettime(CLOCK_MONOTONIC, &started);
    size_t used = 0;
    cp->reply_cmd = 0;
    cp->reply_src = 0;
    cp->pdp_received=0;memset(cp->pdp,0,sizeof(cp->pdp));
    reply[0] = 0;
    for (;;) {
        ssize_t n = msgrcv(cp->rx, &m, sizeof(m)-4, 0, IPC_NOWAIT);
        if (n >= 0) {
            cp->reply_cmd = m.cmd;
            cp->reply_src = m.src;
            if (n < 16 || m.magic != 0x3a3a3a3a || m.src != 0x100f ||
                m.dst != cp->key || m.len > (unsigned)n-16 ||
                m.len > sizeof(m.payload)) { errno = EPROTO; return -1; }
            /* B03 0x22444/0x225ea sends a typed PDP completion instead of
             * 0x152f: result, cid, error. The error word is uninitialised on
             * success. Accept only our exact IMS activation and CID 5. */
            if (m.cmd != 0x152f) {
                if(m.cmd==0x159b && m.len==12 && !strcmp(command,"AT+ZPDPACT=0,\"IPV4V6\",\"ims\",0,1,1")) {
                    memcpy(cp->pdp,m.payload,12);cp->pdp_received=1;
                    if(cp->pdp[0]!=0 && cp->pdp[0]!=1){errno=EPROTO;return -1;}
                    if(!cp->pdp[0] && cp->pdp[1]!=5){errno=EPROTO;return -1;}
                    const char *result=cp->pdp[0]?"\r\nERROR\r\n":"\r\nOK\r\n";
                    size_t size=strlen(result);
                    if(size>=capacity){errno=EMSGSIZE;return -1;}
                    memcpy(reply,result,size+1);return (int)size;
                }
                goto deadline;
            }
            if (m.len > MF79U_AT_BYTES) { errno = EPROTO; return -1; }
            /* Vendor replies carry plain text, not app_send_req_at. */
            size_t count = m.len;
            while (count && m.payload[count-1] == 0) --count;
            if (count >= capacity-used) { errno = EMSGSIZE; return -1; }
            memcpy(reply+used, m.payload, count);
            used += count;
            reply[used] = 0;
            if (terminal(reply)) return (int)used;
        } else if (errno != ENOMSG && errno != EINTR) return -1;
deadline:
        clock_gettime(CLOCK_MONOTONIC, &now);
        if (now.tv_sec-started.tv_sec > (long)timeout_seconds+1) {
            errno = ETIMEDOUT; return -1;
        }
        usleep(20000);
    }
}
