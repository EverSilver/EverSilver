import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { HTTPException } from 'hono/http-exception';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';

import { requireAuth, type AuthVariables } from './auth';
import { RazorpayClient, verifyWebhookSignature } from './razorpay';
import { BillingStore, tierFromPlanId, type Tier } from './db';

// ---------------------------------------------------------------------------
// NOTE on @hono/zod-validator: if you'd rather not add the dep, replace
// `zValidator('json', schema)` with a small inline middleware that calls
// `schema.safeParse(await c.req.json())`. Kept as zValidator for clarity.
// ---------------------------------------------------------------------------

export interface Env {
  BILLING_KV: KVNamespace;
  RAZORPAY_KEY_ID: string;
  RAZORPAY_KEY_SECRET: string;
  RAZORPAY_WEBHOOK_SECRET: string;
  RAZORPAY_PLAN_ID_PRO: string;
  RAZORPAY_PLAN_ID_ULTRA: string;
  JWT_SECRET: string;
  ALLOWED_ORIGIN?: string;
}

type AppEnv = { Bindings: Env; Variables: AuthVariables };

const app = new Hono<AppEnv>();

app.use('*', logger());
app.use('*', async (c, next) => {
  const origin = c.env.ALLOWED_ORIGIN || '*';
  return cors({
    origin,
    allowMethods: ['GET', 'POST', 'OPTIONS'],
    allowHeaders: ['Authorization', 'Content-Type', 'X-Razorpay-Signature'],
    maxAge: 600,
  })(c, next);
});

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------
app.get('/health', (c) => c.json({ ok: true, service: 'billing-worker', ts: Date.now() }));

// ---------------------------------------------------------------------------
// POST /api/billing/subscribe
// ---------------------------------------------------------------------------
const subscribeSchema = z.object({
  tier: z.enum(['pro', 'ultra']),
});

app.post(
  '/api/billing/subscribe',
  requireAuth(),
  zValidator('json', subscribeSchema, (result, c) => {
    if (!result.success) {
      return c.json({ error: 'invalid_tier', details: result.error.flatten() }, 400);
    }
  }),
  async (c) => {
    const user = c.get('user');
    const { tier } = c.req.valid('json');

    const planId =
      tier === 'pro' ? c.env.RAZORPAY_PLAN_ID_PRO : c.env.RAZORPAY_PLAN_ID_ULTRA;
    if (!planId) throw new HTTPException(500, { message: 'plan_id_not_configured' });

    const client = new RazorpayClient({
      keyId: c.env.RAZORPAY_KEY_ID,
      keySecret: c.env.RAZORPAY_KEY_SECRET,
    });

    const subscription = await client.createSubscription({
      plan_id: planId,
      total_count: 120, // 10 years of monthly billing; effectively "until cancelled"
      customer_notify: 1,
      notes: { userId: user.sub, tier },
    });

    const store = new BillingStore(c.env.BILLING_KV);
    await store.upsertUser(user.sub, {
      email: user.email,
      subscriptionId: subscription.id,
      subscriptionStatus: subscription.status,
    });
    await store.linkSubscription(subscription.id, user.sub);

    return c.json({
      subscriptionId: subscription.id,
      keyId: c.env.RAZORPAY_KEY_ID,
      shortUrl: subscription.short_url,
    });
  }
);

// ---------------------------------------------------------------------------
// GET /api/billing/status
// ---------------------------------------------------------------------------
app.get('/api/billing/status', requireAuth(), async (c) => {
  const user = c.get('user');
  const store = new BillingStore(c.env.BILLING_KV);
  const record = await store.getUser(user.sub);
  if (!record) {
    return c.json({
      tier: 'free' as Tier,
      subscriptionId: null,
      status: null,
      currentPeriodEnd: null,
      cancelAtPeriodEnd: false,
    });
  }
  return c.json({
    tier: record.tier,
    subscriptionId: record.subscriptionId ?? null,
    status: record.subscriptionStatus ?? null,
    currentPeriodEnd: record.currentPeriodEnd ?? null,
    cancelAtPeriodEnd: !!record.cancelAtPeriodEnd,
  });
});

// ---------------------------------------------------------------------------
// POST /api/billing/cancel
// ---------------------------------------------------------------------------
app.post('/api/billing/cancel', requireAuth(), async (c) => {
  const user = c.get('user');
  const store = new BillingStore(c.env.BILLING_KV);
  const record = await store.getUser(user.sub);
  if (!record?.subscriptionId) {
    throw new HTTPException(404, { message: 'no_active_subscription' });
  }

  const client = new RazorpayClient({
    keyId: c.env.RAZORPAY_KEY_ID,
    keySecret: c.env.RAZORPAY_KEY_SECRET,
  });
  const cancelled = await client.cancelSubscription(record.subscriptionId, true);

  await store.upsertUser(user.sub, {
    subscriptionStatus: cancelled.status,
    cancelAtPeriodEnd: true,
    currentPeriodEnd: cancelled.current_end ?? record.currentPeriodEnd,
  });

  return c.json({
    ok: true,
    status: cancelled.status,
    cancelAtPeriodEnd: true,
    currentPeriodEnd: cancelled.current_end,
  });
});

// ---------------------------------------------------------------------------
// POST /api/billing/webhook  (public, but signature-verified)
// ---------------------------------------------------------------------------
app.post('/api/billing/webhook', async (c) => {
  const signature = c.req.header('x-razorpay-signature') || '';
  const raw = await c.req.text();

  const ok = await verifyWebhookSignature(raw, signature, c.env.RAZORPAY_WEBHOOK_SECRET);
  if (!ok) {
    return c.json({ error: 'invalid_signature' }, 400);
  }

  let event: WebhookEvent;
  try {
    event = JSON.parse(raw) as WebhookEvent;
  } catch {
    return c.json({ error: 'invalid_json' }, 400);
  }

  const store = new BillingStore(c.env.BILLING_KV);

  // Idempotency: Razorpay may retry the same event.
  const eventId = event.id || `${event.event}:${event.created_at}`;
  const fresh = await store.markWebhookProcessed(eventId);
  if (!fresh) return c.json({ ok: true, idempotent: true });

  const sub = event.payload?.subscription?.entity;
  const payment = event.payload?.payment?.entity;
  const subscriptionId = sub?.id || payment?.subscription_id;

  if (!subscriptionId) {
    // Nothing actionable; ack so Razorpay stops retrying.
    return c.json({ ok: true, skipped: 'no_subscription_id' });
  }

  const user = await store.getUserBySubscription(subscriptionId);
  if (!user) {
    // Could be a stale subscription; ack and move on.
    return c.json({ ok: true, skipped: 'user_not_found' });
  }

  const planId = sub?.plan_id;
  const inferredTier = planId
    ? tierFromPlanId(planId, c.env.RAZORPAY_PLAN_ID_PRO, c.env.RAZORPAY_PLAN_ID_ULTRA)
    : null;

  switch (event.event) {
    case 'subscription.activated':
    case 'subscription.charged': {
      await store.upsertUser(user.id, {
        tier: inferredTier ?? user.tier,
        subscriptionStatus: sub?.status ?? 'active',
        currentPeriodEnd: sub?.current_end ?? user.currentPeriodEnd,
        cancelAtPeriodEnd: false,
      });
      break;
    }
    case 'subscription.cancelled': {
      // Soft: keep tier until period end, then downgrade.
      await store.upsertUser(user.id, {
        subscriptionStatus: sub?.status ?? 'cancelled',
        cancelAtPeriodEnd: true,
        currentPeriodEnd: sub?.current_end ?? user.currentPeriodEnd,
      });
      break;
    }
    case 'subscription.completed':
    case 'subscription.halted': {
      await store.upsertUser(user.id, {
        tier: 'free',
        subscriptionStatus: sub?.status ?? event.event.split('.')[1],
        cancelAtPeriodEnd: false,
      });
      break;
    }
    case 'payment.failed': {
      // Don't immediately downgrade; Razorpay will retry. Just record status.
      await store.upsertUser(user.id, {
        subscriptionStatus: 'payment_failed',
      });
      break;
    }
    default: {
      // Unknown event — ack to stop retries.
      break;
    }
  }

  return c.json({ ok: true });
});

// ---------------------------------------------------------------------------
// Error handler
// ---------------------------------------------------------------------------
app.onError((err, c) => {
  if (err instanceof HTTPException) {
    return c.json({ error: err.message }, err.status);
  }
  console.error('unhandled', err);
  return c.json({ error: 'internal_error' }, 500);
});

app.notFound((c) => c.json({ error: 'not_found' }, 404));

export default app;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface WebhookEvent {
  id?: string;
  event: string;
  created_at: number;
  payload: {
    subscription?: {
      entity: {
        id: string;
        plan_id?: string;
        status?: string;
        current_start?: number;
        current_end?: number;
        ended_at?: number | null;
        notes?: Record<string, string>;
      };
    };
    payment?: {
      entity: {
        id: string;
        subscription_id?: string;
        status?: string;
        amount?: number;
        currency?: string;
      };
    };
  };
}
