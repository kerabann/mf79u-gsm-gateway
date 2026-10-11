#ifndef MF79U_SIP_SETTINGS_H
#define MF79U_SIP_SETTINGS_H
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
struct sip_settings {
	char role[9],extension[65],extension_password[257];
 char server[254],transport[4],username[65],password[257],realm[129],incoming_user[65],bind[16],trusted_peers[256],codecs[64],ca_file[256];
 unsigned port,local_port,registration;
};
static int sip_safe_word(const char *s,const char *extra){if(!*s)return 0;for(;*s;s++)if(!isalnum((unsigned char)*s)&&!strchr(extra,*s))return 0;return 1;}
static int sip_phone(const char *s){if(*s=='+')s++;size_t n=strlen(s);if(n<3||n>32)return 0;for(;*s;s++)if(*s<'0'||*s>'9')return 0;return 1;}
static int sip_load_settings(const char *path,struct sip_settings *s){
 *s=(struct sip_settings){.role="TRUNK",.extension="100",.server="192.168.0.169",.transport="UDP",.username="mf79u",.realm="*",.incoming_user="mf79u",.bind="0.0.0.0",.trusted_peers="192.168.0.169,192.168.1.28",.codecs="OPUS,G722,PCMA,PCMU,G729",.ca_file="/usr/zte/mf79u/ca-bundle.pem",.port=5060,.local_port=5080};
 FILE *f=fopen(path,"r");if(!f)return errno==ENOENT?0:1;char line[1200];int result=0;
 while(fgets(line,sizeof(line),f)){
  if(!strchr(line,'\n')&&!feof(f)){result=1;break;}line[strcspn(line,"\r\n")]=0;char *eq=strchr(line,'=');if(!eq){result=1;break;}*eq++=0;
  char *dst=NULL;size_t cap=0;
  #define FIELD(name) if(!strcmp(line,#name)){dst=s->name;cap=sizeof(s->name);}
  FIELD(role) else FIELD(extension) else FIELD(extension_password) else FIELD(server) else FIELD(transport) else FIELD(username) else FIELD(password) else FIELD(realm) else FIELD(incoming_user) else FIELD(bind) else FIELD(trusted_peers) else FIELD(codecs) else FIELD(ca_file)
  #undef FIELD
  else if(!strcmp(line,"voice_mode")){
   /* Shared INI: the native controller owns radio registration. Validate its
    * field here so initial startup and SIGHUP accept the generated config. */
   if(strcmp(eq,"AUTO") && strcmp(eq,"VOLTE") && strcmp(eq,"CS") && strcmp(eq,"VOWIFI")){result=1;break;}
   continue;
  }
  else if(!strcmp(line,"vowifi_uplink")){
   /* Native owns this shared field. Empty is legacy Wi-Fi default. */
   if(*eq && strcmp(eq,"WIFI") && strcmp(eq,"USB")){result=1;break;}
   continue;
  }
  else {unsigned *n=!strcmp(line,"port")?&s->port:!strcmp(line,"local_port")?&s->local_port:!strcmp(line,"register")?&s->registration:NULL;char *end;unsigned long value=strtoul(eq,&end,10);if(!n||!*eq||*end||value>65535){result=1;break;}*n=(unsigned)value;continue;}
  if(strlen(eq)>=cap){result=1;break;}if(cap==sizeof(s->ca_file)&&!strcmp(line,"ca_file")&&!*eq)continue;strcpy(dst,eq);
 }
 memset(line,0,sizeof(line));fclose(f);
 if((!strcmp(s->role,"TRUNK") && (!sip_safe_word(s->server,".-")||!sip_safe_word(s->username,"_.+~-")||!sip_safe_word(s->incoming_user,"_.+~-")))||!s->port||s->local_port<1024||s->registration>1 || (strcmp(s->transport,"UDP")&&strcmp(s->transport,"TCP")&&strcmp(s->transport,"TLS")))result=1;
 struct in_addr ip;if(inet_pton(AF_INET,s->bind,&ip)!=1)result=1;
 if(strcmp(s->role,"TRUNK") && strcmp(s->role,"SERVER") && strcmp(s->role,"DISABLED"))result=1;
 if(!sip_safe_word(s->extension,"_.+~-"))result=1;
 if(!strcmp(s->role,"SERVER") && (strlen(s->extension_password)<12 || !strcmp(s->bind,"0.0.0.0") || strcmp(s->transport,"UDP")))result=1;
 return result;
}
#endif
