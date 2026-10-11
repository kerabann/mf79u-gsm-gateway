#define _GNU_SOURCE
#include <stdio.h>
#include <strings.h>
#include "vowifi-access.h"
int main(void){
 const char *text="REGISTER sip:ims.example SIP/2.0\r\nP-Access-Network-Info: 3GPP-E-UTRAN-FDD;utran-cell-id-3gpp=synthetic\r\nContent-Length: 4\r\n\r\nBODY";char out[512];size_t n=vowifi_access_header(text,strlen(text),"001122aAbBcC",out,sizeof(out));
 if(!n || !memmem(out,n,"i-wlan-node-id=001122aAbBcC",26) || memcmp(out+n-4,"BODY",4) || !memmem(out,n,"IEEE-802.11",10) || !memmem(out,n,"Cellular-Network-Info:3GPP-E-UTRAN",33))return 1;
 if(vowifi_access_header(text,strlen(text),"bad",out,sizeof(out)) || vowifi_access_header("payload",7,"001122aAbBcC",out,sizeof(out)) || vowifi_access_header(text,strlen(text),"001122aAbBcC",out,8))return 2;
 n=vowifi_access_header_kind(text,strlen(text),NULL,out,sizeof(out),1);
 if(!n || !memmem(out,n,"IEEE-802.3",10) || memmem(out,n,"i-wlan-node-id",14) || memcmp(out+n-4,"BODY",4))return 3;
 puts("PASS VoWiFi access header: SIP header only, body preserved, bounded output");return 0;
}
