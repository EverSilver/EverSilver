/**
 * Razorpay API wrapper for Cloudflare Workers.
 *
 * The official `razorpay` npm package depends on Node's `crypto` and `http`
 * modules, which work under `nodejs_compat` but add weight. We use direct
 * fetch + WebCrypto here for a leaner, Workers-native client.
 */

const RAZORPAY_API = 'https://api.razorpay.com/v1';

export interface RazorpayConfig {
  keyId: string;
  keySecret: string;
}

export interface CreateSubscriptionInput {
  plan_id: string;
  total_count: number; // billing cycles. For "until cancelled" we use a large value, e.g. 120 months.
  customer_notify?: 0 | 1;
  quantity?: number;
  notes?: Record<string, string>;
}

export interface RazorpaySubscription {
  id: string;
  entity: 'subscription';
  plan_id: string;
  status:
    | 'created'
    | 'authenticated'
    | 'active'
    | 'pending'
    | 'halted'
    | 'cancelled'
    | 'completed'
    | 'expired';
  current_start: number | null;
  current_end: number | null;
  ended_at: number | null;
  short_url?: string;
  notes?: Record<string, string>;
  [k: string]: unknown;
}

function basicAuth(keyId: string, keySecret: string): string {
  return 'Basic ' + btoa(`${keyId}:${keySecret}`);
}

export class RazorpayClient {
  constructor(private config: RazorpayConfig) {}

  async createSubscription(input: CreateSubscriptionInput): Promise<RazorpaySubscription> {
    const res = await fetch(`${RAZORPAY_API}/subscriptions`, {
      method: 'POST',
      headers: {
        Authorization: basicAuth(this.config.keyId, this.config.keySecret),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(input),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Razorpay createSubscription failed (${res.status}): ${text}`);
    }
    return (await res.json()) as RazorpaySubscription;
  }

  async cancelSubscription(
    subscriptionId: string,
    cancelAtCycleEnd = true
  ): Promise<RazorpaySubscription> {
    const res = await fetch(
      `${RAZORPAY_API}/subscriptions/${encodeURIComponent(subscriptionId)}/cancel`,
      {
        method: 'POST',
        headers: {
          Authorization: basicAuth(this.config.keyId, this.config.keySecret),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ cancel_at_cycle_end: cancelAtCycleEnd ? 1 : 0 }),
      }
    );
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Razorpay cancelSubscription failed (${res.status}): ${text}`);
    }
    return (await res.json()) as RazorpaySubscription;
  }

  async fetchSubscription(subscriptionId: string): Promise<RazorpaySubscription> {
    const res = await fetch(
      `${RAZORPAY_API}/subscriptions/${encodeURIComponent(subscriptionId)}`,
      {
        headers: {
          Authorization: basicAuth(this.config.keyId, this.config.keySecret),
        },
      }
    );
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Razorpay fetchSubscription failed (${res.status}): ${text}`);
    }
    return (await res.json()) as RazorpaySubscription;
  }
}

/**
 * Verify a Razorpay webhook signature using HMAC-SHA256.
 * Razorpay signs the raw request body with the webhook secret and sends the
 * hex digest in the `X-Razorpay-Signature` header.
 *
 * https://razorpay.com/docs/webhooks/validate-test/
 */
export async function verifyWebhookSignature(
  rawBody: string,
  signatureHex: string,
  secret: string
): Promise<boolean> {
  if (!signatureHex || typeof signatureHex !== 'string') return false;

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const computed = new Uint8Array(
    await crypto.subtle.sign('HMAC', key, encoder.encode(rawBody))
  );

  const provided = hexToBytes(signatureHex);
  if (!provided || provided.length !== computed.length) return false;

  let diff = 0;
  for (let i = 0; i < computed.length; i++) diff |= computed[i] ^ provided[i];
  return diff === 0;
}

function hexToBytes(hex: string): Uint8Array | null {
  if (hex.length % 2 !== 0) return null;
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    const byte = parseInt(hex.substr(i * 2, 2), 16);
    if (Number.isNaN(byte)) return null;
    out[i] = byte;
  }
  return out;
}

/** Compute an HMAC-SHA256 hex digest (used in tests + payment signature verify). */
export async function hmacSha256Hex(message: string, secret: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', key, encoder.encode(message)));
  return Array.from(sig)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
