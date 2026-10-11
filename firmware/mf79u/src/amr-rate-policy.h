/* One-call, fail-closed AMR-NB/WB CMR policy. Caller serializes access.
 * SDP and peer addresses exist only in RAM. No SIP bodies or audio logging. */
#ifndef MF79U_AMR_RATE_POLICY_H
#define MF79U_AMR_RATE_POLICY_H
#include <stddef.h>
#include <stdint.h>
struct mf79u_amr_codec {
    unsigned char listed, mapped, invalid, mode_set, align, fmtp, map_seen;
    uint16_t modes; /* mapped: 1=NB, 2=WB; allowed modes 0..7 / 0..8 */
    unsigned rtp_clock;
};
struct mf79u_amr_sdp {
    struct mf79u_amr_codec codec[128];
    uint32_t address;
    unsigned port, valid;
};
struct mf79u_amr_policy {
    struct mf79u_amr_sdp leg[2]; /* RX remote, TX local */
    char call_id[256];
    unsigned cseq, offer_side, have_offer, active, enabled;
    unsigned long eligible, changed;
};
void mf79u_amr_observe(struct mf79u_amr_policy *,int tx,const void *,size_t,int logfd);
/* Validate the full datagram before copying; return 1 only if CMR changed. */
int mf79u_amr_rewrite(struct mf79u_amr_policy *,unsigned local_port,uint32_t peer_ip,
                     unsigned peer_port,const void *,size_t,void *copy,size_t capacity);
/* Select only offered, supported profiles. Rebuild Content-Length; no headers
 * or identities are logged. Return zero to leave an unrecognized offer intact.
 * preferred: 0=WB/G722/NB, 1=G722 first, 2=NB first (diagnostic overrides). */
size_t mf79u_codec_offer(const void *,size_t,void *,size_t,unsigned preferred);
#endif
