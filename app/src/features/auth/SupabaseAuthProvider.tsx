/**
 * Eversilver Supabase Auth Provider
 *
 * Drop-in replacement for `LocalAuthProvider`, backed by Supabase Auth.
 * Public API (the `useAuth()` hook, `EversilverUser`, `SubscriptionTier`)
 * is identical so consumers don't change.
 *
 * Config:
 *   VITE_SUPABASE_URL       — your Supabase project URL
 *   VITE_SUPABASE_ANON_KEY  — your Supabase anon key
 *
 * Subscription tier is stored in `user_metadata.tier`.
 */
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  AuthContext,
  type AuthContextValue,
  type AuthState,
  type EversilverUser,
  type SubscriptionTier,
} from './types';

type SupabaseUserLike = {
  id: string;
  email?: string | null;
  created_at?: string;
  user_metadata?: Record<string, unknown> | null;
};

function pickString(meta: Record<string, unknown> | null | undefined, key: string): string | null {
  if (!meta) return null;
  const v = meta[key];
  return typeof v === 'string' && v.length > 0 ? v : null;
}

function extractMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) return err.message;
  if (err && typeof err === 'object' && 'message' in err) {
    const m = (err as { message?: unknown }).message;
    if (typeof m === 'string' && m.length > 0) return m;
  }
  return fallback;
}

function pickTier(meta: Record<string, unknown> | null | undefined): SubscriptionTier {
  const t = pickString(meta, 'tier');
  return t === 'pro' || t === 'ultra' ? t : 'free';
}

export function mapSupabaseUser(user: SupabaseUserLike | null | undefined): EversilverUser | null {
  if (!user) return null;
  const email = user.email ?? '';
  const displayName =
    pickString(user.user_metadata, 'display_name') ??
    pickString(user.user_metadata, 'displayName') ??
    (email ? email.split('@')[0] : 'user');
  return {
    id: user.id,
    email,
    displayName,
    tier: pickTier(user.user_metadata),
    createdAt: user.created_at ?? new Date().toISOString(),
  };
}

let cachedClient: SupabaseClient | null = null;

/**
 * Build (or reuse) a Supabase client from Vite env vars.
 *
 * Exposed for tests so they can reset the cache via `__resetSupabaseClient`.
 */
export function getSupabaseClient(): SupabaseClient {
  if (cachedClient) return cachedClient;
  const url = (import.meta.env.VITE_SUPABASE_URL ?? '') as string;
  const anonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY ?? '') as string;
  if (!url || !anonKey) {
    throw new Error(
      'SupabaseAuthProvider: missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY env vars.'
    );
  }
  cachedClient = createClient(url, anonKey);
  return cachedClient;
}

/** Test-only: clear the cached client so a fresh `createClient` mock is picked up. */
export function __resetSupabaseClient(): void {
  cachedClient = null;
}

export function SupabaseAuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true, error: null });
  // Hold the client in a ref so we instantiate it exactly once per provider.
  const clientRef = useRef<SupabaseClient | null>(null);
  if (!clientRef.current) {
    clientRef.current = getSupabaseClient();
  }
  const supabase = clientRef.current;

  useEffect(() => {
    let cancelled = false;

    void supabase.auth
      .getSession()
      .then(({ data }) => {
        if (cancelled) return;
        const user = mapSupabaseUser(data.session?.user as SupabaseUserLike | undefined);
        setState({ user, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : 'Failed to load session';
        setState({ user: null, loading: false, error: message });
      });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      const user = mapSupabaseUser(session?.user as SupabaseUserLike | undefined);
      setState(prev => ({ ...prev, user, loading: false }));
    });

    return () => {
      cancelled = true;
      sub.subscription.unsubscribe();
    };
  }, [supabase]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      setState(prev => ({ ...prev, loading: true, error: null }));
      try {
        if (!email || !password) throw new Error('Email and password required');
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        const user = mapSupabaseUser(data.user as SupabaseUserLike | null);
        setState({ user, loading: false, error: null });
      } catch (err) {
        const message = extractMessage(err, 'Sign in failed');
        setState(prev => ({ ...prev, loading: false, error: message }));
        throw err instanceof Error ? err : new Error(message);
      }
    },
    [supabase]
  );

  const signUp = useCallback(
    async (email: string, password: string, displayName: string) => {
      setState(prev => ({ ...prev, loading: true, error: null }));
      try {
        if (!email || !password || !displayName) throw new Error('All fields required');
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { display_name: displayName, tier: 'free' } },
        });
        if (error) throw error;
        const user = mapSupabaseUser(data.user as SupabaseUserLike | null);
        setState({ user, loading: false, error: null });
      } catch (err) {
        const message = extractMessage(err, 'Sign up failed');
        setState(prev => ({ ...prev, loading: false, error: message }));
        throw err instanceof Error ? err : new Error(message);
      }
    },
    [supabase]
  );

  const signOut = useCallback(async () => {
    const { error } = await supabase.auth.signOut();
    if (error) {
      setState(prev => ({ ...prev, error: error.message }));
      throw error;
    }
    setState({ user: null, loading: false, error: null });
  }, [supabase]);

  const upgradeTier = useCallback(
    async (tier: SubscriptionTier) => {
      const { data, error } = await supabase.auth.updateUser({ data: { tier } });
      if (error) {
        setState(prev => ({ ...prev, error: error.message }));
        throw error;
      }
      const user = mapSupabaseUser(data.user as SupabaseUserLike | null);
      setState(prev => ({ ...prev, user: user ?? prev.user }));
    },
    [supabase]
  );

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
