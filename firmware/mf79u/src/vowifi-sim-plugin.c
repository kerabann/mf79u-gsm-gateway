/* MF79U strongSwan AKA card. Linked under the eap-simaka-reauth plugin slot.
 * Real USIM computes RES/CK/IK; no Ki/OPc is extracted or stored. */
#include <daemon.h>
#include <plugins/plugin.h>
#include <simaka_manager.h>
#include <simaka_card.h>
#include "cp-ipc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
static char last_rand[16],last_auts[14];static int have_auts;
static int hex_digit(unsigned char c){if(c>='0' && c<='9')return c-'0';if(c>='a' && c<='f')return c-'a'+10;if(c>='A' && c<='F')return c-'A'+10;return -1;}
static int unhex(char *s,char *out,int max){
    if(*s=='"')s++;size_t n=strcspn(s,"\"\r\n");if(n%2 || n>(size_t)max*2)return -1;
    for(size_t i=0;i<n/2;i++){int a=hex_digit((unsigned char)s[i*2]),b=hex_digit((unsigned char)s[i*2+1]);if(a<0 || b<0)return -1;out[i]=(char)((a<<4)|b);}return (int)n/2;
}
static status_t quintuplet(simaka_card_t *card,identification_t *id,char rand[16],char autn[16],char ck[16],char ik[16],char res[16],int *res_len){
    (void)card;(void)id;struct mf79u_cp cp;char cmd[80],reply[512],rh[33],ah[33];status_t result=FAILED;
    for(int i=0;i<16;i++){sprintf(rh+i*2,"%02x",(unsigned char)rand[i]);sprintf(ah+i*2,"%02x",(unsigned char)autn[i]);}
    snprintf(cmd,sizeof(cmd),"AT^MBAU=\"%s\",\"%s\"",rh,ah);have_auts=0;
    if(mf79u_cp_open(&cp)){DBG1(DBG_LIB,"MF79U AKA IPC unavailable errno=%d",errno);goto done;}
    int n=mf79u_cp_query(&cp,cmd,reply,sizeof(reply),8);mf79u_cp_close(&cp);
    DBG1(DBG_LIB,"MF79U AKA reply bytes=%d terminal_ok=%d",n,!!strstr(reply,"\r\nOK\r\n"));
    if(n<0 || !strstr(reply,"\r\nOK\r\n"))goto done;
    char *p=strstr(reply,"^MBAU:");if(!p)goto done;p+=6;
    p[strcspn(p,"\r\n")]=0;
    char *f[8];int count=0;for(char *x=p;x && count<8;){while(*x==' ')x++;f[count++]=x;char *next=strchr(x,',');if(next)*next=0;size_t size=strlen(x);while(size && x[size-1]==' ')x[--size]=0;x=next?next+1:NULL;}
    DBG1(DBG_LIB,"MF79U AKA fields=%d status=%d",count,count?atoi(f[0]):-1);
    for(int i=1;i<count;i++){char tmp[32];int len=unhex(f[i],tmp,sizeof(tmp));memwipe(tmp,sizeof(tmp));DBG1(DBG_LIB,"MF79U AKA field=%d decoded_bytes=%d",i,len);}
    if((count==4 || count==5) && !strcmp(f[0],"0")){
        int len=unhex(f[count==5?3:1],res,16);
        /* B03: status, CK, IK, padded RES, decimal RES hex-character length. */
        if(count==5){char *s=f[4],*end=NULL;if(*s=='"')s++;unsigned long reported=strtoul(s,&end,10);if(end==s)goto done;if(*end=='"')end++;if(*end || reported<8 || reported>32 || reported%2 || len<(int)(reported/2))goto done;len=(int)(reported/2);}
        if(len>=4 && unhex(f[count==5?1:2],ck,16)==16 && unhex(f[count==5?2:3],ik,16)==16){*res_len=len;result=SUCCESS;DBG1(DBG_LIB,"MF79U AKA RES bytes=%d",len);}
    }else if(count==2 && !strcmp(f[0],"1") && unhex(f[1],last_auts,14)==14){memcpy(last_rand,rand,16);have_auts=1;result=INVALID_STATE;}
 done:
    memwipe(cmd,sizeof(cmd));memwipe(reply,sizeof(reply));memwipe(rh,sizeof(rh));memwipe(ah,sizeof(ah));
    if(result!=SUCCESS){memwipe(ck,16);memwipe(ik,16);memwipe(res,16);}return result;
}
static bool resync(simaka_card_t *c,identification_t *id,char rand[16],char auts[14]){(void)c;(void)id;if(!have_auts || !memeq_const(rand,last_rand,16))return FALSE;memcpy(auts,last_auts,14);have_auts=0;memwipe(last_auts,14);return TRUE;}
static simaka_card_t card={.get_triplet=(void*)return_false,.get_quintuplet=quintuplet,.resync=resync,.set_pseudonym=(void*)nop,.get_pseudonym=(void*)return_null,.set_reauth=(void*)nop,.get_reauth=(void*)return_null};
static simaka_card_t *get_card(plugin_t *p){(void)p;return &card;}
static char *get_name(plugin_t *p){(void)p;return "eap-simaka-reauth";}
static int get_features(plugin_t *p,plugin_feature_t **features){(void)p;static plugin_feature_t f[]={PLUGIN_CALLBACK(simaka_manager_register,get_card),PLUGIN_PROVIDE(CUSTOM,"aka-card"),PLUGIN_DEPENDS(CUSTOM,"aka-manager")};*features=f;return countof(f);}
static void destroy(plugin_t *p){memwipe(last_rand,16);memwipe(last_auts,14);free(p);}
PLUGIN_DEFINE(eap_simaka_reauth){plugin_t *p=calloc(1,sizeof(*p));if(p){p->get_name=get_name;p->get_features=get_features;p->destroy=destroy;}return p;}
