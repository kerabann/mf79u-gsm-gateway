// Isolated regression for SSH Save: invalid input must be visible beside the
// button, and a successful request must restore the button and clear secrets.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();let requests=0;
const get=id=>{if(!elements.has(id))elements.set(id,{value:'',checked:false,textContent:'Save SSH settings',disabled:false,hidden:true,classList:{toggle(){}},replaceChildren(){},append(){}});return elements.get(id)};
const context={$:get,document:{createElement(){return {append(){}}}},location:{hostname:'192.168.0.1'},api:async()=>{requests++;return {enabled:false,running:false,username:'admin',port:22,passwordSet:true}},confirm:()=>false};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/control/web/system.js','utf8'),context);
(async()=>{
 get('system-ssh-password').value='short-test';get('system-ssh-confirm').value='short-test';
 await get('system-ssh-save').onclick();
 assert.equal(requests,0);assert.match(get('system-ssh-notice').textContent,/12–128/);assert.equal(get('system-ssh-notice').hidden,false);assert.equal(get('system-ssh-save').disabled,false);
 get('system-ssh-password').value='fixture-password-long';get('system-ssh-confirm').value='different-fixture';await get('system-ssh-save').onclick();assert.equal(requests,0);assert.match(get('system-ssh-notice').textContent,/do not match/);
 get('system-ssh-confirm').value=get('system-ssh-password').value;await get('system-ssh-save').onclick();assert.equal(requests,1);assert.equal(get('system-ssh-password').value,'');assert.equal(get('system-ssh-confirm').value,'');assert.equal(get('system-ssh-save').textContent,'Save SSH settings');assert.equal(get('system-ssh-notice').textContent,'SSH settings saved.');
 const info={imei:'490154203237518',imeiWriteAvailable:true,ssh:{},gateway:{},runtime:{},operatorCodecs:[],sipCodecs:[]};context.api=async()=>info;
 await context.loadSystem();assert.equal(get('system-imei').value,info.imei);assert.equal(get('system-imei-notice').hidden,true);assert.equal(get('system-imei-save').disabled,false);
 delete info.imei;info.imeiError='IMEI read unavailable';await context.loadSystem();assert.equal(get('system-imei').value,'');assert.equal(get('system-imei-notice').hidden,false);assert.equal(get('system-imei-notice').textContent,info.imeiError);assert.equal(get('system-imei-save').disabled,true);
 delete info.imeiError;await context.loadSystem();assert.match(get('system-imei-notice').textContent,/Current IMEI unavailable/);
 info.imei='490154203237518';await context.loadSystem();assert.equal(get('system-imei').value,info.imei);assert.equal(get('system-imei-notice').hidden,true);assert.equal(get('system-imei-save').disabled,false);
 console.log('System IMEI read/error/recovery and SSH Save validation passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
