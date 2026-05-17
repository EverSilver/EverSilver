import { describe, expect, it } from 'vitest';

import { formatInr, hasFeature, minimumTierFor, tierRank, TIERS } from '../tiers';

describe('tierRank', () => {
  it('orders free < pro < ultra', () => {
    expect(tierRank('free')).toBe(0);
    expect(tierRank('pro')).toBe(1);
    expect(tierRank('ultra')).toBe(2);
    expect(tierRank('free')).toBeLessThan(tierRank('pro'));
    expect(tierRank('pro')).toBeLessThan(tierRank('ultra'));
  });
});

describe('hasFeature', () => {
  it('returns true for features in the tier', () => {
    expect(hasFeature('free', 'core.chat')).toBe(true);
    expect(hasFeature('free', 'core.memory.basic')).toBe(true);
  });

  it('returns false for free tier on pro-only features', () => {
    expect(hasFeature('free', 'core.voice')).toBe(false);
    expect(hasFeature('free', 'core.memory.unlimited')).toBe(false);
    expect(hasFeature('free', 'core.web.fetch')).toBe(false);
  });

  it('grants pro all its features and inherits free ones', () => {
    for (const f of TIERS.pro.features) {
      expect(hasFeature('pro', f)).toBe(true);
    }
    expect(hasFeature('pro', 'core.models.frontier')).toBe(false);
  });

  it('grants ultra all features including ultra-only', () => {
    for (const f of TIERS.ultra.features) {
      expect(hasFeature('ultra', f)).toBe(true);
    }
    expect(hasFeature('ultra', 'core.models.frontier')).toBe(true);
    expect(hasFeature('ultra', 'core.meet.agent')).toBe(true);
  });

  it('returns false for unknown features at every tier', () => {
    expect(hasFeature('free', 'not.a.real.feature')).toBe(false);
    expect(hasFeature('pro', 'not.a.real.feature')).toBe(false);
    expect(hasFeature('ultra', 'not.a.real.feature')).toBe(false);
  });
});

describe('minimumTierFor', () => {
  it('returns free for core.chat', () => {
    expect(minimumTierFor('core.chat')).toBe('free');
  });

  it('returns pro for pro-tier features', () => {
    expect(minimumTierFor('core.voice')).toBe('pro');
    expect(minimumTierFor('core.memory.unlimited')).toBe('pro');
  });

  it('returns ultra for ultra-only features', () => {
    expect(minimumTierFor('core.models.frontier')).toBe('ultra');
    expect(minimumTierFor('core.meet.agent')).toBe('ultra');
  });

  it('returns null for unknown features', () => {
    expect(minimumTierFor('definitely.not.a.feature')).toBeNull();
    expect(minimumTierFor('')).toBeNull();
  });
});

describe('formatInr', () => {
  it('formats whole rupee values with the rupee symbol', () => {
    const out = formatInr(499);
    // Intl with style:currency + INR yields '₹499' (no fraction). Allow optional
    // narrow no-break space between symbol and digits across ICU versions.
    expect(out).toMatch(/^₹\s?499$/);
  });

  it('uses Indian comma grouping for large numbers', () => {
    const out = formatInr(100000);
    // Indian grouping: 1,00,000 (lakh), not 100,000.
    expect(out).toMatch(/1,00,000/);
  });

  it('formats 0 as ₹0', () => {
    expect(formatInr(0)).toMatch(/^₹\s?0$/);
  });

  it('drops fractional digits', () => {
    const out = formatInr(1499.7);
    expect(out).not.toMatch(/\./);
    expect(out).toMatch(/1,499|1,500/); // rounded to nearest int
  });
});
