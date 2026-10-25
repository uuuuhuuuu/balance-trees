// Optional integration check: a running showcase on localhost:8000 and Chromium.
// Uses Node 24's native WebSocket; no browser automation dependencies.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const artifacts = await mkdtemp(join(tmpdir(), 'balance-trees-browser-'));
const browser = spawn(process.env.CHROMIUM ?? 'chromium', [
  '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
  '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
  `--user-data-dir=${join(artifacts, 'profile')}`, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'] });
let socket;
try {
  const endpoint = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Chromium did not start in 15 seconds')), 15000);
    browser.once('error', reject);
    browser.once('exit', code => reject(new Error(`Chromium exited: ${code}`)));
    let stderr = '';
    browser.stderr.on('data', data => {
      stderr += data;
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) { clearTimeout(timer); resolve(match[1]); }
    });
  });
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let id = 0;
  const pending = new Map(), exceptions = [];
  socket.onmessage = event => {
    const value = JSON.parse(event.data);
    if (value.method === 'Runtime.exceptionThrown') exceptions.push(value.params.exceptionDetails);
    if (value.id) {
      const request = pending.get(value.id); pending.delete(value.id);
      clearTimeout(request.timer);
      if (value.error) request.reject(new Error(JSON.stringify(value.error)));
      else request.resolve(value.result);
    }
  };
  const call = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const key = ++id;
    const timer = setTimeout(() => { pending.delete(key); reject(new Error(`CDP timeout: ${method}`)); }, 20000);
    pending.set(key, { resolve, reject, timer });
    socket.send(JSON.stringify({ id: key, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const { targetId } = await call('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await call('Target.attachToTarget', { targetId, flatten: true });
  const page = (method, params = {}) => call(method, params, sessionId);
  await page('Runtime.enable'); await page('Page.enable');
  const evaluate = async expression => {
    const response = await page('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails));
    return response.result.value;
  };
  const waitFor = async expression => {
    const until = Date.now() + 30000;
    while (Date.now() < until) {
      if (await evaluate(expression)) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`Timed out waiting for ${expression}`);
  };
  const navigate = async path => {
    await page('Page.navigate', { url: `http://127.0.0.1:8000/${path}` });
    await waitFor('document.readyState === "complete"');
  };
  const screenshot = async name => {
    const { data } = await page('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(join(artifacts, name), Buffer.from(data, 'base64'));
  };
  await page('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await navigate('index.html');
  await waitFor('document.querySelector("#source-badge")?.textContent === "Python implementation"');
  const registeredCount = await evaluate('fetch("./api/config").then(r => r.json()).then(data => Object.keys(data.strategies).length)');
  assert.equal(await evaluate('document.querySelector("#strategy").options.length'), registeredCount + 1);
  await evaluate(`document.querySelector('#tutorial').close(); document.querySelector('#strategy').value='random-level'; document.querySelector('#count').value='10000'; document.querySelector('#order').value='random'; document.querySelector('#generate').click();`);
  await waitFor('document.querySelector("#source-badge").textContent === "Browser simulation"');
  await evaluate('document.querySelector("#play").click()');
  await waitFor('document.querySelector("#metric-nodes").textContent === "10000" && document.querySelector("#play-label").textContent === "Replay"');
  assert.equal(await evaluate('document.querySelectorAll("#nodes .tree-node").length <= 48'), true);
  assert.equal(await evaluate('document.body.classList.contains("compact-preview")'), true);
  assert.match(await evaluate('document.querySelector("#visible-count").textContent'), /10,000 nodes shown/);
  assert.equal(await evaluate('document.querySelector("#error").hidden'), true);
  await screenshot('preview-desktop.png');
  await navigate('results.html');
  await waitFor('document.querySelectorAll("[data-workload]:not([hidden])").length === 1');
  assert.equal(await evaluate('[...document.querySelectorAll("[data-workload]:not([hidden]) img")].every(img => img.complete && img.naturalWidth > 0)'), true);
  await evaluate('document.querySelector("#workload").value="increasing"; document.querySelector("#workload").dispatchEvent(new Event("change"))');
  assert.equal(await evaluate('document.querySelector("[data-workload]:not([hidden])").dataset.workload'), 'increasing');
  await screenshot('graphs-desktop.png');
  await navigate('summary.html');
  const expected = await evaluate('fetch("./results/results.json").then(r => r.json()).then(data => ({groups:data.summaries.length,strategies:data.metadata.strategies.length}))');
  assert.equal(await evaluate('document.querySelectorAll("article.card").length'), expected.strategies);
  assert.equal(await evaluate('document.querySelectorAll("#all-results tbody tr").length'), expected.groups);
  await screenshot('summary-desktop.png');
  await page('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  assert.equal(await evaluate('document.documentElement.scrollWidth <= 390'), true);
  await screenshot('summary-mobile.png');
  await navigate('results.html');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= 390'), true);
  await screenshot('graphs-mobile.png');
  await navigate('index.html');
  await waitFor('document.querySelector("#source-badge")?.textContent === "Python implementation"');
  await evaluate(`document.querySelector('#strategy').value='hash-priority'; document.querySelector('#count').value='1000'; document.querySelector('#generate').click();`);
  await waitFor('document.querySelector("#source-badge").textContent === "Browser simulation"');
  await evaluate('document.querySelector("#play").click()');
  await waitFor('document.querySelector("#metric-nodes").textContent === "1000" && document.querySelector("#play-label").textContent === "Replay"');
  assert.equal(await evaluate('document.querySelectorAll("#nodes .tree-node").length <= 12'), true);
  await evaluate('document.querySelector("#tree-stage").scrollIntoView()');
  await screenshot('preview-mobile.png');
  const overflow = await evaluate('[...document.querySelectorAll("body *")].filter(element => element.getBoundingClientRect().right > 391).slice(0,12).map(element => ({tag:element.tagName,id:element.id,className:String(element.className),right:element.getBoundingClientRect().right}))');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= 390'), true, JSON.stringify(overflow));
  assert.deepEqual(exceptions, []);
  console.log(`Browser checks passed: 10,000-key random-level preview, 48-node window, graphs, filters, full table and mobile layout. Screenshots: ${artifacts}`);
} finally {
  socket?.close();
  browser.kill('SIGTERM');
}
