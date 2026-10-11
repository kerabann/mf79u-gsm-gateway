/* Read-only feature check. No bind, connect, payloads, or key material. */
#include <errno.h>
#include <linux/netlink.h>
#include <net/ethernet.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
int main(void) {
    const struct {const char *name;int domain,type,protocol;} checks[]={
        {"IPv4 UDP",AF_INET,SOCK_DGRAM,0},
        {"IPv4 RAW ESP",AF_INET,SOCK_RAW,50},
        {"IPv4 RAW UDP",AF_INET,SOCK_RAW,17},
        {"NETLINK_ROUTE",AF_NETLINK,SOCK_RAW,NETLINK_ROUTE},
        {"NETLINK_XFRM",AF_NETLINK,SOCK_RAW,NETLINK_XFRM},
        {"PACKET all",AF_PACKET,SOCK_DGRAM,0x0300},
        {"PF_KEY v2",AF_KEY,SOCK_RAW,2}
    };
    for(unsigned i=0;i<sizeof(checks)/sizeof(checks[0]);i++) {
        errno=0;int fd=socket(checks[i].domain,checks[i].type,checks[i].protocol);
        if(fd<0)printf("%s: errno=%d %s\n",checks[i].name,errno,strerror(errno));
        else {printf("%s: available\n",checks[i].name);close(fd);}
    }
    return 0;
}
