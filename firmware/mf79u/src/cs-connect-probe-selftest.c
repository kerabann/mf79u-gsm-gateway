#include "cs-ring-state.h"
#include "cs-connect-probe.h"
#include <stdio.h>
int main(void) {
    struct cs_ring_state state={0};struct cs_ring_packet packets[2],connect;
    struct cs_connect_probe probe={0};
    if(cs_connect_probe_packet(&probe,3,5,0,&connect) || probe.attempted)return 1;
    if(cs_connect_probe_packet(&probe,0x13,5,1,&connect) || probe.attempted)return 2;
    if(cs_connect_probe_packet(&probe,3,0x25,1,&connect) || probe.attempted)return 3;
    if(cs_ring_receive(&state,3,5,packets)!=2 || packets[0].bytes[1]!=8 || packets[1].bytes[1]!=1)return 4;
    if(!cs_connect_probe_packet(&probe,3,5,1,&connect) || connect.length!=2 || connect.bytes[0]!=0x83 || connect.bytes[1]!=7)return 5;
    for(unsigned i=0;i<100;++i)if(cs_connect_probe_packet(&probe,3,5,1,&connect) || connect.length)return 6;
    if(cs_ring_receive(&state,3,0xf,packets) || state.state!=CS_RING_ALERTING)return 7;
    if(cs_ring_receive(&state,3,0x25,packets)!=1 || packets[0].bytes[1]!=0x2d)return 8;
    if(cs_ring_receive(&state,3,0x2a,packets) || state.state!=CS_RING_IDLE)return 9;
    if(!cs_ring_packet(7,&connect) || !cs_ring_packet(5,&connect))return 10;
    puts("PASS one-call CONNECT diagnostic: confirm/alert prerequisite, TI0 only, single consumed budget, no retry/redial; ordinary ring builder still forbids answer/dial");
    return 0;
}
