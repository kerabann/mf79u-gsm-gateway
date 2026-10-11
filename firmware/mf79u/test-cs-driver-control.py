#!/usr/bin/env python3
"""Actual kernel command parser/gates with instrumented CC enqueue; no hardware."""
from pathlib import Path
import subprocess,tempfile,json
B=Path(__file__).resolve().parent
s=(B/'src/cs-driver-runtime.inc').read_text()
def fn(name):
 start=s.index('static int '+name+'(');brace=s.index('{',start);end=brace+1;depth=1
 while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[start:end]
code=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
typedef uint32_t u32;typedef unsigned char u8;
struct cs_kobj_attribute {int unused;};
#define CS_MO_MM_CLEARING 8
static struct {struct {u32 stage;}mo;}call;
static u32 session_epoch,enabled,call_id,desired_enabled,fault,rearm_requested,mm_quiescent,last_id;
static unsigned long long lease_at;
static u32 action_seen,id_seen,count;
static unsigned long long cs_monotonic_ns(void){return 100;}
static int enqueue(u32 action,u32 id,const u8 *p,u32 n){(void)p;(void)n;action_seen=action;id_seen=id;count++;return 0;}
'''+fn('word')+'\n'+fn('action_name')+'\n'+fn('control')+r'''
static int send(const char *s){return control(0,0,s,strlen(s));}
int main(void){
 assert(send("SESSION 10 0\n")>0 && session_epoch==10);
 assert(send("RESUME 9 0\n")==-116 && !desired_enabled);
 assert(send("RESUME 10 0\n")>0 && desired_enabled);
 assert(send("SESSION 11 0\n")==-16);
 enabled=1;
 assert(send("DIAL 10 1 +1234567\n")>0 && action_seen==1 && id_seen==1);
 assert(send("DIAL 10 2 12;ATH\n")<0);
 assert(send("DIAL 42949672960 1 1234567\n")<0);
 assert(send("DIAL 10 2 1234567\nHANGUP 10 2\n")<0);
 call_id=last_id=1;call.mo.stage=9;
 u32 saved=count;
 assert(send("ANSWER 10 2\n")==-116 && count==saved);
 assert(send("ANSWER 9 1\n")==-116 && count==saved);
 assert(send("ANSWER 10 1\n")>0 && action_seen==4);
 assert(send("SUSPEND 10 0\n")==-16);
 assert(send("REARM 10 1\n")==-16);
 call.mo.stage=8;mm_quiescent=1;
 assert(send("REARM 10 1\n")>0 && rearm_requested==1);
 rearm_requested=2;
 assert(send("REARM 10 1\n")>0 && rearm_requested==2);
 call_id=0;call.mo.stage=0;
 assert(send("DIAL 10 1 1234567\n")==-16);
 assert(send("DIAL 10 2 1234567\n")>0);
 puts("PASS kernel command parser: epoch, call ownership, replay, bounded digits, MM-gated idempotent rearm");
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'test.c';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
(B/'build/cs-driver-control-fixture.json').write_text(json.dumps({'physical_access':False,'actual_control_function':True,'stale_epoch_and_call_rejected':True,'idempotent_rearm':True},indent=2)+'\n')
