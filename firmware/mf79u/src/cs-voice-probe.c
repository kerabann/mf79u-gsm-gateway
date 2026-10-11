/* Read-only B03 CS capability audit. No dial, answer, configuration or raw RPM. */
#include "cp-ipc.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
int main(void) {
 struct mf79u_cp cp;if(mf79u_cp_open(&cp)){perror("CP queue");return 1;}
 const char *cmd[]={"AT+CLCC","AT+CLCC=?","AT+CVMOD?","AT+ZAMRSUP?"};
 for(unsigned i=0;i<sizeof(cmd)/sizeof(cmd[0]);i++){
  char reply[4096];int n=mf79u_cp_query(&cp,cmd[i],reply,sizeof(reply),5);
  printf("CS_PROBE command=%s transport=%s ok=%d rejected=%d\n",cmd[i],n<0?"failed":"ok",n>0 && strstr(reply,"\r\nOK\r\n")!=NULL,n>0 && strstr(reply,"ERROR")!=NULL);
  memset(reply,0,sizeof(reply));
 }
 const char *nodes[]={"/dev/voice_device","/dev/volte_device","/dev/snd/controlC0","/sys/class/sound","/dev/slic-0"};
 for(unsigned i=0;i<sizeof(nodes)/sizeof(nodes[0]);i++)printf("CS_AUDIO path=%s present=%d\n",nodes[i],access(nodes[i],F_OK)==0);
 mf79u_cp_close(&cp);return 0;
}
