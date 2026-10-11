#include "cs-status.h"
#include <assert.h>
int main(int argc,char **argv) {
    struct mf79u_cs_status status={0};
    if(argc==2 && !strcmp(argv[1],"--snapshot")) {
        if(mf79u_cs_status_read(&status))return 1;
        printf("CS_STATUS armed=%u state=%s events=%u sent=%u errors=%u audio_ready=0 answer_forbidden=1\n",
            status.armed,mf79u_cs_state_name(status.state),status.events,status.sent,status.errors);
        return 0;
    }
    if(argc!=1)return 2;
    assert(!mf79u_cs_status_parse("MF79U_CS 1 1 1 7 2 0 1\n",&status));
    assert(status.armed==1 && status.state==1 && status.events==7 && status.sent==2);
    assert(!strcmp(mf79u_cs_state_name(status.state),"alerting"));
    assert(!mf79u_cs_status_parse("MF79U_CS 1 1 2 9 3 0 1\n",&status));
    assert(!strcmp(mf79u_cs_state_name(status.state),"releasing"));
    assert(!mf79u_cs_status_parse("MF79U_CS 1 0 0 4294967295 3 0 1\n",&status));
    const char *invalid[]={"", "MF79U_CS 2 1 0 0 0 0 1\n", "MF79U_CS 1 2 0 0 0 0 1\n",
        "MF79U_CS 1 1 3 0 0 0 1\n", "MF79U_CS 1 0 1 0 0 0 1\n", "MF79U_CS 1 1 1 0 0 0 0\n",
        "MF79U_CS 1 1 -1 0 0 0 1\n", "MF79U_CS 1 1 0 4294967296 0 0 1\n",
        "MF79U_CS 1 1 0 0 0 0 1", "MF79U_CS 1 1 0 0 0 0 1\nEXTRA", "MF79U_CS 1 1 0 0 0 0 1 \n"};
    for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++)assert(mf79u_cs_status_parse(invalid[i],&status));
    puts("PASS CS status ABI: alerting/clearing, unsigned limits, malformed and unsafe snapshots rejected");
    return 0;
}
