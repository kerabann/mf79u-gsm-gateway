#ifndef MF79U_CP_IPC_H
#define MF79U_CP_IPC_H
#include <stddef.h>
#include <stdint.h>

/* B03 libatutils send_app_req / send_req_and_wait ABI. */
#define MF79U_AT_BYTES 3488
struct mf79u_cp { int tx, rx; int32_t key; uint16_t reply_cmd; int32_t reply_src; uint16_t request_cmd; int pdp_received; int32_t pdp[3]; };
int mf79u_cp_open(struct mf79u_cp *cp);
int mf79u_cp_open_direct(struct mf79u_cp *cp);
void mf79u_cp_close(struct mf79u_cp *cp);
int mf79u_cp_query(struct mf79u_cp *cp, const char *command,
                  char *reply, size_t capacity, unsigned timeout_seconds);
#endif
