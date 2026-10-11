/* Read-only state ABI for our bounded CS ring module. No modem commands. */
#ifndef MF79U_CS_STATUS_H
#define MF79U_CS_STATUS_H
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef MF79U_CS_STATUS_FILE
#define MF79U_CS_STATUS_FILE "/sys/mf79u_cs/status"
#endif
struct mf79u_cs_status {
    unsigned armed,state;
    uint32_t events,sent,errors;
};
static const char *mf79u_cs_state_name(unsigned state) {
    return state==1?"alerting":state==2?"releasing":"idle";
}
static int mf79u_cs_status_parse(const char *text,struct mf79u_cs_status *out) {
    uint32_t values[7];
    if(!text || !out || strncmp(text,"MF79U_CS ",9))return -1;
    const char *p=text+9;
    for(unsigned i=0;i<7;i++) {
        if(*p<'0' || *p>'9')return -1;
        char *end;errno=0;unsigned long value=strtoul(p,&end,10);
        if(errno || value>UINT32_MAX || end-p>10)return -1;
        values[i]=(uint32_t)value;
        if(i<6){if(*end!=' ')return -1;p=end+1;}
        else if(strcmp(end,"\n"))return -1;
    }
    if(values[0]!=1 || values[1]>1 || values[2]>2 || values[6]!=1 ||
       (!values[1] && values[2]))return -1;
    *out=(struct mf79u_cs_status){values[1],values[2],values[3],values[4],values[5]};
    return 0;
}
static int mf79u_cs_status_read(struct mf79u_cs_status *out) {
    char text[128];FILE *f=fopen(MF79U_CS_STATUS_FILE,"r");if(!f)return -1;
    int valid=fgets(text,sizeof(text),f)!=NULL;
    if(valid && (fgetc(f)!=EOF || ferror(f)))valid=0;
    fclose(f);return valid?mf79u_cs_status_parse(text,out):-1;
}
#endif
