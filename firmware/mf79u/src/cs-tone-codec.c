/* Synthetic file conversion only: external PCM16LE/16k/320, internal AMR-NB. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <interf_enc.h>
#include <interf_dec.h>
#include "pcm-resample.h"
static const unsigned sizes[8]={12,13,15,17,19,20,26,31};
int main(int argc,char **argv) {
    if(argc!=4)return 1;
    char *end=0;unsigned mode=(unsigned)strtoul(argv[1],&end,10);
    if(*end || mode>7)return 1;
    FILE *in=fopen(argv[2],"rb"),*out=fopen(argv[3],"wb");
    if(!in || !out)return 2;
    void *enc=Encoder_Interface_init(0),*dec=Decoder_Interface_init();
    if(!enc || !dec)return 2;
    struct mf79u_resample down={0},up={0};
    unsigned char bytes[640],amr[64];short pcm[320],nb[160],decoded[160],wb[320];
    unsigned frames=0;int failed=0;
    if(fwrite("#!AMR\n",1,6,out)!=6)failed=1;
    while(!failed) {
        size_t n=fread(bytes,1,640,in);if(!n)break;
        if(n!=640){failed=1;break;}
        for(unsigned i=0;i<320;i++)pcm[i]=(int16_t)((unsigned)bytes[2*i]|((unsigned)bytes[2*i+1]<<8));
        mf79u_downsample(&down,pcm,nb);
        int z=Encoder_Interface_Encode(enc,(enum Mode)mode,nb,amr,0);
        if(z!=(int)sizes[mode]+1 || amr[0]!=(mode<<3|4) || fwrite(amr,1,z,out)!=(size_t)z){failed=1;break;}
        Decoder_Interface_Decode(dec,amr,decoded,0);mf79u_upsample(&up,decoded,wb);
        for(unsigned i=0;i<320;i++){bytes[2*i]=(uint16_t)wb[i]&255;bytes[2*i+1]=(uint16_t)wb[i]>>8;}
        if(fwrite(bytes,1,640,stdout)!=640){failed=1;break;}
        frames++;
    }
    if(ferror(in) || fclose(out) || fflush(stdout))failed=1;
    fclose(in);Encoder_Interface_exit(enc);Decoder_Interface_exit(dec);
    fprintf(stderr,"mode=%u frames=%u success=%u\n",mode,frames,!failed);
    return failed?2:0;
}
