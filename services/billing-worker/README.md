# Eversilver Billing Worker

Cloudflare Worker backend for **Razorpay UPI subscriptions** (India).
Handles subscription creation, webhook ingestion, status, and cancellation
for two INR plans:

| Tier  | Price       | Plan env var               |
| ----- | ----------- | -------------------------- |
| Pro   | ₹499 / mo   | `RAZORPAY_PLAN_ID_PRO`     |
| Ultra | ₹1499 / mo  | `RAZORPAY_PLAN_ID_ULTRA`   |

Built with [Hono v4](https://hono.dev) + Workers KV. Stateless, edge-deployed,
no Node-only dependencies on the hot path.

---

## Endpoints

| Method | Path                       | Auth   | Purpose                                                   |
| ------ | -------------------------- | ------ | --------------------------------------------------------- |
| GET    | `/health`                  | public | Liveness                                                  |
| POST   | `/api/billing/subscribe`   | JWT    | `{ tier: "pro"\|"ultra" }` → `{ subscriptionId, keyId }`   |
| GET    | `/api/billing/status`      | JWT    | Current tier + subscription state                         |
| POST   | `/api/billing/cancel`      | JWT    | Cancel at period end (no immediate revoke)                |
| POST   | `/api/billing/webhook`     | HMAC   | Razorpay events, `X-Razorpay-Signature` verified          |

Auth is **HS256 JWT** in `Authorization: Bearer <token>`. The same `JWT_SECRET`
must be shared with the frontend issuer.

Webhook signature is verified with `HMAC-SHA256(raw_body, RAZORPAY_WEBHOOK_SECRET)`
in constant time using WebCrypto.

---

## One-time setup

```bash
cd services/billing-worker
npm install
```

### 1. Create the KV namespace

```bash
npx wrangler kv:namespace create BILLING_KV
npx wrangler kv:namespace create BILLING_KV --preview
```

Paste both ids into `wrangler.toml` under `[[kv_namespaces]]`.

### 2. Create Razorpay plans (one-time, in Razorpay dashboard)

In the Razorpay Dashboard → **Subscriptions → Plans**, create two monthly plans
in INR (₹499 and ₹1499). Note the `plan_xxx` ids.

Update `wrangler.toml`:

```toml
[vars]
RAZORPAY_PLAN_ID_PRO   = "plan_xxx_pro"
RAZORPAY_PLAN_ID_ULTRA = "plan_xxx_ultra"
ALLOWED_ORIGIN         = "https://eversilver.app"
```

### 3. Set secrets

```bash
npx wrangler secret put RAZORPAY_KEY_ID
npx wrangler secret put RAZORPAY_KEY_SECRET
npx wrangler secret put RAZORPAY_WEBHOOK_SECRET
npx wrangler secret put JWT_SECRET
```

`JWT_SECRET` must be at least 32 characters and identical to what your
frontend / auth service uses to sign tokens.

### 4. Configure the webhook in Razorpay

In Dashboard → **Settings → Webhooks**, add:

* **URL**: `https://eversilver-billing-worker.<your-account>.workers.dev/api/billing/webhook`
* **Secret**: same value you set for `RAZORPAY_WEBHOOK_SECRET`
* **Events**:
  - `subscription.activated`
  - `subscription.charged`
  - `subscription.cancelled`
  - `subscription.halted`
  - `subscription.completed`
  - `payment.failed`

---

## Deploy

```bash
npx wrangler deploy
```

The worker is live at the `workers.dev` subdomain printed by Wrangler. Point
your frontend `BILLING_API_BASE` at it (or attach a custom route).

### Local dev

```bash
cp .dev.vars.example .dev.vars
# edit .dev.vars with test keys
npm run dev
```

For local webhook testing, use the [Razorpay CLI](https://github.com/razorpay/razorpay-cli)
or `ngrok` to forward to `http://localhost:8787/api/billing/webhook`.

---

## Tests

```bash
npm test
```

Covers:
- `/health` smoke
- subscribe happy path + missing auth + invalid tier
- status defaults + auth
- cancel: 404 path + success path
- webhook: bad signature, signature-verified activation, idempotency, halted → free
- JWT: wrong-secret rejection, expired-token rejection

---

## Frontend integration

```ts
// 1. Create the subscription
const r = await fetch(`${API}/api/billing/subscribe`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${jwt}`,
  },
  body: JSON.stringify({ tier: 'pro' }),
});
const { subscriptionId, keyId } = await r.json();

// 2. Open Razorpay Checkout
const rzp = new (window as any).Razorpay({
  key: keyId,
  subscription_id: subscriptionId,
  name: 'Eversilver',
  description: 'Pro plan — monthly',
  handler: (resp: any) => {
    // resp.razorpay_payment_id / razorpay_subscription_id / razorpay_signature
    // Activation is also confirmed server-side via webhook.
  },
  theme: { color: '#0b0b0b' },
});
rzp.open();
```

The worker doesn't trust the client `handler` callback. Tier is upgraded only
when `subscription.activated` / `subscription.charged` arrives via webhook.

---

## D1 alternative

If you'd rather use SQL than KV, apply `schema.sql`:

```bash
npx wrangler d1 create eversilver-billing
npx wrangler d1 execute eversilver-billing --file=./schema.sql
```

Uncomment the `[[d1_databases]]` block in `wrangler.toml`, then swap the
`BillingStore` implementation in `src/db.ts` to read/write D1. KV is the default
because subscription state is tiny, read-heavy, and tolerates eventual
consistency.

---

## Caveats

1. **Webhook delivery is eventually consistent.** Don't grant access purely on
   the `subscribe` response; wait for `subscription.activated`. The status
   endpoint reflects the webhook-driven truth.
2. **KV eventual consistency.** A `PUT` may take a few seconds to propagate
   globally. For multi-region UX, read the user's own record from the same
   colo when possible, or move to D1 if strict read-after-write is required.
3. **`total_count: 120`** in `createSubscription` simulates "until cancelled"
   for monthly plans (10 years). Razorpay does not have an unbounded option;
   adjust to your retention policy.
4. **Idempotency window** is 30 days (KV TTL). Razorpay rarely retries beyond
   24h, so this is safe.
5. **Currency is INR** and **plans must be created in INR** in the Razorpay
   dashboard. UPI is enabled automatically for INR subscriptions.
6. **`nodejs_compat`** is enabled in `wrangler.toml` only as a safety net for
   the `razorpay` npm package if you swap to it later. The shipped code uses
   WebCrypto + fetch directly and does **not** require it at runtime.
