#ifndef MF79U_VOWIFI_PCSCF_H
#define MF79U_VOWIFI_PCSCF_H
#include <arpa/inet.h>
#include <stdio.h>
#include <string.h>
struct vowifi_pcscf_choices {char address[4][INET_ADDRSTRLEN];unsigned count,current,tried;};
static int vowifi_pcscf_load(struct vowifi_pcscf_choices *s,const char *path,const char *preferred){
 FILE *f=fopen(path,"r");if(!f)return 0;memset(s,0,sizeof(*s));char line[64];unsigned rows=0;
 while(s->count<4 && rows++<32 && fgets(line,sizeof(line),f)){
  line[strcspn(line,"\r\n")]=0;struct in_addr ip;
  if(inet_pton(AF_INET,line,&ip)!=1 || !ip.s_addr)continue;
  unsigned i;for(i=0;i<s->count;i++)if(!strcmp(s->address[i],line))break;
  if(i==s->count)strcpy(s->address[s->count++],line);
 }
 fclose(f);for(unsigned i=0;i<s->count;i++)if(!strcmp(s->address[i],preferred)){s->current=i;break;}return s->count>0;
}
static int vowifi_pcscf_next(struct vowifi_pcscf_choices *s){
 s->tried|=1u<<s->current;
 for(unsigned i=1;i<s->count;i++){unsigned next=(s->current+i)%s->count;if(!(s->tried&(1u<<next))){s->current=next;return 1;}}
 return 0;
}
#endif
