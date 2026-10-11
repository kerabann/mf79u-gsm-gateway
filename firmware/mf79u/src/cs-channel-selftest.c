#include "cs-channel-delta.h"
#include <stdio.h>
int main(void) {
    struct cs_channel_snapshot a={0x20400000U,12,4,16,1,0},b=a;
    unsigned int sent,received;
    b.send=4;b.recv=12;
    if(!cs_channel_delta(&a,&b,&sent,&received) || sent!=8 || received!=8)return 1;
    a=b;if(!cs_channel_delta(&a,&b,&sent,&received) || sent || received)return 2;
    b.base+=16;if(cs_channel_delta(&a,&b,&sent,&received) || sent || received)return 3;
    b=a;b.flags=0;if(cs_channel_valid(&b))return 4;
    b=a;b.send=16;if(cs_channel_valid(&b))return 5;
    b=a;b.recv=1;if(cs_channel_valid(&b))return 6;
    b=a;b.size=0x100004U;if(cs_channel_valid(&b))return 7;
    b=a;b.base=0x23fffffcU;if(cs_channel_valid(&b))return 8;
    b=a;b.base=0x8200fff0U;if(!cs_channel_valid(&b))return 9;
    b.size=20;if(cs_channel_valid(&b))return 10;
    puts("PASS channel metadata: wraparound, idle, descriptor replacement, inactive/alignment/range rejection; no payload access");
    return 0;
}
