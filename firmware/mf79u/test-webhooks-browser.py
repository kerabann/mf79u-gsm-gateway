#!/usr/bin/env python3
"""All eight tabs + Telegram scoped Save in a disposable Playwright fixture."""
from pathlib import Path
import os
import subprocess
import sys
import time
import urllib.request

root = Path(__file__).resolve().parents[2]
report = root / 'reports/webhooks-ui'
report.mkdir(parents=True, exist_ok=True)
server = subprocess.Popen([sys.executable, str(Path(__file__).with_name('test-ui-e2e-server.py')), '--port', '18093'], stdout=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:18093/api/session', timeout=1).close()
            break
        except OSError:
            time.sleep(.1)
    else:
        raise RuntimeError('Disposable fixture did not start')
    script = r'''
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
let browser;
(async()=>{
 browser=await chromium.launch({headless:true,executablePath:process.env.MF79U_BROWSER_EXECUTABLE||undefined});const page=await browser.newPage(),errors=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 const tabs=['status','mobile','sip','sms','webhooks','wifi','network','system'];
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:900});
  for(const tab of tabs){
   await page.goto('http://127.0.0.1:18093/#'+tab);await page.locator('#shell').waitFor({state:'visible'});await page.locator(`section[data-view="${tab}"]`).waitFor({state:'visible'});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert.equal(overflow,false,`${tab}/${width} overflows`);
   assert.equal(await page.locator('nav [data-page]').count(),8);
   if(tab==='webhooks'){
    assert.equal(await page.locator('section[data-view="webhooks"] article').count(),1);
    assert.equal(await page.getByText('Delete after send to chat',{exact:true}).count(),1);
    await page.screenshot({path:process.env.MF79U_BROWSER_REPORT+`/webhooks-${width}.png`,fullPage:true});
   }
   checks.push({tab,width,overflow});
  }
 }
 await page.goto('http://127.0.0.1:18093/#mobile');await page.locator('#shell').waitFor({state:'visible'});
 await page.locator('#voice-vowifi-sms-option').waitFor({state:'attached'});
 await page.locator('#voice-mode').selectOption('VOWIFI_SMS');await page.locator('#save-settings').click();
 await page.waitForFunction(()=>document.getElementById('voice-cellular-sms').textContent.includes('registered'));
 assert.equal(await page.locator('#voice-mode').inputValue(),'VOWIFI_SMS');
 await page.goto('http://127.0.0.1:18093/#sms');await page.locator('#shell').waitFor({state:'visible'});
 await page.waitForFunction(()=>document.getElementById('sms-transport').textContent.includes('Calls remain VoWiFi only'));
 await page.goto('http://127.0.0.1:18093/#webhooks');await page.locator('#shell').waitFor({state:'visible'});
 await page.locator('#telegram-enabled').check();await page.locator('#telegram-bot-token').fill('1234:'+ 'x'.repeat(30));await page.locator('#telegram-chat-id').fill('-1001234');await page.locator('#telegram-interface').selectOption('bridge0');await page.locator('#telegram-delete-after-send').check();
 let writes=[];page.on('request',r=>{if(r.method()!=='GET')writes.push(new URL(r.url()).pathname)});
 await page.locator('#save-settings').click();await page.waitForFunction(()=>document.getElementById('notice').textContent==='Webhook settings saved.');
 assert.deepEqual(writes,['/api/webhooks/telegram']);assert.equal(await page.locator('#telegram-bot-token').inputValue(),'');assert.equal(await page.locator('#telegram-delete-after-send').isChecked(),true);
 assert.equal(await page.locator('#telegram-interface option[value="wan5"]').count(),0);
 assert.deepEqual(errors,[]);
 const report={passed:true,fixture:true,deviceAccess:false,realTelegramOrSMS:false,views:checks,scopedSave:true,deleteCheckbox:true,tokenCleared:true,errors};
 fs.writeFileSync(process.env.MF79U_BROWSER_REPORT+'/result.json',JSON.stringify(report,null,2)+'\n');console.log('PASS all eight tabs at 1280/390/320px (24 views), Telegram scoped Save/deletion checkbox/token clearing; no overflow or JS errors.');await browser.close();
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exitCode=1});
'''
    subprocess.run(['node', '-e', script], cwd=root, env=dict(os.environ, MF79U_BROWSER_REPORT=str(report)), check=True)
finally:
    server.terminate()
    server.wait(timeout=10)
