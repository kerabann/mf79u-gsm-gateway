#!/usr/bin/env python3
"""Actual adapter main/input loop with synchronous instrumented kernel/process IO."""
from pathlib import Path
import subprocess,tempfile,json
B=Path(__file__).resolve().parent
header=r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdarg.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <signal.h>
#include <time.h>
#include <poll.h>
static int f_open(const char *,int,...),f_close(int),f_kill(pid_t,int),f_poll(struct pollfd *,nfds_t,int),f_clock(clockid_t,struct timespec *);
static ssize_t f_read(int,void *,size_t),f_write(int,const void *,size_t);
static FILE *f_fopen(const char *,const char *);
static pid_t f_fork(void),f_waitpid(pid_t,int *,int);
#define open f_open
#define close f_close
#define kill f_kill
#define poll f_poll
#define clock_gettime f_clock
#define read f_read
#define write f_write
#define fopen f_fopen
#define fork f_fork
#define waitpid f_waitpid
#define main adapter_main
#define CS_ADAPTER_LOCK "/tmp/mf79u-adapter-fixture.lock"
'''
tail=r'''
#undef main
#undef open
#undef close
#undef kill
#undef poll
#undef clock_gettime
#undef read
#undef write
#undef fopen
#undef fork
#undef waitpid
static struct state kernel;
static unsigned frame,starts,stops,alive,answers,rearms,suspends;
static const char *input_line;
static int f_open(const char *p,int flags,...){
 if(strstr(p,"/control"))return 2000;
 if(!strcmp(p,"/dev/urandom"))return 2001;
 return open(p,flags,0600);
}
static int f_close(int f){return f>=2000?0:close(f);}
static int f_clock(clockid_t c,struct timespec *t){(void)c;t->tv_sec=frame/50;t->tv_nsec=(frame%50)*20000000;return 0;}
static FILE *f_fopen(const char *p,const char *mode){
 static char b[256];(void)mode;
 if(strstr(p,"/session"))snprintf(b,sizeof(b),"MF79U_CS_DRIVER 1 %u %u %u %u %u %u %u %u %u\n",kernel.epoch,kernel.enabled,kernel.desired,kernel.stage,kernel.id,kernel.incoming,kernel.mm,kernel.audio,kernel.fault);
 else if(strstr(p,"/caller"))snprintf(b,sizeof(b),"MF79U_CS_CALLER 1 %u %u anonymous\n",kernel.epoch,kernel.id);
 else if(strstr(p,"/pcm_info"))snprintf(b,sizeof(b),"MF79U_CS_PCM 1 %d 8000 160 320\n",kernel.stage==5 || kernel.stage==10);
 else assert(0);
 return fmemopen(b,strlen(b),"r");
}
static ssize_t f_read(int f,void *b,size_t n){
 if(f==2001){assert(n==4);*(unsigned *)b=99;return 4;}
 assert(f==0 && input_line);size_t size=strlen(input_line);assert(n>=size);memcpy(b,input_line,size);input_line=0;return size;
}
static ssize_t f_write(int f,const void *b,size_t n){
 assert(f==2000 && n<128);char line[128],name[16];unsigned e,id;memcpy(line,b,n);line[n]=0;
 assert(sscanf(line,"%15s %u %u",name,&e,&id)==3);
 if(!strcmp(name,"SESSION")){assert(!kernel.enabled && !kernel.id);kernel.epoch=e;}
 else {assert(e==kernel.epoch);
  if(!strcmp(name,"PING"))assert(!id);
  else if(!strcmp(name,"RESUME")){assert(!strcmp(line,"RESUME 99 0 3\n"));kernel.enabled=kernel.desired=1;}
  else if(!strcmp(name,"SUSPEND")){assert(!kernel.id && !alive);kernel.enabled=kernel.desired=0;suspends++;}
  else if(!strcmp(name,"DIAL")){assert(!kernel.id && !alive);kernel.id=id;kernel.stage=1;kernel.incoming=0;kernel.mm=0;}
  else if(!strcmp(name,"ANSWER")){assert(id==kernel.id && kernel.stage==9);kernel.stage=10;answers++;}
  else if(!strcmp(name,"HANGUP")){assert(id==kernel.id);kernel.stage=8;kernel.mm=kernel.audio=1;}
  else if(!strcmp(name,"REARM")){assert(id==kernel.id && !alive && kernel.mm && kernel.audio);kernel.id=kernel.stage=0;rearms++;}
  else assert(0);
 }return n;
}
static pid_t f_fork(void){assert(!alive);alive=1;starts++;return 4000;}
static int f_kill(pid_t p,int s){assert(p==4000 && s==SIGTERM);alive=0;stops++;return 0;}
static pid_t f_waitpid(pid_t p,int *status,int options){(void)status;(void)options;assert(p==4000);return alive?0:p;}
static int f_poll(struct pollfd *p,nfds_t n,int timeout){
 assert(n==1 && timeout==20);frame++;input_line=0;
 switch(frame){
 case 1:input_line="RESUME 99 0 3\n";break;
 case 3:input_line="DIAL 99 2 1234567\n";break;
 case 4:kernel.stage=5;break;
 case 2000:assert(alive && starts==1 && !stops);break;
 case 2004:input_line="HANGUP 99 2\n";break;
 case 2006:input_line="DIAL 99 3 1234567\n";break;
 case 2008:kernel.stage=5;break;
 case 2010:input_line="HANGUP 99 3\n";break;
 case 2012:kernel.id=4;kernel.stage=9;kernel.mm=0;kernel.incoming=1;break;
 case 2013:input_line="ANSWER 99 4\n";break;
 case 2014:assert(alive && starts==3 && kernel.stage==10);kernel.stage=5;break;
 case 2016:input_line="HANGUP 99 4\n";break;
 case 2018:input_line="SUSPEND 99 0\n";break;
 case 2020:input_line="QUIT 99 0\n";break;
 default:break;
 }assert(frame<2030);p->revents=input_line?POLLIN:0;return input_line?1:0;
}
int main(void){
 kernel.audio=1;char *args[]={"fixture","--owned-pipe",0};assert(adapter_main(2,args)==0);
 assert(starts==3 && stops==3 && rearms==3 && answers==1 && suspends>=1 && !kernel.id && !kernel.enabled);
 puts("PASS actual adapter: async MO ownership, 40s streaming, repeated calls, MT explicit answer, media close before rearm, suspension ACK");
 unlink(CS_ADAPTER_LOCK);
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'fixture.c';p.write_text(header+'\n'+(B/'src/cs-voice-adapter.c').read_text()+'\n'+tail)
 exe=Path(d)/'fixture'
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
(B/'build/cs-adapter-fixture.json').write_text(json.dumps({'physical_access':False,'actual_main_loop':True,'kernel_and_process_io_mocked':True,'repeated_calls':3,'streaming_seconds':40,'close_before_rearm':True},indent=2)+'\n')
