/* GPL-2.0-or-later. MF79U userspace IPsec packet adapter for B03 without TUN.
 * Owned, portless NOARP bridge carries only locally sourced inner packets.
 * Authenticated inbound packets are injected through an IP_HDRINCL socket.
 * No USB/WLAN bridge membership or kernel code is modified. */
#include <networking/tun_device.h>
#include "vowifi-ipv4-checksum.h"
#include <linux/if_packet.h>
#include <linux/if_ether.h>
#include <linux/sockios.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <string.h>
#define IFACE "vowifi0"
#define OWNER "/dev/mf79u/vowifi/interface-owner"
typedef struct {tun_device_t public;int packet,raw,ctl,mtu;host_t *address;uint8_t mask;} device;
static int control(device *d,int cmd,struct ifreq *req){strcpy(req->ifr_name,IFACE);return ioctl(d->ctl,cmd,req);}
static bool read_packet(tun_device_t *p,chunk_t *out){device *d=(void*)p;unsigned char buf[65536];struct sockaddr_ll peer;socklen_t len=sizeof(peer);ssize_t n;
 do{n=recvfrom(d->packet,buf,sizeof(buf),0,(void*)&peer,&len);if(n<0){if(getenv("MF79U_PACKET_FIXTURE"))fprintf(stderr,"packet_read_errno=%d\n",errno);return FALSE;}if(getenv("MF79U_PACKET_FIXTURE"))fprintf(stderr,"packet_received length=%ld type=%u first=%u\n",(long)n,peer.sll_pkttype,n>0?buf[0]:0);
 }while(peer.sll_pkttype!=PACKET_OUTGOING);
 if(getenv("MF79U_PACKET_FIXTURE"))fprintf(stderr,"packet_metadata length=%ld first=%u type=%u\n",(long)n,n>0?buf[0]:0,peer.sll_pkttype);
 size_t bytes;if(!mf79u_vowifi_checksum(buf,(size_t)n,&bytes))return FALSE;*out=chunk_clone(chunk_create(buf,bytes));return TRUE;}
static bool write_packet(tun_device_t *p,chunk_t packet){device *d=(void*)p;if(packet.len<20 || (packet.ptr[0]>>4)!=4)return FALSE;struct sockaddr_in to={.sin_family=AF_INET};memcpy(&to.sin_addr,packet.ptr+16,4);return sendto(d->raw,packet.ptr,packet.len,0,(void*)&to,sizeof(to))==(ssize_t)packet.len;}
static bool set_address(tun_device_t *p,host_t *a,uint8_t mask){device *d=(void*)p;struct ifreq req={0};if(a->get_family(a)!=AF_INET)return FALSE;memcpy(&req.ifr_addr,a->get_sockaddr(a),sizeof(struct sockaddr_in));if(control(d,SIOCSIFADDR,&req))return FALSE;host_t *m=host_create_netmask(AF_INET,mask);if(!m)return FALSE;memcpy(&req.ifr_addr,m->get_sockaddr(m),sizeof(struct sockaddr_in));m->destroy(m);if(control(d,SIOCSIFNETMASK,&req))return FALSE;DESTROY_IF(d->address);d->address=a->clone(a);d->mask=mask;return TRUE;}
static host_t *get_address(tun_device_t *p,uint8_t *mask){device *d=(void*)p;if(mask)*mask=d->mask;return d->address;}
static bool up(tun_device_t *p){device *d=(void*)p;struct ifreq req={0};if(control(d,SIOCGIFFLAGS,&req))return FALSE;req.ifr_flags|=IFF_UP|IFF_NOARP;return !control(d,SIOCSIFFLAGS,&req);}
static bool set_mtu(tun_device_t *p,int mtu){device *d=(void*)p;struct ifreq req={0};req.ifr_mtu=mtu;if(control(d,SIOCSIFMTU,&req))return FALSE;d->mtu=mtu;return TRUE;}
static int get_mtu(tun_device_t *p){return ((device*)p)->mtu;}
static char *get_name(tun_device_t *p){(void)p;return IFACE;}
static int get_fd(tun_device_t *p){return ((device*)p)->packet;}
static void destroy(tun_device_t *p){device *d=(void*)p;close(d->packet);close(d->raw);struct ifreq req={0};if(!control(d,SIOCGIFFLAGS,&req)){req.ifr_flags&=~IFF_UP;control(d,SIOCSIFFLAGS,&req);}ioctl(d->ctl,SIOCBRDELBR,IFACE);unlink(OWNER);close(d->ctl);DESTROY_IF(d->address);free(d);}
tun_device_t *tun_device_create(const char *template){(void)template;if(if_nametoindex(IFACE))return NULL;device *d=calloc(1,sizeof(*d));if(!d)return NULL;
 d->ctl=socket(AF_INET,SOCK_DGRAM,0);d->packet=socket(AF_PACKET,SOCK_DGRAM,htons(ETH_P_ALL));d->raw=socket(AF_INET,SOCK_RAW,IPPROTO_RAW);int one=1;
 if(d->ctl<0 || d->packet<0 || d->raw<0 || setsockopt(d->raw,IPPROTO_IP,IP_HDRINCL,&one,sizeof(one)) || ioctl(d->ctl,SIOCBRADDBR,IFACE))goto fail;
 struct timeval timeout={.tv_sec=1};setsockopt(d->packet,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
 struct sockaddr_ll addr={.sll_family=AF_PACKET,.sll_protocol=htons(ETH_P_ALL),.sll_ifindex=(int)if_nametoindex(IFACE)};

 d->public=(tun_device_t){.read_packet=read_packet,.write_packet=write_packet,.set_address=set_address,.get_address=get_address,.up=up,.set_mtu=set_mtu,.get_mtu=get_mtu,.get_name=get_name,.get_fd=get_fd,.destroy=destroy};
 int owner=open(OWNER,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(owner<0)goto cleanup;
 int recorded=dprintf(owner,"%ld %u\n",(long)getpid(),if_nametoindex(IFACE));close(owner);if(recorded<=0){unlink(OWNER);goto cleanup;}
 if(!set_mtu(&d->public,1400) || !up(&d->public) || bind(d->packet,(void*)&addr,sizeof(addr)))goto cleanup;return &d->public;
 cleanup:{struct ifreq req={0};if(!control(d,SIOCGIFFLAGS,&req)){req.ifr_flags&=~IFF_UP;control(d,SIOCSIFFLAGS,&req);}ioctl(d->ctl,SIOCBRDELBR,IFACE);unlink(OWNER);}
 fail:if(d->ctl>=0)close(d->ctl);if(d->packet>=0)close(d->packet);if(d->raw>=0)close(d->raw);free(d);return NULL;}
