/* SPDX-License-Identifier: GPL-2.0-only
 * Separately built, explicitly authorized one-call diagnostic. Not the voice
 * backend. It emits a single MT CONNECT after successful confirm+alert; no MO
 * setup/dial, number handling, SIP forwarding or audio activation is present.
 */
#ifndef MF79U_CS_CONNECT_PROBE_H
#define MF79U_CS_CONNECT_PROBE_H
struct cs_connect_probe { unsigned int attempted; };
static int cs_connect_probe_packet(struct cs_connect_probe *probe,unsigned int header,
                                    unsigned int type,int confirmed,
                                    struct cs_ring_packet *packet) {
    packet->length=0;
    if(probe->attempted || header!=3U || type!=5U || !confirmed)return 0;
    /* Consume the budget before enqueue; a failed enqueue must never cause an
     * automatic second answer on a retransmission or another call. */
    probe->attempted=1;
    packet->length=2;packet->bytes[0]=0x83;packet->bytes[1]=0x07;
    return 1;
}
#endif
