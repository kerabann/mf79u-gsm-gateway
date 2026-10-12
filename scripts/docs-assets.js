"use strict";
// Only source assets and a loopback fixture are read. No modem API is used.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'docs/assets/screenshots');
const url = process.env.MF79U_DOCS_URL;
assert.equal(new URL(url).hostname, '127.0.0.1');
fs.mkdirSync(out, { recursive: true });
fs.mkdirSync(path.join(root, 'reports'), { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.MF79U_BROWSER_EXECUTABLE || undefined });
  const checks = [], errors = [], unexpectedWrites = [];
  try {
    const context = await browser.newContext({ locale: 'en-GB', timezoneId: 'UTC',
      deviceScaleFactor: 1, colorScheme: 'light', reducedMotion: 'reduce' });
    const page = await context.newPage();
    let variant = '';
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.route('**/*', async route => {
      const request = route.request(), target = new URL(request.url());
      assert.equal(target.origin, url, 'Documentation renderer must stay on loopback');
      if (request.method() !== 'GET') {
        if (target.pathname === '/api/wifi/scan' && variant === 'wifi-client') {
          return route.fulfill({ json: { networks: [
            { ssid: 'Demo Home', security: 'WPA2', signal: -48, supported: true },
            { ssid: 'Demo Guest', security: 'OPEN', signal: -65, supported: true }
          ] } });
        }
        unexpectedWrites.push(target.pathname);
        return route.abort();
      }
      if (!target.pathname.startsWith('/api/')) return route.continue();
      const response = await route.fetch();
      const data = await response.json();
      if (target.pathname === '/api/settings') {
        data.sip.role = variant === 'sip-trunk' ? 'TRUNK' : 'SERVER';
        data.sip.server = 'pbx.example.com';
        data.sip.username = 'gateway'; data.sip.incomingUser = 'gateway';
        data.sip.register = variant === 'sip-trunk';
        data.wifi.ssid = variant === 'wifi-client' ? 'Demo Home' : 'MF79U Demo';
        data.wifi.mode = variant === 'wifi-client' ? 'CLIENT' : 'HOTSPOT';
        data.webhooks.telegramSMS.interface = 'bridge0';
      } else if (target.pathname === '/api/settings/credentials') {
        for (const key of Object.keys(data)) data[key] = '';
      } else if (target.pathname === '/api/status') {
        data.radio.network_provider = 'Demo operator';
        data.radio.lte_rsrp = '-89 dBm'; data.radio.lte_rsrq = '-10 dB';
        data.gateway.role = variant === 'sip-trunk' ? 'TRUNK' : 'SERVER';
        data.gateway.registerMode = variant === 'sip-trunk';
        data.wifi.mode = variant === 'wifi-client' ? 'CLIENT' : 'HOTSPOT';
        data.wifi.state = variant === 'wifi-client' ? 'COMPLETED' : 'ENABLED';
        data.wifi.ssid = variant === 'wifi-client' ? 'Demo Home' : 'MF79U Demo';
        data.telegramSMS.delivered = 0;
      } else if (target.pathname === '/api/system/info') {
        data.imei = ''; data.imeiWriteAvailable = false;
        data.imeiError = 'Device identity omitted in public screenshots.';
        data.firmware = { wa_inner_version: 'B03' };
      } else if (target.pathname === '/api/sms') {
        data.messages = [{ id: '1', number: 'Demo sender',
          text: 'Example message. Synthetic text for the public UI gallery.',
          date: '26,10,12,12,00,00,+00', tag: '1', direction: 'received' }];
      }
      await route.fulfill({ response, json: data });
    });
    const tabs = ['status', 'mobile', 'sip', 'sms', 'webhooks', 'wifi', 'network', 'system'];
    async function view(tab, width, name, capture = true) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto('about:blank');
      await page.goto(url + '/#' + tab);
      await page.locator('#shell').waitFor({ state: 'visible' });
      await page.locator(`section[data-view="${tab}"]`).waitFor({ state: 'visible' });
      await page.waitForFunction(() => document.getElementById('ims-label').textContent !== 'Checking network…');
      if (tab === 'system') await page.locator('#system-imei-notice').waitFor({ state: 'visible' });
      if (tab === 'sms') await page.locator('#sms-list .sms-item').waitFor({ state: 'visible' });
      if (variant === 'wifi-client') {
        await page.locator('#wifi-scan').click();
        await page.locator('#wifi-networks button').first().waitFor({ state: 'visible' });
      }
      await page.evaluate(() => document.fonts.ready);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      assert.equal(overflow, false, `${name}/${width} overflow`);
      assert.equal(await page.locator('nav [data-page]').count(), 8);
      assert.equal(await page.locator('input[type="password"]').evaluateAll(inputs => inputs.every(input => input.value === '')), true);
      if (capture) await page.screenshot({ path: path.join(out, `${name}-${width}.png`), fullPage: true });
      checks.push({ view: name, width, overflow, captured: capture });
    }
    for (const width of [1280, 390, 320]) {
      variant = '';
      for (const tab of tabs) await view(tab, width, tab, width !== 320);
      variant = 'sip-trunk'; await view('sip', width, variant, width !== 320);
      variant = 'wifi-client'; await view('wifi', width, variant, width !== 320);
    }
    variant = '';
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(url + '/');
      await page.locator('#shell').waitFor({ state: 'visible' });
      await page.evaluate(() => showLogin());
      await page.locator('#login').waitFor({ state: 'visible' });
      await page.screenshot({ path: path.join(out, `login-${width}.png`), fullPage: true });
    }
    assert.deepEqual(errors, []); assert.deepEqual(unexpectedWrites, []);
    // An editorial overview contains unaltered, cropped source screenshots.
    const overview = await context.newPage();
    const png = name => 'data:image/png;base64,' + fs.readFileSync(path.join(out, name)).toString('base64');
    await overview.setViewportSize({ width: 1440, height: 920 });
    await overview.setContent(`<html lang="en"><style>
      *{box-sizing:border-box}body{margin:0;padding:46px;background:#eef3f9;color:#142940;font-family:Arial,sans-serif}
      .eyebrow{font-size:14px;letter-spacing:2px;color:#3367a8}h1{font-size:40px;margin:14px 0 10px}
      p{font-size:18px;color:#546880;margin:0 0 28px}.views{display:flex;align-items:flex-start;gap:24px}
      .desktop{width:1090px}.mobile{width:216px}header{padding:11px 16px;background:#fff;border-bottom:1px solid #dce4ee;font-size:13px;color:#546880}
      article{border:1px solid #dce4ee;background:white;border-radius:10px;overflow:hidden;box-shadow:0 12px 26px #14294010}
      img{display:block;width:100%}.desktop img{height:592px;object-fit:cover;object-position:top}.mobile img{height:650px;object-fit:cover;object-position:top}
      footer{color:#546880;font-size:13px;margin-top:20px}
      </style><div class="eyebrow">ZTE MF79U · DEVICE-LOCAL GATEWAY</div><h1>SIM voice &amp; SMS. Connected to SIP.</h1>
      <p>Eight focused tabs for calls, messaging, Wi-Fi and system management.</p><div class="views">
      <article class="desktop"><header>Desktop · Status</header><img src="${png('status-1280.png')}"></article>
      <article class="mobile"><header>Mobile · Mobile settings</header><img src="${png('mobile-390.png')}"></article></div>
      <footer>Rendered from the source UI with synthetic demo data. Full screenshots are in the UI gallery.</footer></html>`);
    await overview.evaluate(() => Promise.all([...document.images].map(img => img.decode())));
    await overview.screenshot({ path: path.join(root, 'docs/assets/ui-overview.png') });
    for (const name of ['architecture', 'voice-routing']) {
      const source = fs.readFileSync(path.join(root, `docs/assets/${name}.svg`), 'utf8');
      await overview.setViewportSize({ width: 1200, height: name === 'architecture' ? 580 : 660 });
      await overview.setContent('<style>body{margin:0}</style>' + source);
      assert.equal(await overview.locator('svg title').count(), 1);
      assert.equal(await overview.locator('svg desc').count(), 1);
      assert.equal(await overview.evaluate(() => [...document.querySelectorAll('svg text')].every(text => {
        const b = text.getBBox(), svg = text.ownerSVGElement.viewBox.baseVal;
        return b.x >= 0 && b.y >= 0 && b.x + b.width <= svg.width && b.y + b.height <= svg.height;
      })), true, `${name} text must stay inside the canvas`);
      await overview.screenshot({ path: path.join(root, `reports/${name}.png`) });
    }
    const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
    const frontend = ['index.html', 'style.css', 'app.js', 'system.js', 'sms-format.js'];
    fs.writeFileSync(path.join(root, 'docs/assets/provenance.json'), JSON.stringify({
      fixture: true, deviceAccess: false, playwright: require('playwright/package.json').version,
      chromium: browser.version(), screenshotWidths: [1280, 390], checkedWidths: [1280, 390, 320],
      sourceAssets: Object.fromEntries(frontend.map(name => [name, hash(path.join(root, 'firmware/mf79u/control/web', name))])),
      screenshots: fs.readdirSync(out).filter(name => name.endsWith('.png')).sort().map(name => ({ file: `screenshots/${name}`, sha256: hash(path.join(out, name)) }))
    }, null, 2) + '\n');
    await overview.close();
    const report = { passed: true, fixture: true, deviceAccess: false,
      widths: [1280, 390, 320], screenshots: 22, checks, errors, unexpectedWrites };
    fs.writeFileSync(path.join(root, 'reports/docs-assets.json'), JSON.stringify(report, null, 2) + '\n');
    console.log('PASS 30 responsive views, 22 public screenshots + overview; no overflow, JS errors, credentials or device access.');
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
