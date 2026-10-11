#ifndef MF79U_IMS_REGISTER_RESPONSE_H
#define MF79U_IMS_REGISTER_RESPONSE_H
#include <stddef.h>
#include <string.h>
#include <strings.h>
/* Headers only: never mistake a MESSAGE response or body for REGISTER. */
static unsigned mf79u_register_response(const void *buffer,size_t length){
 const char *s=buffer;
 if(length<12 || memcmp(s,"SIP/2.0 ",8) || s[8]<'1' || s[8]>'6' || s[9]<'0' || s[9]>'9' || s[10]<'0' || s[10]>'9' || s[11]!=' ')return 0;
 for(size_t start=0;start<length;){
  size_t end=start;while(end<length && s[end]!='\r' && s[end]!='\n')end++;
  if(end==start)break;
  if(end-start>=5 && !strncasecmp(s+start,"CSeq:",5)){
   size_t p=start+5;while(p<end && (s[p]==' ' || s[p]=='\t'))p++;
   size_t number=p;while(p<end && s[p]>='0' && s[p]<='9')p++;
   if(p==number || p==end || (s[p]!=' ' && s[p]!='\t'))return 0;
   while(p<end && (s[p]==' ' || s[p]=='\t'))p++;
   if(end-p!=8 || memcmp(s+p,"REGISTER",8))return 0;
   return (unsigned)(s[8]-'0')*100+(unsigned)(s[9]-'0')*10+(unsigned)(s[10]-'0');
  }
  start=end;if(start<length && s[start]=='\r')start++;if(start<length && s[start]=='\n')start++;
 }
 return 0;
}
#endif
