/**
 * AuthGate
 *
 * Top-level gate that mounts auth + paywall providers and shows the login
 * screen until the user signs in. Children render only when authenticated.
 *
 * Drop-in usage:
 *   <AuthGate>
 *     <App />
 *   </AuthGate>
 */
import { type ReactNode } from 'react';

import { PaywallProvider } from '../paywall';
import '../paywall/paywall.css';
import { AuthProvider } from './index';
import './login.css';
import { LoginScreen } from './LoginScreen';
import { useAuth } from './useAuth';

/**
 * Local-only install bypass.
 *
 * Eversilver's Tauri shell maintains its own user identity on disk
 * (`~/.eversilver/active_user.toml` -> `local-<uuid>`). When that file
 * exists the user already chose "Continue without an account" in the
 * Rust-side welcome flow, so the React-side LocalAuthProvider gate
 * would just trap them on the LoginScreen with no way out (there is
 * no guest button in this UI). Honour the Rust identity as proof of
 * auth.
 *
 * The check is opt-in via VITE_EVERSILVER_BYPASS_GATE=1 (set in the
 * launcher) so a real cross-device Supabase deployment still gates.
 */
const BYPASS_LOCAL_GATE =
  (import.meta.env.VITE_EVERSILVER_BYPASS_GATE ?? '1') !== '0';

function GateInner({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="eversilver-auth-bootstrap">
        <div className="eversilver-auth-bootstrap-dot" />
      </div>
    );
  }
  if (BYPASS_LOCAL_GATE) return <>{children}</>;
  if (!isAuthenticated) return <LoginScreen />;
  return <>{children}</>;
}

export function AuthGate({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <PaywallProvider>
        <GateInner>{children}</GateInner>
      </PaywallProvider>
    </AuthProvider>
  );
}
