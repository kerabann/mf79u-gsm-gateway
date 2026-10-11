/* Read a non-consuming kernel ring snapshot, emit scrubbed fatal diagnostics. */
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/klog.h>
#include <time.h>
#include <unistd.h>
int main(int argc,char **argv) {
    long seconds=0;char *end;
    if(argc==2){seconds=strtol(argv[1],&end,10);if(*end || seconds<1 || seconds>180)return 2;}
    else if(argc!=1)return 2;
    setvbuf(stdout,NULL,_IONBF,0);
    char *buffer=calloc(1,262145);if(!buffer)return 1;
    unsigned long seen[2048]={0};unsigned used=0;
    time_t deadline=time(NULL)+seconds,last_heartbeat=0;
    do {
    int n=klogctl(3,buffer,262144);
    if(n<0){perror("read kernel snapshot");free(buffer);return 1;}
    if(!seconds)printf("Kernel snapshot bytes=%d\n",n);
    buffer[n]=0;
    unsigned hits=0;
    for(char *line=strtok(buffer,"\n");line;line=strtok(NULL,"\n")) {
        if(!strstr(line,"Oops") && !strstr(line,"panic") && !strstr(line,"BUG:") &&
           !strstr(line,"watchdog") && !strstr(line,"segfault") && !strstr(line,"reset") &&
           !strstr(line,"Call Trace") && !strstr(line,"PC is at") &&
           !strstr(line,"Unhandled fault") && !strstr(line,"Out of memory") &&
           !strstr(line,"Killed process") && !strstr(line,"oom-killer"))continue;
        unsigned long hash=5381;for(const unsigned char *p=(void*)line;*p;p++)hash=hash*33+*p;
        unsigned i;for(i=0;i<used;i++)if(seen[i]==hash)break;
        if(seconds && i<used)continue;
        if(used<2048)seen[used++]=hash;
        hits++;size_t len=strlen(line);if(len>200)len=200;
        for(size_t i=0;i<len;) {
            size_t j=i;while(j<len && isxdigit((unsigned char)line[j]))j++;
            if(j-i>=16){fputs("[redacted]",stdout);i=j;}
            else {putchar(line[i]);i++;}
        }
        putchar('\n');
    }
    if(!seconds)printf("Fatal/reset diagnostic lines=%u\n",hits);
    else if(time(NULL)-last_heartbeat>=5){
        FILE *f=fopen("/proc/uptime","r");double uptime=0;
        if(f){if(fscanf(f,"%lf",&uptime)!=1)uptime=0;fclose(f);}
        printf("ALIVE uptime=%.2f\n",uptime);last_heartbeat=time(NULL);
    }
    if(seconds)usleep(200000);
    }while(seconds && time(NULL)<deadline);
    free(buffer);return 0;
}
