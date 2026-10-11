#include "voice-backend-policy.h"
#include <stdio.h>
#include <string.h>
#define CHECK(expr) do{if(!(expr)){fprintf(stderr,"voice policy failure line %u\n",__LINE__);return 1;}}while(0)
int main(void) {
    struct mf79u_voice_policy p={0};
    struct mf79u_voice_inputs in={1,0,0,1,1,0};
    mf79u_voice_reconcile(&p,&in,0);CHECK(p.selected==MF79U_VOICE_NONE); /* Ringing alone is insufficient. */
    CHECK(!mf79u_voice_admit(&p,MF79U_VOICE_CS));
    in.cs_audio=1;mf79u_voice_reconcile(&p,&in,1);CHECK(p.selected==MF79U_VOICE_CS);
    CHECK(mf79u_voice_admit(&p,MF79U_VOICE_CS));CHECK(!mf79u_voice_admit(&p,MF79U_VOICE_CS));
    in.ims_ready=1;mf79u_voice_reconcile(&p,&in,2);
    mf79u_voice_reconcile(&p,&in,30);CHECK(p.selected==MF79U_VOICE_CS && !p.end_call);
    CHECK(mf79u_voice_event_current(&p,MF79U_VOICE_CS));CHECK(!mf79u_voice_event_current(&p,MF79U_VOICE_IMS));
    mf79u_voice_ended(&p);mf79u_voice_reconcile(&p,&in,31);CHECK(p.selected==MF79U_VOICE_IMS);
    CHECK(mf79u_voice_admit(&p,MF79U_VOICE_IMS));in.ims_ready=0;
    mf79u_voice_reconcile(&p,&in,32);CHECK(p.end_call && p.owner==MF79U_VOICE_IMS);
    CHECK(!mf79u_voice_admit(&p,MF79U_VOICE_CS));CHECK(!mf79u_voice_event_current(&p,MF79U_VOICE_IMS));
    in.ims_ready=1;mf79u_voice_reconcile(&p,&in,33);CHECK(p.end_call); /* Failure remains latched. */
    in.ims_ready=0;mf79u_voice_ended(&p);mf79u_voice_reconcile(&p,&in,34);CHECK(p.selected==MF79U_VOICE_CS);
    in.ims_ready=1;mf79u_voice_reconcile(&p,&in,35);CHECK(p.selected==MF79U_VOICE_CS);
    mf79u_voice_reconcile(&p,&in,39);CHECK(p.selected==MF79U_VOICE_CS);
    in.ims_ready=0;mf79u_voice_reconcile(&p,&in,40);
    in.ims_ready=1;mf79u_voice_reconcile(&p,&in,41);mf79u_voice_reconcile(&p,&in,45);CHECK(p.selected==MF79U_VOICE_CS);
    mf79u_voice_reconcile(&p,&in,46);CHECK(p.selected==MF79U_VOICE_IMS);
    in.cs_only=1;mf79u_voice_reconcile(&p,&in,47);CHECK(p.selected==MF79U_VOICE_CS);
    in.cs_registered=0;mf79u_voice_reconcile(&p,&in,48);CHECK(p.selected==MF79U_VOICE_NONE);
    in.cs_registered=1;in.cs_signaling=0;mf79u_voice_reconcile(&p,&in,49);CHECK(p.selected==MF79U_VOICE_NONE);
    in.cs_signaling=1;in.cs_audio=0;mf79u_voice_reconcile(&p,&in,50);CHECK(p.selected==MF79U_VOICE_NONE);
    in.cs_only=0;mf79u_voice_reconcile(&p,&in,51);CHECK(p.selected==MF79U_VOICE_IMS);
    CHECK(mf79u_voice_admit(&p,MF79U_VOICE_IMS));in.enabled=0;
    mf79u_voice_reconcile(&p,&in,52);CHECK(p.end_call);
    mf79u_voice_ended(&p);mf79u_voice_reconcile(&p,&in,53);CHECK(p.selected==MF79U_VOICE_NONE);
    CHECK(!strcmp(mf79u_voice_name(p.selected),"none"));
    /* Exercise repeated network loss/recovery without leaked call ownership. */
    for(unsigned i=0;i<1000;++i){
        in=(struct mf79u_voice_inputs){1,0,0,1,1,1};mf79u_voice_reconcile(&p,&in,100+i*10);
        CHECK(mf79u_voice_admit(&p,MF79U_VOICE_CS));in.cs_audio=0;
        mf79u_voice_reconcile(&p,&in,101+i*10);CHECK(p.end_call);
        mf79u_voice_ended(&p);mf79u_voice_reconcile(&p,&in,102+i*10);CHECK(p.selected==MF79U_VOICE_NONE);
    }
    puts("PASS voice backend: readiness gates, IMS/CS selection, call ownership, no migration/redial, latched loss, disabled/CS-only, stable IMS promotion, 1000 recovery cycles");
    return 0;
}
