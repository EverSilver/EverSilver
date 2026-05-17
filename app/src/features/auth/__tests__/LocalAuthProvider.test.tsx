/**
 * LocalAuthProvider tests
 *
 * Covers the PBKDF2-backed local auth flow:
 *   - bootstrap state
 *   - sign up creates an account with hashed password
 *   - sign in succeeds with the right password, fails with the wrong one
 *   - sign in errors when no account exists for the email
 *   - sign out clears the session pointer but keeps the user record
 *   - session survives a remount
 *   - upgradeTier mutates the persisted user
 *   - invalid JSON in storage is recovered from gracefully
 *   - useAuth throws outside the provider
 *   - children render normally
 */
import { act, render, renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it } from 'vitest';

import { LocalAuthProvider } from '../LocalAuthProvider';
import { useAuth } from '../useAuth';

const USERS_KEY = 'eversilver.auth.users.v1';
const SESSION_KEY = 'eversilver.auth.session.v1';

const VALID_PASSWORD = 'password123';
const SHORT_PASSWORD = 'short';

function wrapper({ children }: { children: ReactNode }) {
  return <LocalAuthProvider>{children}</LocalAuthProvider>;
}

describe('LocalAuthProvider (PBKDF2)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('starts in a loading state then resolves with no user', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('signs up, hashes the password, and starts a session', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.signUp('new@example.com', VALID_PASSWORD, 'New User');
    });

    expect(result.current.user?.email).toBe('new@example.com');
    expect(result.current.user?.displayName).toBe('New User');
    expect(result.current.user?.tier).toBe('free');
    expect(result.current.isAuthenticated).toBe(true);

    // Storage: user record exists with a HASHED password (not plaintext).
    const users = JSON.parse(localStorage.getItem(USERS_KEY) ?? '{}');
    const stored = users['new@example.com'];
    expect(stored).toBeTruthy();
    expect(stored.passwordHash.algo).toBe('pbkdf2-sha256');
    expect(stored.passwordHash.hash).not.toContain(VALID_PASSWORD);
    expect(typeof stored.passwordHash.salt).toBe('string');
    expect(stored.passwordHash.iterations).toBeGreaterThan(100_000);

    // Session pointer matches the stored user id.
    const session = JSON.parse(localStorage.getItem(SESSION_KEY) ?? '{}');
    expect(session.userId).toBe(stored.id);
  });

  it('rejects sign up with missing fields', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await expect(result.current.signUp('a@b.com', VALID_PASSWORD, '')).rejects.toThrow(
        /required/i
      );
    });
    expect(result.current.user).toBeNull();
  });

  it('rejects sign up with a too-short password', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await expect(
        result.current.signUp('a@b.com', SHORT_PASSWORD, 'A')
      ).rejects.toThrow(/at least 8/i);
    });
    expect(result.current.user).toBeNull();
  });

  it('rejects sign up when the email is already registered', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.signUp('dupe@example.com', VALID_PASSWORD, 'First');
    });
    await act(async () => {
      await result.current.signOut();
    });
    await act(async () => {
      await expect(
        result.current.signUp('dupe@example.com', VALID_PASSWORD, 'Second')
      ).rejects.toThrow(/already exists/i);
    });
  });

  it('signs in with the correct password after sign up', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.signUp('u@example.com', VALID_PASSWORD, 'U');
    });
    await act(async () => {
      await result.current.signOut();
    });
    expect(result.current.user).toBeNull();

    await act(async () => {
      await result.current.signIn('u@example.com', VALID_PASSWORD);
    });

    expect(result.current.user?.email).toBe('u@example.com');
    expect(result.current.isAuthenticated).toBe(true);
  });

  it('rejects sign in with the wrong password', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.signUp('u@example.com', VALID_PASSWORD, 'U');
    });
    await act(async () => {
      await result.current.signOut();
    });

    await act(async () => {
      await expect(result.current.signIn('u@example.com', 'wrongpass')).rejects.toThrow(
        /incorrect password/i
      );
    });
    expect(result.current.user).toBeNull();
  });

  it('rejects sign in when no account exists for the email', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await expect(
        result.current.signIn('nobody@example.com', VALID_PASSWORD)
      ).rejects.toThrow(/no account/i);
    });
  });

  it('rejects sign in with missing fields', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await expect(result.current.signIn('', '')).rejects.toThrow(/required/i);
    });
  });

  it('signs out, clears the session, but keeps the user record', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.signUp('u@example.com', VALID_PASSWORD, 'U');
    });
    expect(localStorage.getItem(SESSION_KEY)).not.toBeNull();

    await act(async () => {
      await result.current.signOut();
    });
    expect(result.current.user).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
    // User record persists so they can sign back in.
    expect(localStorage.getItem(USERS_KEY)).not.toBeNull();
  });

  it('persists session across re-mount', async () => {
    const first = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(first.result.current.loading).toBe(false));
    await act(async () => {
      await first.result.current.signUp('persisted@example.com', VALID_PASSWORD, 'P');
    });
    first.unmount();

    const second = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(second.result.current.loading).toBe(false));
    expect(second.result.current.user?.email).toBe('persisted@example.com');
    expect(second.result.current.isAuthenticated).toBe(true);
  });

  it('upgradeTier mutates the user and persists', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.signUp('u@example.com', VALID_PASSWORD, 'U');
    });

    await act(async () => {
      await result.current.upgradeTier('ultra');
    });

    expect(result.current.user?.tier).toBe('ultra');
    const users = JSON.parse(localStorage.getItem(USERS_KEY) ?? '{}');
    expect(users['u@example.com'].tier).toBe('ultra');
  });

  it('upgradeTier is a no-op when no user is signed in', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.upgradeTier('pro');
    });
    expect(result.current.user).toBeNull();
  });

  it('gracefully recovers when storage holds invalid JSON', async () => {
    localStorage.setItem(USERS_KEY, '{not json');
    localStorage.setItem(SESSION_KEY, '{also not json');
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
  });

  it('useAuth throws when used outside a provider', () => {
    expect(() => renderHook(() => useAuth())).toThrow(/useAuth must be used within/i);
  });

  it('renders children', () => {
    const { getByText } = render(
      <LocalAuthProvider>
        <div>child-marker</div>
      </LocalAuthProvider>
    );
    expect(getByText('child-marker')).toBeInTheDocument();
  });
});
