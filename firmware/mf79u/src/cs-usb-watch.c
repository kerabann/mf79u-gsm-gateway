/* Mac-only passive B03 USB AT observation. Never writes to an endpoint.
 * Only state metadata is printed; CLIP/phone numbers/other URCs are discarded. */
#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void line(const char *s){
    unsigned id,dir,state;
    if(!strcmp(s,"RING") || !strncmp(s,"+CRING: VOICE",13))puts("CS_USB incoming_ring");
    else if(sscanf(s,"^DSCI: %u,%u,%u",&id,&dir,&state)==3 && id>=1 && id<=8 && dir<=1 && state<=6)
        printf("CS_USB id=%u direction=%u state=%u\n",id,dir,state);
    else if(sscanf(s,"^CEND: %u",&id)==1 && id>=1 && id<=8)printf("CS_USB id=%u ended\n",id);
    else if(sscanf(s,"^CONN: %u",&id)==1 && id>=1 && id<=8)printf("CS_USB id=%u connected\n",id);
    else if(!strncmp(s,"+CLIP:",6))puts("CS_USB caller_indication redacted=1");
    else if(!strcmp(s,"NO CARRIER"))puts("CS_USB no_carrier");
}
int main(int argc,char **argv){
    if(argc!=2)return 2;
    char *end;long seconds=strtol(argv[1],&end,10);if(*end || seconds<1 || seconds>1800)return 2;
    libusb_context *ctx=NULL;if(libusb_init(&ctx))return 1;
    libusb_device_handle *h=libusb_open_device_with_vid_pid(ctx,0x19d2,0x0581);
    if(!h){libusb_exit(ctx);return 1;}
    if(libusb_claim_interface(h,4)){libusb_close(h);libusb_exit(ctx);return 1;}
    setvbuf(stdout,NULL,_IONBF,0);puts("CS_USB_READY passive=1 dial=0 answer=0");
    char buffer[4096],text[512];size_t used=0;int overflow=0,result=0;
    double deadline=now()+seconds;
    while(now()<deadline){
        int got=0,rc=libusb_bulk_transfer(h,0x84,(unsigned char*)buffer,sizeof(buffer),&got,250);
        if(rc && rc!=LIBUSB_ERROR_TIMEOUT){result=1;break;}
        for(int i=0;i<got;i++){
            if(buffer[i]=='\r' || buffer[i]=='\n'){
                if(!overflow && used){text[used]=0;line(text);}
                memset(text,0,sizeof(text));used=0;overflow=0;
            }else if(used<sizeof(text)-1)text[used++]=buffer[i];else overflow=1;
        }
    }
    memset(buffer,0,sizeof(buffer));memset(text,0,sizeof(text));
    libusb_release_interface(h,4);libusb_close(h);libusb_exit(ctx);
    puts("CS_USB_DONE");return result;
}
