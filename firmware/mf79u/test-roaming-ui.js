// B03 reports named roaming states, and may omit them before registration.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/control/web/app.js','utf8');
const start=source.indexOf('function radioNetworkLabel('),end=source.indexOf('async function status()',start);
assert.ok(start>=0&&end>start);
const context={};vm.createContext(context);vm.runInContext(source.slice(start,end),context);
for(const [network_type,simcard_roam,modem_main_state,expected] of [
 ['LTE','International','modem_init_complete','LTE · International roaming'],
 ['EDGE','Internal','modem_init_complete','EDGE · Domestic roaming'],
 ['LTE','Home','modem_init_complete','LTE · Home network'],
 ['LTE','1','modem_init_complete','LTE · Roaming'],
 ['LTE','0','modem_init_complete','LTE · Home network'],
 ['LTE','','modem_init_complete','LTE · Roaming status unknown'],
 ['LTE',undefined,'modem_init_complete','LTE · Roaming status unknown'],
 ['LTE','unexpected','modem_init_complete','LTE · Roaming status unknown'],
 ['NO_SERVICE','International','modem_init_complete','Not registered'],
 ['LIMITED_SERVICE_LTE','Home','modem_init_complete','Not registered'],
 ['','Home','modem_init_complete','Not registered'],
 ['LTE','International','modem_sim_undetected','Not registered'],
 ['LTE','Home','modem_waitpin','Not registered'],
])assert.equal(context.radioNetworkLabel({network_type,simcard_roam,modem_main_state}),expected);
assert.ok(source.includes('vendorOK?radioNetworkLabel(r)'));
console.log('B03 international/domestic/home, unknown and unregistered roaming display passed.');
