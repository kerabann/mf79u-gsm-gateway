/* Owned CS pipe adapter. No radio control or global ATH. Kernel epoch/id and
 * real MM/audio quiescence delimit calls; PCM child owns its socket exclusively. */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#ifndef CS_DRIVER_BASE
#define CS_DRIVER_BASE "/sys/mf79u_cs_voice"
#endif
#ifndef CS_ADAPTER_LOCK
#define CS_ADAPTER_LOCK "/dev/.mf79u-cs-adapter.lock"
#endif
#ifndef CS_PCM_BINARY
#define CS_PCM_BINARY "/mnt/userdata/mf79u/.mf79u-cs-pcm-bridge"
#endif
struct state {unsigned epoch,enabled,desired,stage,id,incoming,mm,audio,fault;};
static unsigned epoch,current_id,seen_id;static uint64_t dial_at;static int ready,connected,quitting,pending_suspend;
static pid_t media=-1;static volatile sig_atomic_t stopping;
static uint64_t ms(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000+t.tv_nsec/1000000;}
static int tracing;
static void trace(const char *event,int value){
    if(!tracing)return;
    int fd=open("/dev/.mf79u-cs-adapter-trace.log",O_WRONLY|O_APPEND|O_CREAT|O_NOFOLLOW,0600);
    if(fd>=0){struct stat s;if(!fstat(fd,&s) && s.st_size<8192){char b[128];
        int n=snprintf(b,sizeof(b),"CS_ADAPTER ms=%llu event=%s value=%d\n",(unsigned long long)ms(),event,value);
        if(n>0 && n<(int)sizeof(b))(void)write(fd,b,(size_t)n);}
        close(fd);}
}
static void signal_stop(int n){(void)n;stopping=1;}
static int state_read(struct state *s){
    FILE *f=fopen(CS_DRIVER_BASE "/session","r");if(!f)return -1;
    char b[256],extra;int ok=fgets(b,sizeof(b),f)!=NULL;fclose(f);
    if(!ok || sscanf(b,"MF79U_CS_DRIVER 1 %u %u %u %u %u %u %u %u %u %c",
        &s->epoch,&s->enabled,&s->desired,&s->stage,&s->id,&s->incoming,&s->mm,&s->audio,&s->fault,&extra)!=9)return -1;
    return s->enabled>1 || s->desired>1 || s->incoming>1 || s->mm>1 || s->audio>1 || s->fault>1 || s->stage>10?-1:0;
}
static int command(const char *name,unsigned e,unsigned id,const char *arg){
    if(!strcmp(name,"HANGUP") || !strcmp(name,"SUSPEND"))trace(name,0);
    char b[128];int n=snprintf(b,sizeof(b),"%s %u %u%s%s\n",name,e,id,arg?" ":"",arg?arg:"");
    int fd=open(CS_DRIVER_BASE "/control",O_WRONLY|O_CLOEXEC);
    int r=fd>=0 && n>0 && n<(int)sizeof(b) && write(fd,b,(size_t)n)==n?0:-1;
    if(fd>=0)close(fd);
    memset(b,0,sizeof(b));return r;
}
static void emit(const char *name,unsigned id){
    if(id)printf("CS_%s %u %u\n",name,epoch,id);else printf("CS_%s %u\n",name,epoch);
}
static int media_stop(void){
    if(media<1)return 0;
    kill(media,SIGTERM);
    uint64_t end=ms()+2000;
    do {if(waitpid(media,NULL,WNOHANG)==media){media=-1;return 0;}usleep(10000);}while(ms()<end);
    kill(media,SIGKILL);waitpid(media,NULL,0);media=-1;return 0;
}
static int media_start(void){
    trace("media_start",0);
    /* At most one call owns this reset-per-start RAM error file. It contains
     * startup errors and exit metadata only, never stdout PCM level windows. */
    int error=open("/dev/.mf79u-cs-pcm-error.log",O_CREAT|O_TRUNC|O_WRONLY|O_CLOEXEC|O_NOFOLLOW,0600);
    media=fork();if(media==0){int null=open("/dev/null",O_RDWR);if(null<0)_exit(126);
        dup2(null,0);dup2(null,1);if(error>=0)dup2(error,2);for(int f=3;f<256;f++)close(f);
        /* Physically compared CS-only emphasis. IMS uses its own process. */
        execl(CS_PCM_BINARY,CS_PCM_BINARY,"--stream-clarity",(char *)NULL);_exit(127);}
    if(error>=0)close(error);
    trace("media_fork",media<0?errno:0);
    return media<0?-1:0;
}
static int pcm_online(void){
    FILE *f=fopen(CS_DRIVER_BASE "/pcm_info","r");if(!f)return 0;
    char b[80];int ok=fgets(b,sizeof(b),f)!=NULL;fclose(f);
    return ok && !strcmp(b,"MF79U_CS_PCM 1 1 8000 160 320\n");
}
static void incoming(const struct state *s){
    char caller[34]="anonymous",b[128],extra;unsigned e=0,id=0;
    FILE *f=fopen(CS_DRIVER_BASE "/caller","r");if(f){
        if(fgets(b,sizeof(b),f) && sscanf(b,"MF79U_CS_CALLER 1 %u %u %33s %c",&e,&id,caller,&extra)==3 && e==epoch && id==s->id){
            if(strcmp(caller,"anonymous")){char *p=caller;if(*p=='+')p++;unsigned n=0;
                while(*p>='0' && *p<='9'){p++;n++;}if(*p || n<3 || n>32)strcpy(caller,"anonymous");}
        }else strcpy(caller,"anonymous");fclose(f);}
    printf("CS_INCOMING %u %u %s\n",epoch,s->id,caller);memset(caller,0,sizeof(caller));memset(b,0,sizeof(b));
}
static int recover(void){
    uint64_t end=ms()+80000,next=0;struct state s;
    while(ms()<end && !stopping){
        if(state_read(&s) || s.fault)return -1;
        if(!s.id && !s.stage && !s.enabled && !s.desired)return 0;
        if(ms()>=next){next=ms()+1000;
            command("PING",s.epoch,0,NULL);
            if(s.id){if(s.mm && s.audio){media_stop();command("REARM",s.epoch,s.id,NULL);}
                else command("HANGUP",s.epoch,s.id,NULL);}
            else command("SUSPEND",s.epoch,0,NULL);
        }usleep(20000);
    }return -1;
}
static int input(const char *b){
    char name[16],arg[34],extra;unsigned e=0,id=0;
    int n=sscanf(b,"%15s %u %u %33s %c",name,&e,&id,arg,&extra);
    if(n<3 || n>4 || e!=epoch)return -1;
    if(!strcmp(name,"QUIT") && n==3 && !id){quitting=1;return 0;}
    if(!strcmp(name,"RESUME") && !id && !current_id &&
       (n==3 || (n==4 && (!strcmp(arg,"2") || !strcmp(arg,"3")))))
        return command(name,epoch,0,n==4?arg:NULL);
    if(!strcmp(name,"SUSPEND") && n==3 && !id && !current_id)
        {int r=command(name,epoch,0,NULL);if(!r)pending_suspend=1;return r;}
    if(!strcmp(name,"DIAL") && n==4 && id && !current_id && ready){
        const char *p=arg;if(*p=='+')p++;unsigned digits=0;while(*p>='0' && *p<='9'){p++;digits++;}
        if(*p || digits<5 || digits>32)return -1;
        tracing=access("/dev/.mf79u-cs-clarity-test",F_OK)==0;
        if(tracing){int fd=open("/dev/.mf79u-cs-adapter-trace.log",O_CREAT|O_TRUNC|O_WRONLY|O_NOFOLLOW,0600);if(fd>=0)close(fd);}
        trace("dial",0);
        if(command(name,epoch,id,arg)){emit("ENDED",id);return -1;}
        current_id=id;connected=seen_id=0;dial_at=ms();return 0;
    }
    if((!strcmp(name,"ANSWER") || !strcmp(name,"HANGUP")) && n==3 && id==current_id && id)
        {trace("pipe_action",!strcmp(name,"HANGUP")?2:4);return command(name,epoch,id,NULL);}
    return -1;
}
int main(int argc,char **argv){
    if(argc!=2 || strcmp(argv[1],"--owned-pipe"))return 2;
    umask(077);int lock=open(CS_ADAPTER_LOCK,O_CREAT|O_RDWR|O_CLOEXEC,0600);
    if(lock<0 || flock(lock,LOCK_EX|LOCK_NB))return 1;
    signal(SIGTERM,signal_stop);signal(SIGINT,signal_stop);signal(SIGPIPE,SIG_IGN);
    setvbuf(stdout,NULL,_IONBF,0);
    if(recover())return 1;
    int random=open("/dev/urandom",O_RDONLY|O_CLOEXEC);
    if(random<0 || read(random,&epoch,sizeof(epoch))!=sizeof(epoch) || !epoch)return 1;
    close(random);
    if(command("SESSION",epoch,0,NULL))return 1;
    emit("HELLO",0);uint64_t ping=0,connected_at=0,exit_at=0,stop_at=0;unsigned previous=0;
    char line[128];size_t used=0;struct state s={0};
    for(;;){
        if(state_read(&s) || s.epoch!=epoch || s.fault){trace("invalid_state",s.fault);break;}
        if(s.stage!=previous)trace("stage",s.stage);
        if(stopping || quitting){if(!exit_at)exit_at=ms()+80000;
            if(ms()>=stop_at){stop_at=ms()+1000;
                if(s.id)command("HANGUP",epoch,s.id,NULL);else command("SUSPEND",epoch,0,NULL);
            }
            if(!s.id && !s.enabled && !s.desired)return 0;
            if(ms()>=exit_at)break;
        }
        if(ms()>=ping){ping=ms()+1000;if(command("PING",epoch,0,NULL))break;}
        if(s.enabled && s.desired && !ready){ready=1;emit("READY",0);}
        if(!s.enabled && !s.desired && (ready || pending_suspend)){trace("suspended",0);ready=pending_suspend=0;emit("SUSPENDED",0);}
        /* Initial/repeated SUSPEND needs an ACK even if already disabled. */
        if(s.id && !current_id){current_id=s.id;connected=0;previous=0;if(s.incoming)incoming(&s);else break;}
        if(s.id && s.id==current_id){
            seen_id=1;
            if(s.stage==4 && previous!=4)emit("ALERT",s.id);
            if(s.stage==5 || (s.incoming && s.stage==10)){
                if(!connected_at){connected_at=ms();if(media_start())command("HANGUP",epoch,s.id,NULL);}
                int media_status=0;
                if(media>0 && waitpid(media,&media_status,WNOHANG)==media){
                    trace("media_exit",media_status);
                    int error=open("/dev/.mf79u-cs-pcm-error.log",O_WRONLY|O_APPEND|O_NOFOLLOW);
                    if(error>=0){char b[80];int n=snprintf(b,sizeof(b),"CS_PCM_EXIT code=%d signal=%d\n",WIFEXITED(media_status)?WEXITSTATUS(media_status):-1,WIFSIGNALED(media_status)?WTERMSIG(media_status):0);
                        if(n>0 && n<(int)sizeof(b))(void)write(error,b,(size_t)n);
                        close(error);}
                    media=-1;command("HANGUP",epoch,s.id,NULL);}
                int online=pcm_online();
                if(s.stage==5 && !connected && media>0 && online){connected=1;emit("CONNECTED",s.id);}
                if(!online && ms()-connected_at>15000){trace("media_deadline",0);command("HANGUP",epoch,s.id,NULL);}
            }
            if(s.stage==8 && s.mm && s.audio){media_stop();command("REARM",epoch,s.id,NULL);}
            previous=s.stage;
        }
        if(current_id && !s.id && !s.stage && seen_id){media_stop();emit("ENDED",current_id);current_id=0;connected=0;connected_at=0;previous=0;tracing=0;}
        if(current_id && !seen_id && ms()-dial_at>5000)break;
        struct pollfd p={0,POLLIN,0};int r=poll(&p,1,20);if(r<0 && errno!=EINTR)break;
        if(r>0 && p.revents && !quitting){char data[128];ssize_t n=read(0,data,sizeof(data));
            if(n<=0){trace("pipe_eof",n);quitting=1;continue;}
            for(ssize_t i=0;i<n;i++){
                if(data[i]=='\n'){line[used]=0;
                    if(!strcmp(line,"SUSPEND") /* never a valid pipe command */){quitting=1;break;}
                    (void)input(line);
                    memset(line,0,sizeof(line));used=0;
                }else if(data[i] && data[i]!='\r' && used<sizeof(line)-1)line[used++]=data[i];
                else {quitting=1;break;}
            }memset(data,0,sizeof(data));
        }
    }
    if(ready)emit("NOT_READY",0);
    trace("loop_exit",0);
    media_stop();
    /* Driver lease clears only its own call if the adapter cannot complete. */
    return 1;
}
