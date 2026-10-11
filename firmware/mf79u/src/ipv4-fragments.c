#include "ipv4-fragments.h"
#include <errno.h>
#include <string.h>
static void put16(unsigned char *p,unsigned value){p[0]=value>>8;p[1]=value;}
int ipv4_emit_fragments(const unsigned char *packet,size_t size,unsigned mtu,
                        uint16_t id,ipv4_emit_fn emit,void *context){
    if(!packet || !emit || !id || size<=20 || size>8192 || packet[0]!=0x45 ||
       packet[6] || packet[7] || mtu<28 || mtu>65535){errno=EINVAL;return -1;}
    size_t chunk=(mtu-20)&~7u,offset=0,payload=size-20;
    unsigned char fragment[mtu<size?mtu:size];int count=0;
    while(offset<payload){size_t part=payload-offset;if(part>mtu-20)part=chunk;
        memcpy(fragment,packet,20);memcpy(fragment+20,packet+20+offset,part);
        put16(fragment+2,(unsigned)part+20);put16(fragment+4,id);
        put16(fragment+6,(unsigned)(offset/8)|(offset+part<payload?0x2000:0));
        put16(fragment+10,0);unsigned sum=0;
        for(unsigned i=0;i<20;i+=2)sum+=(unsigned)fragment[i]<<8|fragment[i+1];
        while(sum>>16)sum=(sum&65535)+(sum>>16);
        put16(fragment+10,(uint16_t)~sum);
        if(emit(context,fragment,part+20))return -1;
        offset+=part;count++;
    }
    return count;
}
