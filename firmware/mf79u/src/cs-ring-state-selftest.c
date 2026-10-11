#include "cs-ring-state.h"
#include <stdio.h>
#include <string.h>
#define CHECK(x) do {if(!(x)){printf("CS_RING_TEST failed line=%u\n",(unsigned int)__LINE__);return 1;}}while(0)
int main(void) {
    struct cs_ring_state state={0};struct cs_ring_packet packets[2];
    /* Exact wire fixtures: TS24.008 CC types, inverse TI flag, cause16. */
    const unsigned char confirmed[]={0x83,0x08},alerting[]={0x83,0x01};
    const unsigned char release[]={0x83,0x2d,0x08,0x02,0xe0,0x90};
    CHECK(cs_ring_receive(&state,3,5,packets)==2);
    CHECK(packets[0].length==2 && !memcmp(packets[0].bytes,confirmed,2));
    CHECK(packets[1].length==2 && !memcmp(packets[1].bytes,alerting,2));
    CHECK(state.state==CS_RING_ALERTING);
    CHECK(cs_ring_receive(&state,3,5,packets)==2); /* retransmission */
    CHECK(cs_ring_receive(&state,0x13,5,packets)==0); /* unknown native TI */
    CHECK(state.state==CS_RING_ALERTING);
    CHECK(cs_ring_receive(&state,3,0x25,packets)==1);
    CHECK(packets[0].length==6 && !memcmp(packets[0].bytes,release,6));
    CHECK(state.state==CS_RING_RELEASING);
    CHECK(cs_ring_receive(&state,3,5,packets)==0);
    CHECK(cs_ring_receive(&state,3,0x2d,packets)==1);
    CHECK(state.state==CS_RING_IDLE && packets[0].bytes[1]==0x2a);
    CHECK(cs_ring_receive(&state,3,0x25,packets)==0);
    CHECK(cs_ring_receive(&state,3,0x2a,packets)==0);
    /* Exhaustively assert the packet builder has no answer/dial message path. */
    for(unsigned int type=0;type<256;++type) {
        int allowed=type==1 || type==8 || type==0x2a || type==0x2d;
        CHECK((cs_ring_packet(type,&packets[0])==0)==allowed);
        CHECK(allowed || packets[0].length==0);
    }
    puts("CS_RING_TEST PASS: TI0 MT transitions, exact wire fixtures, no CONNECT/SETUP output");return 0;
}
