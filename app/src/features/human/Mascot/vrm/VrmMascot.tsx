/**
 * VrmMascot
 *
 * Renders a `.vrm` (VRoid / Mixamo-style) or `.glb` 3D character in place of
 * the 2D Ghosty SVG when `VITE_MASCOT_MODEL_URL` is set. Falls back to the
 * SVG mascot when the model fails to load.
 *
 * Drop a `.vrm` file at `app/public/mascot.vrm` and add to `.env`:
 *
 *     VITE_MASCOT_MODEL_URL=/mascot.vrm
 *
 * The component maps the existing `MascotFace` state machine to VRM
 * expressions so the rest of the codebase doesn't need to know which
 * renderer is active.
 */
import { Suspense, useEffect, useRef, useState } from 'react';

import { YellowMascot, type YellowMascotProps } from '../YellowMascot';
import type { MascotFace } from '../Ghosty';
import { loadVrmModel, type LoadedVrm, mapFaceToExpression } from './vrmLoader';

export interface VrmMascotProps extends Pick<YellowMascotProps, 'face' | 'arm' | 'size'> {
  /** Override the model URL (default reads from VITE_MASCOT_MODEL_URL). */
  modelUrl?: string;
  /** Camera distance — tune per model. */
  cameraDistance?: number;
  /** Background color for the canvas (transparent by default). */
  background?: string;
  /** Active mouth shape (visemes A/E/I/O/U). Maps to VRM viseme expressions. */
  viseme?: 'A' | 'E' | 'I' | 'O' | 'U' | null;
}

const DEFAULT_MODEL_URL = (import.meta.env.VITE_MASCOT_MODEL_URL as string | undefined) ?? '';

export function VrmMascot({
  face = 'idle',
  arm: _arm,
  size = '100%',
  modelUrl = DEFAULT_MODEL_URL,
  cameraDistance = 1.4,
  background = 'transparent',
  viseme,
}: VrmMascotProps) {
  // If no model URL is configured, render the SVG fallback. The VRM bundle
  // (three.js + three-vrm) is heavy — we keep it lazy so users who never set
  // a model URL never pay the kilobytes.
  if (!modelUrl) {
    return <YellowMascot face={face} />;
  }
  return (
    <Suspense fallback={<YellowMascot face={face} />}>
      <VrmCanvas
        face={face}
        modelUrl={modelUrl}
        cameraDistance={cameraDistance}
        background={background}
        viseme={viseme}
        size={size}
      />
    </Suspense>
  );
}

// Internal canvas + scene component — declared separately so the import of
// react-three-fiber + three-vrm only runs after VITE_MASCOT_MODEL_URL is set.
function VrmCanvas({
  face,
  modelUrl,
  cameraDistance,
  background,
  viseme,
  size,
}: Required<Pick<VrmMascotProps, 'face' | 'modelUrl' | 'cameraDistance' | 'background'>> & {
  viseme: VrmMascotProps['viseme'];
  size: VrmMascotProps['size'];
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<LoadedVrm | null>(null);

  useEffect(() => {
    let cancelled = false;
    let cleanup: (() => void) | null = null;

    const container = containerRef.current;
    if (!container) return;

    loadVrmModel({ container, modelUrl, cameraDistance, background })
      .then(result => {
        if (cancelled) {
          result.dispose();
          return;
        }
        setLoaded(result);
        cleanup = result.dispose;
      })
      .catch(err => {
        if (!cancelled) {
          console.error('[VrmMascot] failed to load model:', err);
          setError(err instanceof Error ? err.message : String(err));
        }
      });

    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [modelUrl, cameraDistance, background]);

  // Drive expressions from the face state machine.
  useEffect(() => {
    if (!loaded) return;
    loaded.setFace(mapFaceToExpression(face as MascotFace));
  }, [face, loaded]);

  useEffect(() => {
    if (!loaded) return;
    loaded.setViseme(viseme ?? null);
  }, [viseme, loaded]);

  if (error) {
    return <YellowMascot face={face} />;
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: size,
        height: size,
        display: 'block',
        background,
      }}
    />
  );
}
