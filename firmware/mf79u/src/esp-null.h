#ifndef MF79U_ESP_NULL_H
#define MF79U_ESP_NULL_H
#include <stddef.h>
#include <stdint.h>
/* RFC 4303 transport ESP, NULL encryption, 96-bit integrity, no ESN.
 * Key bytes remain caller-owned RAM. This layer has no I/O or logging. */
struct esp_null_sa {uint32_t spi,tx_sequence,rx_highest;uint64_t rx_window;};
typedef int (*esp_digest_fn)(void *context,const unsigned char *data,size_t len,
                             unsigned char digest[32]);
typedef int (*esp_cipher_fn)(void *context,int encrypt,const unsigned char iv[16],
                            const unsigned char *input,size_t len,unsigned char *output);
typedef int (*esp_random_fn)(void *context,unsigned char *output,size_t len);
int esp_null_encode(struct esp_null_sa *sa,const unsigned char *udp,size_t len,
                    unsigned char *out,size_t capacity,esp_digest_fn digest,void *context);
int esp_null_decode(struct esp_null_sa *sa,const unsigned char *packet,size_t len,
                    unsigned char *udp,size_t capacity,esp_digest_fn digest,void *context);
int esp_cbc_encode(struct esp_null_sa *sa,const unsigned char *udp,size_t len,
                   unsigned char *out,size_t capacity,esp_digest_fn digest,
                   esp_cipher_fn cipher,esp_random_fn random,void *context);
int esp_cbc_decode(struct esp_null_sa *sa,const unsigned char *packet,size_t len,
                   unsigned char *udp,size_t capacity,esp_digest_fn digest,
                   esp_cipher_fn cipher,void *context);
#endif
