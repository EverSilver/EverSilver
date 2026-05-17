import { act, renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// We mock the razorpay module at the top level so every dynamic re-import of
// PaywallProvider receives the same vi.fn instances.
const openRazorpayCheckoutMock = vi.fn().mockResolvedValue(undefined);
vi.mock('../razorpay', () => ({ openRazorpayCheckout: openRazorpayCheckoutMock }));

// Fetch is touched by createSubscription() when VITE_BILLING_API_URL is set.
// We default to no env URL so createSubscription returns null without fetching.

type Modules = {
  PaywallProvider: typeof import('../PaywallProvider').PaywallProvider;
  usePaywall: typeof import('../PaywallProvider').usePaywall;
  useEntitlement: typeof import('../PaywallProvider').useEntitlement;
  LocalAuthProvider: typeof import('../../auth').LocalAuthProvider;
  useAuth: typeof import('../../auth').useAuth;
};

/** Reload all paywall-touching modules so config.ts re-reads import.meta.env. */
async function loadModulesWith({
  billingEnabled,
  billingApiUrl,
}: {
  billingEnabled: boolean;
  billingApiUrl?: string;
}): Promise<Modules> {
  vi.resetModules();
  vi.stubEnv('VITE_BILLING_ENABLED', billingEnabled ? 'true' : 'false');
  if (billingApiUrl !== undefined) {
    vi.stubEnv('VITE_BILLING_API_URL', billingApiUrl);
  } else {
    vi.stubEnv('VITE_BILLING_API_URL', '');
  }

  const paywallMod = await import('../PaywallProvider');
  const authMod = await import('../../auth');
  return {
    PaywallProvider: paywallMod.PaywallProvider,
    usePaywall: paywallMod.usePaywall,
    useEntitlement: paywallMod.useEntitlement,
    LocalAuthProvider: authMod.LocalAuthProvider,
    useAuth: authMod.useAuth,
  };
}

function makeWrapper(mods: Modules) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <mods.LocalAuthProvider>
        <mods.PaywallProvider>{children}</mods.PaywallProvider>
      </mods.LocalAuthProvider>
    );
  };
}

/** Hook helper that exposes both useAuth + usePaywall to a single renderHook. */
function makeUseCombined(mods: Modules) {
  return function useCombined() {
    return { auth: mods.useAuth(), paywall: mods.usePaywall() };
  };
}

beforeEach(() => {
  localStorage.clear();
  openRazorpayCheckoutMock.mockClear();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('PaywallProvider â€” BILLING_ENABLED=false (preview mode)', () => {
  it('auto-grants PREVIEW_TIER (ultra) to a signed-in user', async () => {
    const mods = await loadModulesWith({ billingEnabled: false });
    const wrapper = makeWrapper(mods);
    const useCombined = makeUseCombined(mods);

    const { result } = renderHook(() => useCombined(), { wrapper });
    await waitFor(() => expect(result.current.auth.loading).toBe(false));

    await act(async () => {
      await result.current.auth.signUp('u@example.com', 'password123', 'Test User');
    });

    // The effect promotes free â†’ ultra (PREVIEW_TIER) automatically.
    await waitFor(() => expect(result.current.auth.user?.tier).toBe('ultra'));
    expect(result.current.paywall.currentTier).toBe('ultra');
    expect(result.current.paywall.billingEnabled).toBe(false);
  });

  it('useEntitlement / hasFeature returns true for arbitrary features', async () => {
    const mods = await loadModulesWith({ billingEnabled: false });
    const wrapper = makeWrapper(mods);
    const useCombined = makeUseCombined(mods);

    const { result } = renderHook(() => useCombined(), { wrapper });
    await waitFor(() => expect(result.current.auth.loading).toBe(false));

    expect(result.current.paywall.hasFeature('core.chat')).toBe(true);
    expect(result.current.paywall.hasFeature('core.models.frontier')).toBe(true);
    expect(result.current.paywall.hasFeature('definitely.not.a.real.feature')).toBe(true);
  });

  it('checkout is a no-op in preview mode (no tier change, no razorpay)', async () => {
    const mods = await loadModulesWith({ billingEnabled: false });
    const wrapper = makeWrapper(mods);
    const useCombined = makeUseCombined(mods);

    const { result } = renderHook(() => useCombined(), { wrapper });
    await waitFor(() => expect(result.current.auth.loading).toBe(false));

    await act(async () => {
      await result.current.auth.signUp('u@example.com', 'password123', 'Test User');
    });
    await waitFor(() => expect(result.current.auth.user?.tier).toBe('ultra'));

    await act(async () => {
      await result.current.paywall.checkout('pro');
    });

    expect(openRazorpayCheckoutMock).not.toHaveBeenCalled();
    // Tier remains ultra (preview), not downgraded.
    expect(result.current.auth.user?.tier).toBe('ultra');
  });
});

describe('PaywallProvider â€” BILLING_ENABLED=true', () => {
  it('respects tier hierarchy via isAtLeast and hasFeature', async () => {
    const mods = await loadModulesWith({ billingEnabled: true });
    const wrapper = makeWrapper(mods);
    const useCombined = makeUseCombined(mods);

    const { result } = renderHook(() => useCombined(), { wrapper });
    await waitFor(() => expect(result.current.auth.loading).toBe(false));

    await act(async () => {
      await result.current.auth.signUp('u@example.com', 'password123', 'Test User');
    });
    // Default tier is free.
    expect(result.current.auth.user?.tier).toBe('free');
    expect(result.current.paywall.currentTier).toBe('free');
    expect(result.current.paywall.isAtLeast('free')).toBe(true);
    expect(result.current.paywall.isAtLeast('pro')).toBe(false);
    expect(result.current.paywall.isAtLeast('ultra')).toBe(false);
    expect(result.current.paywall.hasFeature('core.chat')).toBe(true);
    expect(result.current.paywall.hasFeature('core.voice')).toBe(false);
    expect(result.current.paywall.hasFeature('core.models.frontier')).toBe(false);
    expect(result.current.paywall.requiredTierFor('core.voice')).toBe('pro');
    expect(result.current.paywall.requiredTierFor('core.models.frontier')).toBe('ultra');
    expect(result.current.paywall.requiredTierFor('not.a.feature')).toBeNull();

    await act(async () => {
      await result.current.auth.upgradeTier('pro');
    });
    expect(result.current.paywall.isAtLeast('pro')).toBe(true);
    expect(result.current.paywall.hasFeature('core.voice')).toBe(true);
    expect(result.current.paywall.hasFeature('core.models.frontier')).toBe(false);

    await act(async () => {
      await result.current.auth.upgradeTier('ultra');
    });
    expect(result.current.paywall.isAtLeast('ultra')).toBe(true);
    expect(result.current.paywall.hasFeature('core.models.frontier')).toBe(true);
  });

  it('checkout falls back to local grant when plan id is REPLACE_ME', async () => {
    const mods = await loadModulesWith({ billingEnabled: true });
    const wrapper = makeWrapper(mods);
    const useCombined = makeUseCombined(mods);

    const { result } = renderHook(() => useCombined(), { wrapper });
    await waitFor(() => expect(result.current.auth.loading).toBe(false));
    await act(async () => {
      await result.current.auth.signUp('u@example.com', 'password123', 'Test User');
    });

    await act(async () => {
      await result.current.paywall.checkout('pro');
    });

    expect(openRazorpayCheckoutMock).not.toHaveBeenCalled();
    expect(result.current.auth.user?.tier).toBe('pro');
    expect(result.current.paywall.currentTier).toBe('pro');
  });

  it('checkout calls openRazorpayCheckout when plan id is real and backend returns a subscription', async () => {
    const mods = await loadModulesWith({
      billingEnabled: true,
      billingApiUrl: 'https://billing.test',
    });

    // Override the pro tier plan id at runtime to be a real-looking value.
    const tiersMod = await import('../tiers');
    tiersMod.TIERS.pro.razorpayPlanId = 'plan_REAL123456';

    // Mock fetch to return a subscription.
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        new Response(JSON.stringify({ subscriptionId: 'sub_abc', keyId: 'rzp_live_xyz' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

    const wrapper = makeWrapper(mods);
    const useCombined = makeUseCombined(mods);
    const { result } = renderHook(() => useCombined(), { wrapper });
    await waitFor(() => expect(result.current.auth.loading).toBe(false));
    await act(async () => {
      await result.current.auth.signUp('u@example.com', 'password123', 'Test User');
    });

    await act(async () => {
      await result.current.paywall.checkout('pro');
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      'https://billing.test/api/billing/subscribe',
      expect.objectContaining({ method: 'POST' })
    );
    expect(openRazorpayCheckoutMock).toHaveBeenCalledTimes(1);
    expect(openRazorpayCheckoutMock).toHaveBeenCalledWith(
      expect.objectContaining({
        keyId: 'rzp_live_xyz',
        subscriptionId: 'sub_abc',
        tierName: 'Pro',
        appName: 'Eversilver',
      })
    );
    // Tier granted after successful checkout.
    expect(result.current.auth.user?.tier).toBe('pro');

    // Restore plan id so other tests aren't affected.
    tiersMod.TIERS.pro.razorpayPlanId = 'plan_REPLACE_ME_PRO';
    fetchSpy.mockRestore();
  });

  it('checkout falls back to local grant when backend returns no subscription', async () => {
    const mods = await loadModulesWith({
      billingEnabled: true,
      billingApiUrl: 'https://billing.test',
    });
    const tiersMod = await import('../tiers');
    tiersMod.TIERS.pro.razorpayPlanId = 'plan_REAL_FALLBACK';

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('boom', { status: 500 }));

    const wrapper = makeWrapper(mods);
    const useCombined = makeUseCombined(mods);
    const { result } = renderHook(() => useCombined(), { wrapper });
    await waitFor(() => expect(result.current.auth.loading).toBe(false));
    await act(async () => {
      await result.current.auth.signUp('u@example.com', 'password123', 'Test User');
    });

    await act(async () => {
      await result.current.paywall.checkout('pro');
    });

    expect(openRazorpayCheckoutMock).not.toHaveBeenCalled();
    expect(result.current.auth.user?.tier).toBe('pro');

    tiersMod.TIERS.pro.razorpayPlanId = 'plan_REPLACE_ME_PRO';
    fetchSpy.mockRestore();
  });

  it('checkout is a no-op when no user is signed in (real plan id path)', async () => {
    const mods = await loadModulesWith({ billingEnabled: true });
    const tiersMod = await import('../tiers');
    tiersMod.TIERS.pro.razorpayPlanId = 'plan_NO_USER_TEST';

    const wrapper = makeWrapper(mods);
    const { result } = renderHook(() => mods.usePaywall(), { wrapper });

    await act(async () => {
      await result.current.checkout('pro');
    });

    expect(openRazorpayCheckoutMock).not.toHaveBeenCalled();
    tiersMod.TIERS.pro.razorpayPlanId = 'plan_REPLACE_ME_PRO';
  });

  it('useEntitlement hook returns same result as paywall.hasFeature', async () => {
    const mods = await loadModulesWith({ billingEnabled: true });
    const wrapper = makeWrapper(mods);
    const { result } = renderHook(() => mods.useEntitlement('core.chat'), { wrapper });
    await waitFor(() => expect(result.current).toBe(true));
    const { result: r2 } = renderHook(() => mods.useEntitlement('core.voice'), { wrapper });
    expect(r2.current).toBe(false);
  });
});

describe('usePaywall outside provider', () => {
  it('throws a clear error', async () => {
    const mods = await loadModulesWith({ billingEnabled: true });
    expect(() => renderHook(() => mods.usePaywall())).toThrow(/usePaywall must be used within/i);
  });
});
