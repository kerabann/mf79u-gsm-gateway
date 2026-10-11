/* SPDX-License-Identifier: GPL-2.0-only
 * Bounded GSM 04.08 wire helpers. No identities, diagnostics, or phone numbers
 * are exposed by the metadata decoder. Extended TI is intentionally rejected.
 */
#ifndef MF79U_CS_WIRE_H
#define MF79U_CS_WIRE_H
struct cs_wire_metadata {
    unsigned int pd,ti,type,nsd,cause_present,cause,coding,location;
};
static int cs_wire_metadata(const unsigned char *p,unsigned int captured,
                           unsigned int length,struct cs_wire_metadata *out) {
    if(!p || !out || captured<2 || length<2 || captured>length)return -1;
    out->pd=p[0]&15U;out->ti=p[0]>>4;out->type=p[1]&63U;out->nsd=p[1]>>6;
    out->cause_present=out->cause=out->coding=out->location=0;
    if(out->pd!=3 || (out->ti&7U)==7U)return 0;
    /* DISCONNECT carries a mandatory Cause LV. RELEASE/RELEASE COMPLETE have
     * optional Cause TLV; accept it only when it is the first IE. Never walk
     * arbitrary IEs or read diagnostics/identity bytes. */
    unsigned int lv=2;
    if(out->type==0x2dU || out->type==0x2aU) {
        if(captured<3 || p[2]!=8U)return 0;
        lv=3;
    } else if(out->type!=0x25U)return 0;
    if(captured<=lv || p[lv]<2 || p[lv]>length-lv-1U || captured<=lv+1U)return -1;
    unsigned int value=lv+2U;
    if(!(p[lv+1U]&128U))value++;
    if(value>=lv+1U+p[lv] || value>=captured)return -1;
    /* No chaining of recommendation octets is admitted by this small reader. */
    if(value==lv+3U && !(p[lv+2U]&128U))return -1;
    out->location=p[lv+1U]&15U;out->coding=(p[lv+1U]>>5)&3U;
    out->cause=p[value]&127U;out->cause_present=1;return 0;
}
#endif
