#!/usr/bin/env python3
"""ASan/UBSan checks for the bounded synthetic tone packer; no modem."""
from pathlib import Path
import json,subprocess,tempfile
BASE=Path(__file__).resolve().parent
source=r'''
#include <assert.h>
#include <string.h>
typedef unsigned int u32;
typedef unsigned char u8;
#include "cs-tone-pack.h"
int main(void) {
 u32 mode=99;
 assert(!cs_tone_mode(0,0,&mode) && mode==99);
 assert(!cs_tone_mode(256,0,&mode));assert(!cs_tone_mode(255,0,&mode));
 assert(!cs_tone_mode(0x95,4,&mode));assert(!cs_tone_mode(1,1,&mode));
 unsigned expected[]={0,2,4,7};
 for(unsigned i=0;i<4;i++){assert(cs_tone_mode(0x95,i,&mode));assert(mode==expected[i]);}
 struct {u8 before[16],data[46],after[16];} s;
 memset(&s,0xa5,sizeof(s));
 assert(!cs_tone_pack(s.data,8,0,0));assert(!cs_tone_pack(s.data,0,100,0));
 assert(!cs_tone_pack(s.data,0,0,3));
 for(unsigned i=0;i<46;i++)assert(s.data[i]==0xa5);
 for(unsigned m=0;m<8;m++)for(unsigned f=0;f<100;f++)for(unsigned p=0;p<3;p++) {
  assert(cs_tone_pack(s.data,m,f,p));
  for(unsigned i=0;i<16;i++){assert(s.before[i]==0xa5);assert(s.after[i]==0xa5);}
  /* Independently undo each candidate to recover the original AMR payload. */
  u8 raw[46];memcpy(raw,s.data,46);
  if(p==1)for(unsigned i=0;i<46;i++) {
    unsigned reversed=0;for(unsigned bit=0;bit<8;bit++)reversed|=((raw[i]>>bit)&1U)<<(7-bit);
    raw[i]=(u8)reversed;
  }
  if(p==2)for(unsigned i=0;i<46;i+=2){u8 b=raw[i];raw[i]=raw[i+1];raw[i+1]=b;}
  assert(!memcmp(raw,cs_tone_payloads[m][f],cs_tone_payload_size[m]));
  for(unsigned i=cs_tone_payload_size[m];i<46;i++)assert(raw[i]==0);
 }
 return 0;
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'check.c').write_text(source)
 subprocess.run(['docker','run','--rm','-v',str(BASE)+':/mf:ro','-v',str(p)+':/check:ro',
  'mf79u-system-tools:local','sh','-eu','-c',
  'gcc -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined -I/mf/src /check/check.c -o /tmp/check\n/tmp/check'],check=True,timeout=30)
r={'sanitizers':'address,undefined','mode_set_bounds':True,'all_2400_candidate_frames_checked':True,
 'writes_bounded_to_46_bytes':True,'independent_inverse_matches_verified_codec_frames':True,'hardware_speech_format_verified':False}
(BASE/'build/cs-tone-pack-fixture.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
