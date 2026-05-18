/**
 * Navigate Eversilver to /chat, wait for the input to render, then send
 * a message and watch for either a reply bubble or an error bubble.
 */
import { WebSocket } from 'ws';

const res = await fetch('http://127.0.0.1:19222/json/list');
const targets = await res.json();
const page = targets.find(t => t.type === 'page' && t.url.includes('tauri.localhost'));
if (!page) {
  console.error('no chat page on :19222');
  process.exit(1);
}

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.once('open', r));

let _id = 0;
function call(method, params = {}) {
  return new Promise(resolve => {
    const id = ++_id;
    const handler = raw => {
      const m = JSON.parse(raw.toString());
      if (m.id === id) {
        ws.off('message', handler);
        resolve(m.result || m.error);
      }
    };
    ws.on('message', handler);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function evalExpr(expression) {
  const r = await call('Runtime.evaluate', { expression, returnByValue: true });
  return r?.result?.value;
}

// 1. Ensure we're on /chat
await evalExpr(`window.location.hash = '#/chat';`);

// 2. Wait up to 15s for the chat input to appear
let inputFound = false;
for (let i = 0; i < 30; i++) {
  await new Promise(r => setTimeout(r, 500));
  const n = await evalExpr(`document.querySelectorAll('input[placeholder*="Type" i], textarea[placeholder*="Type" i]').length`);
  if (n > 0) { inputFound = true; break; }
}
if (!inputFound) {
  console.error('chat input never rendered');
  process.exit(2);
}
console.log('chat input ready');

// 3. Send a message via the surrounding form
const probe = `switchai-test-${Date.now()}`;
const drive = await evalExpr(`(() => {
  const input = document.querySelector('input[placeholder*="Type" i], textarea[placeholder*="Type" i]');
  if (!input) return 'no input';
  const setter = Object.getOwnPropertyDescriptor(input.constructor.prototype, 'value').set;
  setter.call(input, ${JSON.stringify(probe)});
  input.dispatchEvent(new Event('input', { bubbles: true }));
  const form = input.closest('form');
  if (form && form.requestSubmit) { form.requestSubmit(); return 'form-submit'; }
  const btn = document.querySelector('button[type="submit"]');
  if (btn) { btn.click(); return 'submit-btn'; }
  const sendBtn = document.querySelector('button[aria-label*="Send" i]');
  if (sendBtn) { sendBtn.click(); return 'send-btn'; }
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  return 'enter';
})()`);
console.log('sent:', probe, '->', drive);

// 4. Poll for the assistant's reply (or error) for up to 60s
const deadline = Date.now() + 60_000;
let lastObserved = '';
while (Date.now() < deadline) {
  await new Promise(r => setTimeout(r, 1500));
  const observed = await evalExpr(`(() => {
    // Grab the visible text of every chat bubble.
    const bubbles = [...document.querySelectorAll('div')].filter(d => {
      const t = (d.innerText || '').trim();
      return t && d.children.length === 0 && t.length > 3 && t.length < 1000;
    }).map(d => d.innerText.trim());
    return bubbles.slice(-6).join(' | ');
  })()`);
  if (observed && observed !== lastObserved) {
    console.log('  ' + observed);
    lastObserved = observed;
  }
  const haveProbe = (lastObserved || '').includes(probe);
  const haveReplyAfterProbe =
    haveProbe &&
    (lastObserved.split(probe)[1] || '').trim().length > 0;
  if (haveReplyAfterProbe) {
    console.log('REPLY OBSERVED');
    ws.close();
    process.exit(0);
  }
  if (/something went wrong|authentication issue|api key|error/i.test(lastObserved)) {
    console.log('ERROR OBSERVED in chat');
    ws.close();
    process.exit(3);
  }
}
ws.close();
console.error('no reply within 60s');
process.exit(4);
