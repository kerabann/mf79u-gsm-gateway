/* Keep the PJMEDIA null-device clock below the B03 CP/watchdog real-time
 * threads. PJSUA otherwise requests SCHED_RR at the maximum priority (99).
 * Use the supported option and preserve the library-owned clock lifecycle. */
#include <pjmedia/master_port.h>
#include <pjmedia/clock.h>

PJ_DECL(pj_status_t) __real_pjmedia_master_port_create(
    pj_pool_t *pool, pjmedia_port *up, pjmedia_port *down, unsigned options,
    pjmedia_master_port **master);

PJ_DEF(pj_status_t) __wrap_pjmedia_master_port_create(
    pj_pool_t *pool, pjmedia_port *up, pjmedia_port *down, unsigned options,
    pjmedia_master_port **master)
{
    return __real_pjmedia_master_port_create(pool, up, down,
        options | PJMEDIA_CLOCK_NO_HIGHEST_PRIO, master);
}
