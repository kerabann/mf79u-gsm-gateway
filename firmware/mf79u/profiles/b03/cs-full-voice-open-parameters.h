/* Full reference voice API parameters; bounded no-call diagnostic only. */
#ifndef CS_I2S_PARAMETERS_H
#define CS_I2S_PARAMETERS_H
static const unsigned short cs_i2s_params_0[]={0,14878,13372,0,0,29756,39151,36192,26385,26962,26385};
static const unsigned short cs_i2s_params_1[]={1,35445,35572,30091,27668,30091,26488,24996,26488,23168,26488};
static const unsigned short cs_i2s_params_2[]={0,0,0,15919,0,32767,0};
static const unsigned short cs_i2s_params_3[]={8192,8192,0,0,6143,8192,7959,32767,32690,0,0,32767,0,32767,0,0,0,0,32767,32767,32767,16383};
static const unsigned short cs_i2s_params_4[]={0,2200,250,8,5,65336,16384,16384,16384,0,0,500};
static const unsigned short cs_i2s_params_5[]={0};
static const unsigned short cs_i2s_params_6[]={2,154,32768,1,2,1,2,0,19,3090,0,0,0,0,113,0,0,0,0,0,0,0,0,0,0,0,0};
static const unsigned short cs_i2s_params_7[]={1,154,0,1,2,1,2,0,19,3090,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
#define CS_I2S_FULL_VOICE_API 1
#define CS_I2S_PARAMETER_REPORT "mf283u-full-voice-open-port-tone-emulation.json"
#define CS_I2S_PARAMETER_SHA256 "e0d35de48cb714deb6f3134529b5c580f0b0d72662bc7876d30a50a7d49077fc"
#define CS_I2S_CONFIGURATION_REPORT "mf283u-voice-inner-init-configuration-emulation.json"
#define CS_I2S_CONFIGURATION_SHA256 "fcd3973a8ee93b68caa32e8218cc0b86225ce275430be02ab3b07d5a427ce5aa"
#define CS_I2S_TIMING 0x01ef2001U
#define CS_I2S_DIV_LO 0x00200019U
#define CS_I2S_DIV_HI 0x00010032U
#define CS_I2S_LOOP 0x000000a9U
#define CS_I2S_CLOCK_MASTER 1
#define CS_I2S_LOOP_MASK 0x1ffU
#define CS_I2S_TDM_EXTRA_CYCLE 1
#define CS_I2S_FIFO_RATE_HZ 8000U
#endif
