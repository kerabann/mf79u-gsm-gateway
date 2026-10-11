/* Real public PCM route; idle-only, B03 compatibility unverified. */
#ifndef CS_I2S_PARAMETERS_H
#define CS_I2S_PARAMETERS_H
static const unsigned short cs_i2s_params_0[]={0,0,0,0,0,32767,0,0,0,0,32767};
static const unsigned short cs_i2s_params_1[]={1,0,0,0,0,32767,0,0,0,0,32767};
static const unsigned short cs_i2s_params_2[]={0,0,0,15919,0,32767,0};
static const unsigned short cs_i2s_params_3[]={8192,8192,0,0,8192,8192,7959,32767,32690,0,0,32767,0,32767,0,0,0,0,32767,32767,32767,16383};
static const unsigned short cs_i2s_params_4[]={0,2200,250,8,5,150,16384,16384,16384,0,0,500};
static const unsigned short cs_i2s_params_5[]={0};
static const unsigned short cs_i2s_params_6[]={3,154,32768,1,2,1,2,0,19,3090,0,0,0,0,0,0,0,0,154,4112,1625,4112,1625,0,0,0,0};
static const unsigned short cs_i2s_params_7[]={1,154,0,1,2,1,2,0,19,3090,0,0,0,0,0,0,0,0,154,4112,1625,4112,1625,0,0,0,0};
#define CS_I2S_PUBLIC_PCM_API 1
#define CS_I2S_PARAMETER_REPORT "mf283u-public-pcm-emulation.json"
#define CS_I2S_PARAMETER_SHA256 "723617394a435276905610e868a7364d9ab43cc0d9b10ca3b334a5b85a6d51ac"
#define CS_I2S_CONFIGURATION_REPORT "mf283u-public-pcm-configuration-emulation.json"
#define CS_I2S_CONFIGURATION_SHA256 "3e3f93caf48552dd65ac2ad45896f035e22825762c97465b389a9433d43a97a4"
#define CS_I2S_TIMING 0x01ef0009U
#define CS_I2S_DIV_LO 0x00000017U
#define CS_I2S_DIV_HI 0x000100cbU
#define CS_I2S_LOOP 0x00000099U
#define CS_I2S_CLOCK_MASTER 1
#define CS_I2S_LOOP_MASK 0x1ffU
#define CS_I2S_TDM_EXTRA_CYCLE 1
#define CS_I2S_FIFO_RATE_HZ 8000U
#endif
