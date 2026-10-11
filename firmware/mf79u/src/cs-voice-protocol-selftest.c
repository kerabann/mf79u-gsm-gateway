#include "cs-voice-protocol.h"
#include <stdio.h>
int main(void) {
 struct mf79u_cs_event e;
 const char *valid[]={"CS_HELLO 1","CS_READY 4294967295","CS_NOT_READY 2","CS_SUSPENDED 3",
  "CS_INCOMING 11 9 anonymous","CS_INCOMING 11 10 +123456789","CS_ALERT 11 10","CS_CONNECTED 11 10","CS_ENDED 11 10"};
 const char *bad[]={"","CS_READY","CS_READY 0","CS_READY -1","CS_READY 4294967296","CS_READY 1 x",
  "CS_CONNECTED 1","CS_CONNECTED 1 0","CS_CONNECTED 1 2 3","CS_READY 1\n",
  "CS_INCOMING 1 1 +","CS_INCOMING 1 1 12","CS_INCOMING 1 1 +123;ATH",
  "CS_INCOMING 1 1 anonymous x","CS_INCOMING 1 1 private","CS_HELLO 1 1"};
 for(unsigned i=0;i<sizeof(valid)/sizeof(valid[0]);i++)if(mf79u_cs_event_parse(valid[i],&e))return 1;
 for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++)if(!mf79u_cs_event_parse(bad[i],&e))return 2;
 if(mf79u_cs_event_parse(valid[4],&e) || e.kind!=CSV_INCOMING || e.epoch!=11 || e.id!=9 || strcmp(e.caller,"anonymous"))return 3;
 puts("PASS CS pipe ABI: epochs/IDs, anonymous/numeric identity, malformed/overflow/extra fields rejected");return 0;
}
