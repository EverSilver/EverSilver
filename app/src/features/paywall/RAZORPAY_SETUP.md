# Razorpay UPI Setup for Eversilver

End-to-end checklist to take the paywall from local-grant stub to real UPI payments.

## 1. Razorpay account (15 min)

1. Sign up at https://dashboard.razorpay.com/signup
2. Complete KYC (PAN, bank account, business proof — sole proprietor is fine)
3. Activate **Subscriptions** add-on from the dashboard (free)
4. Switch to **Test Mode** first while wiring things up

## 2. Create plans (5 min)

In the Razorpay dashboard → Subscriptions → Plans → Create plan:

| Plan             | Interval | Amount (paise) | Notes       |
| ---------------- | -------- | -------------- | ----------- |
| Eversilver Pro   | Monthly  | 49900          | ₹499/month  |
| Eversilver Ultra | Monthly  | 149900         | ₹1499/month |

Razorpay uses paise (1 INR = 100 paise). After creation, copy each `plan_xxxxxxxxxxxxxx` ID.

Paste them into `app/src/features/paywall/tiers.ts` replacing `plan_REPLACE_ME_PRO` and `plan_REPLACE_ME_ULTRA`.

## 3. Get API keys

Dashboard → Settings → API Keys → Generate Test Key. You get:

- `rzp_test_xxxxxxxxxxxxxx` (Key ID — safe in frontend)
- `xxxxxxxxxxxxxxxxxxxxxxxx` (Key Secret — backend only, never commit)

Put them in `.env`:

```
RAZORPAY_KEY_ID=rzp_test_xxx
RAZORPAY_KEY_SECRET=xxx
```

## 4. Backend endpoints (this is what you need to build)

Minimum two endpoints. Easiest hosting: a Cloudflare Worker or a small Fastify server on Render/Railway.

### POST /api/billing/subscribe

Creates a Razorpay subscription for the authenticated user.

```ts
// pseudo
import Razorpay from 'razorpay';

const rzp = new Razorpay({ key_id: env.RAZORPAY_KEY_ID, key_secret: env.RAZORPAY_KEY_SECRET });

app.post('/api/billing/subscribe', async (req, res) => {
  const { tier, userId } = req.body;
  const planMap = { pro: env.RAZORPAY_PLAN_ID_PRO, ultra: env.RAZORPAY_PLAN_ID_ULTRA };
  const subscription = await rzp.subscriptions.create({
    plan_id: planMap[tier],
    total_count: 12, // 12 months
    customer_notify: 1,
    notes: { userId, tier },
  });
  res.json({ subscriptionId: subscription.id, keyId: env.RAZORPAY_KEY_ID });
});
```

### POST /api/billing/webhook

Receives Razorpay's authorization/charge events. Configure in dashboard:

- URL: `https://your-api.example.com/api/billing/webhook`
- Active events: `subscription.activated`, `subscription.charged`, `subscription.halted`, `subscription.cancelled`, `payment.captured`, `payment.failed`
- Set a webhook secret and put it in `RAZORPAY_WEBHOOK_SECRET`

```ts
import crypto from 'node:crypto';

app.post('/api/billing/webhook', async (req, res) => {
  const signature = req.headers['x-razorpay-signature'];
  const expected = crypto
    .createHmac('sha256', env.RAZORPAY_WEBHOOK_SECRET)
    .update(req.rawBody)
    .digest('hex');
  if (signature !== expected) return res.sendStatus(400);

  const event = req.body.event;
  const payload = req.body.payload;

  if (event === 'subscription.activated' || event === 'subscription.charged') {
    const { userId, tier } = payload.subscription.entity.notes;
    await db.users.update(userId, { tier });
  } else if (event === 'subscription.cancelled' || event === 'subscription.halted') {
    const { userId } = payload.subscription.entity.notes;
    await db.users.update(userId, { tier: 'free' });
  }
  res.sendStatus(200);
});
```

## 5. Test with UPI

In Razorpay test mode, use UPI ID `success@razorpay` to simulate a successful UPI payment. Other test values:

- `failure@razorpay` — payment failure
- Test cards: 4111 1111 1111 1111 (Visa)

## 6. Going live

1. Complete Razorpay activation (full KYC + GST if applicable)
2. Regenerate **Live** API keys
3. Recreate plans in **Live Mode** (test plans don't carry over)
4. Update `.env` with `rzp_live_*` keys and live plan IDs
5. Update webhook URL to production and re-add live webhook secret
6. Toggle off any `upiOnly` overrides if you want card/netbanking too

## 7. UPI-only mode (optional)

To restrict checkout to UPI only — useful if you want the simplest Indian-payment UX:

In `PaywallProvider.tsx`, find the `openRazorpayCheckout({ ... })` call and set:

```ts
upiOnly: true,
```

This filters out cards, netbanking, and wallets at checkout.

## 8. Compliance reminders

- Razorpay requires Indian PAN + GST for activation
- Subscription mandates need explicit UPI authentication on every renewal — Razorpay handles this UI
- Display "auto-renewal" terms clearly per RBI's recurring payment guidelines (already covered in `PricingScreen` footer)
- Refund policy must be linked from your app (1-week minimum window is industry norm)
