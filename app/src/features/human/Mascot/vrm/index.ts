/**
 * 3D mascot module.
 *
 * Renders a `.vrm` or `.glb` character in place of the 2D Ghosty SVG when
 * `VITE_MASCOT_MODEL_URL` is set. Lazy-loaded so the three.js dependency
 * never enters the bundle for users who haven't configured a model.
 */
export { VrmMascot } from './VrmMascot';
export type { VrmMascotProps } from './VrmMascot';
export { mapFaceToExpression, type MascotExpression } from './vrmLoader';
