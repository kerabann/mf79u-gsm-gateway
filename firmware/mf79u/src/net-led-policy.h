#ifndef MF79U_NET_LED_POLICY_H
#define MF79U_NET_LED_POLICY_H
#include <stddef.h>
#include <stdint.h>
#define MF79U_LED_SOCKET "/dev/.mf79u-net-led/control.sock"
#define MF79U_LED_MAGIC 0x4d464c31u
/* Only call index/direction/state cross the socket, never a telephone number. */
struct mf79u_led_event { uint32_t magic; int32_t id, direction, state; };
struct mf79u_led_calls { int state[8], direction[8], anonymous_ring; };
void mf79u_led_clear(struct mf79u_led_calls *calls);
int mf79u_led_parse(const void *text,size_t size,struct mf79u_led_event *event);
int mf79u_led_apply(struct mf79u_led_calls *calls,const struct mf79u_led_event *event);
unsigned mf79u_led_color(int registered,const struct mf79u_led_calls *calls);
unsigned mf79u_led_service_color(int registered,int ims_ready,const struct mf79u_led_calls *calls);
unsigned mf79u_led_access_color(int registered,int ims_ready,int wifi_ready,const struct mf79u_led_calls *calls);
unsigned mf79u_led_mode_color(int registered,int ims_ready,int wifi_ready,int vowifi_only,const struct mf79u_led_calls *calls);
int mf79u_led_registration(const char *network,const char *main_state);
void mf79u_led_notify(const void *text,size_t size);
int mf79u_led_selftest(void);
#endif
