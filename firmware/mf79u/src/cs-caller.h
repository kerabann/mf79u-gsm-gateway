/* Bounded SETUP Calling Party BCD reader. Restricted, unavailable, malformed
 * or unsupported identities are anonymous. No logging or persistent storage. */
#ifndef MF79U_CS_CALLER_H
#define MF79U_CS_CALLER_H
static int cs_calling_number(const unsigned char *p,unsigned n,char out[34]) {
    static const char anonymous[]="anonymous";
    for(unsigned i=0;i<sizeof(anonymous);i++)out[i]=anonymous[i];
    if(!p || n<2U || n>256U || (p[0]&15U)!=3U || (p[1]&63U)!=5U)return 0;
    unsigned at=2,found=0;char result[34];
    for(unsigned i=0;i<34U;i++)result[i]=0;
    while(at<n) {
        unsigned tag=p[at++];
        if(tag&0x80U)continue;
        if(at>=n)return 0;
        unsigned size=p[at++];if(size>n-at)return 0;
        if(tag==0x5cU) {
            if(found++ || size<2U)return 0;
            unsigned pos=at+1U,end=at+size;
            if(!(p[at]&0x80U)) {
                if(pos>=end || !(p[pos]&0x80U) || ((p[pos]>>5)&3U)!=0)return 0;
                pos++;
            }
            unsigned length=0;
            if(((p[at]>>4)&7U)==1U)result[length++]='+';
            for(;pos<end;pos++) {
                unsigned low=p[pos]&15U,high=p[pos]>>4;
                if(low>9U || length>=33U)return 0;
                result[length++]=(char)('0'+low);
                if(high==15U){if(pos+1U!=end)return 0;break;}
                if(high>9U || length>=33U)return 0;
                result[length++]=(char)('0'+high);
            }
            unsigned digits=length-(result[0]=='+');
            if(digits<3U || digits>32U)return 0;
            result[length]=0;
        }
        at+=size;
    }
    if(found)for(unsigned i=0;i<34U;i++)out[i]=result[i];
    for(unsigned i=0;i<34U;i++)((volatile char *)result)[i]=0;
    return found!=0;
}
#endif
