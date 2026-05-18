/**
 * One-shot CDP helper that clicks the "Continue without an account"
 * button on Eversilver's Welcome page and waits for the route to change.
 *
 * Usage:
 *   node scripts/click-local-button.mjs
 */
import { WebSocket } from 'ws';

const CDP_WS = process.env.EVERSILVER_CDP_WS;
if (!CDP_WS) {
  // Discover the page WS URL automatically if not provided.
  const res = await fetch('http://127.0.0.1:19222/json/list');
  const targets = await res.json();
  const page = targets.find(t => t.type === 'page' && !t.url.includes('devtools'));
  if (!page) {
    console.error('No CEF page target found on http://127.0.0.1:19222');
    process.exit(1);
  }
  process.env.EVERSILVER_CDP_WS = page.webSocketDebuggerUrl;
}
const wsUrl = process.env.EVERSILVER_CDP_WS;
console.log('connecting to', wsUrl);

const ws = new WebSocket(wsUrl);
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
console.log('connected');

const findScript = `(() => {
  const btn = [...document.querySelectorAll('button')]
    .find(b => /Continue without an account/i.test(b.textContent || ''));
  if (!btn) return { found: false, route: location.hash };
  btn.scrollIntoView({ block: 'center' });
  btn.click();
  return { found: true, route_before: location.hash };
})()`;

const result = await send('Runtime.evaluate', {
  expression: findScript,
  returnByValue: true,
  awaitPromise: false,
});
console.log('click result:', JSON.stringify(result?.result?.value, null, 2));

// Poll route for 8s
for (let i = 0; i < 16; i++) {
  await new Promise(r => setTimeout(r, 500));
  const after = await send('Runtime.evaluate', {
    expression: 'location.hash',
    returnByValue: true,
  });
  const hash = after?.result?.value;
  console.log(`+${(i + 1) * 500}ms route=${hash}`);
  if (hash && hash !== '#/' && hash !== '#') {
    console.log('ROUTE CHANGED — auth gate passed');
    break;
  }
}
ws.close();
process.exit(0);
