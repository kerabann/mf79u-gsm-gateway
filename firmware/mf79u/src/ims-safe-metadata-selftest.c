#include "ims-safe-metadata.h"
#include <assert.h>
#include <stdio.h>
int main(void){
 struct mf79u_ims_scalar scalar;struct mf79u_ims_method method;
 errno=EAGAIN;
 assert(mf79u_ims_scalar("SOFTWARE media errno result=22",&scalar) && errno==EAGAIN);
 assert(!strcmp(scalar.tag,"ioctl_errno") && scalar.value==22);
 assert(mf79u_ims_scalar("SOFTWARE PCM preopen result=-1",&scalar) && scalar.value==-1);
 assert(mf79u_ims_scalar("SOFTWARE media ioctl result=1075082757",&scalar));
 assert(!mf79u_ims_scalar("SOFTWARE media result result=0",&scalar));
 assert(mf79u_ims_scalar("SOFTWARE media result result=-1",&scalar));
 assert(!mf79u_ims_scalar("SOFTWARE media ioctl result=1075082756",&scalar));
 assert(!mf79u_ims_scalar("SOFTWARE media ioctl result=1074820611",&scalar));
 const char *bad[]={"SOFTWARE media errno result=22 identity=private", "SOFTWARE media errno result=",
  "SOFTWARE media errno result= 22", "SOFTWARE media errno result=+22", "SOFTWARE media errno result=999999999999999999999",
  "SOFTWARE media errno result=2147483648", "SOFTWARE media errno result=-2147483649",
  "SOFTWARE media errno result=22\nprivate", "Unknown diagnostic result=1", "RX SIP response 200 bytes=123"};
 for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++)assert(!mf79u_ims_scalar(bad[i],&scalar));
 assert(mf79u_ims_method("TX_ESP protected SIP method CANCEL bytes=500",&method));
 assert(!strcmp(method.direction,"TX") && !strcmp(method.method,"CANCEL") && method.bytes==500);
 assert(mf79u_ims_method("RX_ESP verified SIP method BYE bytes=600",&method) && !strcmp(method.direction,"RX"));
 assert(mf79u_ims_method("TX SIP method REGISTER bytes=1913",&method));
 const char *unsafe[]={"TX SIP method PRIVATE bytes=500", "TX SIP method INVITE bytes=500 private",
  "AUTH SIP method INVITE bytes=500", "TX SIP method INVITE bytes=0", "TX SIP method INVITE bytes=7001",
  "TX SIP method INVITE bytes=999999999999999", "TX SIP method INVITE bytes=-1", "TX SIP method INVITE bytes=",
  "TX SIP method INVITE bytes=+500", "RX SIP method MESSAGE bytes=500\nprivate"};
 for(unsigned i=0;i<sizeof(unsafe)/sizeof(unsafe[0]);i++)assert(!mf79u_ims_method(unsafe[i],&method));
 puts("PASS exact IMS media scalars/methods; private suffixes, unknown tags and numeric overflow rejected");return 0;
}
