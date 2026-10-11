/* Real public PCM route; idle-only, B03 compatibility unverified. */
#ifndef CS_I2S_PARAMETERS_H
#define CS_I2S_PARAMETERS_H
static const unsigned short cs_i2s_params_0[]={0,0,0,0,0,32767,0,0,0,0,32767};
static const unsigned short cs_i2s_params_1[]={1,0,0,0,0,32767,0,0,0,0,32767};
static const unsigned short cs_i2s_params_2[]={0,0,0,15919,0,32767,0};
static const unsigned short cs_i2s_params_3[]={8192,8192,0,0,8192,8192,7959,32767,32690,0,0,32767,0,32767,0,0,0,0,32767,32767,32767,16383};
static const unsigned short cs_i2s_params_4[]={0,2200,250,8,5,150,16384,16384,16384,0,0,500};
static const unsigned short cs_i2s_params_5[]={0};
static const unsigned short cs_i2s_params_6[]={3,112,32768,4112,1625,4112,1625,0,19,3090,0,0,0,0,0,0,0,0,48,4113,3250,4113,3250,0,0,0,0};
static const unsigned short cs_i2s_params_7[]={1,112,0,4112,1625,4112,1625,0,19,3090,0,0,0,0,0,0,0,0,48,4113,3250,4113,3250,0,0,0,0};
#define CS_I2S_PUBLIC_PCM_API 1
#define CS_I2S_PARAMETER_REPORT "mf283u-public-pcm-arm-slave-emulation.json"
#define CS_I2S_PARAMETER_SHA256 "44e3a7473f08c72e585bbdbbe46778a19251dd04690e35ee5008c5b5dde236ad"
#define CS_I2S_CONFIGURATION_REPORT "mf283u-public-pcm-arm-slave-configuration-emulation.json"
#define CS_I2S_CONFIGURATION_SHA256 "0f745fc5b4c21d9630a4d9e2d3c927debd2d550e925a0439d936803959c25dfc"
#define CS_I2S_TIMING 0x01ef0008U
#define CS_I2S_DIV_LO 0x00000000U
#define CS_I2S_DIV_HI 0x00000000U
#define CS_I2S_LOOP 0x00000099U
#define CS_I2S_CLOCK_MASTER 0
#define CS_I2S_LOOP_MASK 0x1ffU
#define CS_I2S_TDM_EXTRA_CYCLE 1
#define CS_I2S_FIFO_RATE_HZ 8000U
#endif
