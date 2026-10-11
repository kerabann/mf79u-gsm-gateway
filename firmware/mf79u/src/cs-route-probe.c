/* SPDX-License-Identifier: GPL-2.0-only
 * Exact B03 OSS routing metadata only. No payload reads, sends or task changes.
 */
typedef unsigned int u32;
typedef unsigned char u8;
extern int printk(const char *,...);
static int match(const volatile u8 *a,const u8 *b,u32 n) {
    for(u32 i=0;i<n;++i)if(a[i]!=b[i])return 0;
    return 1;
}
int init_module(void) {
    static const u8 stub[8]={0x38,0xb5,0x14,0x46,0xa1,0xf5,0x33,0x43};
    static const u8 send[8]={0xf0,0xb5,0x87,0xb0,0x0e,0x46,0x04,0x46};
    if(!match((const volatile u8 *)0xbf30053cU,stub,8) ||
       !match((const volatile u8 *)0xbf4afebcU,send,8) ||
       *(const volatile u32 *)0xbf59e3c0U!=0xbf55a954U ||
       *(const volatile u32 *)0xbf59e3bcU!=39U)return -19;
    u32 list=*(const volatile u32 *)0xbf5bcd88U;
    if(list<0xc0000000U || list>0xc3bbff64U || (list&3U))return -71;
    static const u8 names[2][4]={{'C','C',0,0},{'A','S','C',0}};
    const u32 index[2]={9,38},registry[2]={0xbf55e8bcU,0xbf55f0e4U};
    u32 callbacks_original=1;
    for(u32 i=0;i<2;++i) {
        u32 task=((const volatile u32 *)list)[index[i]];
        if(task<0xc0000000U || task>0xc3bbff44U || (task&3U) ||
           !match((const volatile u8 *)(task+16U),names[i],i?4:3) ||
           *(const volatile u32 *)(task+8U)!=1U ||
           *(const volatile u32 *)registry[i]!=task)return -71;
        u32 callback=*(const volatile u32 *)(task+0x50U);
        if(i && callback!=0xbf47be95U)return -71;
        if(!i && callback!=0xbf30053dU)callbacks_original=0;
        printk("<6>MF79U_CS_ROUTE name=%s task=%08x callback=%08x phase=%u registry=verified\n",names[i],task,callback,*(const volatile u8 *)(task+0x9aU));
    }
    /* Source-checked B03 GSMA registry descriptor. Only persistent routing
     * metadata, never a radio payload or sequence-variable write. */
    u32 gsma=*(const volatile u32 *)0xbf55ec1cU;
    static const u8 gsma_name[5]={'G','S','M','A',0};
    if(gsma>=0xc0000000U && gsma<=0xc3bbff44U && !(gsma&3U) &&
       match((const volatile u8 *)(gsma+16U),gsma_name,5) &&
       *(const volatile u32 *)(gsma+8U)==1U) {
        for(u32 i=0;i<39U;i++)if(((const volatile u32 *)list)[i]==gsma)
            printk("<6>MF79U_CS_ROUTE name=GSMA task=%08x callback=%08x phase=%u index=%u registry=verified\n",
                gsma,*(const volatile u32 *)(gsma+0x50U),*(const volatile u8 *)(gsma+0x9aU),i);
    } else printk("<6>MF79U_CS_ROUTE gsma_registry_unresolved=1 no_payload_reads=1\n");
    u32 gate=*(const volatile u32 *)0xbf356258U;
    u32 mm=*(const volatile u32 *)0xbf600bacU;
    if(!((mm>=0xc0000000U && mm<=0xc3bbff98U) ||
         (mm>=0xbf59e000U && mm<=0xbf61af98U)))return -71;
    u32 protocol=*(const volatile u8 *)(mm+0x15U);
    u32 references=*(const volatile u8 *)(mm+0x65U);
    u32 dsp_original=*(const volatile u32 *)0xbf3e9b98U==0xbf3ea119U;
    printk("<6>MF79U_CS_ROUTE callbacks_original=%u admission_original=%u mm_cc_references=%u mm_active_protocol=%u dsp_selfcheck_original=%u quiescent=%u\n",
        callbacks_original,gate==0xbf300537U,references,protocol,dsp_original,
        callbacks_original && gate==0xbf300537U && !references && protocol!=3U && dsp_original);
    printk("<6>MF79U_CS_ROUTE send_signature=verified no_calls=1 no_sends=1\n");
    return 0;
}
void cleanup_module(void) {printk("<6>MF79U_CS_ROUTE unloaded\n");}
