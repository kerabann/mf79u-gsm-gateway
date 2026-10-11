#ifndef MF79U_IPV4_FRAGMENTS_H
#define MF79U_IPV4_FRAGMENTS_H
#include <stddef.h>
#include <stdint.h>
typedef int (*ipv4_emit_fn)(void*,const unsigned char*,size_t);
/* Fragment one complete IPv4 datagram after ESP encryption. Nonzero ID is
 * shared by every fragment; each header receives its own length/checksum. */
int ipv4_emit_fragments(const unsigned char *packet,size_t size,unsigned mtu,
                        uint16_t id,ipv4_emit_fn emit,void *context);
#endif
