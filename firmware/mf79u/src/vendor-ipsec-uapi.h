/* B03 libsoftap::ipsec_set fields recovered from checked disassembly offsets. */
#ifndef MF79U_VENDOR_IPSEC_UAPI_H
#define MF79U_VENDOR_IPSEC_UAPI_H
#include <stddef.h>
#include <stdint.h>
struct vendor_ipsec_sa {
    char direction[8];uint32_t family;uint16_t sport,dport;
    char src4[32],dst4[32],src6[64],dst6[64];
    char authentication_key_hex[64],encryption_key_hex[64];
    uint32_t spi;
    char protocol[16],mode[16],encryption_algorithm[16],authentication_algorithm[16];
};
_Static_assert(sizeof(struct vendor_ipsec_sa)==404,"B03 IPsec ABI size");
_Static_assert(offsetof(struct vendor_ipsec_sa,authentication_key_hex)==208,"auth key offset");
_Static_assert(offsetof(struct vendor_ipsec_sa,spi)==336,"SPI offset");
#endif
