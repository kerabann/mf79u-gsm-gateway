#include <assert.h>
#include "voice-registration-policy.h"
int main(void){
 enum voice_mode mode;
 assert(!voice_mode_parse("VOWIFI_SMS",&mode) && mode==VOICE_VOWIFI_SMS);
 assert(!strcmp(voice_mode_name(mode),"VOWIFI_SMS") && voice_mode_vowifi_only(mode));
 for(unsigned long retry=0;retry<100;retry+=10)
  assert(voice_registration_target(mode,1,0,retry,0)==3);
 assert(voice_registration_target(mode,1,0,100,2)==2); /* Existing call remains pinned. */
 assert(voice_mode_parse("VOWIFI_SMS;CS",&mode));
 return 0;
}
