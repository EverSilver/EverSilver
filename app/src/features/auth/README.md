# Eversilver Auth + UPI Paywall Integration

Drop-in login + Razorpay/UPI subscription scaffolding.

## Wire-up

Edit `app/src/main.tsx` (or wherever your root provider tree lives):

```tsx
import { AuthProvider, LoginScreen, useAuth } from './features/auth';
import './features/auth/login.css';
import { PaywallProvider } from './features/paywall';
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
  </AuthProvider>
);
```

## Gating features

```tsx
import { PaywallGate, useEntitlement } from './features/paywall';

// Component-level gate
<PaywallGate feature="core.voice">
  <VoiceControls />
</PaywallGate>;

// Inline check
const canUseVoice = useEntitlement('core.voice');
```

## Pricing (INR)

Edit `app/src/features/paywall/tiers.ts`:

| Tier  | Price         | Features                                        |
| ----- | ------------- | ----------------------------------------------- |
| Free  | ₹0            | chat, basic memory                              |
| Pro   | ₹499 / month  | + voice, mascot, integrations, web fetch        |
| Ultra | ₹1499 / month | + frontier models, Meet agent, priority compute |

## UPI / Razorpay setup

See `app/src/features/paywall/RAZORPAY_SETUP.md` for the full step-by-step:

1. Create Razorpay account + activate Subscriptions
2. Create plans (₹499 Pro, ₹1499 Ultra)
3. Get API keys
4. Build a minimal backend with `/api/billing/subscribe` and `/api/billing/webhook`
5. Paste plan IDs into `tiers.ts`
6. Test with UPI ID `success@razorpay`

Until the backend is wired, paywall grants tiers locally so the UI stays usable in dev.

## Backend integration (auth)

The auth scaffold is localStorage-based. To go production:

1. **Auth** — replace `signIn`/`signUp` in `AuthProvider.tsx` with real backend calls (Supabase, Clerk, Auth0, or your own JWT API)
2. **Session sync** — replace localStorage with a refresh-token cycle so sessions persist across machines
