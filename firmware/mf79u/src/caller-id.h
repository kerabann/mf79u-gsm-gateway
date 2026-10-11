#ifndef MF79U_CALLER_ID_H
#define MF79U_CALLER_ID_H
#include <stddef.h>
/* Returns a validated telephone number, or anonymous. No SIP display names. */
int mf79u_caller_id(const void *packet,size_t length,char out[40]);
#endif
