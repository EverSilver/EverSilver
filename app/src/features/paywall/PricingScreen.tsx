/**
 * Eversilver Pricing Screen
 *
 * In preview mode (BILLING_ENABLED=false) this screen shows a single
 * "free during preview — everything unlocked" panel instead of tier cards.
 */
import { usePaywall } from './PaywallProvider';
import { TIERS, formatInr } from './tiers';
import { BILLING_ENABLED } from './config';
import type { SubscriptionTier } from '../auth';

const TIER_ORDER: SubscriptionTier[] = ['free', 'pro', 'ultra'];

function PreviewBanner() {
  return (
    <div className="eversilver-pricing-screen">
      <div className="eversilver-preview-banner">
        <h1>Free during preview</h1>
        <p>Every feature is unlocked while Eversilver is in private preview.</p>
        <p className="eversilver-preview-note">
          No payment required. Pricing will be announced later.
        </p>
      </div>
    </div>
  );
}

export function PricingScreen() {
  const { currentTier, checkout, isAtLeast } = usePaywall();

  if (!BILLING_ENABLED) return <PreviewBanner />;

  return (
    <div className="eversilver-pricing-screen">
      <header className="eversilver-pricing-header">
        <h1>Choose your plan</h1>
        <p>Pay securely with UPI, cards, or net banking.</p>
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
                <span className="amount">{formatInr(def.priceMonthlyInr)}</span>
                <span className="period"> / month</span>
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
                  {tierId === 'free' ? 'Start free' : 'Pay with UPI'}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <footer className="eversilver-pricing-footer">
        <p>
          Subscriptions auto-renew monthly via UPI mandate or card.
          Cancel anytime from your account settings. Prices include GST where applicable.
        </p>
      </footer>
    </div>
  );
}
