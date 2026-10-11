// Run the complete frontend against a non-secret DOM/API fixture.
// Regressions cover transaction controls, scoped saves, drafts and late polls.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(__dirname+'/control/web/index.html','utf8');
const elements=new Map(),timers=[];
function element(id='') {return {id,value:'',checked:false,type:'text',hidden:false,disabled:false,textContent:'',dataset:{},children:[],listeners:{},classList:{toggle(){}},setAttribute(){},removeAttribute(){},replaceChildren(){this.children=[]},append(...v){this.children.push(...v)},addEventListener(name,fn){this.listeners[name]=fn}}}
for(const id of html.matchAll(/id="([^"]+)"/g))elements.set(id[1],element(id[1]));
const get=id=>elements.get(id)||element(id);
const sections=new Map();for(const m of html.matchAll(/<section data-view="([^"]+)"[^>]*>([\s\S]*?)<\/section>/g))sections.set(m[1],[...m[2].matchAll(/<(?:input|select|textarea)[^>]*id="([^"]+)"/g)].map(x=>get(x[1])));
const views=[...sections.keys()].map(view=>Object.assign(element(),{dataset:{view}}));
const pages=[...sections.keys()].map(page=>Object.assign(element(),{dataset:{page}}));
const saveControls=element();
const document={getElementById:get,createElement:()=>element(),querySelector:()=>saveControls,querySelectorAll(selector){
 if(selector==='[data-view]')return views;if(selector==='[data-page]')return pages;
 if(selector.startsWith('#'))return [get(selector.slice(1))];
 const match=selector.match(/section\[data-view="([^"]+)"\]/);if(match)return sections.get(match[1]);
 if(selector.startsWith('section:not'))return [...sections].filter(([v])=>v!=='system').flatMap(([,fields])=>fields);
 return [];
}};
const profile={webhooks:{telegramSMS:{enabled:false,botTokenSet:true,chatId:'-1001234',interface:'bridge0',deleteAfterSend:false}},voiceMode:'AUTO',vowifi:{uplink:'USB',gateway:'192.168.0.169',dns:['1.1.1.1']},internetSharing:false,sip:{role:'SERVER',extension:'100',extensionPassword:'fixture-only-password',extensionPasswordSet:true,server:'pbx',port:5060,transport:'UDP',username:'fixture',realm:'*',bind:'192.168.0.1',register:false,incomingUser:'100',localPort:5080,trustedPeers:[],codecs:['OPUS','PCMA']},wifi:{mode:'HOTSPOT',enabled:true,ssid:'Fixture AP',security:'WPA2',password:'fixture-only-wifi',passwordSet:true,network:{mode:'DHCP',dns:[]}},lan:{mode:'STATIC',address:'192.168.0.1/24',gateway:'192.168.0.1',subnet:'192.168.0.0/24',poolStart:'192.168.0.2',poolEnd:'192.168.0.253',dns:['1.1.1.1'],routes:[]}};
let saved=structuredClone(profile),requests=[],snapshot={radio:{},gateway:{running:true,role:'SERVER'},runtime:{voiceReady:true,imsReady:true,imsAccess:'WIFI',callBackend:'none'},wifi:{mode:'HOTSPOT',state:'ENABLED'},interfaces:[],pendingNetwork:'',networkError:''};
let deferredMutation='',releaseMutation;
const ctx={document,location:{hash:'#network',origin:'http://fixture',hostname:'fixture'},window:{},history:{replaceState(){}},structuredClone,setInterval:fn=>timers.push(fn),confirm:()=>false,console,
 api:undefined,fetch:async(path,opt)=>{let value={};const name=path.slice(5);requests.push({name,method:opt.method,body:opt.body?JSON.parse(opt.body):null});if(name===deferredMutation)await new Promise(resolve=>releaseMutation=resolve);
 if(name==='session')value={csrf:'fixture'};else if(name==='settings'&&opt.method==='GET')value=structuredClone(saved);else if(name==='settings'&&opt.method==='PUT')saved=JSON.parse(opt.body);else if(name==='settings/credentials')value={sipPassword:saved.sip.password||'',sipExtensionPassword:saved.sip.extensionPassword||'',wifiPassword:saved.wifi.password||''};else if(name==='webhooks/telegram'){saved.webhooks.telegramSMS=JSON.parse(opt.body)}else if(name==='status')value=structuredClone(snapshot);else if(name==='apply')value={networkToken:'fixture-network'};else if(name==='network/confirm'){snapshot.pendingNetwork='';snapshot.networkNotice='Network settings confirmed.'}
 return {ok:true,status:200,json:async()=>value};
 }};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/control/web/app.js','utf8'),ctx);
const run=code=>vm.runInContext(code,ctx);
(async()=>{
 await ctx.entered();requests=[];
 // A malformed Network draft must not prevent a scoped Mobile save.
 get('lan-pool').value='invalid draft';ctx.changed();ctx.location.hash='#mobile';get('voice-mode').value='CS';ctx.changed();
 const candidate=ctx.collect();assert.equal(candidate.voiceMode,'CS');assert.equal(candidate.lan.poolStart,profile.lan.poolStart);
 await ctx.refreshSettings(['mobile']);assert.equal(get('lan-pool').value,'invalid draft');ctx.location.hash='#network';ctx.route();assert.equal(get('save-state').textContent,'Unsaved changes');
 assert.throws(()=>ctx.collect(),/IP pool/);assert.equal(run('savedSettings.lan.poolStart'),profile.lan.poolStart);
 // Only SIP's own draft and codecs belong to its Save.
 ctx.location.hash='#sip';get('sip-role').value='DISABLED';run('settings.sip.codecs=[]');const disabled=ctx.collect();assert.equal(disabled.sip.role,'DISABLED');assert.equal(disabled.voiceMode,'AUTO');get('sip-role').value='SERVER';assert.throws(()=>ctx.collect(),/codec/);
 ctx.renderNetworkState({pendingNetwork:'fixture-network',networkReady:false,networkRemaining:90});assert.equal(get('network-confirm').disabled,true);assert.equal(get('network-rollback').disabled,false);assert.equal(get('save-settings').disabled,true);
 ctx.renderNetworkState({pendingNetwork:'fixture-network',networkReady:true,networkRemaining:42});assert.equal(get('network-confirm').disabled,false);assert.match(get('network-progress').textContent,/42 seconds/);
 ctx.renderNetworkState({pendingNetwork:'fixture-network',networkReady:false,networkRollingBack:true});assert.equal(get('network-rollback').disabled,true);
 ctx.renderNetworkState({networkNotice:'Network changes rolled back.'});assert.equal(get('network-confirm').disabled,true);assert.equal(get('network-pending').hidden,true);assert.equal(get('notice').textContent,'');assert.equal(get('network-notice').hidden,true);
 ctx.location.hash='#network';ctx.renderNetworkState({networkError:'Actual connection failure'});assert.equal(get('network-notice').hidden,false);
 // Automatic rollback reloads the confirmed network fields, retaining SIP drafts.
 get('lan-pool').value='192.168.0.3-192.168.0.253';run('dirtyViews.delete("network")');ctx.location.hash='#sip';get('sip-username').value='unsaved-sip';ctx.changed();run('networkToken="fixture-network"');snapshot.networkNotice='Network changes rolled back.';await ctx.status();assert.equal(get('lan-pool').value,'192.168.0.2-192.168.0.253');assert.equal(get('sip-username').value,'unsaved-sip');
 // A late readiness poll cannot offer the competing action during a mutation.
 ctx.location.hash='#network';snapshot.pendingNetwork='fixture-network';snapshot.networkReady=true;run('networkToken="fixture-network"');ctx.renderNetworkState(snapshot);
 deferredMutation='network/rollback';const rollbackClick=get('network-rollback').onclick();await ctx.status();
 assert.equal(get('network-confirm').disabled,true);assert.equal(get('network-rollback').disabled,true);assert.match(get('network-progress').textContent,/Restoring/);
 snapshot.pendingNetwork='';releaseMutation();await rollbackClick;
 snapshot.pendingNetwork='fixture-network';run('networkToken="fixture-network"');ctx.renderNetworkState(snapshot);
 deferredMutation='network/confirm';const confirmClick=get('network-confirm').onclick();await ctx.status();
 assert.equal(get('network-rollback').disabled,true);assert.equal(get('network-confirm').disabled,true);assert.match(get('network-progress').textContent,/Confirming/);
 releaseMutation();await confirmClick;deferredMutation='';
 // Webhooks Save is scoped, retains other drafts and never applies/reloads SIP.
 ctx.location.hash='#webhooks';ctx.route();assert.equal(saveControls.hidden,false);assert.equal(views.length,8);
 get('telegram-enabled').checked=true;get('telegram-bot-token').value='fixture-only-token';get('telegram-delete-after-send').checked=true;ctx.changed();
 const telegram=ctx.collect();assert.equal(telegram.webhooks.telegramSMS.deleteAfterSend,true);assert.equal(telegram.sip.username,profile.sip.username);
 requests=[];await ctx.save();const writes=requests.filter(r=>r.method!=='GET');assert.equal(writes.length,1);assert.equal(writes[0].name,'webhooks/telegram');assert.equal(writes[0].body.interface,'bridge0');assert.equal(writes[0].body.botTokenSet,true);assert.equal(writes[0].body.deleteAfterSend,true);assert.equal(get('telegram-bot-token').value,'');
 ctx.telegramInterfaces([{name:'wan0'},{name:'wan5'}],'wan0');assert.equal(get('telegram-interface').value,'wan0');assert(!get('telegram-interface').children.some(o=>o.value==='wan5'));
 // Logout/expiry erase editable credentials and transaction/draft state.
 ctx.showLogin();assert.equal(run('settings'),null);assert.equal(run('savedSettings'),null);assert.equal(run('networkToken'),'');
 console.log('PASS complete frontend: scoped saves, invalid drafts, network apply/confirm/rollback, automatic restoration and session reset');
})().catch(e=>{console.error(e);process.exitCode=1});
