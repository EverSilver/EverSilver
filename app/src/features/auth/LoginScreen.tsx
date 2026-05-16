/**
 * Eversilver Login Screen
 *
 * Drop-in login + signup UI for the Eversilver desktop app.
 * Mount this as a gate before the main AppRoutes when `!isAuthenticated`.
 */
import { useState, type FormEvent } from 'react';
import { useAuth } from './AuthProvider';

type Mode = 'signin' | 'signup';

export function LoginScreen() {
  const { signIn, signUp, loading, error } = useAuth();
  const [mode, setMode] = useState<Mode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      if (mode === 'signin') {
        await signIn(email, password);
      } else {
        await signUp(email, password, displayName);
      }
    } catch {
      // error is surfaced via auth state
    }
  }

  return (
    <div className="eversilver-login-screen">
      <div className="eversilver-login-card">
        <h1 className="eversilver-login-title">Eversilver</h1>
        <p className="eversilver-login-subtitle">
          {mode === 'signin' ? 'Welcome back' : 'Create your account'}
        </p>

        <form onSubmit={handleSubmit} className="eversilver-login-form">
          {mode === 'signup' && (
            <label className="eversilver-login-field">
              <span>Display name</span>
              <input
                type="text"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                required
                autoComplete="name"
              />
            </label>
          )}

          <label className="eversilver-login-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>

          <label className="eversilver-login-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            />
          </label>

          {error && <div className="eversilver-login-error">{error}</div>}

          <button type="submit" disabled={loading} className="eversilver-login-submit">
            {loading ? 'Working…' : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
          className="eversilver-login-toggle"
        >
          {mode === 'signin'
            ? "Don't have an account? Sign up"
            : 'Already have an account? Sign in'}
        </button>
      </div>
    </div>
  );
}
