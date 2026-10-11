#ifndef MF79U_VOWIFI_ACCESS_H
#define MF79U_VOWIFI_ACCESS_H
#include <string.h>
#include <strings.h>
#include <stdio.h>
/* Change only the access header of actual SIP messages. Content-Length and
 * media payload stay unchanged. The caller supplies a complete SIP message. */
static size_t vowifi_access_header_kind(const void *input,size_t length,const char *node,char *out,size_t capacity,int ethernet){
 if(!ethernet && (!node || strlen(node)!=12))return 0;
 for(unsigned i=0;!ethernet && i<12;i++)if(!((node[i]>='0'&&node[i]<='9')||(node[i]>='a'&&node[i]<='f')||(node[i]>='A'&&node[i]<='F')))return 0;
 const char *p=input;size_t boundary=0,start=0,end=0;
 for(size_t i=0;i+3<length;i++)if(!memcmp(p+i,"\r\n\r\n",4)){boundary=i+2;break;}
 if(!boundary)return 0;
 const char key[]="P-Access-Network-Info:";
 for(size_t i=0;i+sizeof(key)-1<boundary;i++)if((!i || (i>=2 && p[i-2]=='\r' && p[i-1]=='\n')) && !strncasecmp(p+i,key,sizeof(key)-1)){
  start=i;for(end=i;end+1<boundary;end++)if(p[end]=='\r' && p[end+1]=='\n')break;end+=2;break;
 }
 if(!end)return 0;
 char header[96];int count=ethernet?snprintf(header,sizeof(header),"P-Access-Network-Info: IEEE-802.3\r\n"):snprintf(header,sizeof(header),"P-Access-Network-Info: IEEE-802.11;i-wlan-node-id=%s\r\n",node);if(count<0 || (size_t)count>=sizeof(header))return 0;size_t old_value=start+sizeof(key)-1;while(old_value+1<end && (p[old_value]==' ' || p[old_value]=='\t'))old_value++;
 const char cellular[]="Cellular-Network-Info:";size_t cell_length=0;
 if(old_value+5<end && !memcmp(p+old_value,"3GPP-",5))cell_length=sizeof(cellular)-1+end-old_value;
 size_t total=length-(end-start)+(size_t)count+cell_length;
 if(total>capacity)return 0;
 memcpy(out,p,start);memcpy(out+start,header,(size_t)count);size_t next=start+(size_t)count;if(cell_length){memcpy(out+next,cellular,sizeof(cellular)-1);next+=sizeof(cellular)-1;memcpy(out+next,p+old_value,end-old_value);next+=end-old_value;}
 memcpy(out+next,p+end,length-end);return total;
}
static size_t vowifi_access_header(const void *input,size_t length,const char *node,char *out,size_t capacity){return vowifi_access_header_kind(input,length,node,out,capacity,0);}
#endif
