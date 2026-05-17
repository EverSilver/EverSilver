/**
 * Eversilver Paywall Provider
 *
 * When BILLING_ENABLED is false (current default), every authenticated user
 * gets the PREVIEW_TIER automatically — useful while the product is in
 * private/personal preview. Flip VITE_BILLING_ENABLED=true to activate
 * Razorpay checkout flow.
 */
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo } from 'react';

import { type SubscriptionTier, useAuth } from '../auth';
import { BILLING_ENABLED, PREVIEW_TIER } from './config';
import { openRazorpayCheckout } from './razorpay';
import { hasFeature, minimumTierFor, tierRank, TIERS } from './tiers';

interface PaywallContextValue {
  currentTier: SubscriptionTier;
  hasFeature: (feature: string) => boolean;
  requiredTierFor: (feature: string) => SubscriptionTier | null;
  isAtLeast: (tier: SubscriptionTier) => boolean;
  checkout: (tier: SubscriptionTier) => Promise<void>;
  /** True when the paywall is dormant and every feature is free. */
  billingEnabled: boolean;
}

const PaywallContext = createContext<PaywallContextValue | null>(null);

interface SubscribeResponse {
  subscriptionId: string;
  keyId: string;
}

async function createSubscription(
  tier: SubscriptionTier,
  userId: string
): Promise<SubscribeResponse | null> {
  const endpoint = import.meta.env.VITE_BILLING_API_URL;
  if (!endpoint) return null;
  const res = await fetch(`${endpoint}/api/billing/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tier, userId }),
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`Billing API ${res.status}`);
  return (await res.json()) as SubscribeResponse;
}

export function PaywallProvider({ children }: { children: ReactNode }) {
  const { user, upgradeTier } = useAuth();

  // When billing is disabled, silently promote every signed-in user to PREVIEW_TIER.
  useEffect(() => {
    if (!BILLING_ENABLED && user && user.tier !== PREVIEW_TIER) {
      void upgradeTier(PREVIEW_TIER);
    }
  }, [user, upgradeTier]);

  const currentTier: SubscriptionTier = BILLING_ENABLED ? (user?.tier ?? 'free') : PREVIEW_TIER;

  const checkFeature = useCallback(
    (feature: string) => (BILLING_ENABLED ? hasFeature(currentTier, feature) : true),
    [currentTier]
  );
  const requiredTierFor = useCallback((feature: string) => minimumTierFor(feature), []);
  const isAtLeast = useCallback(
    (tier: SubscriptionTier) => tierRank(currentTier) >= tierRank(tier),
    [currentTier]
  );

  const checkout = useCallback(
    async (tier: SubscriptionTier) => {
      if (!BILLING_ENABLED) {
        // Paywall dormant — do nothing. UI should not show upgrade CTAs.
        return;
      }
      const def = TIERS[tier];
      if (!def.razorpayPlanId || def.razorpayPlanId.startsWith('plan_REPLACE_ME')) {
        console.warn('[Eversilver Paywall] Razorpay plan id not set; granting tier locally.');
        await upgradeTier(tier);
        return;
      }
      if (!user) {
        console.warn('[Eversilver Paywall] No authenticated user.');
        return;
      }

      let sub: SubscribeResponse | null = null;
      try {
        sub = await createSubscription(tier, user.id);
      } catch (err) {
        console.error('[Eversilver Paywall] Subscription creation failed:', err);
      }

      if (!sub) {
        console.warn('[Eversilver Paywall] No backend wired; granting tier locally.');
        await upgradeTier(tier);
        return;
      }

      try {
        await openRazorpayCheckout({
          keyId: sub.keyId,
          subscriptionId: sub.subscriptionId,
          tierName: def.name,
          appName: 'Eversilver',
          themeColor: '#5b6478',
          prefill: { name: user.displayName, email: user.email },
          upiOnly: false,
        });
        await upgradeTier(tier);
      } catch (err) {
        console.error('[Eversilver Paywall] Checkout failed:', err);
      }
    },
    [user, upgradeTier]
  );

  const value = useMemo<PaywallContextValue>(
    () => ({
      currentTier,
      hasFeature: checkFeature,
      requiredTierFor,
      isAtLeast,
      checkout,
      billingEnabled: BILLING_ENABLED,
    }),
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
