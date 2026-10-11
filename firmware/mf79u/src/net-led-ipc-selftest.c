/* Standalone public synthetic URCs: no native IMS library, CP, or SIM call. */
#include "net-led-policy.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv){
    (void)argv;if(argc!=1)return 2;
    const char *events[]={"\r\nRING\r\n^DSCI: 6,1,4\r\n","RING","^DSCI: 6,1,6\r\n^CEND: 6,0,101","RING","^CONN: 7,0","^CEND: 7,0,101","^ORIG: 3,0"};
    for(unsigned i=0;i<sizeof(events)/sizeof(events[0]);i++){
        mf79u_led_notify(events[i],strlen(events[i]));
        printf("SYNTHETIC IPC stage=%u\n",i+1);fflush(stdout);sleep(1);
        if(system("/dev/.mf79u-net-led-app --status"))return 1;
    }
    puts("LED IPC test result=0; sender exits to test automatic idle recovery");return 0;
}
