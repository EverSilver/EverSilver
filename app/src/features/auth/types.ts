/**
 * Shared types and context for Eversilver auth providers.
 *
 * Both `LocalAuthProvider` and `SupabaseAuthProvider` expose this same
 * `AuthContextValue` shape so consumers can swap providers without
 * touching call sites.
 */
import { createContext } from 'react';

export type SubscriptionTier = 'free' | 'pro' | 'ultra';

export interface EversilverUser {
  id: string;
  email: string;
  displayName: string;
  tier: SubscriptionTier;
  createdAt: string;
}

export interface AuthState {
  user: EversilverUser | null;
  loading: boolean;
  error: string | null;
}

export interface AuthContextValue extends AuthState {
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName: string) => Promise<void>;
  signOut: () => Promise<void>;
  upgradeTier: (tier: SubscriptionTier) => Promise<void>;
  isAuthenticated: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
