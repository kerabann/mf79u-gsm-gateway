/* Offline I2S duplex reference parameters; opt-in B03 diagnostic only. */
#ifndef CS_I2S_PARAMETERS_H
#define CS_I2S_PARAMETERS_H
static const unsigned short cs_i2s_params_0[]={0,14878,13372,0,0,29756,39151,36192,26385,26962,26385};
static const unsigned short cs_i2s_params_1[]={1,35445,35572,30091,27668,30091,26488,24996,26488,23168,26488};
static const unsigned short cs_i2s_params_2[]={0,0,0,0,0,32767,0};
static const unsigned short cs_i2s_params_3[]={0,0,0,0,6143,8192,0,32767,32690,0,0,32767,0,32767,0,0,0,0,32767,32767,32767,0};
static const unsigned short cs_i2s_params_4[]={0,2200,250,8,5,65336,16384,16384,16384,0,0,500};
static const unsigned short cs_i2s_params_5[]={0};
static const unsigned short cs_i2s_params_6[]={2,154,32768,1,2,1,2,0,3,3074,0,0,0,0,113,0,0,0,48,4113,3250,4113,3250,0,0,0,0};
static const unsigned short cs_i2s_params_7[]={0,154,0,1,2,1,2,0,3,3074,0,0,0,0,0,0,0,0,48,4113,3250,4113,3250,0,0,0,0};
#define CS_I2S_PARAMETER_REPORT "mf283u-idle-afe-tone-loop-emulation.json"
#define CS_I2S_PARAMETER_SHA256 "7ea513f53aca8eac894c1b9c0e2ea9fc4c57193bd247127fcc670b71c36a00ed"
#define CS_I2S_CONFIGURATION_REPORT "mf283u-voice-inner-init-extra-cycle0-configuration-emulation.json"
#define CS_I2S_CONFIGURATION_SHA256 "f6ed3f411358c85133f211263cdbb2ae93c27f0cf1a058afadd62b542850f579"
#define CS_I2S_TIMING 0x01ef2021U
#define CS_I2S_DIV_LO 0x00200019U
#define CS_I2S_DIV_HI 0x00010032U
#define CS_I2S_LOOP 0x000000a9U
#define CS_I2S_CLOCK_MASTER 1
#define CS_I2S_LOOP_MASK 0x1ffU
#define CS_I2S_TDM_EXTRA_CYCLE 0
#endif
