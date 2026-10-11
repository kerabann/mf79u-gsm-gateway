#ifndef MF79U_VOICE_REGISTRATION_POLICY_H
#define MF79U_VOICE_REGISTRATION_POLICY_H
#include <string.h>
enum voice_mode { VOICE_AUTO,VOICE_VOLTE,VOICE_CS,VOICE_VOWIFI,VOICE_VOWIFI_SMS };
static int voice_mode_vowifi_only(enum voice_mode mode){return mode==VOICE_VOWIFI || mode==VOICE_VOWIFI_SMS;}
static const char *voice_mode_name(enum voice_mode mode){return mode==VOICE_VOWIFI_SMS?"VOWIFI_SMS":mode==VOICE_VOWIFI?"VOWIFI":mode==VOICE_CS?"CS":mode==VOICE_VOLTE?"VOLTE":"AUTO";}
static int voice_mode_parse(const char *s,enum voice_mode *m){
    if(!strcmp(s,"AUTO"))*m=VOICE_AUTO;else if(!strcmp(s,"VOLTE"))*m=VOICE_VOLTE;
    else if(!strcmp(s,"CS"))*m=VOICE_CS;else if(!strcmp(s,"VOWIFI"))*m=VOICE_VOWIFI;
    else if(!strcmp(s,"VOWIFI_SMS"))*m=VOICE_VOWIFI_SMS;else return -1;
    return 0;
}
/* A conversation remains on its admitting backend until confirmed clearing.
 * Retry promotion creates a new registration attempt, never replays DIAL. */
static int voice_registration_target(enum voice_mode mode,int fallback,
                                     unsigned long now,unsigned long retry,int owner){
    if(owner)return owner;
    if(mode==VOICE_CS)return 2;
    if(mode==VOICE_VOLTE)return 1;
    if(voice_mode_vowifi_only(mode))return 3;
    /* AUTO falls back directly to GSM CS. */
    return fallback && now<retry?2:1;
}
#endif
