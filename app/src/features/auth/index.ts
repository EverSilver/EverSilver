/**
 * Eversilver auth barrel.
 *
 * Two interchangeable providers expose the same `useAuth()` surface:
 *   - `LocalAuthProvider`     — localStorage + PBKDF2 (preview / dev / personal)
 *   - `SupabaseAuthProvider`  — Supabase-backed real auth (production)
 *
 * `AuthProvider` defaults to `LocalAuthProvider` so existing imports keep
 * working. Swap to Supabase by changing this single line OR by importing
 * `SupabaseAuthProvider` directly. See `PROVIDER_SELECTION.md`.
 */
export { LocalAuthProvider } from './LocalAuthProvider';
export { SupabaseAuthProvider } from './SupabaseAuthProvider';
export { LocalAuthProvider as AuthProvider } from './LocalAuthProvider';
export { useAuth } from './useAuth';
export type { AuthContextValue, AuthState, EversilverUser, SubscriptionTier } from './types';
export { LoginScreen } from './LoginScreen';
export { AuthGate } from './AuthGate';
