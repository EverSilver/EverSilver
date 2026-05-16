/**
 * Eversilver Paywall Provider
 *
 * Centralized entitlement checks. Use `useEntitlement('core.voice')` in
 * any component to gate features. Use <PaywallGate feature="..."> to wrap
 * an entire UI region.
 */
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';
import { useAuth, type SubscriptionTier } from '../auth';
import { TIERS, hasFeature, minimumTierFor, tierRank } from './tiers';

interface PaywallContextValue {
  currentTier: SubscriptionTier;
  hasFeature: (feature: string) => boolean;
  requiredTierFor: (feature: string) => SubscriptionTier | null;
  isAtLeast: (tier: SubscriptionTier) => boolean;
  checkout: (tier: SubscriptionTier) => Promise<void>;
}

const PaywallContext = createContext<PaywallContextValue | null>(null);

export function PaywallProvider({ children }: { children: ReactNode }) {
  const { user, upgradeTier } = useAuth();
  const currentTier: SubscriptionTier = user?.tier ?? 'free';

  const checkFeature = useCallback(
    (feature: string) => hasFeature(currentTier, feature),
    [currentTier]
  );

  const requiredTierFor = useCallback((feature: string) => minimumTierFor(feature), []);

  const isAtLeast = useCallback(
    (tier: SubscriptionTier) => tierRank(currentTier) >= tierRank(tier),
    [currentTier]
  );

  const checkout = useCallback(
    async (tier: SubscriptionTier) => {
      const def = TIERS[tier];
      if (!def.stripePriceId || def.stripePriceId.startsWith('price_REPLACE_ME')) {
        console.warn('[Eversilver Paywall] Stripe price ID not configured; granting tier locally.');
        await upgradeTier(tier);
        return;
      }
      // TODO: replace with real Stripe Checkout session creation
      // 1. POST to your backend /api/billing/checkout with { priceId, userId }
      // 2. Backend creates Stripe Checkout Session
      // 3. Redirect user to session.url
      // 4. On webhook completion, backend updates user.tier
      // 5. Client re-fetches user and calls upgradeTier(tier)
      console.warn('[Eversilver Paywall] Stripe checkout not wired; granting locally.');
      await upgradeTier(tier);
    },
    [upgradeTier]
  );

  const value = useMemo<PaywallContextValue>(
    () => ({ currentTier, hasFeature: checkFeature, requiredTierFor, isAtLeast, checkout }),
    [currentTier, checkFeature, requiredTierFor, isAtLeast, checkout]
  );

  return <PaywallContext.Provider value={value}>{children}</PaywallContext.Provider>;
}

export function usePaywall(): PaywallContextValue {
  const ctx = useContext(PaywallContext);
  if (!ctx) throw new Error('usePaywall must be used within PaywallProvider');
  return ctx;
}

export function useEntitlement(feature: string): boolean {
  const { hasFeature } = usePaywall();
  return hasFeature(feature);
}
