// Native voice state overrides stale SIP state and identifies the IMS access.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/control/web/app.js','utf8').match(/^async function status\(\).+$/m)[0];
const elements=new Map();const get=id=>{if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,disabled:false,classList:{toggle(){}},replaceChildren(){},append(){}});return elements.get(id)};
const snapshot={radio:{},vendorSession:false,gateway:{imsReady:false,role:'TRUNK',running:true,registerMode:false,activeCall:false},runtime:{voiceBackend:'ims',voiceReady:true,imsReady:true,imsAccess:'WIFI',registrationState:'ready',callBackend:'none'},wifi:{mode:'CLIENT',state:'COMPLETED'},interfaces:[]};
const ctx={$:get,api:async()=>snapshot,settings:{sip:{server:'pbx',port:5060,transport:'UDP'},lan:{address:'192.168.0.1/24'}},document:{createElement(){return {append(){}}}},networkToken:'',networkNotice:'',notice(){}};
vm.createContext(ctx);vm.runInContext(source,ctx);
(async()=>{
 await ctx.status();assert.equal(get('voice-current').textContent,'VoWiFi');assert.equal(get('ims-state').textContent,'Registered');assert.equal(get('voice-vowifi-option').disabled,false);
 snapshot.gateway.imsReady=true;Object.assign(snapshot.runtime,{voiceReady:false,imsReady:false,voiceBackend:'none',imsAccess:'NONE',registrationState:'waiting_for_wifi',smsOnly:true});
 await ctx.status();assert.equal(get('voice-current').textContent,'Unavailable');assert.equal(get('ims-state').textContent,'Not registered');assert.match(get('call-state').textContent,/Voice unavailable/);
 Object.assign(snapshot.runtime,{voiceReady:true,imsReady:true,voiceBackend:'ims',imsAccess:'LTE',registrationState:'ready'});await ctx.status();assert.equal(get('voice-current').textContent,'VoLTE');
 delete snapshot.runtime.imsAccess;await ctx.status();assert.equal(get('voice-vowifi-option').disabled,true);
 console.log('PASS actual status UI: Wi-Fi IMS, LTE IMS, stale SIP readiness and legacy capability gate');
})().catch(e=>{console.error(e);process.exitCode=1});
