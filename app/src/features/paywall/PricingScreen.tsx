/**
 * Eversilver Pricing Screen
 *
 * Full pricing page showing all tiers with CTAs.
 */
import { usePaywall } from './PaywallProvider';
import { TIERS } from './tiers';
import type { SubscriptionTier } from '../auth';

const TIER_ORDER: SubscriptionTier[] = ['free', 'pro', 'ultra'];

export function PricingScreen() {
  const { currentTier, checkout, isAtLeast } = usePaywall();

  return (
    <div className="eversilver-pricing-screen">
      <header className="eversilver-pricing-header">
        <h1>Choose your plan</h1>
        <p>Unlock the full power of Eversilver.</p>
      </header>

      <div className="eversilver-pricing-grid">
        {TIER_ORDER.map(tierId => {
          const def = TIERS[tierId];
          const isCurrent = currentTier === tierId;
          const isDowngrade = isAtLeast(tierId) && !isCurrent;

          return (
            <div
              key={tierId}
              className={`eversilver-pricing-card ${isCurrent ? 'is-current' : ''}`}
              data-tier={tierId}
            >
              <h2>{def.name}</h2>
              <div className="eversilver-pricing-price">
                <span className="amount">${def.priceMonthlyUsd}</span>
                <span className="period">/month</span>
              </div>
              <p className="eversilver-pricing-description">{def.description}</p>

              <ul className="eversilver-pricing-features">
                {def.features.map(f => (
                  <li key={f}>{f.replace(/^core\./, '').replace(/\./g, ' ')}</li>
                ))}
              </ul>

              {isCurrent ? (
                <button disabled className="eversilver-pricing-cta is-current">
                  Current plan
                </button>
              ) : isDowngrade ? (
                <button disabled className="eversilver-pricing-cta is-downgrade">
                  Downgrade unavailable
                </button>
              ) : (
                <button
                  onClick={() => checkout(tierId)}
                  className="eversilver-pricing-cta"
                >
                  {tierId === 'free' ? 'Start free' : `Upgrade to ${def.name}`}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
