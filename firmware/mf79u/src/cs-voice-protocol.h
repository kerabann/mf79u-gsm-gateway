/* Private pipe ABI for the owned CS adapter. Epoch/call ID suppress stale
 * notifications; identities stay in RAM and are never diagnostic log text. */
#ifndef MF79U_CS_VOICE_PROTOCOL_H
#define MF79U_CS_VOICE_PROTOCOL_H
#include <stdint.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
enum mf79u_cs_event_kind { CSV_HELLO=1,CSV_READY,CSV_NOT_READY,CSV_SUSPENDED,
    CSV_INCOMING,CSV_ALERT,CSV_CONNECTED,CSV_ENDED };
struct mf79u_cs_event {enum mf79u_cs_event_kind kind;uint32_t epoch,id;char caller[34];};
static int mf79u_cs_event_parse(const char *line,struct mf79u_cs_event *out) {
    static const char *names[]={"CS_HELLO","CS_READY","CS_NOT_READY","CS_SUSPENDED",
        "CS_INCOMING","CS_ALERT","CS_CONNECTED","CS_ENDED"};
    if(!line || !out || strlen(line)>127)return -1;
    struct mf79u_cs_event e={0};const char *p=NULL;
    for(unsigned i=0;i<8;i++) {
        size_t n=strlen(names[i]);
        if(!strncmp(line,names[i],n) && line[n]==' '){e.kind=(enum mf79u_cs_event_kind)(i+1);p=line+n+1;break;}
    }
    if(!p)return -1;
    unsigned fields=e.kind>=CSV_INCOMING?2:1;
    for(unsigned i=0;i<fields;i++) {
        if(*p<'0' || *p>'9')return -1;
        char *end;errno=0;unsigned long n=strtoul(p,&end,10);
        if(errno || !n || n>UINT32_MAX || end-p>10)return -1;
        if(i==0)e.epoch=(uint32_t)n;else e.id=(uint32_t)n;
        p=end;
        if(i+1<fields){if(*p++!=' ')return -1;}
    }
    if(e.kind==CSV_INCOMING) {
        if(*p++!=' ')return -1;
        size_t n=strlen(p);if(!n || n>=sizeof(e.caller))return -1;
        if(strcmp(p,"anonymous")) {
            const char *q=p;if(*q=='+')q++;
            if(strlen(q)<3 || strlen(q)>32)return -1;
            for(;*q;q++)if(*q<'0' || *q>'9')return -1;
        }
        memcpy(e.caller,p,n+1);p+=n;
    }
    if(*p)return -1;
    *out=e;return 0;
}
#endif
