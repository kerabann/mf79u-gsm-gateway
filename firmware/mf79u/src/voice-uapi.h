/* Recovered from this B03 libvoice.so. No driver implementation is supplied.
 * Encoded ioctl size is NOT proof of field layout or driver-side validation.
 * Do not issue these against arbitrary device nodes.
 */
#ifndef MF79U_VOICE_UAPI_H
#define MF79U_VOICE_UAPI_H
#define MF79U_VOICE_OPEN_REQUEST      0x4014760aU
#define MF79U_VOICE_CLOSE_REQUEST     0x4014760bU
#define MF79U_VOICE_SLIC_FLAG_REQUEST 0x8004760cU
#define MF79U_VOICE_LOOP_REQUEST      0x4004760dU
#define MF79U_VOICE_CONFIG_ABI_SIZE   20U
/* Opaque until the driver's exact configuration fields are recovered. */
struct mf79u_voice_config_opaque { unsigned char bytes[MF79U_VOICE_CONFIG_ABI_SIZE]; };
#endif
