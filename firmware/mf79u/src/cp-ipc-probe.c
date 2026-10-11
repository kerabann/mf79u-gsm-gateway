/* Read-only proof of the local CP path. No USB AT client, no SIM identifiers. */
#include "cp-ipc.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    int direct=argc==3 && !strcmp(argv[1],"--direct");
    if(direct){argv++;argc--;}
    if (argc != 2 || (strcmp(argv[1], "AT+CFUN?") && strcmp(argv[1],"AT+CEREG?") &&
                     strcmp(argv[1],"AT^SYSINFO") && strcmp(argv[1],"AT+CIREP?") && strcmp(argv[1],"AT+CGCONTRDP=5"))) {
        fputs("Only read-only CFUN/CEREG/SYSINFO/CIREP probes are supported\n", stderr);
        return 2;
    }
    struct mf79u_cp cp;
    if (direct?mf79u_cp_open_direct(&cp):mf79u_cp_open(&cp)) { perror("CP application queue"); return 1; }
    char reply[4096];
    int n = mf79u_cp_query(&cp, argv[1], reply, sizeof(reply), 5);
    int result = 1, state = -1;
    if (n < 0) fprintf(stderr,"Local CP query failed: errno=%d reply_cmd=0x%04x\n",errno,cp.reply_cmd);
    else {
        const char *prefix=!strcmp(argv[1],"AT+CFUN?")?"+CFUN:":
            !strcmp(argv[1],"AT+CEREG?")?"+CEREG:":!strcmp(argv[1],"AT^SYSINFO")?"^SYSINFO:":!strcmp(argv[1],"AT+CGCONTRDP=5")?"+CGCONTRDP:":"+CIREP:";
        const char *p = strstr(reply,prefix);
        if(p && !strcmp(argv[1],"AT+CGCONTRDP=5")) {
            const char *start=p+strlen(prefix);int field=0;
            while(*start && *start!='\r' && *start!='\n') {
                const char *end=start+strcspn(start,",\r\n");int dots=0,colons=0,quotes=0;
                for(const char *q=start;q<end;q++){dots+=*q=='.';colons+=*q==':';quotes+=*q=='"';}
                printf("BEARER_FIELD index=%d length=%u dots=%d colons=%d quotes=%d\n",field++,(unsigned)(end-start),dots,colons,quotes);
                start=*end==','?end+1:end;
            }
        }
        if (p && sscanf(p+strlen(prefix), " %d", &state) == 1 && strstr(reply, "\r\nOK\r\n")) {
            printf("LOCAL_CP_OK command=%s first_integer=%d response_bytes=%d ims_apn=%d\n",argv[1],state,n,strstr(reply,"\"ims\"")!=NULL);
            result = 0;
        } else fprintf(stderr, "Local CP reply missing expected field; command=%s bytes=%d ok=%d error=%d\n",
                       argv[1],n,strstr(reply,"\r\nOK\r\n")!=NULL,strstr(reply,"ERROR")!=NULL);
    }
    mf79u_cp_close(&cp);
    return result;
}
