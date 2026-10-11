#define _GNU_SOURCE
#include "net-led-policy.h"
#include "cp-ipc.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/mount.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define DIR "/dev/.mf79u-net-led"
#define DEMO_MAGIC 0x4d464c32u
#define STATUS_MAGIC 0x4d464c33u
static const char *channels[]={"net_red","net_green","net_blue","wifi_blue"};
static int led_fd[4]={-1,-1,-1,-1},old[4],bound[4],control=-1,lockfd=-1;
static struct mf79u_cp radio={.tx=-1,.rx=-1};
static volatile sig_atomic_t stopping;
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void stop(int signal_number){(void)signal_number;stopping=1;}
static void paths(unsigned i,char *target,char *sink){
    snprintf(target,160,"/sys/class/leds/led:%s/brightness",channels[i]);
    snprintf(sink,160,DIR "/%s.sink",channels[i]);
}
static int same_file(const char *a,const char *b){
    struct stat x,y;return !stat(a,&x) && !stat(b,&y) && x.st_dev==y.st_dev && x.st_ino==y.st_ino;
}
static int brightness(unsigned i){
    char text[24];if(lseek(led_fd[i],0,SEEK_SET)<0)return -1;
    ssize_t n=read(led_fd[i],text,sizeof(text)-1);if(n<1)return -1;text[n]=0;return atoi(text);
}
static int set_brightness(unsigned i,int value){
    char text[24];int n=snprintf(text,sizeof(text),"%d\n",value);
    return lseek(led_fd[i],0,SEEK_SET)<0 || write(led_fd[i],text,(size_t)n)!=n?-1:0;
}
static unsigned hardware_mask(void){unsigned mask=0;for(unsigned i=0;i<3;i++)if(brightness(i)>0)mask|=1u<<i;return mask;}
static int set_color(unsigned color){
    for(unsigned i=0;i<3;i++)if(!(color&(1u<<i)) && set_brightness(i,0))return -1;
    for(unsigned i=0;i<3;i++)if((color&(1u<<i)) && set_brightness(i,1))return -1;
    return 0;
}
static void cleanup(void){
    if(control>=0){close(control);unlink(MF79U_LED_SOCKET);}
    for(unsigned i=0;i<4;i++){
        char target[160],sink[160];paths(i,target,sink);
        if(bound[i] && same_file(target,sink))umount2(target,MNT_DETACH);
        if(led_fd[i]>=0){set_brightness(i,old[i]);close(led_fd[i]);}
    }
    if(lockfd>=0)close(lockfd);
    mf79u_cp_close(&radio);
}
static int prepare(void){
    if(mkdir(DIR,0700) && errno!=EEXIST)return -1;
    struct stat dir;if(lstat(DIR,&dir) || !S_ISDIR(dir.st_mode) || dir.st_uid!=0)return -1;
    lockfd=open(DIR "/lock",O_CREAT|O_RDWR|O_NOFOLLOW,0600);
    if(lockfd<0 || flock(lockfd,LOCK_EX|LOCK_NB))return -1;
    for(unsigned i=0;i<4;i++){
        char target[160],sink[160],trigger[160],text[256];paths(i,target,sink);
        /* Recover only a stale bind of our own exact inode, never a foreign mount. */
        if(same_file(target,sink) && umount2(target,MNT_DETACH))return -1;
        snprintf(trigger,sizeof(trigger),"/sys/class/leds/led:%s/trigger",channels[i]);
        int fd=open(trigger,O_RDONLY);if(fd<0)return -1;
        ssize_t n=read(fd,text,sizeof(text)-1);close(fd);if(n<1)return -1;text[n]=0;
        if(strncmp(text,"[none]",6)){errno=EBUSY;return -1;}
        led_fd[i]=open(target,O_RDWR);if(led_fd[i]<0)return -1;
        old[i]=brightness(i);if(old[i]<0)return -1;
        fd=open(sink,O_CREAT|O_RDWR|O_NOFOLLOW,0600);if(fd<0)return -1;
        struct stat st;if(fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_uid!=0){close(fd);return -1;}close(fd);
        /* Saved FDs address actual GPIOs. Competing sysfs writers reach RAM;
         * the vendor LED service is disabled by the owned boot configuration. */
        if(mount(sink,target,NULL,MS_BIND,NULL))return -1;
        bound[i]=1;
    }
    control=socket(AF_UNIX,SOCK_DGRAM,0);if(control<0)return -1;
    int one=1;if(setsockopt(control,SOL_SOCKET,SO_PASSCRED,&one,sizeof(one)))return -1;
    struct sockaddr_un address={.sun_family=AF_UNIX};strcpy(address.sun_path,MF79U_LED_SOCKET);
    unlink(address.sun_path);if(bind(control,(struct sockaddr*)&address,sizeof(address)) || chmod(address.sun_path,0600))return -1;
    return 0;
}
static int registration(void){
    if(radio.rx<0 && mf79u_cp_open(&radio))return -1;
    char reply[4096];
    const char *commands[]={"AT+CEREG?","AT+CGREG?","AT+CREG?"};
    const char *prefixes[]={"+CEREG:","+CGREG:","+CREG:"};int valid=0;
    for(unsigned i=0;i<3;i++) {
        if(mf79u_cp_query(&radio,commands[i],reply,sizeof(reply),2)<0)continue;
        char *p=strstr(reply,prefixes[i]);int mode,state;
        if(!p || sscanf(p+strlen(prefixes[i])," %d,%d",&mode,&state)!=2 || !strstr(reply,"\r\nOK\r\n"))continue;
        valid=1;if(state==1 || state==5)return 1;
    }
    return valid?0:-1;
}
static int wifi_active(void){
    const char *names[]={"wlan0","wlan0-vxd"};
    for(unsigned i=0;i<2;i++){
        char path[128];snprintf(path,sizeof(path),"/sys/class/net/%s/flags",names[i]);
        FILE *f=fopen(path,"r");if(!f)continue;
        unsigned flags=0;int valid=fscanf(f,"%x",&flags)==1;fclose(f);
        if(valid && (flags&1))return 1;
    }
    return 0;
}
static int registered_service(void){
    /* Atomic, bounded status from our live controller; never use stale vendor
     * IMS flags after a SIM change or the exit of the private IMS engine. */
    char text[2048],path[80],exe[256];
    FILE *f=fopen("/dev/.mf79u-native-status.json","r");if(!f)return 0;
    size_t n=fread(text,1,sizeof(text)-1,f);int eof=feof(f);fclose(f);
    if(!eof)return 0;
    text[n]=0;
    const char *pid=strstr(text,"\"pid\":");
    if(!pid || strstr(text,"\"state\":\"stopped\""))return 0;
    char *end;long owner=strtol(pid+6,&end,10);
    if(owner<2 || owner>2147483647L || end==pid+6 || *end!=',' || kill((pid_t)owner,0))return 0;
    snprintf(path,sizeof(path),"/proc/%ld/exe",owner);
    ssize_t length=readlink(path,exe,sizeof(exe)-1);if(length<1)return 0;exe[length]=0;
    const char *name=strrchr(exe,'/');if(!name)return 0;
    if(strcmp(name+1,".mf79u-native-gateway") && strcmp(name+1,"mf79u-native-gateway"))return 0;
    return strstr(text,"\"imsReady\":true")?(strstr(text,"\"imsAccess\":\"WIFI\"")?2:1):0;
}
static int vowifi_only(void){
    /* Persisted preference is available before native starts at boot. */
    FILE *f=fopen("/mnt/userdata/mf79u/gateway.ini","r");if(!f)return 0;
    char line[1024];int only=0;
    while(fgets(line,sizeof(line),f))if(!strncmp(line,"voice_mode=",11)){
        line[strcspn(line,"\r\n")]=0;only=!strcmp(line+11,"VOWIFI") || !strcmp(line+11,"VOWIFI_SMS");break;
    }
    memset(line,0,sizeof(line));fclose(f);return only;
}
static int client(int demo){
    umask(0077);int fd=socket(AF_UNIX,SOCK_DGRAM,0);if(fd<0)return 1;
    struct sockaddr_un local={.sun_family=AF_UNIX},peer={.sun_family=AF_UNIX};
    snprintf(local.sun_path,sizeof(local.sun_path),DIR "/client-%ld.sock",(long)getpid());strcpy(peer.sun_path,MF79U_LED_SOCKET);
    unlink(local.sun_path);if(bind(fd,(struct sockaddr*)&local,sizeof(local))){close(fd);return 1;}
    struct timeval timeout={.tv_sec=2};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    int result=0;const unsigned colors[]={1,4,3,2,5};
    for(unsigned i=0;i<(demo?6u:1u);i++){
        struct mf79u_led_event event={.magic=demo?DEMO_MAGIC:STATUS_MAGIC,.state=demo?(i<5?(int)colors[i]:-1):0};
        if(sendto(fd,&event,sizeof(event),0,(struct sockaddr*)&peer,sizeof(peer))!=(ssize_t)sizeof(event)){perror("LED service");result=1;break;}
        if(demo){if(i<5){printf("DEMO synthetic color mask=%u\n",colors[i]);fflush(stdout);sleep(1);}}
        else{char text[160];ssize_t n=recv(fd,text,sizeof(text)-1,0);if(n<1){result=1;break;}text[n]=0;puts(text);}
    }
    close(fd);unlink(local.sun_path);return result;
}
int main(int argc,char **argv){
    if(argc==2 && !strcmp(argv[1],"--selftest")){int n=mf79u_led_selftest();printf("LED policy selftest=%d\n",n);return n;}
    if(argc==2 && !strcmp(argv[1],"--status"))return client(0);
    if(argc==2 && !strcmp(argv[1],"--demo"))return client(1);
    if(argc!=1)return 2;
    signal(SIGINT,stop);signal(SIGTERM,stop);signal(SIGHUP,stop);signal(SIGPIPE,SIG_IGN);
    if(prepare()){perror("NET LED setup");cleanup();return 1;}
    struct mf79u_led_calls calls;mf79u_led_clear(&calls);pid_t owner=0;
    int registered=0,ims_registered=0,wifi_only=0,demo=-1;double next_poll=0,last_ok=0,demo_until=0;unsigned color=0;
    if(set_color(1)){cleanup();return 1;}
    while(!stopping){
        double t=now();
        if(t>=next_poll){int value=registration();if(value>=0){registered=value;last_ok=t;}else if(t-last_ok>10)registered=0;ims_registered=registered_service();wifi_only=vowifi_only();next_poll=now()+2;}
        if(owner && kill(owner,0) && errno==ESRCH){mf79u_led_clear(&calls);owner=0;}
        if(!registered && ims_registered!=2)mf79u_led_clear(&calls);
        if(demo>=0 && now()>=demo_until)demo=-1;
        unsigned wanted=demo>=0?(unsigned)demo:mf79u_led_mode_color(registered,ims_registered!=0,ims_registered==2,wifi_only,&calls);
        if(wanted!=color || hardware_mask()!=wanted){if(set_color(wanted)){perror("NET LED update");break;}color=wanted;}
        if(set_brightness(3,wifi_active())){perror("Wi-Fi LED update");break;}
        fd_set set;FD_ZERO(&set);FD_SET(control,&set);struct timeval timeout={.tv_usec=100000};
        if(select(control+1,&set,NULL,NULL,&timeout)<=0)continue;
        struct mf79u_led_event event;struct sockaddr_un sender;struct iovec iov={&event,sizeof(event)};
        char ancillary[CMSG_SPACE(sizeof(struct ucred))];
        struct msghdr message={.msg_name=&sender,.msg_namelen=sizeof(sender),.msg_iov=&iov,.msg_iovlen=1,.msg_control=ancillary,.msg_controllen=sizeof(ancillary)};
        ssize_t n=recvmsg(control,&message,MSG_DONTWAIT);if(n!=(ssize_t)sizeof(event) || (message.msg_flags&(MSG_TRUNC|MSG_CTRUNC)))continue;
        struct ucred *credentials=NULL;
        for(struct cmsghdr *c=CMSG_FIRSTHDR(&message);c;c=CMSG_NXTHDR(&message,c))
            if(c->cmsg_level==SOL_SOCKET && c->cmsg_type==SCM_CREDENTIALS && c->cmsg_len>=CMSG_LEN(sizeof(struct ucred)))credentials=(struct ucred*)CMSG_DATA(c);
        if(!credentials || credentials->uid!=0)continue;
        if(event.magic==STATUS_MAGIC){
            char text[224];int length=snprintf(text,sizeof(text),"{\"registered\":%s,\"ims_registered\":%s,\"color_mask\":%u,\"hardware_mask\":%u,\"wifi\":%s,\"demo\":%s}",registered?"true":"false",ims_registered?"true":"false",color,hardware_mask(),brightness(3)>0?"true":"false",demo>=0?"true":"false");
            sendto(control,text,(size_t)length,MSG_DONTWAIT,(struct sockaddr*)&sender,message.msg_namelen);
        }else if(event.magic==DEMO_MAGIC && (event.state==-1 || event.state==1 || event.state==2 || event.state==3 || event.state==4 || event.state==5)){
            demo=event.state;demo_until=now()+2;
        }else if(event.magic==MF79U_LED_MAGIC){
            if(owner && owner!=credentials->pid && !kill(owner,0))continue;
            if(!mf79u_led_apply(&calls,&event))owner=credentials->pid;
        }
    }
    cleanup();return 0;
}
