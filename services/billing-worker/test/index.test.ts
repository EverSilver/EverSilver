import { describe, it, expect, beforeEach, vi } from 'vitest';
import app, { type Env } from '../src/index';
import { signJwt } from '../src/auth';
import { hmacSha256Hex } from '../src/razorpay';

// -----------------------------------------------------------------------------
// In-memory KV stub
// -----------------------------------------------------------------------------
class MemoryKV {
  private store = new Map<string, { value: string; expiresAt?: number }>();
  async get(key: string): Promise<string | null> {
    const v = this.store.get(key);
    if (!v) return null;
    if (v.expiresAt && Date.now() > v.expiresAt) {
      this.store.delete(key);
      return null;
    }
    return v.value;
  }
  async put(key: string, value: string, opts?: { expirationTtl?: number }) {
    this.store.set(key, {
      value,
      expiresAt: opts?.expirationTtl ? Date.now() + opts.expirationTtl * 1000 : undefined,
    });
  }
  async delete(key: string) {
    this.store.delete(key);
  }
  async list() {
    return { keys: [...this.store.keys()].map((name) => ({ name })) };
  }
}

const JWT_SECRET = 'test_jwt_secret_at_least_32_characters_long_xxxx';
const WEBHOOK_SECRET = 'test_webhook_secret_xyz';

function makeEnv(): Env {
  return {
    BILLING_KV: new MemoryKV() as unknown as KVNamespace,
    RAZORPAY_KEY_ID: 'rzp_test_key',
    RAZORPAY_KEY_SECRET: 'rzp_test_secret',
    RAZORPAY_WEBHOOK_SECRET: WEBHOOK_SECRET,
    RAZORPAY_PLAN_ID_PRO: 'plan_pro_test',
    RAZORPAY_PLAN_ID_ULTRA: 'plan_ultra_test',
    JWT_SECRET,
    ALLOWED_ORIGIN: '*',
  };
}

async function bearer(userId: string, email = 'user@example.com'): Promise<string> {
  const token = await signJwt(
    { sub: userId, email, iat: Math.floor(Date.now() / 1000) },
    JWT_SECRET
  );
  return `Bearer ${token}`;
}

// -----------------------------------------------------------------------------
// Mock global fetch for Razorpay API calls
// -----------------------------------------------------------------------------
beforeEach(() => {
  vi.restoreAllMocks();
});

function mockRazorpayFetch(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      return handler(url, init ?? {});
    })
  );
}

// -----------------------------------------------------------------------------
// Tests
// -----------------------------------------------------------------------------
describe('GET /health', () => {
  it('returns ok', async () => {
    const res = await app.request('/health', {}, makeEnv());
    expect(res.status).toBe(200);
    const body = (await res.json()) as { ok: boolean };
    expect(body.ok).toBe(true);
  });
});

describe('POST /api/billing/subscribe', () => {
  it('returns 401 without auth', async () => {
    const res = await app.request(
      '/api/billing/subscribe',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"tier":"pro"}' },
      makeEnv()
    );
    expect(res.status).toBe(401);
  });

  it('returns 400 for invalid tier', async () => {
    const env = makeEnv();
    const res = await app.request(
      '/api/billing/subscribe',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: await bearer('user_1'),
        },
        body: JSON.stringify({ tier: 'platinum' }),
      },
      env
    );
    expect(res.status).toBe(400);
  });

  it('creates a subscription on the pro plan', async () => {
    mockRazorpayFetch(async (url, init) => {
      expect(url).toBe('https://api.razorpay.com/v1/subscriptions');
      const body = JSON.parse(init.body as string);
      expect(body.plan_id).toBe('plan_pro_test');
      return new Response(
        JSON.stringify({
          id: 'sub_ABCD',
          entity: 'subscription',
          plan_id: 'plan_pro_test',
          status: 'created',
          short_url: 'https://rzp.io/i/abc',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    });

    const env = makeEnv();
    const res = await app.request(
      '/api/billing/subscribe',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: await bearer('user_1'),
        },
        body: JSON.stringify({ tier: 'pro' }),
      },
      env
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { subscriptionId: string; keyId: string };
    expect(body.subscriptionId).toBe('sub_ABCD');
    expect(body.keyId).toBe('rzp_test_key');

    // Stored in KV
    const stored = await env.BILLING_KV.get('user:user_1');
    expect(stored).toContain('sub_ABCD');
  });
});

describe('GET /api/billing/status', () => {
  it('returns 401 without auth', async () => {
    const res = await app.request('/api/billing/status', {}, makeEnv());
    expect(res.status).toBe(401);
  });

  it('returns free tier defaults for a new user', async () => {
    const env = makeEnv();
    const res = await app.request(
      '/api/billing/status',
      { headers: { Authorization: await bearer('user_new') } },
      env
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { tier: string; subscriptionId: null };
    expect(body.tier).toBe('free');
    expect(body.subscriptionId).toBeNull();
  });
});

describe('POST /api/billing/cancel', () => {
  it('returns 404 when user has no subscription', async () => {
    const env = makeEnv();
    const res = await app.request(
      '/api/billing/cancel',
      { method: 'POST', headers: { Authorization: await bearer('user_x') } },
      env
    );
    expect(res.status).toBe(404);
  });

  it('cancels an active subscription', async () => {
    const env = makeEnv();
    // Seed a user with an active subscription
    await env.BILLING_KV.put(
      'user:user_2',
      JSON.stringify({
        id: 'user_2',
        tier: 'pro',
        subscriptionId: 'sub_ZZZ',
        subscriptionStatus: 'active',
        createdAt: 1,
        updatedAt: 1,
      })
    );

    mockRazorpayFetch(async (url) => {
      expect(url).toBe('https://api.razorpay.com/v1/subscriptions/sub_ZZZ/cancel');
      return new Response(
        JSON.stringify({
          id: 'sub_ZZZ',
          entity: 'subscription',
          plan_id: 'plan_pro_test',
          status: 'cancelled',
          current_end: 9999999999,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    });

    const res = await app.request(
      '/api/billing/cancel',
      { method: 'POST', headers: { Authorization: await bearer('user_2') } },
      env
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { cancelAtPeriodEnd: boolean; status: string };
    expect(body.cancelAtPeriodEnd).toBe(true);
    expect(body.status).toBe('cancelled');
  });
});

describe('POST /api/billing/webhook', () => {
  function buildEvent(eventName: string, sub: Record<string, unknown>, id = 'evt_1') {
    return {
      id,
      event: eventName,
      created_at: 1700000000,
      payload: { subscription: { entity: { id: 'sub_WHK', plan_id: 'plan_pro_test', ...sub } } },
    };
  }

  it('rejects bad signatures', async () => {
    const env = makeEnv();
    const res = await app.request(
      '/api/billing/webhook',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Razorpay-Signature': 'deadbeef' },
        body: JSON.stringify(buildEvent('subscription.activated', { status: 'active' })),
      },
      env
    );
    expect(res.status).toBe(400);
  });

  it('activates a subscription on subscription.activated', async () => {
    const env = makeEnv();
    // Seed link
    await env.BILLING_KV.put('sub:sub_WHK', 'user_wh');
    await env.BILLING_KV.put(
      'user:user_wh',
      JSON.stringify({
        id: 'user_wh',
        tier: 'free',
        createdAt: 1,
        updatedAt: 1,
      })
    );

    const evt = buildEvent('subscription.activated', {
      status: 'active',
      current_end: 1800000000,
    });
    const raw = JSON.stringify(evt);
    const sig = await hmacSha256Hex(raw, WEBHOOK_SECRET);

    const res = await app.request(
      '/api/billing/webhook',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Razorpay-Signature': sig },
        body: raw,
      },
      env
    );
    expect(res.status).toBe(200);

    const updated = JSON.parse((await env.BILLING_KV.get('user:user_wh')) || '{}');
    expect(updated.tier).toBe('pro');
    expect(updated.subscriptionStatus).toBe('active');
    expect(updated.currentPeriodEnd).toBe(1800000000);
  });

  it('is idempotent on duplicate event ids', async () => {
    const env = makeEnv();
    await env.BILLING_KV.put('sub:sub_WHK', 'user_wh');
    await env.BILLING_KV.put(
      'user:user_wh',
      JSON.stringify({ id: 'user_wh', tier: 'free', createdAt: 1, updatedAt: 1 })
    );

    const evt = buildEvent('subscription.activated', { status: 'active' }, 'evt_dup');
    const raw = JSON.stringify(evt);
    const sig = await hmacSha256Hex(raw, WEBHOOK_SECRET);

    const first = await app.request(
      '/api/billing/webhook',
      { method: 'POST', headers: { 'X-Razorpay-Signature': sig }, body: raw },
      env
    );
    expect(first.status).toBe(200);

    const second = await app.request(
      '/api/billing/webhook',
      { method: 'POST', headers: { 'X-Razorpay-Signature': sig }, body: raw },
      env
    );
    const body = (await second.json()) as { idempotent?: boolean };
    expect(body.idempotent).toBe(true);
  });

  it('downgrades to free on subscription.halted', async () => {
    const env = makeEnv();
    await env.BILLING_KV.put('sub:sub_WHK', 'user_wh');
    await env.BILLING_KV.put(
      'user:user_wh',
      JSON.stringify({
        id: 'user_wh',
        tier: 'pro',
        subscriptionId: 'sub_WHK',
        createdAt: 1,
        updatedAt: 1,
      })
    );

    const evt = buildEvent('subscription.halted', { status: 'halted' }, 'evt_halt');
    const raw = JSON.stringify(evt);
    const sig = await hmacSha256Hex(raw, WEBHOOK_SECRET);

    const res = await app.request(
      '/api/billing/webhook',
      { method: 'POST', headers: { 'X-Razorpay-Signature': sig }, body: raw },
      env
    );
    expect(res.status).toBe(200);

    const updated = JSON.parse((await env.BILLING_KV.get('user:user_wh')) || '{}');
    expect(updated.tier).toBe('free');
  });
});

describe('JWT auth', () => {
  it('rejects a token signed with a different secret', async () => {
    const env = makeEnv();
    const badToken = await signJwt({ sub: 'user_1' }, 'wrong_secret');
    const res = await app.request(
      '/api/billing/status',
      { headers: { Authorization: `Bearer ${badToken}` } },
      env
    );
    expect(res.status).toBe(401);
  });

  it('rejects expired tokens', async () => {
    const env = makeEnv();
    const expired = await signJwt(
      { sub: 'user_1', exp: Math.floor(Date.now() / 1000) - 60 },
      JWT_SECRET
    );
    const res = await app.request(
      '/api/billing/status',
      { headers: { Authorization: `Bearer ${expired}` } },
      env
    );
    expect(res.status).toBe(401);
  });
});
