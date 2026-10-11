#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static double now(void){struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);return (double)ts.tv_sec+(double)ts.tv_nsec/1e9;}
int main(int argc,char **argv){
 libusb_context *ctx=NULL; int rc=libusb_init(&ctx); if(rc){fprintf(stderr,"init: %s\n",libusb_error_name(rc));return 1;}
 libusb_device **list=NULL; ssize_t n=libusb_get_device_list(ctx,&list); if(n<0)return 1;
 int result=2;
 for(ssize_t i=0;i<n;i++){
  struct libusb_device_descriptor d; if(libusb_get_device_descriptor(list[i],&d)||d.idVendor!=0x19d2)continue;
  fprintf(stderr,"USB %04x:%04x bus=%u address=%u\n",d.idVendor,d.idProduct,libusb_get_bus_number(list[i]),libusb_get_device_address(list[i]));
  struct libusb_config_descriptor *c=NULL;
  rc=libusb_get_active_config_descriptor(list[i],&c);if(rc){fprintf(stderr,"config: %s\n",libusb_error_name(rc));continue;}
  int iface=d.idProduct==0x0581?4:0;
  unsigned char epin=0,epout=0;
  for(int j=0;j<c->bNumInterfaces;j++)for(int k=0;k<c->interface[j].num_altsetting;k++){
   const struct libusb_interface_descriptor *a=&c->interface[j].altsetting[k];
   fprintf(stderr,"interface %u alt=%u class=%02x",a->bInterfaceNumber,a->bAlternateSetting,a->bInterfaceClass);
   for(int e=0;e<a->bNumEndpoints;e++){
    const struct libusb_endpoint_descriptor *p=&a->endpoint[e];
    fprintf(stderr," ep=%02x type=%u packet=%u",p->bEndpointAddress,p->bmAttributes&3,p->wMaxPacketSize);
    if(a->bInterfaceNumber==iface && (p->bmAttributes&3)==2){if(p->bEndpointAddress&0x80)epin=p->bEndpointAddress;else epout=p->bEndpointAddress;}
   } fputc('\n',stderr);
  }
  libusb_free_config_descriptor(c);result=0;
  if(argc<2)continue;
  if((d.idProduct!=0x1602 && d.idProduct!=0x0581) || !epin || !epout){fprintf(stderr,"AT requires PID1602/interface0 or PID0581/interface4\n");result=1;continue;}
  libusb_device_handle *h=NULL;rc=libusb_open(list[i],&h);if(rc){fprintf(stderr,"open: %s\n",libusb_error_name(rc));result=1;continue;}
  rc=libusb_claim_interface(h,iface);if(rc){fprintf(stderr,"claim: %s\n",libusb_error_name(rc));libusb_close(h);result=1;continue;}
  unsigned char b[4096];int got=0;
  while(libusb_bulk_transfer(h,epin,b,sizeof(b),&got,50)==0){}
  size_t len=strlen(argv[1]); if(len>2046){result=1;goto close;}
  memcpy(b,argv[1],len);b[len++]='\r';got=0;
  rc=libusb_bulk_transfer(h,epout,b,(int)len,&got,1000);
  if(rc || got!=(int)len){fprintf(stderr,"write: %s (%d bytes)\n",libusb_error_name(rc),got);result=1;goto close;}
  size_t expected=argc>2?(size_t)strtoul(argv[2],NULL,10):0, received=0;
  /* argv[3] extends response waiting for asynchronous radio commands.
     Existing invocations keep their original idle timeout. */
  unsigned wait_seconds=argc>3?(unsigned)strtoul(argv[3],NULL,10):0;
  if(argc>3 && (wait_seconds<3 || wait_seconds>60)){result=1;goto close;}
  char terminal[128]={0};size_t terminal_used=0;
  double limit=now()+(wait_seconds?wait_seconds:30), idle=wait_seconds?limit:now()+3;
  while(now()<limit && now()<idle){
   got=0;rc=libusb_bulk_transfer(h,epin,b,sizeof(b),&got,250);
   if(got>0){
    fwrite(b,1,(size_t)got,stdout);fflush(stdout);received+=(size_t)got;idle=wait_seconds?limit:now()+1;
    size_t keep=(size_t)got;if(keep>=sizeof(terminal))keep=sizeof(terminal)-1;
    size_t old=terminal_used;
    if(old+keep>=sizeof(terminal)){old=sizeof(terminal)-1-keep;memmove(terminal,terminal+terminal_used-old,old);}
    memcpy(terminal+old,b+(size_t)got-keep,keep);terminal_used=old+keep;terminal[terminal_used]=0;
    if(wait_seconds && (strstr(terminal,"\r\nOK\r\n") || strstr(terminal,"\r\nERROR\r\n") || strstr(terminal,"\r\n+CME ERROR:")))break;
    if(expected && received>=expected+6)break;
   } else usleep(1000);
   if(rc!=0 && rc!=LIBUSB_ERROR_TIMEOUT){fprintf(stderr,"read: %s\n",libusb_error_name(rc));result=1;break;}
  }
 close:libusb_release_interface(h,iface);libusb_close(h);
 }
 libusb_free_device_list(list,1);libusb_exit(ctx);return result;
}
