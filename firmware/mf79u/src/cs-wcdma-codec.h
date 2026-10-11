/* TS24.008 Supported Codec List / TS26.103 NB speech bitmaps. */
#ifndef MF79U_CS_WCDMA_CODEC_H
#define MF79U_CS_WCDMA_CODEC_H
static unsigned int cs_wcdma_codec_offer(unsigned char *wire,unsigned int length,
                                        unsigned int capacity,unsigned int rat) {
    if(!wire || length<2U || length>capacity)return 0;
    unsigned int type=wire[1]&63U;
    if(rat!=3U || (type!=5U && type!=8U))return length;
    static const unsigned char list[]={0x40,6,0,1,0x1f,4,1,0x60};
    if(capacity-length<sizeof(list))return 0;
    for(unsigned int i=0;i<sizeof(list);i++)wire[length+i]=list[i];
    return length+sizeof(list);
}
#endif
