/* Read-only UDP interface selectors; no packet/identity/key access. */
#include <arpa/inet.h>
#include <linux/inet_diag.h>
#include <linux/netlink.h>
#include <linux/sock_diag.h>
#include <net/if.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
int main(void){
 FILE *f=fopen("/dev/mf79u/vowifi/address","r");char text[64];struct in_addr vip;
 if(!f)return 1;int ok=fgets(text,sizeof(text),f)!=NULL;fclose(f);text[strcspn(text,"\r\n")]=0;if(!ok || inet_pton(AF_INET,text,&vip)!=1)return 1;
 int fd=socket(AF_NETLINK,SOCK_RAW,NETLINK_SOCK_DIAG);if(fd<0)return 1;struct timeval timeout={.tv_sec=2};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
 struct {struct nlmsghdr header;struct inet_diag_req_v2 query;} request={.header={.nlmsg_len=sizeof(request),.nlmsg_type=SOCK_DIAG_BY_FAMILY,.nlmsg_flags=NLM_F_REQUEST|NLM_F_DUMP,.nlmsg_seq=7},.query={.sdiag_family=AF_INET,.sdiag_protocol=IPPROTO_UDP,.idiag_states=~0u}};
 struct sockaddr_nl to={.nl_family=AF_NETLINK};if(sendto(fd,&request,sizeof(request),0,(void*)&to,sizeof(to))!=sizeof(request))return 1;
 char buffer[8192];int n;
 while((n=recv(fd,buffer,sizeof(buffer),0))>0)for(struct nlmsghdr *h=(void*)buffer;NLMSG_OK(h,(unsigned)n);h=NLMSG_NEXT(h,n)){
  if(h->nlmsg_type==NLMSG_DONE){close(fd);return 0;}
  if(h->nlmsg_type==NLMSG_ERROR){printf("UDP_DIAG error=%d\n",((struct nlmsgerr*)NLMSG_DATA(h))->error);close(fd);return 1;}
  if(h->nlmsg_len<NLMSG_LENGTH(sizeof(struct inet_diag_msg)))continue;struct inet_diag_msg *s=NLMSG_DATA(h);if(s->id.idiag_src[0]!=vip.s_addr)continue;
  char iface[IF_NAMESIZE]="none";if(s->id.idiag_if)if_indextoname(s->id.idiag_if,iface);
  printf("VOWIFI_UDP port=%u interface=%s inode=%u\n",ntohs(s->id.idiag_sport),iface,s->idiag_inode);
 }
 close(fd);return 1;
}
