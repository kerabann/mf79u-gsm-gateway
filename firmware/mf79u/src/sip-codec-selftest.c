/* Encode/parse/decode each SIP codec. No network, SIM or calls. */
#include <pjsua-lib/pjsua.h>
#include <pjmedia-codec/opus.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
int main(void){
    if(pjsua_create()!=PJ_SUCCESS)return 1;
    pjsua_config cfg;pjsua_config_default(&cfg);cfg.thread_cnt=0;
    pjsua_logging_config log;pjsua_logging_config_default(&log);log.level=0;log.console_level=0;log.msg_logging=PJ_FALSE;
    pjsua_media_config media;pjsua_media_config_default(&media);media.clock_rate=16000;
    if(pjsua_init(&cfg,&log,&media)!=PJ_SUCCESS)return 2;
    pjmedia_codec_mgr *mgr=pjmedia_endpt_get_codec_mgr(pjsua_get_pjmedia_endpt());
    pjmedia_codec_info all[32];unsigned count=32;
    if(pjmedia_codec_mgr_enum_codecs(mgr,&count,all,NULL)!=PJ_SUCCESS)return 3;
    const char *names[]={"opus","G722","PCMA","PCMU","G729"};
    for(unsigned n=0;n<5;n++){
        pjmedia_codec_info *info=NULL;
        for(unsigned i=0;i<count;i++)if(!pj_stricmp2(&all[i].encoding_name,names[n]))info=&all[i];
        if(!info)return 4;
        pjmedia_codec_param param;pjmedia_codec *codec;
        if(pjmedia_codec_mgr_get_default_param(mgr,info,&param)!=PJ_SUCCESS)return 5;
        param.setting.vad=0;param.setting.plc=1;
        if(!n){pjmedia_codec_opus_config op;pjmedia_codec_opus_get_config(&op);op.sample_rate=16000;op.channel_cnt=1;op.bit_rate=24000;op.complexity=3;op.frm_ptime=20;op.packet_loss=2;if(pjmedia_codec_opus_set_default_param(&op,&param)!=PJ_SUCCESS)return 5;}
        if(pjmedia_codec_mgr_alloc_codec(mgr,info,&codec)!=PJ_SUCCESS)return 5;
        pj_pool_t *pool=pjsua_pool_create("codec-test",4096,4096);
        if(codec->op->init(codec,pool)!=PJ_SUCCESS || codec->op->open(codec,&param)!=PJ_SUCCESS)return 6;
        unsigned samples=param.info.clock_rate*param.info.channel_cnt*param.info.frm_ptime/1000;
        if(samples>2048)return 7;
        short pcm[2048],decoded[2064];unsigned char bits[2048];unsigned passed=0;
        struct timespec start,end;clock_gettime(CLOCK_MONOTONIC,&start);
        for(unsigned frame=0;frame<60;frame++){
            for(unsigned i=0;i<samples;i++)pcm[i]=(short)((i%20<10?1:-1)*5000);
            memset(decoded,0x5a,sizeof(decoded));pjmedia_frame input={.buf=pcm,.size=samples*2,.type=PJMEDIA_FRAME_TYPE_AUDIO};
            input.timestamp.u64=frame*samples;pjmedia_frame encoded={.buf=bits},parts[8];unsigned part_count=8,total=0;
            if(codec->op->encode(codec,&input,sizeof(bits),&encoded)!=PJ_SUCCESS || !encoded.size ||
               codec->op->parse(codec,encoded.buf,encoded.size,&input.timestamp,&part_count,parts)!=PJ_SUCCESS)return 8;
            for(unsigned i=0;i<part_count;i++){
                pjmedia_frame output={.buf=(unsigned char*)decoded+total,.size=samples*2-total};
                if(codec->op->decode(codec,parts+i,samples*2-total,&output)!=PJ_SUCCESS)return 9;
                total+=(unsigned)output.size;
            }
            if(n==0 && frame==0 && total==0)continue; /* Opus buffers one frame for in-band FEC. */
            if(total!=samples*2){printf("FRAME_SIZE codec=%s samples=%u rate=%u channels=%u ptime=%u decoded=%u parts=%u\n",names[n],samples,param.info.clock_rate,param.info.channel_cnt,param.info.frm_ptime,total,part_count);return 10;}
            for(unsigned i=samples;i<2064;i++)if(decoded[i]!=0x5a5a)return 11;
            for(unsigned i=0;i<samples;i++)if(decoded[i]){passed++;break;}
        }
        clock_gettime(CLOCK_MONOTONIC,&end);
        if(passed<50)return 12;
        long elapsed=(end.tv_sec-start.tv_sec)*1000000+(end.tv_nsec-start.tv_nsec)/1000;
        printf("SIP codec=%s PCM=%u/%u passed=%u/60 mean_encode_decode_us=%ld\n",names[n],param.info.clock_rate,param.info.channel_cnt,passed,elapsed/60);
        codec->op->close(codec);pjmedia_codec_mgr_dealloc_codec(mgr,codec);pj_pool_release(pool);
    }
    pjsua_destroy();puts("All five SIP codec pipelines passed");return 0;
}
