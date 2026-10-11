/* SPDX-License-Identifier: GPL-2.0-only
 * Verify the sysfs attribute ABI from the live kernel's own implementation.
 * Creates/removes only our empty kobject. No CP access or call-control IO.
 */
typedef unsigned int u32;
typedef unsigned char u8;
extern int printk(const char *,...);
extern void *kobject_create_and_add(const char *,void *);
extern void kobject_put(void *);
extern long probe_kernel_read(void *,const void *,unsigned long);
static int read_word(u32 address,u32 *word) {
    if(address<0xc0000000U || address>0xc3bbfffcU || (address&3U))return -71;
    return probe_kernel_read(word,(const void *)address,4)?-71:0;
}
int init_module(void) {
    void *object=kobject_create_and_add("mf79u_cs_abi_probe",(void *)0);
    if(!object)return -12;
    u32 type=0,ops=0,show=0,store=0;int result=-71;
    u8 code[32];
    /* Upstream v3.4: kobject.ktype+20, kobj_type.sysfs_ops+4.
     * Read the implementation before admitting any attribute struct layout. */
    if(read_word((u32)object+20U,&type) || read_word(type+4U,&ops) ||
       read_word(ops,&show) || read_word(ops+4U,&store))goto done;
    if(show<0xc0000001U || show>0xc3bbffe1U || !(show&1U) ||
       probe_kernel_read(code,(const void *)(show&~1U),sizeof(code)))goto done;
    printk("<6>MF79U_CS_SYSFS object=%08x type=%08x ops=%08x show=%08x store=%08x\n",(u32)object,type,ops,show,store);
    for(u32 i=0;i<sizeof(code);i+=8)
        printk("<6>MF79U_CS_SYSFS show_offset=%u code=%02x%02x%02x%02x%02x%02x%02x%02x\n",i,code[i],code[i+1],code[i+2],code[i+3],code[i+4],code[i+5],code[i+6],code[i+7]);
    result=0;
done:
    kobject_put(object);
    if(!result)printk("<6>MF79U_CS_SYSFS own_object_removed=1 no_cp_io=1\n");
    return result;
}
void cleanup_module(void) {printk("<6>MF79U_CS_SYSFS unloaded\n");}
