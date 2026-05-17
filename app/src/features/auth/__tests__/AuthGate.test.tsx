/**
 * AuthGate tests
 *
 * Verifies the gate that mounts auth + paywall providers and decides
 * whether to render the login screen or the wrapped children.
 */
import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { AuthGate } from '../AuthGate';

const USERS_KEY = 'eversilver.auth.users.v1';
const SESSION_KEY = 'eversilver.auth.session.v1';

describe('AuthGate', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the bootstrap dot while hydrating, then the login screen when unauthenticated', async () => {
    const { container } = render(
      <AuthGate>
        <div>protected-child</div>
      </AuthGate>
    );

    // After hydration, login screen should be visible and the gated child
    // should NOT be rendered.
    await waitFor(() => expect(screen.queryByText('Eversilver')).toBeInTheDocument());
    expect(screen.queryByText('protected-child')).toBeNull();

    // Login form fields are present.
    expect(container.querySelector('input[type="email"]')).not.toBeNull();
    expect(container.querySelector('input[type="password"]')).not.toBeNull();
  });

  it('renders children once a session is hydrated from storage', async () => {
    // Seed the user record + session pointer directly.
    const userId = 'test-user-id';
    const stored = {
      [userId.toLowerCase()]: {
        id: userId,
        email: 'u@example.com',
        displayName: 'U',
        tier: 'free',
        createdAt: new Date().toISOString(),
        passwordHash: {
          algo: 'pbkdf2-sha256',
          iterations: 600_000,
          salt: 'AAAAAAAAAAAAAAAAAAAAAA==',
          hash: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        },
      },
    };
    localStorage.setItem(USERS_KEY, JSON.stringify(stored));
    localStorage.setItem(SESSION_KEY, JSON.stringify({ userId }));

    // Fix the email key to match what LocalAuthProvider stores (normalized to lowercase).
    const users = JSON.parse(localStorage.getItem(USERS_KEY) ?? '{}');
    const u = Object.values(users)[0] as { email: string; id: string };
    users[u.email] = u;
    delete users[userId.toLowerCase()];
    localStorage.setItem(USERS_KEY, JSON.stringify(users));

    render(
      <AuthGate>
        <div data-testid="protected">protected-child</div>
      </AuthGate>
    );

    await waitFor(() => expect(screen.queryByTestId('protected')).not.toBeNull());
    expect(screen.queryByText(/Welcome back/i)).toBeNull();
  });

  it('keeps the login screen up after a failed sign-in attempt', async () => {
    const { container } = render(
      <AuthGate>
        <div data-testid="protected">protected-child</div>
      </AuthGate>
    );
    await waitFor(() => expect(screen.queryByText('Eversilver')).toBeInTheDocument());

    const emailInput = container.querySelector('input[type="email"]') as HTMLInputElement;
    const passwordInput = container.querySelector('input[type="password"]') as HTMLInputElement;
    const submit = container.querySelector('button[type="submit"]') as HTMLButtonElement;

    await act(async () => {
      emailInput.value = 'nobody@example.com';
      emailInput.dispatchEvent(new Event('input', { bubbles: true }));
      passwordInput.value = 'wrongpass123';
      passwordInput.dispatchEvent(new Event('input', { bubbles: true }));
      submit.click();
      // wait a tick for the async rejection to settle
      await new Promise(r => setTimeout(r, 50));
    });

    // Still showing the login screen, gated child not mounted.
    expect(screen.queryByText('Eversilver')).toBeInTheDocument();
    expect(screen.queryByTestId('protected')).toBeNull();
  });
});
