# Auth Provider Selection

Eversilver ships two auth providers behind the same `useAuth()` surface.
Both expose identical types (`EversilverUser`, `SubscriptionTier`,
`AuthContextValue`) so call sites do not change when you swap them.

## LocalAuthProvider (default)

- **Backing store:** `localStorage`
- **Sign-in:** stub — accepts any non-empty email + password
- **Sign-up:** stub — creates a local user record
- **Session:** persisted across page loads via `localStorage`
- **Use it for:** preview builds, dev, personal/single-user installs,
  unit tests, screenshot/marketing builds where a real backend is overkill.

Pros: zero config, zero network, instant. Cons: not real auth — there is no
password verification, no remote session, and no account recovery.

## SupabaseAuthProvider

- **Backing store:** Supabase Auth (Postgres + GoTrue)
- **Sign-in:** `supabase.auth.signInWithPassword`
- **Sign-up:** `supabase.auth.signUp` with `display_name` + `tier='free'`
  written into `user_metadata`
- **Sign-out:** `supabase.auth.signOut`
- **Tier upgrade:** `supabase.auth.updateUser({ data: { tier } })`
- **Session sync:** listens to `supabase.auth.onAuthStateChange`

Required environment:

```bash
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>
```

Use it for production builds and any deployment where users actually need
real accounts.

## How to swap

### Option A — flip the default (everywhere)

Edit `src/features/auth/index.ts`:

```ts
// Before
export { LocalAuthProvider as AuthProvider } from './LocalAuthProvider';

// After
export { SupabaseAuthProvider as AuthProvider } from './SupabaseAuthProvider';
```

All existing `import { AuthProvider } from '.../features/auth'` call sites
pick up the new implementation automatically.

### Option B — explicit per call site

```tsx
import { SupabaseAuthProvider } from '@/features/auth';

<SupabaseAuthProvider>
  <App />
</SupabaseAuthProvider>
```

### Option C — env-driven

```tsx
import { LocalAuthProvider, SupabaseAuthProvider } from '@/features/auth';

const AuthProvider = import.meta.env.VITE_AUTH_BACKEND === 'supabase'
  ? SupabaseAuthProvider
  : LocalAuthProvider;
```

## Migration notes

Tier metadata lives in `user_metadata.tier` for the Supabase provider. If you
later move tier ownership to a server-side `subscriptions` table (recommended
for production), update `mapSupabaseUser` to read from your row instead of
user metadata — the public `useAuth()` surface stays the same.
