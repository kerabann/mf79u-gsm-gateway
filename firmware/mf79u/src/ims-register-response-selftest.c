#include "ims-register-response.h"
#include <assert.h>
#include <stdio.h>
int main(void){
 const char *registered="SIP/2.0 200 OK\r\nCSeq: 2 REGISTER\r\n\r\n";
 const char *rejected="SIP/2.0 500 Error\r\ncseq:\t7 REGISTER\r\n\r\n";
 const char *message="SIP/2.0 500 Error\r\nCSeq: 7 MESSAGE\r\n\r\nCSeq: 8 REGISTER\r\n";
 const char *body="SIP/2.0 500 Error\r\n\r\nCSeq: 8 REGISTER\r\n";
 const char *bad="SIP/2.0 500 Error\r\nCSeq: REGISTER\r\n\r\n";
 assert(mf79u_register_response(registered,strlen(registered))==200);
 assert(mf79u_register_response(rejected,strlen(rejected))==500);
 assert(!mf79u_register_response(message,strlen(message)));
 assert(!mf79u_register_response(body,strlen(body)));
 assert(!mf79u_register_response(bad,strlen(bad)));
 for(size_t n=0;n<12;n++)assert(!mf79u_register_response(rejected,n));
 puts("PASS bounded REGISTER status; MESSAGE/body/malformed/truncation ignored");return 0;
}
