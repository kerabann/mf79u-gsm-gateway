#define _GNU_SOURCE
#include <assert.h>
#include <stdlib.h>
#include <unistd.h>
#include "vowifi-pcscf.h"
int main(void){
 char path[]="/tmp/mf79u-pcscf-XXXXXX";int fd=mkstemp(path);assert(fd>=0);FILE*f=fdopen(fd,"w");assert(f);fputs("invalid\n0.0.0.0\n192.0.2.1\n192.0.2.1\n192.0.2.2\n",f);fclose(f);
 struct vowifi_pcscf_choices s;assert(vowifi_pcscf_load(&s,path,"192.0.2.2") && s.count==2 && s.current==1);
 assert(vowifi_pcscf_next(&s) && s.current==0 && !vowifi_pcscf_next(&s));
 assert(vowifi_pcscf_load(&s,path,"192.0.2.99") && s.current==0 && s.count==2);
 unlink(path);assert(!vowifi_pcscf_load(&s,path,""));puts("PASS P-CSCF provider-only selection, deduplication, valid preferred endpoint and bounded failover");return 0;
}
