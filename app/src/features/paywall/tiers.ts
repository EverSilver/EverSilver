/**
 * Eversilver Subscription Tiers (India / UPI)
 *
 * Pricing in INR. Payments via Razorpay (UPI, cards, netbanking, wallets).
 * Razorpay Plan IDs are created in the Razorpay dashboard:
 *   https://dashboard.razorpay.com/app/subscriptions/plans
 * After creating each plan, paste its `plan_id` into `razorpayPlanId` below.
 */
import type { SubscriptionTier } from '../auth';

export interface TierDefinition {
  id: SubscriptionTier;
  name: string;
  priceMonthlyInr: number;
  description: string;
  features: string[];
  /** Razorpay Plan ID (plan_xxxxxxxxxxxxxx) — required for paid tiers. */
  razorpayPlanId?: string;
}

export const TIERS: Record<SubscriptionTier, TierDefinition> = {
  free: {
    id: 'free',
    name: 'Free',
    priceMonthlyInr: 0,
    description: 'Get started with core Eversilver features.',
    features: ['core.chat', 'core.memory.basic'],
  },
  pro: {
    id: 'pro',
    name: 'Pro',
    priceMonthlyInr: 499,
    description: 'Unlock the full Eversilver experience.',
    features: [
      'core.chat',
      'core.memory.basic',
      'core.memory.unlimited',
      'core.voice',
      'core.mascot',
      'core.integrations.all',
      'core.web.fetch',
    ],
    razorpayPlanId: 'plan_REPLACE_ME_PRO',
  },
  ultra: {
    id: 'ultra',
    name: 'Ultra',
    priceMonthlyInr: 1499,
    description: 'Everything in Pro, plus advanced models and priority compute.',
    features: [
      'core.chat',
      'core.memory.basic',
      'core.memory.unlimited',
      'core.voice',
      'core.mascot',
      'core.integrations.all',
      'core.web.fetch',
      'core.models.frontier',
      'core.meet.agent',
      'core.priority.compute',
    ],
    razorpayPlanId: 'plan_REPLACE_ME_ULTRA',
  },
};

const TIER_ORDER: SubscriptionTier[] = ['free', 'pro', 'ultra'];

export function tierRank(tier: SubscriptionTier): number {
  return TIER_ORDER.indexOf(tier);
}

export function hasFeature(tier: SubscriptionTier, feature: string): boolean {
  return TIERS[tier].features.includes(feature);
}

export function minimumTierFor(feature: string): SubscriptionTier | null {
  for (const tier of TIER_ORDER) {
    if (TIERS[tier].features.includes(feature)) return tier;
  }
  return null;
}

export function formatInr(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount);
}
