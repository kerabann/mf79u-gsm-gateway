#include "caller-id.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
    char out[40];
    const char *good="INVITE sip:x@pbx SIP/2.0\r\nFrom: \"Trunk account\" <sip:123456789@ims>\r\nP-Asserted-Identity: <tel:+35798765432>\r\n\r\n";
    assert(mf79u_caller_id(good,strlen(good),out) && !strcmp(out,"+35798765432"));
    const char *private="INVITE sip:x@pbx SIP/2.0\r\nPrivacy: id;user\r\nFrom: <sip:123456@ims>\r\n\r\n";
    assert(!mf79u_caller_id(private,strlen(private),out) && !strcmp(out,"anonymous"));
    const char *display="INVITE sip:x@pbx SIP/2.0\r\nFrom: \"+357123456\" <sip:trunk@ims>\r\n\r\n";
    assert(!mf79u_caller_id(display,strlen(display),out));
    const char *bad="INVITE sip:x@pbx SIP/2.0\r\nFrom: <sip:12345oops@ims>\r\n\r\n";
    assert(!mf79u_caller_id(bad,strlen(bad),out));
    const char *compact="INVITE sip:x@pbx SIP/2.0\r\nf: <sip:12345678@ims>;tag=x\r\n\r\n";
    assert(mf79u_caller_id(compact,strlen(compact),out) && !strcmp(out,"12345678"));
    puts("Caller ID tests passed: asserted identity, From, privacy and malformed input");return 0;
}
