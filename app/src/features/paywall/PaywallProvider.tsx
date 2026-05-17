/**
 * Eversilver Paywall Provider (India / UPI / Razorpay)
 *
 * Centralized entitlement checks + Razorpay checkout dispatch.
 *
 * Flow:
 *  1. User taps "Upgrade" → checkout(tier)
 *  2. Frontend calls backend POST /api/billing/subscribe { tierId, userId }
 *  3. Backend creates Razorpay subscription, returns { subscriptionId, keyId }
 *  4. Frontend opens Razorpay checkout (UPI-first)
 *  5. After successful UPI authorization, Razorpay webhook hits backend
 *  6. Backend marks user.tier server-side and pushes update to client
 *  7. Client calls upgradeTier(tier) so the UI reflects entitlement immediately
 */
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';
import { useAuth, type SubscriptionTier } from '../auth';
import { TIERS, hasFeature, minimumTierFor, tierRank } from './tiers';
import { openRazorpayCheckout } from './razorpay';

interface PaywallContextValue {
  currentTier: SubscriptionTier;
  hasFeature: (feature: string) => boolean;
  requiredTierFor: (feature: string) => SubscriptionTier | null;
  isAtLeast: (tier: SubscriptionTier) => boolean;
  checkout: (tier: SubscriptionTier) => Promise<void>;
}

const PaywallContext = createContext<PaywallContextValue | null>(null);

interface SubscribeResponse {
  subscriptionId: string;
  keyId: string;
}

/**
 * Replace this with a real backend call once your billing service is up.
 * Until then, the function falls back to a local-only upgrade so the UI
 * stays functional during dev.
 */
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
          upiOnly: false, // set true if you want to restrict to UPI only
        });
        // Webhook will confirm and update server-side; reflect locally too.
        await upgradeTier(tier);
      } catch (err) {
        console.error('[Eversilver Paywall] Checkout failed:', err);
      }
    },
    [user, upgradeTier]
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
