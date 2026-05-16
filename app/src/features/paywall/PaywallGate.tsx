/**
 * Eversilver Paywall Gate
 *
 * Wrap premium UI: <PaywallGate feature="core.voice">...</PaywallGate>
 * Shows an upgrade prompt when the user lacks entitlement.
 */
import type { ReactNode } from 'react';
import { useEntitlement, usePaywall } from './PaywallProvider';
import { TIERS } from './tiers';

interface PaywallGateProps {
  feature: string;
  children: ReactNode;
  fallback?: ReactNode;
}

export function PaywallGate({ feature, children, fallback }: PaywallGateProps) {
  const allowed = useEntitlement(feature);
  const { requiredTierFor, checkout } = usePaywall();

  if (allowed) return <>{children}</>;
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
          ${def.priceMonthlyUsd}<span>/month</span>
        </p>
        <button onClick={() => checkout(requiredTier)} className="eversilver-paywall-cta">
          Upgrade now
        </button>
      </div>
    </div>
  );
}
