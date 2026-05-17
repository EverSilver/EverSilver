/**
 * Eversilver Local Auth Provider
 *
 * Local-first auth backed by localStorage + PBKDF2 password hashing.
 * Suitable for personal-use / preview builds. For real cross-device auth,
 * use `SupabaseAuthProvider` (drop-in replacement with same public API).
 *
 * Storage layout (localStorage keys):
 *   - `eversilver.auth.users.v1`    — Record<email, StoredUser>
 *   - `eversilver.auth.session.v1`  — { userId } pointing into the users map
 *
 * Sessions are reactive across tabs via the `storage` event.
 */
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';

import { type HashedPassword, hashPassword, verifyPassword } from './crypto';
import {
  AuthContext,
  type AuthContextValue,
  type AuthState,
  type EversilverUser,
  type SubscriptionTier,
} from './types';

const USERS_KEY = 'eversilver.auth.users.v1';
const SESSION_KEY = 'eversilver.auth.session.v1';

interface StoredUser extends EversilverUser {
  /** Hashed password — never stored in plaintext. */
  passwordHash: HashedPassword;
}

interface StoredSession {
  userId: string;
}

function loadUsers(): Record<string, StoredUser> {
  try {
    const raw = localStorage.getItem(USERS_KEY);
    return raw ? (JSON.parse(raw) as Record<string, StoredUser>) : {};
  } catch {
    return {};
  }
}

function saveUsers(users: Record<string, StoredUser>): void {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

function loadSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

function saveSession(session: StoredSession | null): void {
  if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  else localStorage.removeItem(SESSION_KEY);
}

function publicUser(stored: StoredUser): EversilverUser {
  // Strip credential fields before exposing to the React tree.
  const { passwordHash: _omit, ...rest } = stored;
  void _omit;
  return rest;
}

function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function LocalAuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true, error: null });

  // Hydrate from storage on mount, and keep in sync if another tab logs in/out.
  useEffect(() => {
    const hydrate = () => {
      const session = loadSession();
      if (!session) {
        setState({ user: null, loading: false, error: null });
        return;
      }
      const users = loadUsers();
      const stored = Object.values(users).find(u => u.id === session.userId);
      setState({ user: stored ? publicUser(stored) : null, loading: false, error: null });
    };
    hydrate();
    const onStorage = (e: StorageEvent) => {
      if (e.key === SESSION_KEY || e.key === USERS_KEY) hydrate();
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      if (!email || !password) throw new Error('Email and password required');
      const key = normalizeEmail(email);
      const users = loadUsers();
      const existing = users[key];
      if (!existing) throw new Error('No account found for that email');
      const ok = await verifyPassword(password, existing.passwordHash);
      if (!ok) throw new Error('Incorrect password');
      saveSession({ userId: existing.id });
      setState({ user: publicUser(existing), loading: false, error: null });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Sign in failed';
      setState(prev => ({ ...prev, loading: false, error: message }));
      throw err;
    }
  }, []);

  const signUp = useCallback(async (email: string, password: string, displayName: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      if (!email || !password || !displayName) throw new Error('All fields required');
      if (password.length < 8) throw new Error('Password must be at least 8 characters');
      const key = normalizeEmail(email);
      const users = loadUsers();
      if (users[key]) throw new Error('An account with that email already exists');
      const passwordHash = await hashPassword(password);
      const stored: StoredUser = {
        id: crypto.randomUUID(),
        email: key,
        displayName: displayName.trim(),
        tier: 'free',
        createdAt: new Date().toISOString(),
        passwordHash,
      };
      users[key] = stored;
      saveUsers(users);
      saveSession({ userId: stored.id });
      setState({ user: publicUser(stored), loading: false, error: null });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Sign up failed';
      setState(prev => ({ ...prev, loading: false, error: message }));
      throw err;
    }
  }, []);

  const signOut = useCallback(async () => {
    saveSession(null);
    setState({ user: null, loading: false, error: null });
  }, []);

  const upgradeTier = useCallback(async (tier: SubscriptionTier) => {
    setState(prev => {
      if (!prev.user) return prev;
      const users = loadUsers();
      const key = prev.user.email;
      const stored = users[key];
      if (!stored) return prev;
      stored.tier = tier;
      users[key] = stored;
      saveUsers(users);
      return { ...prev, user: publicUser(stored) };
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
