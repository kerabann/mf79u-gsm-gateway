#include <unistd.h>
#include "sip-settings.h"
int main(void){
 char path[]="/tmp/mf79u-sip-config-XXXXXX";int fd=mkstemp(path);if(fd<0)return 1;close(fd);
 const char *fields[]={"", "vowifi_uplink=\n", "vowifi_uplink=WIFI\n", "vowifi_uplink=USB\n", "vowifi_uplink=LTE\n", "foreign=USB\n"};
 for(unsigned i=0;i<6;i++){
  FILE *f=fopen(path,"w");if(!f){unlink(path);return 2;}
  fprintf(f,"voice_mode=%s\n%s",i%2?"VOWIFI_SMS":"VOWIFI",fields[i]);fclose(f);
  struct sip_settings settings;int result=sip_load_settings(path,&settings);
  if((i<4 && result) || (i>=4 && !result)){unlink(path);return 3;}
 }
 unlink(path);if(!sip_phone("+1234"))return 4;
 puts("PASS shared SIP INI: legacy, Wi-Fi, USB accepted; invalid source and unknown fields rejected");return 0;
}
