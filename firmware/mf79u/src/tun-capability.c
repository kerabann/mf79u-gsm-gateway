/* Temporary TUN capability probe. No IP address, route or traffic is created. */
#include <errno.h>
#include <fcntl.h>
#include <linux/if_tun.h>
#include <net/if.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>
int main(void) {
    const char *path="/dev/.mf79u-tun-capability";
    if(mknod(path,S_IFCHR|0600,makedev(10,200))){perror("temporary TUN node");return 1;}
    int fd=open(path,O_RDWR);int saved=errno;
    unlink(path);
    if(fd<0){printf("TUN open failed errno=%d\n",saved);return 2;}
    struct ifreq interface;memset(&interface,0,sizeof(interface));
    strcpy(interface.ifr_name,"mf79probe0");interface.ifr_flags=IFF_TUN|IFF_NO_PI;
    int result=ioctl(fd,TUNSETIFF,&interface);saved=errno;
    if(result<0)printf("TUN interface failed errno=%d\n",saved);
    else printf("PASS temporary TUN created; no address, route or traffic\n");
    close(fd); /* Non-persistent interface is removed here. */
    return result<0?3:0;
}
