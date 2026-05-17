/**
 * KV-backed user/subscription store.
 *
 * Key layout:
 *   user:{userId}                 -> UserRecord JSON
 *   sub:{subscriptionId}          -> userId (string)
 *   webhook:{eventId}             -> "1" (idempotency marker, TTL ~30 days)
 */

export type Tier = 'free' | 'pro' | 'ultra';

export interface UserRecord {
  id: string;
  email?: string;
  tier: Tier;
  subscriptionId?: string;
  subscriptionStatus?: string;
  currentPeriodEnd?: number; // unix seconds
  cancelAtPeriodEnd?: boolean;
  createdAt: number;
  updatedAt: number;
}

export class BillingStore {
  constructor(private kv: KVNamespace) {}

  private userKey(id: string) {
    return `user:${id}`;
  }
  private subKey(id: string) {
    return `sub:${id}`;
  }
  private webhookKey(id: string) {
    return `webhook:${id}`;
  }

  async getUser(userId: string): Promise<UserRecord | null> {
    const raw = await this.kv.get(this.userKey(userId));
    return raw ? (JSON.parse(raw) as UserRecord) : null;
  }

  async putUser(user: UserRecord): Promise<void> {
    user.updatedAt = Math.floor(Date.now() / 1000);
    await this.kv.put(this.userKey(user.id), JSON.stringify(user));
  }

  async upsertUser(
    userId: string,
    patch: Partial<UserRecord> & { email?: string }
  ): Promise<UserRecord> {
    const existing = await this.getUser(userId);
    const now = Math.floor(Date.now() / 1000);
    const next: UserRecord = {
      id: userId,
      tier: 'free',
      createdAt: now,
      updatedAt: now,
      ...existing,
      ...patch,
      id: userId,
    };
    await this.putUser(next);
    return next;
  }

  async linkSubscription(subscriptionId: string, userId: string): Promise<void> {
    await this.kv.put(this.subKey(subscriptionId), userId);
  }

  async getUserBySubscription(subscriptionId: string): Promise<UserRecord | null> {
    const userId = await this.kv.get(this.subKey(subscriptionId));
    if (!userId) return null;
    return this.getUser(userId);
  }

  /** Returns true if the event was newly recorded, false if it was already processed. */
  async markWebhookProcessed(eventId: string, ttlSeconds = 60 * 60 * 24 * 30): Promise<boolean> {
    const existing = await this.kv.get(this.webhookKey(eventId));
    if (existing) return false;
    await this.kv.put(this.webhookKey(eventId), '1', { expirationTtl: ttlSeconds });
    return true;
  }
}

export function tierFromPlanId(
  planId: string,
  proPlanId: string,
  ultraPlanId: string
): Tier | null {
  if (planId === proPlanId) return 'pro';
  if (planId === ultraPlanId) return 'ultra';
  return null;
}
