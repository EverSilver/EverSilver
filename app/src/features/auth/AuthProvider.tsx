/**
 * Eversilver Auth Provider
 *
 * Local-first auth scaffolding for personal-use Eversilver builds.
 * Wire to a real backend (Supabase / Clerk / Auth0 / custom JWT) by
 * replacing the `signIn`, `signUp`, and `signOut` implementations.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type SubscriptionTier = 'free' | 'pro' | 'ultra';

export interface EversilverUser {
  id: string;
  email: string;
  displayName: string;
  tier: SubscriptionTier;
  createdAt: string;
}

interface AuthState {
  user: EversilverUser | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName: string) => Promise<void>;
  signOut: () => Promise<void>;
  upgradeTier: (tier: SubscriptionTier) => Promise<void>;
  isAuthenticated: boolean;
}

const STORAGE_KEY = 'eversilver.auth.session';

const AuthContext = createContext<AuthContextValue | null>(null);

function loadSession(): EversilverUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as EversilverUser) : null;
  } catch {
    return null;
  }
}

function persistSession(user: EversilverUser | null): void {
  if (user) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true, error: null });

  useEffect(() => {
    setState({ user: loadSession(), loading: false, error: null });
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      if (!email || !password) throw new Error('Email and password required');
      // TODO: replace with real backend call
      const user: EversilverUser = {
        id: crypto.randomUUID(),
        email,
        displayName: email.split('@')[0],
        tier: 'free',
        createdAt: new Date().toISOString(),
      };
      persistSession(user);
      setState({ user, loading: false, error: null });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Sign in failed';
      setState({ user: null, loading: false, error: message });
      throw err;
    }
  }, []);

  const signUp = useCallback(async (email: string, password: string, displayName: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      if (!email || !password || !displayName) throw new Error('All fields required');
      const user: EversilverUser = {
        id: crypto.randomUUID(),
        email,
        displayName,
        tier: 'free',
        createdAt: new Date().toISOString(),
      };
      persistSession(user);
      setState({ user, loading: false, error: null });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Sign up failed';
      setState({ user: null, loading: false, error: message });
      throw err;
    }
  }, []);

  const signOut = useCallback(async () => {
    persistSession(null);
    setState({ user: null, loading: false, error: null });
  }, []);

  const upgradeTier = useCallback(async (tier: SubscriptionTier) => {
    setState(prev => {
      if (!prev.user) return prev;
      const updated = { ...prev.user, tier };
      persistSession(updated);
      return { ...prev, user: updated };
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      signIn,
      signUp,
      signOut,
      upgradeTier,
      isAuthenticated: state.user !== null,
    }),
    [state, signIn, signUp, signOut, upgradeTier]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
