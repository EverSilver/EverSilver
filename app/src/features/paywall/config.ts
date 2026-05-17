/**
 * Paywall master switch.
 *
 * BILLING_ENABLED=false (default) — All features unlocked for every signed-in
 *   user. Pricing screen shows a "free during preview" banner. PaywallGate
 *   never blocks. Razorpay code stays in place, just dormant.
 *
 * BILLING_ENABLED=true — Normal tiered behavior. Users must upgrade through
 *   Razorpay (or local-grant fallback if backend not yet wired) to access
 *   higher-tier features.
 *
 * Flip via env: VITE_BILLING_ENABLED=true
 */
export const BILLING_ENABLED: boolean =
  (import.meta.env.VITE_BILLING_ENABLED ?? 'false').toString().toLowerCase() === 'true';

/** Tier granted automatically to every user when billing is disabled. */
export const PREVIEW_TIER = 'ultra' as const;
