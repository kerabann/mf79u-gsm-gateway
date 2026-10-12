#ifndef MF79U_IMS_SAFE_METADATA_H
#define MF79U_IMS_SAFE_METADATA_H
#include <errno.h>
#include <stdlib.h>
#include <string.h>
/* Accept exact scalar diagnostic names only. Never relay arbitrary vendor
 * trace, SIP headers/bodies, identifiers, authentication or PCM buffers. */
struct mf79u_ims_scalar {const char *tag;long value;};
static int mf79u_ims_scalar(const char *line,struct mf79u_ims_scalar *out){
 const struct {const char *name,*tag;} fields[]={
  {"SOFTWARE media device opened","device_open"},
  {"SOFTWARE media ioctl","ioctl"},
  {"SOFTWARE media result","ioctl_result"},
  {"SOFTWARE media errno","ioctl_errno"},
  {"SOFTWARE PCM resource owned","resource_owned"},
  {"SOFTWARE PCM preopen","preopen"},
  {"SOFTWARE PCM preclose","preclose"},
  {"SOFTWARE media thread normal scheduling","thread_scheduling"},
  {"SOFTWARE worker original stack bytes","original_stack_bytes"},
  {"SOFTWARE worker selected stack bytes","selected_stack_bytes"},
  {"MEDIA open errno","open_errno"},
  {"MEDIA ioctl request","vendor_ioctl"},
  {"MEDIA ioctl return","vendor_ioctl_result"},
  {"MEDIA ioctl errno","vendor_ioctl_errno"},
  {"NATIVE codec assertion line","codec_assertion_line"},
  {"SOCKET connect type","socket_type"},
  {"SOCKET connect destination port","socket_port"},
  {"SOCKET connect result","socket_result"},
  {"SOCKET connect errno","socket_errno"}
 };
 for(unsigned i=0;i<sizeof(fields)/sizeof(fields[0]);i++){
  size_t n=strlen(fields[i].name);
  if(strncmp(line,fields[i].name,n) || strncmp(line+n," result=",8))continue;
  const char *p=line+n+8;
  if(*p=='-')p++;
  if(*p<'0' || *p>'9')return 0;
  for(const char *q=p;*q;q++)if(*q<'0' || *q>'9')return 0;
  char *end;int saved_errno=errno;errno=0;long value=strtol(line+n+8,&end,10);
  int overflow=errno;errno=saved_errno;
  if(overflow || *end || value<(-2147483647L-1) || value>2147483647L)return 0;
  /* Successful encoder/decoder frames are hot paths. Retain setup requests
   * and failures without adding per-frame stdout work to confirmed audio. */
  if((!strcmp(fields[i].tag,"ioctl_result") || !strcmp(fields[i].tag,"vendor_ioctl_result")) && value>=0)return 0;
  if((!strcmp(fields[i].tag,"ioctl") || !strcmp(fields[i].tag,"vendor_ioctl")) &&
     (value==0x40147604L || value==0x40107603L))return 0;
  out->tag=fields[i].tag;out->value=value;return 1;
 }
 return 0;
}
struct mf79u_ims_method {const char *direction,*method;unsigned bytes;};
static int mf79u_ims_method(const char *line,struct mf79u_ims_method *out){
 const struct {const char *prefix,*direction;} directions[]={
  {"TX","TX"},{"TX_WRITEV","TX"},{"TX_ESP protected","TX"},
  {"RX","RX"},{"RX_ESP verified","RX"}
 };
 const char *method=NULL,*direction=NULL;
 for(unsigned i=0;i<sizeof(directions)/sizeof(directions[0]);i++){
  size_t n=strlen(directions[i].prefix);
  if(!strncmp(line,directions[i].prefix,n) && !strncmp(line+n," SIP method ",12)){
   method=line+n+12;direction=directions[i].direction;break;
  }
 }
 if(!method)return 0;
 const char *methods[]={"REGISTER","INVITE","ACK","BYE","CANCEL","OPTIONS","SUBSCRIBE","NOTIFY","PRACK","UPDATE","MESSAGE"};
 for(unsigned i=0;i<sizeof(methods)/sizeof(methods[0]);i++){
  size_t n=strlen(methods[i]);
  if(strncmp(method,methods[i],n) || strncmp(method+n," bytes=",7))continue;
  const char *p=method+n+7;if(*p<'0' || *p>'9')return 0;
  unsigned bytes=0;
  for(;*p;p++){
   if(*p<'0' || *p>'9' || bytes>7000)return 0;
   bytes=bytes*10+(unsigned)(*p-'0');
  }
  if(!bytes || bytes>7000)return 0;
  out->direction=direction;out->method=methods[i];out->bytes=bytes;return 1;
 }
 return 0;
}
#endif
