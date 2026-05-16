/**
 * Eversilver Subscription Tiers
 *
 * Define your tier hierarchy and feature gates here.
 * Tiers are checked via `useEntitlement(feature)` from PaywallProvider.
 */
import type { SubscriptionTier } from '../auth';

export interface TierDefinition {
  id: SubscriptionTier;
  name: string;
  priceMonthlyUsd: number;
  description: string;
  features: string[];
  stripePriceId?: string;
}

export const TIERS: Record<SubscriptionTier, TierDefinition> = {
  free: {
    id: 'free',
    name: 'Free',
    priceMonthlyUsd: 0,
    description: 'Get started with basic Eversilver features.',
    features: ['core.chat', 'core.memory.basic'],
  },
  pro: {
    id: 'pro',
    name: 'Pro',
    priceMonthlyUsd: 19,
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
    stripePriceId: 'price_REPLACE_ME_PRO',
  },
  ultra: {
    id: 'ultra',
    name: 'Ultra',
    priceMonthlyUsd: 49,
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
    stripePriceId: 'price_REPLACE_ME_ULTRA',
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
