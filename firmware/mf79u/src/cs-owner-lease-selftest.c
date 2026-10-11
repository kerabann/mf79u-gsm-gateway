#include "cs-owner-lease.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    const unsigned long long now=1000000000000ULL;
    assert(!cs_lease_expired(now,0));
    assert(!cs_lease_expired(now,now+1200000000ULL)); /* bootstrap refresh */
    assert(!cs_lease_expired(now,now));
    assert(!cs_lease_expired(now,now-10000000000ULL));
    assert(cs_lease_expired(now,now-10000000001ULL));
    assert(cs_lease_expired(now,now-30000000000ULL));
    assert(!cs_lease_expired(18446744073709551614ULL,18446744073709551615ULL));
    puts("PASS CS lease: heartbeat during DSP bootstrap, exact timeout, real owner loss");
}
