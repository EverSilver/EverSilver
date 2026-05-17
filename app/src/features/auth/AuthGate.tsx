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
import { AuthProvider } from './index';
import { LoginScreen } from './LoginScreen';
import { useAuth } from './useAuth';
import './login.css';
import '../paywall/paywall.css';

function GateInner({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="eversilver-auth-bootstrap">
        <div className="eversilver-auth-bootstrap-dot" />
      </div>
    );
  }
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
