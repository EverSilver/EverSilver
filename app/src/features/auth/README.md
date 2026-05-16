# Eversilver Auth + Paywall Integration

Drop-in login + subscription scaffolding for personal Eversilver builds.

## Wire-up

Edit `app/src/main.tsx` (or wherever your root provider tree lives):

```tsx
import { AuthProvider, useAuth, LoginScreen } from './features/auth';
import { PaywallProvider } from './features/paywall';
import './features/auth/login.css';
import './features/paywall/paywall.css';

function GatedApp() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div>Loading…</div>;
  if (!isAuthenticated) return <LoginScreen />;
  return <AppRoutes />;
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <AuthProvider>
    <PaywallProvider>
      <GatedApp />
    </PaywallProvider>
  </AuthProvider>,
);
```

## Gating features

```tsx
import { PaywallGate, useEntitlement } from './features/paywall';

// Component-level gate
<PaywallGate feature="core.voice">
  <VoiceControls />
</PaywallGate>

// Inline check
const canUseVoice = useEntitlement('core.voice');
```

## Tier configuration

Edit `app/src/features/paywall/tiers.ts` — add features, prices, Stripe IDs.

## Backend integration

The current scaffold is localStorage-based. To go production:

1. **Auth** — replace `signIn`/`signUp` in `AuthProvider.tsx` with real backend calls (Supabase, Clerk, Auth0, or your own JWT API)
2. **Paywall** — replace the `checkout()` stub in `PaywallProvider.tsx` with a real Stripe Checkout flow, and add a webhook endpoint to mark `user.tier` after successful payment
3. **Session sync** — replace localStorage with a refresh-token cycle so sessions persist across machines
