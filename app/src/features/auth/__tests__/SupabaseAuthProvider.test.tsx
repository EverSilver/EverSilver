import { act, renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---- Mock @supabase/supabase-js with a controllable fake client. ----

type AuthChangeCallback = (event: string, session: unknown) => void;

interface FakeAuth {
  getSession: ReturnType<typeof vi.fn>;
  onAuthStateChange: ReturnType<typeof vi.fn>;
  signInWithPassword: ReturnType<typeof vi.fn>;
  signUp: ReturnType<typeof vi.fn>;
  signOut: ReturnType<typeof vi.fn>;
  updateUser: ReturnType<typeof vi.fn>;
  /** Test helper to fire the change callback. */
  __fireChange: (event: string, session: unknown) => void;
}

let fakeAuth: FakeAuth;
let unsubscribe: ReturnType<typeof vi.fn>;
const createClientMock = vi.fn();

function makeFakeAuth(): FakeAuth {
  let cb: AuthChangeCallback | null = null;
  unsubscribe = vi.fn();
  return {
    getSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
    onAuthStateChange: vi.fn((fn: AuthChangeCallback) => {
      cb = fn;
      return { data: { subscription: { unsubscribe } } };
    }),
    signInWithPassword: vi.fn(),
    signUp: vi.fn(),
    signOut: vi.fn().mockResolvedValue({ error: null }),
    updateUser: vi.fn(),
    __fireChange: (event, session) => cb?.(event, session),
  };
}

vi.mock('@supabase/supabase-js', () => ({
  createClient: (...args: unknown[]) => {
    createClientMock(...args);
    return { auth: fakeAuth };
  },
}));

// Import AFTER vi.mock so the provider picks up the fake.
import { SupabaseAuthProvider, __resetSupabaseClient, mapSupabaseUser } from '../SupabaseAuthProvider';
import { useAuth } from '../useAuth';

function wrapper({ children }: { children: ReactNode }) {
  return <SupabaseAuthProvider>{children}</SupabaseAuthProvider>;
}

const supaUser = (overrides: Record<string, unknown> = {}) => ({
  id: 'uid-123',
  email: 'u@example.com',
  created_at: '2024-01-01T00:00:00Z',
  user_metadata: { display_name: 'You', tier: 'free' },
  ...overrides,
});

describe('mapSupabaseUser', () => {
  it('returns null for null input', () => {
    expect(mapSupabaseUser(null)).toBeNull();
    expect(mapSupabaseUser(undefined)).toBeNull();
  });

  it('maps a full supabase user', () => {
    const mapped = mapSupabaseUser(supaUser());
    expect(mapped).toEqual({
      id: 'uid-123',
      email: 'u@example.com',
      displayName: 'You',
      tier: 'free',
      createdAt: '2024-01-01T00:00:00Z',
    });
  });

  it('falls back to email prefix when display_name missing', () => {
    const mapped = mapSupabaseUser(supaUser({ user_metadata: {} }));
    expect(mapped?.displayName).toBe('u');
    expect(mapped?.tier).toBe('free');
  });

  it('accepts pro and ultra tiers, defaults unknown to free', () => {
    expect(mapSupabaseUser(supaUser({ user_metadata: { tier: 'pro' } }))?.tier).toBe('pro');
    expect(mapSupabaseUser(supaUser({ user_metadata: { tier: 'ultra' } }))?.tier).toBe('ultra');
    expect(mapSupabaseUser(supaUser({ user_metadata: { tier: 'enterprise' } }))?.tier).toBe('free');
    expect(mapSupabaseUser(supaUser({ user_metadata: null }))?.tier).toBe('free');
  });

  it('supports camelCase displayName fallback', () => {
    const mapped = mapSupabaseUser(supaUser({ user_metadata: { displayName: 'Camel' } }));
    expect(mapped?.displayName).toBe('Camel');
  });

  it('handles missing email gracefully', () => {
    const mapped = mapSupabaseUser(supaUser({ email: null, user_metadata: {} }));
    expect(mapped?.email).toBe('');
    expect(mapped?.displayName).toBe('user');
  });
});

describe('SupabaseAuthProvider', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_SUPABASE_URL', 'https://test.supabase.co');
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'anon-key-test');
    fakeAuth = makeFakeAuth();
    createClientMock.mockClear();
    __resetSupabaseClient();
  });

  it('throws if env vars are missing', () => {
    vi.stubEnv('VITE_SUPABASE_URL', '');
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', '');
    __resetSupabaseClient();
    expect(() => renderHook(() => useAuth(), { wrapper })).toThrow(/VITE_SUPABASE/);
  });

  it('initial fetch with no session leaves user null', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(fakeAuth.getSession).toHaveBeenCalled();
    expect(fakeAuth.onAuthStateChange).toHaveBeenCalled();
  });

  it('hydrates user from an existing session on mount', async () => {
    fakeAuth.getSession.mockResolvedValueOnce({
      data: { session: { user: supaUser({ user_metadata: { tier: 'pro' } }) } },
      error: null,
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user?.id).toBe('uid-123');
    expect(result.current.user?.tier).toBe('pro');
  });

  it('records error when getSession rejects', async () => {
    fakeAuth.getSession.mockRejectedValueOnce(new Error('boom'));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toMatch(/boom/);
    expect(result.current.user).toBeNull();
  });

  it('signs in via signInWithPassword', async () => {
    fakeAuth.signInWithPassword.mockResolvedValueOnce({
      data: { user: supaUser() },
      error: null,
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.signIn('u@example.com', 'pw');
    });

    expect(fakeAuth.signInWithPassword).toHaveBeenCalledWith({
      email: 'u@example.com',
      password: 'pw',
    });
    expect(result.current.user?.id).toBe('uid-123');
    expect(result.current.isAuthenticated).toBe(true);
  });

  it('rejects sign in with missing fields without calling supabase', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await expect(result.current.signIn('', '')).rejects.toThrow(/required/i);
    });
    expect(fakeAuth.signInWithPassword).not.toHaveBeenCalled();
    expect(result.current.error).toMatch(/required/i);
  });

  it('surfaces sign in errors from supabase', async () => {
    fakeAuth.signInWithPassword.mockResolvedValueOnce({
      data: { user: null },
      error: { message: 'invalid credentials' },
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await expect(result.current.signIn('u@e.com', 'pw')).rejects.toBeTruthy();
    });
    expect(result.current.error).toMatch(/invalid credentials/);
  });

  it('signs up with display_name and tier=free in options.data', async () => {
    fakeAuth.signUp.mockResolvedValueOnce({
      data: { user: supaUser({ user_metadata: { display_name: 'New Person', tier: 'free' } }) },
      error: null,
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.signUp('new@example.com', 'pw', 'New Person');
    });

    expect(fakeAuth.signUp).toHaveBeenCalledWith({
      email: 'new@example.com',
      password: 'pw',
      options: { data: { display_name: 'New Person', tier: 'free' } },
    });
    expect(result.current.user?.displayName).toBe('New Person');
    expect(result.current.user?.tier).toBe('free');
  });

  it('rejects sign up with missing fields', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await expect(result.current.signUp('a@b.com', 'pw', '')).rejects.toThrow(/required/i);
    });
    expect(fakeAuth.signUp).not.toHaveBeenCalled();
  });

  it('surfaces sign up errors from supabase', async () => {
    fakeAuth.signUp.mockResolvedValueOnce({
      data: { user: null },
      error: { message: 'email taken' },
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await expect(result.current.signUp('a@b.com', 'pw', 'A')).rejects.toBeTruthy();
    });
    expect(result.current.error).toMatch(/email taken/);
  });

  it('signs out via supabase.auth.signOut and clears user', async () => {
    fakeAuth.getSession.mockResolvedValueOnce({
      data: { session: { user: supaUser() } },
      error: null,
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    await act(async () => {
      await result.current.signOut();
    });

    expect(fakeAuth.signOut).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('signOut surfaces errors', async () => {
    fakeAuth.signOut.mockResolvedValueOnce({ error: { message: 'nope' } });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await expect(result.current.signOut()).rejects.toBeTruthy();
    });
    expect(result.current.error).toMatch(/nope/);
  });

  it('upgradeTier calls updateUser with the new tier in user metadata', async () => {
    fakeAuth.getSession.mockResolvedValueOnce({
      data: { session: { user: supaUser() } },
      error: null,
    });
    fakeAuth.updateUser.mockResolvedValueOnce({
      data: { user: supaUser({ user_metadata: { display_name: 'You', tier: 'ultra' } }) },
      error: null,
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    await act(async () => {
      await result.current.upgradeTier('ultra');
    });

    expect(fakeAuth.updateUser).toHaveBeenCalledWith({ data: { tier: 'ultra' } });
    expect(result.current.user?.tier).toBe('ultra');
  });

  it('upgradeTier surfaces errors', async () => {
    fakeAuth.updateUser.mockResolvedValueOnce({
      data: { user: null },
      error: { message: 'rate limited' },
    });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await expect(result.current.upgradeTier('pro')).rejects.toBeTruthy();
    });
    expect(result.current.error).toMatch(/rate limited/);
  });

  it('reacts to onAuthStateChange events', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();

    await act(async () => {
      fakeAuth.__fireChange('SIGNED_IN', { user: supaUser({ id: 'uid-evt' }) });
    });
    expect(result.current.user?.id).toBe('uid-evt');

    await act(async () => {
      fakeAuth.__fireChange('SIGNED_OUT', null);
    });
    expect(result.current.user).toBeNull();
  });

  it('unsubscribes the auth state listener on unmount', async () => {
    const hook = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
    hook.unmount();
    expect(unsubscribe).toHaveBeenCalled();
  });
});
