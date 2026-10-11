/* All call commands execute in CC/SIM0. The PCM worker only operates audio
 * and attaches/detaches idle callbacks. No connected-call media deadline. */
static void publish(u32 previous) {
    cs_status_state=call.mo.stage;
    if(previous!=call.mo.stage) {
        stage_tick=tick;
        printk("<6>" LOG " state=%u previous=%u incoming=%u\n",call.mo.stage,previous,call.incoming);
    }
}
static int enqueue(u32 action,u32 id,const u8 *number,u32 length) {
    struct command *c=__kmalloc_node(sizeof(*c),0xd0U,-1);if(!c)return -12;
    c->magic=COMMAND_MAGIC;c->action=action;c->length=length;c->epoch=session_epoch;c->id=id;
    for(u32 i=0;i<33U;i++)c->number[i]=i<length?number[i]:0;
    int result=((int (*)(u32,void *,u32,u32))0xbf438315U)(COMMAND_ID,c,sizeof(*c),cc_task);
    if(result){for(u32 i=0;i<33U;i++)c->number[i]=0;kfree(c);}
    return result;
}
static void observe(u32 phase,u32 id,void *payload,u32 length,void *work) {
    u32 previous=call.mo.stage;cs_status_events++;
    struct cs_mo_packet packets[2];
    if(phase==1U && id==COMMAND_ID && length==sizeof(struct command) && ram((u32)payload,length)) {
        struct command *c=payload;
        if(c->magic==COMMAND_MAGIC && c->epoch==session_epoch && c->length<=33U) {
            if(c->action==1U && enabled && desired_enabled && !fault &&
               !call.mo.stage && c->id>last_id) {
                last_id=c->id;call_id=c->id;mm_quiescent=mm_release_sent=0;
                if(cs_call_begin(&call,c->number,c->length) || mm(0xaa3cU)) {
                    cs_mo_forget(&call.mo);call.mo.stage=CS_MO_MM_CLEARING;mm_quiescent=1;
                }
            }
            if(c->id==call_id && call_id) {
                if(c->action==2U) {
                    if(cs_call_hangup(&call,&packets[0])) {
                        if(transmit(&packets[0])) {call.mo.stage=CS_MO_MM_CLEARING;mm(0xaa3eU);}
                    } else if(call.mo.stage==CS_MO_MM_PENDING || call.mo.stage==CS_MO_RELEASING ||
                              call.mo.stage==CS_MO_DISCONNECTING) {
                        call.mo.stage=CS_MO_MM_CLEARING;cs_mo_forget(&call.mo);mm(0xaa3eU);
                    }
                }
                if(c->action==3U && call.mo.stage==CS_MO_MM_CLEARING && mm_cc_released())mm_quiescent=1;
                if(c->action==4U && cs_call_answer(&call,&packets[0]) && transmit(&packets[0])) {
                    call.mo.stage=CS_MO_MM_CLEARING;mm(0xaa3eU);
                }
                if(c->action==5U && rearm_requested==2U && mm_quiescent && cs_audio_restored) {
                    cs_call_init(&call);call_id=0;mm_release_sent=mm_quiescent=0;rearm_requested=0;
                    for(u32 i=0;i<34U;i++)caller[i]=0;
                    static const char anon[]="anonymous";
                    for(u32 i=0;i<sizeof(anon);i++)caller[i]=anon[i];
                }
            }
            for(u32 i=0;i<33U;i++)c->number[i]=0;
        }
    } else if(phase==1U && id==0xaa3dU && length==4U && ram((u32)payload,4U)) {
        u8 connection=255;
        if(!probe_kernel_read(&connection,payload,1) && !(connection&1U) &&
           cs_call_established(&call,&packets[0]) && transmit(&packets[0])) {
            call.mo.stage=CS_MO_MM_CLEARING;mm(0xaa3eU);
        }
    } else if(phase==1U && id==0xaa3fU && length==4U && ram((u32)payload,4U) && call_id) {
        u8 connection=255;
        if(!probe_kernel_read(&connection,payload,1) && !(connection&1U)) {
            /* B03 AA3F constructor stores the release reason at offset2.
             * Scalar metadata only: no number, packet body or PCM samples. */
            unsigned short reason=0xffffU;
            int reason_read=probe_kernel_read(&reason,(const u8 *)payload+2U,2U);
            printk("<6>" LOG " mm_release_reason=%u reason_read=%d state_before=%u incoming=%u\n",
                   (u32)reason,reason_read,previous,call.incoming);
            cs_mo_forget(&call.mo);call.mo.stage=CS_MO_MM_CLEARING;mm_quiescent=1;
        }
    } else if(phase==1U && id==0xaa45U && length==20U && ram((u32)payload,20U)) {
        u32 size=0,pointer=0;u8 connection=255,header[2];
        if(!probe_kernel_read(&connection,payload,1) && !connection &&
           !probe_kernel_read(&size,(const u8 *)payload+12U,4) &&
           !probe_kernel_read(&pointer,(const u8 *)payload+16U,4) && size>=2U && size<=2048U &&
           ram(pointer,size) && !probe_kernel_read(header,(const void *)pointer,2)) {
            int admit=enabled && desired_enabled && !fault && !call_id && last_id!=0xffffffffU;
            int n=cs_call_receive(&call,header[0],header[1]>>2,admit,packets);
            printk("<6>" LOG " rx_type=%02x expected_transaction=%u state_before=%u state_after=%u\n",
                header[1]>>2,header[0]==call.rx_header,previous,call.mo.stage);
            if(!previous && call.mo.stage==CS_CALL_RINGING) {
                call_id=++last_id;mm_quiescent=mm_release_sent=0;
                for(u32 i=0;i<34U;i++)caller[i]=0;
                static const char anon[]="anonymous";
                for(u32 i=0;i<sizeof(anon);i++)caller[i]=anon[i];
                __sync_synchronize();
                if(pending_header==header[0])for(u32 i=0;i<34U;i++)caller[i]=pending_caller[i];
                pending_header=0xffU;
                for(u32 i=0;i<34U;i++)pending_caller[i]=0;
            }
            for(int i=0;i<n;i++)if(transmit(&packets[i])){call.mo.stage=CS_MO_MM_CLEARING;break;}
            if(call.mo.stage==CS_MO_MM_CLEARING && previous!=CS_MO_MM_CLEARING)mm(0xaa3eU);
        }
    }
    publish(previous);original(phase,id,payload,length,work);
}
static void observe_asc(u32 phase,u32 id,void *payload,u32 length,void *work) {
    /* Bounded scalar trace of the existing owned ASC callback. No extra hook. */
    if(call_id && phase==2U) {
        if(asc_trace_call!=call_id){asc_trace_call=call_id;asc_trace_count=0;}
        if(asc_trace_count++<128U) {
            printk("<6>" LOG " asc_phase=%u asc_id=%04x length=%u state=%u\n",
                   phase,id,length,call.mo.stage);
            if((id==0xabdfU || id==0xe1f2U || id==0xaad4U) && length==12U && ram((u32)payload,12U)) {
                u32 env[3];u8 prefix[7];struct cs_wire_metadata info;
                if(!probe_kernel_read(env,payload,12U) && env[1]>=2U && env[1]<=2048U &&
                   ram(env[2],env[1]) && !probe_kernel_read(prefix,(const void *)env[2],2U)) {
                    u32 captured=2U,type=prefix[1]&63U;
                    if((prefix[0]&15U)==3U && (type==0x25U || type==0x2dU || type==0x2aU)) {
                        captured=env[1]<7U?env[1]:7U;
                        if(probe_kernel_read(prefix,(const void *)env[2],captured))captured=2U;
                    }
                    int decoded=cs_wire_metadata(prefix,captured,env[1],&info);
                    if(decoded>=0)printk("<6>" LOG " asc_wire_id=%04x pd=%u type=%02x nsd=%u wire_length=%u metadata_read=%d cause_present=%u cause=%u coding=%u\n",
                           id,info.pd,info.type,info.nsd,env[1],decoded,info.cause_present,info.cause,info.coding);
                }
            }
            if(id==0xabd9U && length==8U && ram((u32)payload,8U)) {
                u8 a=255,b=255;unsigned short c=65535;
                if(!probe_kernel_read(&a,payload,1U) && !probe_kernel_read(&b,(const u8 *)payload+1U,1U) &&
                   !probe_kernel_read(&c,(const u8 *)payload+4U,2U))
                    printk("<6>" LOG " asc_rr_release_field0=%u field1=%u field4=%u\n",a,b,(u32)c);
            }
        }
    }
    if(enabled && desired_enabled && !call_id && phase==2U && (id==0xabdfU || id==0xe1f2U) &&
       length==12U && ram((u32)payload,12U)) {
        u32 envelope[3];u8 wire[256];
        if(!probe_kernel_read(envelope,payload,12U) && !(envelope[0]&255U) &&
           envelope[1]>=2U && envelope[1]<=256U && ram(envelope[2],envelope[1]) &&
           !probe_kernel_read(wire,(const void *)envelope[2],envelope[1]) &&
           (wire[0]&0x8fU)==3U && (wire[1]&63U)==5U) {
            cs_calling_number(wire,envelope[1],pending_caller);
            __sync_synchronize();pending_header=wire[0];
        }
        for(u32 i=0;i<256U;i++)((volatile u8 *)wire)[i]=0;
    }
    original_asc(phase,id,payload,length,work);
}
static int word(const char **at,u32 *out) {
    const char *p=*at;u32 value=0,count=0;
    if(*p<'0' || *p>'9')return 0;
    while(*p>='0' && *p<='9') {
        u32 digit=(u32)(*p++-'0');if(++count>10U || value>(0xffffffffU-digit)/10U)return 0;
        value=value*10U+digit;
    }
    *at=p;*out=value;return 1;
}
static int action_name(const char *p,const char *name,u32 n) {
    for(u32 i=0;i<n;i++)if(p[i]!=name[i])return 0;
    return name[n]==0;
}
static int control(void *object,struct cs_kobj_attribute *attr,const char *buffer,u32 length) {
    (void)object;(void)attr;char line[128];
    if(!length || length>=128U || buffer[length-1U]!='\n')return -22;
    for(u32 i=0;i<length-1U;i++){if(!buffer[i] || buffer[i]=='\n' || buffer[i]=='\r')return -22;line[i]=buffer[i];}
    line[length-1U]=0;const char *p=line;u32 n=0,e=0,id=0;
    while(p[n] && p[n]!=' ')n++;
    if(!p[n])return -22;
    p+=n+1U;if(!word(&p,&e) || !e || *p++!=' ' || !word(&p,&id))return -22;
    if(action_name(line,"SESSION",n)) {
        if(*p || id || enabled || call_id || desired_enabled)return -16;
        session_epoch=e;last_id=0;cs_rat=2U;lease_at=cs_monotonic_ns();return (int)length;
    }
    if(e!=session_epoch)return -116;
    lease_at=cs_monotonic_ns();
    if(action_name(line,"PING",n))return !*p && !id?(int)length:-22;
    if(action_name(line,"RESUME",n)) {
        u32 rat=2U;
        if(*p && (*p++!=' ' || !word(&p,&rat) || *p))return -22;
        if(id || fault || call_id || (rat!=2U && rat!=3U))return -22;
        cs_rat=rat;desired_enabled=1;
        printk("<6>" LOG " cs_rat=%u wcdma_nb_codec_offer=%u\n",rat,rat==3U);
        return (int)length;
    }
    if(action_name(line,"SUSPEND",n)) {
        if(*p || id || call_id)return -16;
        desired_enabled=0;return (int)length;
    }
    if(!enabled || !id)return -19;
    if(action_name(line,"REARM",n)) {
        if(*p || id!=call_id || !mm_quiescent || call.mo.stage!=CS_MO_MM_CLEARING)return -16;
        if(!rearm_requested)rearm_requested=1;
        return (int)length;
    }
    if(action_name(line,"DIAL",n)) {
        if(*p++!=' ' || call_id || id<=last_id || fault)return -16;
        u32 size=0,digits=0;if(*p=='+')size++;
        while(p[size]){if(p[size]<'0' || p[size]>'9' || ++digits>32U)return -22;size++;}
        if(digits<5U)return -22;
        int result=enqueue(1,id,(const u8 *)p,size);return result?result:(int)length;
    }
    if(*p || id!=call_id)return -116;
    u32 action=action_name(line,"ANSWER",n)?4U:action_name(line,"HANGUP",n)?2U:0U;
    if(!action)return -22;
    int result=enqueue(action,id,(const u8 *)0,0);return result?result:(int)length;
}
static int session_show(void *o,struct cs_kobj_attribute *a,char *p) {
    (void)o;(void)a;
    return scnprintf(p,256U,"MF79U_CS_DRIVER 1 %u %u %u %u %u %u %u %u %u\n",
        session_epoch,enabled,desired_enabled,call.mo.stage,call_id,call.incoming,
        mm_quiescent,cs_audio_restored,fault);
}
static int caller_show(void *o,struct cs_kobj_attribute *a,char *p) {
    (void)o;(void)a;return scnprintf(p,128U,"MF79U_CS_CALLER 1 %u %u %s\n",session_epoch,call_id,caller);
}
static struct cs_kobj_attribute driver_attributes[]={
    {{"control",0200,0},(void *)0,(void *)control},
    {{"session",0400,0},session_show,(void *)0},
    {{"caller",0400,0},caller_show,(void *)0}
};
static int attach(void) {
    if(*(const volatile u8 *)0xbf59e7e1U!=1U || *(const volatile u8 *)0xbf59e8e3U!=1U ||
       !cs_audio_layout() || !cs_i2s_layout() || !cs_audio_rearm())return 0;
    if(!__sync_bool_compare_and_swap(asc_slot,(u32)original_asc,(u32)observe_asc))return 0;
    if(!__sync_bool_compare_and_swap(slot,(u32)original,(u32)observe)) {
        __sync_bool_compare_and_swap(asc_slot,(u32)observe_asc,(u32)original_asc);return 0;
    }
    if(!__sync_bool_compare_and_swap(admission,0xbf300537U,(u32)ordinary_admission)) {
        __sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
        __sync_bool_compare_and_swap(asc_slot,(u32)observe_asc,(u32)original_asc);return 0;
    }
    enabled=cs_status_armed=1;return 1;
}
static void detach(void) {
    cs_status_armed=0;
    int cc=__sync_bool_compare_and_swap(slot,(u32)observe,(u32)original);
    int asc=__sync_bool_compare_and_swap(asc_slot,(u32)observe_asc,(u32)original_asc);
    int gate=__sync_bool_compare_and_swap(admission,(u32)ordinary_admission,0xbf300537U);
    if(!cc || !asc || !gate)fault=1;
    enabled=0;
}
static int worker(void *unused) {
    (void)unused;unsigned long long next=cs_monotonic_ns();u32 stop_stage=0xffffffffU;
    for(;;) {
        if(kthread_should_stop())return 0;
        if(!enabled){
            if(desired_enabled && session_epoch && !fault && !attach())fault=1;
            msleep(20);continue;
        }
        usleep_range(1000,1500);unsigned long long now=cs_monotonic_ns();
        /* MT SIP has already answered before ANSWER_PENDING. Attach its
         * speech route while waiting for network CONNECT ACK, rather than
         * keeping the frontend closed until the peer acknowledges it. */
        cs_audio_step(cs_status_state==CS_MO_CONNECTED ||
                      (call.incoming && cs_status_state==CS_CALL_ANSWER_PENDING),now);
        /* Audio bootstrap can sleep while the adapter refreshes its lease.
         * Snapshot once: a heartbeat newer than this worker's timestamp is
         * live, not an unsigned elapsed-time wraparound. */
        unsigned long long heartbeat=lease_at;
        if(cs_lease_expired(now,heartbeat))desired_enabled=0;
        if(rearm_requested==1U && mm_quiescent && !cs_audio_started && !cs_port_tone_started) {
            if(!cs_audio_rearm())fault=1;
            else {
                rearm_requested=2U;
                if(enqueue(5,call_id,(const u8 *)0,0))rearm_requested=1U;
                stop_stage=0xffffffffU;
            }
        }
        if(!desired_enabled && !call_id){detach();continue;}
        if(!desired_enabled && call_id && stop_stage!=cs_status_state) {
            if(!enqueue(2,call_id,(const u8 *)0,0))stop_stage=cs_status_state;
        }
        if(now<next)continue;
        next=now+1000000000ULL;tick++;
        u32 stage=cs_status_state;
        if(stage==CS_MO_MM_CLEARING && !mm_quiescent)enqueue(3,call_id,(const u8 *)0,0);
        /* No connected-call timeout. Signaling establishment/clearing remains
         * bounded; MM idle is never synthesized after an expired timer. */
        u32 limit=stage==CS_MO_MM_PENDING?25U:stage==CS_CALL_RINGING?60U:
                  stage==CS_CALL_ANSWER_PENDING?30U:35U; /* TS24.008 T313 */
        if(stage && stage!=CS_MO_CONNECTED && !mm_quiescent &&
           tick-stage_tick>=limit && stop_stage!=stage)
            if(!enqueue(2,call_id,(const u8 *)0,0))stop_stage=stage;
    }
}
