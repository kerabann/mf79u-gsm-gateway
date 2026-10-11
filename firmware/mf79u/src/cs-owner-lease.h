/* Worker timestamps may precede a heartbeat updated during DSP bootstrap. */
#ifndef MF79U_CS_OWNER_LEASE_H
#define MF79U_CS_OWNER_LEASE_H
static inline int cs_lease_expired(unsigned long long now,unsigned long long heartbeat){
    return heartbeat && now>=heartbeat && now-heartbeat>10000000000ULL;
}
#endif
