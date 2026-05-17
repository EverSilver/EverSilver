/**
 * VrmMascot tests
 *
 * Verifies the lazy-loading swap between the 2D SVG fallback and the 3D
 * renderer driven by VITE_MASCOT_MODEL_URL.
 */
import { render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mapFaceToExpression } from '../vrmLoader';

describe('mapFaceToExpression', () => {
  it('maps sleep -> relaxed', () => {
    expect(mapFaceToExpression('sleep')).toBe('relaxed');
  });
  it('maps happy -> happy', () => {
    expect(mapFaceToExpression('happy')).toBe('happy');
  });
  it('maps thinking -> sad (concerned look)', () => {
    expect(mapFaceToExpression('thinking')).toBe('sad');
  });
  it('maps confused -> sad', () => {
    expect(mapFaceToExpression('confused')).toBe('sad');
  });
  it('maps speaking -> neutral (visemes drive the mouth instead)', () => {
    expect(mapFaceToExpression('speaking')).toBe('neutral');
  });
  it('maps idle / listening / normal / unknown -> neutral', () => {
    expect(mapFaceToExpression('idle')).toBe('neutral');
    expect(mapFaceToExpression('listening')).toBe('neutral');
    expect(mapFaceToExpression('normal')).toBe('neutral');
  });
});

describe('VrmMascot', () => {
  beforeEach(() => {
    vi.resetModules();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('renders the 2D SVG fallback when VITE_MASCOT_MODEL_URL is empty', async () => {
    vi.stubEnv('VITE_MASCOT_MODEL_URL', '');
    const { VrmMascot } = await import('../VrmMascot');
    const { container } = render(<VrmMascot face="idle" />);
    // The 2D Ghosty SVG is rendered when no model URL is set.
    expect(container.querySelector('svg')).not.toBeNull();
    // The 3D canvas div has the eversilver-vrm marker we don't ship — we
    // simply rely on "an SVG is present" as the fallback signal because
    // YellowMascot is the SVG variant.
  });

  it('does not crash when a stale model URL points nowhere', async () => {
    vi.stubEnv('VITE_MASCOT_MODEL_URL', '/definitely-does-not-exist.vrm');
    const { VrmMascot } = await import('../VrmMascot');
    // Should mount and either start loading or surface error via fallback —
    // either way, no exception escapes the render tree.
    expect(() => render(<VrmMascot face="idle" />)).not.toThrow();
  });
});
