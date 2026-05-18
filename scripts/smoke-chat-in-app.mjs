/**
 * End-to-end smoke test: drive a chat message in the running Eversilver UI
 * via CDP and assert that a non-error reply lands within a sensible window.
 *
 * Run after `pnpm win:switchai` has wired the config and both the
 * SwitchAI backend (:8088) and Eversilver (:7788 + UI) are up.
 *
 * Usage:
 *   node scripts/smoke-chat-in-app.mjs
 */
import { WebSocket } from 'ws';

async function findChatPage() {
  const res = await fetch('http://127.0.0.1:19222/json/list');
  const targets = await res.json();
  // The main app window; skip mascot/overlay child webviews.
  return targets.find(
    t => t.type === 'page' && t.url.startsWith('http://tauri.localhost')
  );
}

const page = await findChatPage();
if (!page) {
  console.error('No CEF page on :19222 — is Eversilver running?');
  process.exit(1);
}
console.log('connecting to', page.webSocketDebuggerUrl);

const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0;
const inflight = new Map();
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    id += 1;
    inflight.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
ws.on('message', raw => {
  const msg = JSON.parse(raw.toString());
  if (msg.id && inflight.has(msg.id)) {
    const { resolve, reject } = inflight.get(msg.id);
    inflight.delete(msg.id);
    if (msg.error) reject(new Error(msg.error.message));
    else resolve(msg.result);
  }
});

await new Promise(r => ws.once('open', r));

// 1. Navigate to /chat
await send('Runtime.evaluate', {
  expression: "window.location.hash = '#/chat';",
  returnByValue: true,
});
await new Promise(r => setTimeout(r, 1200));

// 2. Snapshot the visible bubble count + last bubble text so we can detect
//    a new reply landing.
const initialSnapshot = await send('Runtime.evaluate', {
  expression: `(() => {
    const bubbles = [...document.querySelectorAll('[class*="bubble"], [class*="message"]')];
    return { count: bubbles.length, lastText: bubbles[bubbles.length - 1]?.innerText || '' };
  })()`,
  returnByValue: true,
});
const baseline = initialSnapshot?.result?.value || { count: 0, lastText: '' };
console.log('baseline:', baseline);

// 3. Find the text input + send button, fill it, click.
const ts = Date.now();
const probe = `smoke-${ts}`;
const driveResult = await send('Runtime.evaluate', {
  expression: `(() => {
    const input = document.querySelector('input[type="text"][placeholder*="Type" i], textarea[placeholder*="Type" i], textarea');
    if (!input) return { ok: false, reason: 'no chat input found' };
    const setter = Object.getOwnPropertyDescriptor(input.constructor.prototype, 'value').set;
    setter.call(input, ${JSON.stringify(probe)});
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    // Try clicking a send button; if not present, dispatch Enter.
    const send = document.querySelector('button[aria-label*="Send" i], button[type="submit"], button[class*="send" i]');
    if (send) { send.click(); return { ok: true, via: 'button' }; }
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
    return { ok: true, via: 'enter' };
  })()`,
  returnByValue: true,
});
console.log('drive:', driveResult?.result?.value);

// 4. Poll for ~45s waiting for a new bubble whose text differs from the
//    probe (so we know the assistant replied).
const deadline = Date.now() + 45_000;
let reply = null;
while (Date.now() < deadline) {
  await new Promise(r => setTimeout(r, 1000));
  const snap = await send('Runtime.evaluate', {
    expression: `(() => {
      const bubbles = [...document.querySelectorAll('[class*="bubble"], [class*="message"]')];
      const texts = bubbles.map(b => b.innerText);
      const last = texts[texts.length - 1] || '';
      return {
        count: bubbles.length,
        last,
        hasError: texts.some(t => /something went wrong|error/i.test(t)),
      };
    })()`,
    returnByValue: true,
  });
  const cur = snap?.result?.value;
  process.stdout.write(`  t+${Math.round((Date.now() - ts) / 1000)}s count=${cur.count} hasError=${cur.hasError} last=${JSON.stringify((cur.last || '').slice(0, 60))}\n`);
  if (cur.hasError) {
    reply = { ok: false, text: cur.last };
    break;
  }
  if (cur.count > baseline.count + 1 && cur.last && cur.last !== probe) {
    reply = { ok: true, text: cur.last };
    break;
  }
}

ws.close();
if (!reply) {
  console.error('NO REPLY within 45s');
  process.exit(2);
}
if (!reply.ok) {
  console.error('CHAT ERROR:', reply.text);
  process.exit(3);
}
console.log('REPLY OK:', JSON.stringify(reply.text));
process.exit(0);
