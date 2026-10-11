/* Backend admission and call ownership. Transport/media remain separate.
 * CS readiness requires registration, signaling AND verified bidirectional
 * media. A registration or ring-only prototype cannot admit a CS SIP call. */
#ifndef MF79U_VOICE_BACKEND_POLICY_H
#define MF79U_VOICE_BACKEND_POLICY_H
enum mf79u_voice_backend { MF79U_VOICE_NONE,MF79U_VOICE_IMS,MF79U_VOICE_CS };
struct mf79u_voice_inputs { int enabled,cs_only,ims_ready,cs_registered,cs_signaling,cs_audio; };
struct mf79u_voice_policy {
    enum mf79u_voice_backend selected,owner;
    int end_call,ims_candidate;
    unsigned long ims_since;
};
static const char *mf79u_voice_name(enum mf79u_voice_backend backend) {
    return backend==MF79U_VOICE_IMS?"ims":backend==MF79U_VOICE_CS?"cs":"none";
}
static int mf79u_voice_usable(enum mf79u_voice_backend backend,const struct mf79u_voice_inputs *in) {
    if(!in->enabled)return 0;
    if(backend==MF79U_VOICE_IMS)return !in->cs_only && in->ims_ready;
    if(backend==MF79U_VOICE_CS)return in->cs_registered && in->cs_signaling && in->cs_audio;
    return 0;
}
static void mf79u_voice_reconcile(struct mf79u_voice_policy *p,const struct mf79u_voice_inputs *in,
                                  unsigned long seconds) {
    int ims=mf79u_voice_usable(MF79U_VOICE_IMS,in),cs=mf79u_voice_usable(MF79U_VOICE_CS,in);
    if(!ims)p->ims_candidate=0;
    else if(!p->ims_candidate){p->ims_candidate=1;p->ims_since=seconds;}
    /* Until the caller acknowledges clearing, a failed call retains ownership.
     * Never migrate a dialog or replay DIAL on a different cellular backend. */
    if(p->owner!=MF79U_VOICE_NONE) {
        p->selected=p->owner;
        p->end_call|=!mf79u_voice_usable(p->owner,in);
        return;
    }
    p->end_call=0;
    if(!in->enabled){p->selected=MF79U_VOICE_NONE;return;}
    /* Promotion back from CS needs five uninterrupted idle-ready seconds.
     * First startup on IMS retains its existing immediate admission behavior. */
    if(ims && (p->selected!=MF79U_VOICE_CS || !cs ||
               (seconds>=p->ims_since && seconds-p->ims_since>=5U)))p->selected=MF79U_VOICE_IMS;
    else p->selected=cs?MF79U_VOICE_CS:MF79U_VOICE_NONE;
}
static int mf79u_voice_admit(struct mf79u_voice_policy *p,enum mf79u_voice_backend backend) {
    if(backend==MF79U_VOICE_NONE || p->selected!=backend || p->owner!=MF79U_VOICE_NONE || p->end_call)return 0;
    p->owner=backend;return 1;
}
static void mf79u_voice_ended(struct mf79u_voice_policy *p) {p->owner=MF79U_VOICE_NONE;p->end_call=0;}
static int mf79u_voice_event_current(const struct mf79u_voice_policy *p,enum mf79u_voice_backend backend) {
    return p->owner==backend && backend!=MF79U_VOICE_NONE && !p->end_call;
}
#endif
