#include <networking/tun_device.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(void){
 tun_device_t *d=tun_device_create(NULL);if(!d){puts("packet_device_create_failed");return 1;}
 host_t *a=host_create_from_string("198.18.1.1",0);int result=1;
 if(!a || !d->set_address(d,a,32) || !d->up(d)){puts("address_or_up_failed");goto done;}
 if(system("ip route add 198.18.1.2/32 dev vowifi0")){puts("fixture_route_failed");goto done;}
 int fd=socket(AF_INET,SOCK_DGRAM,0);struct sockaddr_in local={.sin_family=AF_INET,.sin_port=htons(19879)},peer={.sin_family=AF_INET,.sin_port=htons(19880)};
 inet_pton(AF_INET,"198.18.1.1",&local.sin_addr);inet_pton(AF_INET,"198.18.1.2",&peer.sin_addr);
 if(bind(fd,(void*)&local,sizeof(local)) || sendto(fd,"fixture",7,0,(void*)&peer,sizeof(peer))!=7){close(fd);goto done;}
 fd_set set;FD_ZERO(&set);FD_SET(d->get_fd(d),&set);struct timeval timeout={.tv_sec=2};chunk_t pkt=chunk_empty;
 int selected=select(d->get_fd(d)+1,&set,NULL,NULL,&timeout);int captured=selected==1 && d->read_packet(d,&pkt);printf("fixture_capture selected=%d read=%d length=%u\n",selected,captured,(unsigned)pkt.len);
 if(captured && pkt.len==35 && !memcmp(pkt.ptr+28,"fixture",7)){
  /* Swap addresses and UDP ports, clear checksums; IP_HDRINCL supplies IPv4. */
  memcpy(pkt.ptr+12,&peer.sin_addr,4);memcpy(pkt.ptr+16,&local.sin_addr,4);memcpy(pkt.ptr+20,&peer.sin_port,2);memcpy(pkt.ptr+22,&local.sin_port,2);pkt.ptr[10]=pkt.ptr[11]=pkt.ptr[26]=pkt.ptr[27]=0;
  int injected=d->write_packet(d,pkt);printf("fixture_injection success=%d\n",injected);if(injected){FD_ZERO(&set);FD_SET(fd,&set);timeout.tv_sec=2;timeout.tv_usec=0;char buf[16];if(select(fd+1,&set,NULL,NULL,&timeout)==1 && recv(fd,buf,sizeof(buf),0)==7 && !memcmp(buf,"fixture",7))result=0;}
 }
 free(pkt.ptr);close(fd);system("ip route del 198.18.1.2/32 dev vowifi0");
 done:DESTROY_IF(a);d->destroy(d);puts(result?"packet_adapter_duplex_failed":"PASS portless bridge adapter: outbound capture and inbound UDP injection");return result;
}
