/* Read-only registration diagnostic. No identifiers, cell IDs or AT mutations. */
#include "cp-ipc.h"
#include <stdio.h>
#include <string.h>
int main(void) {
 struct mf79u_cp cp;if(mf79u_cp_open(&cp))return 1;
 const char *cmd[]={"AT+CPIN?","AT+CFUN?","AT+CREG?","AT+CGREG?","AT+CEREG?","AT+COPS?","AT+CSQ","AT^SYSINFO","AT^SYSCONFIG?","AT+ZSET=\"VOICE_SUPPORT\"","AT+ZSET=\"OPEN_VOICE_FLAG\""};
 const char *prefix[]={"+CPIN:","+CFUN:","+CREG:","+CGREG:","+CEREG:","+COPS:","+CSQ:","^SYSINFO:","^SYSCONFIG:","+ZSET:","+ZSET:"};
 for(unsigned i=0;i<sizeof(cmd)/sizeof(cmd[0]);i++){
  char reply[4096];int count=mf79u_cp_query(&cp,cmd[i],reply,sizeof(reply),5),a=-1,b=-1,cme=-1;
  const char *p=strstr(reply,prefix[i]);const char *e=strstr(reply,"+CME ERROR:");if(e)sscanf(e,"+CME ERROR: %d",&cme);
  printf("REG_QUERY command=%s transport=%d ok=%d cme=%d",cmd[i],count>=0,count>0&&strstr(reply,"\r\nOK\r\n")!=NULL,cme);
  if(p){
   if(i==0)printf(" ready=%d pin_required=%d puk_required=%d",strstr(p,"READY")!=NULL,strstr(p,"SIM PIN")!=NULL,strstr(p,"SIM PUK")!=NULL);
   else if(i>=9){const char *value=strrchr(p,',');if(value && sscanf(value+1,"%d",&a)==1)printf(" first=%d",a);}
   else if(sscanf(p+strlen(prefix[i])," %d,%d",&a,&b)==2)printf(" first=%d second=%d",a,b);
   else if(sscanf(p+strlen(prefix[i])," %d",&a)==1)printf(" first=%d",a);
  }
  puts("");memset(reply,0,sizeof(reply));
 }
 mf79u_cp_close(&cp);return 0;
}
