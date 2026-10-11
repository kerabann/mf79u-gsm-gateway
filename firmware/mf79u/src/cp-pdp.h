#ifndef MF79U_CP_PDP_H
#define MF79U_CP_PDP_H
#include <stddef.h>
/* Translate confirmed CID5 CGCONTRDP data to the B03 IMS ZPDPACT result. */
int mf79u_pdp_translate(const char *details,char *reply,size_t capacity);
int mf79u_pdp_selftest(void);
#endif
