/**
 * Eversilver Paywall Gate
 *
 * Wrap premium UI: <PaywallGate feature="core.voice">...</PaywallGate>
 * When billing is disabled (preview mode), the gate is a pass-through.
 */
import type { ReactNode } from 'react';
import { useEntitlement, usePaywall } from './PaywallProvider';
import { TIERS, formatInr } from './tiers';

interface PaywallGateProps {
  feature: string;
  children: ReactNode;
  fallback?: ReactNode;
}

export function PaywallGate({ feature, children, fallback }: PaywallGateProps) {
  const allowed = useEntitlement(feature);
  const { requiredTierFor, checkout, billingEnabled } = usePaywall();

  if (allowed) return <>{children}</>;
  if (!billingEnabled) return <>{children}</>; // safety net — should never block in preview
  if (fallback) return <>{fallback}</>;

  const requiredTier = requiredTierFor(feature);
  if (!requiredTier) return null;
  const def = TIERS[requiredTier];

  return (
    <div className="eversilver-paywall-prompt">
      <div className="eversilver-paywall-card">
        <h3>Upgrade to {def.name}</h3>
        <p>{def.description}</p>
        <p className="eversilver-paywall-price">
          {formatInr(def.priceMonthlyInr)}<span> / month</span>
        </p>
        <button onClick={() => checkout(requiredTier)} className="eversilver-paywall-cta">
          Pay with UPI
        </button>
        <p className="eversilver-paywall-fineprint">
          UPI · Cards · Net Banking · Wallets — powered by Razorpay
        </p>
      </div>
    </div>
  );
}
