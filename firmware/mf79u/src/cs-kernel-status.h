/* SPDX-License-Identifier: GPL-2.0-only
 * Exact live B03 sysfs ABI. No kernel-owned structure is modified.
 * Attribute layout is admitted only after checking kernel show/store code.
 */
#ifndef MF79U_CS_KERNEL_STATUS_H
#define MF79U_CS_KERNEL_STATUS_H
extern void *kobject_create_and_add(const char *,void *);
extern void kobject_put(void *);
extern int sysfs_create_file(void *,const void *);
extern void sysfs_remove_file(void *,const void *);
extern int scnprintf(char *,unsigned int,const char *,...);
struct cs_attribute { const char *name;unsigned short mode;unsigned short padding; };
struct cs_kobj_attribute {
    struct cs_attribute attr;
    int (*show)(void *,struct cs_kobj_attribute *,char *);
    void *store;
};
static void *cs_status_object;
static volatile u32 cs_status_armed,cs_status_state,cs_status_events;
static volatile u32 cs_status_sent,cs_status_errors;
#ifndef CS_STATUS_ANSWER_FORBIDDEN
#define CS_STATUS_ANSWER_FORBIDDEN 1U
#endif
#ifndef CS_STATUS_OBJECT_NAME
#define CS_STATUS_OBJECT_NAME "mf79u_cs"
#endif
static int cs_status_show(void *object,struct cs_kobj_attribute *attr,char *buffer) {
    (void)object;(void)attr;
    u32 armed=cs_status_armed,state=cs_status_state,count=cs_status_events;
    u32 sent=cs_status_sent,errors=cs_status_errors;
    if(!cs_status_armed){
        armed=0;
#ifndef CS_STATUS_REPORT_INACTIVE_STATE
        state=0;
#endif
    }
    return scnprintf(buffer,256U,"MF79U_CS 1 %u %u %u %u %u %u\n",armed,state,count,sent,errors,CS_STATUS_ANSWER_FORBIDDEN);
}
static struct cs_kobj_attribute cs_status_attribute={
    {"status",0400,0},cs_status_show,(void *)0
};
static int cs_status_read_word(u32 address,u32 *word) {
    if(address<0xc0000000U || address>0xc3bbfffcU || (address&3U))return -71;
    return probe_kernel_read(word,(const void *)address,4)?-71:0;
}
static void cs_status_remove(void) {
    if(!cs_status_object)return;
    sysfs_remove_file(cs_status_object,&cs_status_attribute.attr);
    kobject_put(cs_status_object);cs_status_object=(void *)0;
}
static int cs_status_create(void) {
    void *object=kobject_create_and_add(CS_STATUS_OBJECT_NAME,(void *)0);
    if(!object)return -12;
    u32 type=0,ops=0,show=0,store=0;u8 code[4];int result=-71;
    /* Live probe: kobj show starts LDR r3,[r1,#8]; store loads #12.
     * Verify the opaque kobject path before admitting our attribute layout. */
    static const u8 show_code[4]={0x8b,0x68,0x03,0xb1};
    static const u8 store_code[4]={0x10,0xb5,0xcc,0x68};
    if(sizeof(struct cs_attribute)!=8U || sizeof(struct cs_kobj_attribute)!=16U ||
       cs_status_read_word((u32)object+20U,&type) || cs_status_read_word(type+4U,&ops) ||
       cs_status_read_word(ops,&show) || cs_status_read_word(ops+4U,&store))goto failed;
    if(show!=0xc010dda1U || store!=0xc010ddadU ||
       probe_kernel_read(code,(const void *)(show&~1U),4))goto failed;
    for(u32 i=0;i<4U;++i)if(code[i]!=show_code[i])goto failed;
    if(probe_kernel_read(code,(const void *)(store&~1U),4))goto failed;
    for(u32 i=0;i<4U;++i)if(code[i]!=store_code[i])goto failed;
    result=sysfs_create_file(object,&cs_status_attribute.attr);
    if(!result){cs_status_object=object;return 0;}
failed:
    kobject_put(object);return result;
}
#endif
