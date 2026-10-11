#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/msg.h>
#include <time.h>
#include <unistd.h>
struct message {int32_t type,dst,src;uint16_t cmd,len;uint32_t magic;unsigned char payload[3496];};
int main(void){
 int q=msgget(0x101e,IPC_CREAT|IPC_EXCL|0600);if(q<0){perror("exclusive stock IMS queue");return 1;}
 setvbuf(stdout,NULL,_IONBF,0);puts("SMS_WATCH_READY exclusive_unused_stock_ims_queue");
 time_t stop=time(NULL)+90;struct message m;
 while(time(NULL)<stop){ssize_t n=msgrcv(q,&m,sizeof(m)-4,0,IPC_NOWAIT);
  if(n<0){if(errno!=ENOMSG&&errno!=EINTR)break;usleep(100000);continue;}
  unsigned len=m.len,port=0;if(m.len==3496){memcpy(&len,m.payload+3488,4);memcpy(&port,m.payload+3492,4);}if(len>3488)len=3488;
  char text[3489];memcpy(text,m.payload,len);text[len]=0;
  printf("STOCK_IMS_EVENT command=0x%04x bytes=%u port=%u sms=%d registration=%d ack=%d\n",m.cmd,len,port,strstr(text,"CMT")!=NULL||strstr(text,"SMS")!=NULL,strstr(text,"REG")!=NULL,strstr(text,"CNMA")!=NULL);
 }
 msgctl(q,IPC_RMID,NULL);puts("SMS_WATCH_DONE queue_removed");return 0;
}