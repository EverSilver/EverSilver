/**
 * VRM / GLB loader for the Eversilver mascot.
 *
 * All three.js + three-vrm code is dynamically imported so the heavy
 * dependency only loads when a model URL is actually configured.
 *
 * Install deps before use:
 *   pnpm --filter eversilver-app add three @pixiv/three-vrm
 *   pnpm --filter eversilver-app add -D @types/three
 */
import type { MascotFace } from '../Ghosty';

export type MascotExpression =
  | 'neutral'
  | 'happy'
  | 'sad'
  | 'angry'
  | 'surprised'
  | 'relaxed'
  | 'blink';

export interface LoadVrmArgs {
  container: HTMLElement;
  modelUrl: string;
  cameraDistance: number;
  background: string;
}

export interface LoadedVrm {
  setFace: (expr: MascotExpression) => void;
  setViseme: (viseme: 'A' | 'E' | 'I' | 'O' | 'U' | null) => void;
  dispose: () => void;
}

export function mapFaceToExpression(face: MascotFace): MascotExpression {
  switch (face) {
    case 'sleep':
      return 'relaxed';
    case 'happy':
      return 'happy';
    case 'thinking':
    case 'confused':
      return 'sad';
    case 'speaking':
    case 'listening':
    case 'idle':
    case 'normal':
    default:
      return 'neutral';
  }
}

/**
 * Loads a `.vrm` or `.glb` into a Three.js scene mounted on the provided
 * container. Returns a controller that exposes face + viseme setters and a
 * disposer for cleanup.
 */
export async function loadVrmModel(args: LoadVrmArgs): Promise<LoadedVrm> {
  // Dynamic imports so the heavy bundle is not pulled in unless used.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const THREE: any = await import(/* @vite-ignore */ 'three');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const gltfMod: any = await import(/* @vite-ignore */ 'three/examples/jsm/loaders/GLTFLoader.js');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const vrm: any = await import(/* @vite-ignore */ '@pixiv/three-vrm');

  const { GLTFLoader } = gltfMod;
  const { VRMLoaderPlugin, VRMUtils } = vrm;

  const { container, modelUrl, cameraDistance, background } = args;
  const width = container.clientWidth || 320;
  const height = container.clientHeight || 320;

  const scene = new THREE.Scene();
  if (background && background !== 'transparent') {
    scene.background = new THREE.Color(background);
  }

  const camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 20);
  camera.position.set(0, 1.35, cameraDistance);

  const renderer = new THREE.WebGLRenderer({
    alpha: background === 'transparent',
    antialias: true,
  });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(width, height);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  // Lighting tuned to look good on white-haired characters with subtle rim light.
  const key = new THREE.DirectionalLight(0xffffff, 1.2);
  key.position.set(1, 1.5, 1);
  scene.add(key);
  const fill = new THREE.HemisphereLight(0xc0c7e0, 0x1a1d2e, 0.6);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xa0b0e0, 0.4);
  rim.position.set(-1, 1, -1);
  scene.add(rim);

  const loader = new GLTFLoader();
  loader.register((parser: unknown) => new VRMLoaderPlugin(parser));

  const gltf = await loader.loadAsync(modelUrl);
  const vrmInstance = gltf.userData.vrm;

  // GLB without VRM metadata — still renders, just no expressions/viseme.
  const isVrm = Boolean(vrmInstance);

  if (isVrm) {
    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.removeUnnecessaryJoints(gltf.scene);
    vrmInstance.scene.traverse((obj: { frustumCulled?: boolean }) => {
      obj.frustumCulled = false;
    });
    // VRM models commonly face -Z; rotate to face the camera.
    vrmInstance.scene.rotation.y = Math.PI;
    scene.add(vrmInstance.scene);
  } else {
    gltf.scene.rotation.y = Math.PI;
    scene.add(gltf.scene);
  }

  let currentExpression: MascotExpression = 'neutral';
  // Tracked for future external querying; intentionally not read inside the loader.
  let _currentViseme: 'A' | 'E' | 'I' | 'O' | 'U' | null = null;

  const setExpressionWeight = (name: string, weight: number) => {
    if (!isVrm || !vrmInstance.expressionManager) return;
    try {
      vrmInstance.expressionManager.setValue(name, weight);
    } catch {
      /* expression not present in this model */
    }
  };

  const clearExpressions = () => {
    for (const name of ['neutral', 'happy', 'sad', 'angry', 'surprised', 'relaxed']) {
      setExpressionWeight(name, 0);
    }
  };

  const clearVisemes = () => {
    for (const name of ['aa', 'ee', 'ih', 'oh', 'ou']) {
      setExpressionWeight(name, 0);
    }
  };

  const applyExpression = (expr: MascotExpression) => {
    clearExpressions();
    setExpressionWeight(expr === 'blink' ? 'blink' : expr, 1);
  };

  const applyViseme = (viseme: typeof _currentViseme) => {
    clearVisemes();
    if (!viseme) return;
    const map: Record<NonNullable<typeof viseme>, string> = {
      A: 'aa',
      E: 'ee',
      I: 'ih',
      O: 'oh',
      U: 'ou',
    };
    setExpressionWeight(map[viseme], 1);
  };

  applyExpression(currentExpression);

  // Animation loop — bob + idle blink + tick the VRM expression manager.
  const clock = new THREE.Clock();
  let blinkPhase = 0;
  let rafId = 0;
  const tick = () => {
    rafId = window.requestAnimationFrame(tick);
    const dt = clock.getDelta();
    blinkPhase += dt;
    // Auto-blink every 3 seconds.
    if (blinkPhase > 3) {
      blinkPhase = 0;
      setExpressionWeight('blink', 1);
      setTimeout(() => setExpressionWeight('blink', 0), 120);
    }
    if (isVrm) vrmInstance.update(dt);
    renderer.render(scene, camera);
  };
  tick();

  // Resize handler — keep canvas matching container size.
  const ro = new ResizeObserver(() => {
    const w = container.clientWidth || 320;
    const h = container.clientHeight || 320;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  });
  ro.observe(container);

  return {
    setFace: (expr: MascotExpression) => {
      currentExpression = expr;
      applyExpression(expr);
    },
    setViseme: viseme => {
      _currentViseme = viseme;
      applyViseme(viseme);
    },
    dispose: () => {
      window.cancelAnimationFrame(rafId);
      ro.disconnect();
      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
      if (isVrm) {
        VRMUtils.deepDispose(vrmInstance.scene);
      } else {
        gltf.scene.traverse(
          (obj: {
            geometry?: { dispose?: () => void };
            material?: { dispose?: () => void } | Array<{ dispose?: () => void }>;
          }) => {
            obj.geometry?.dispose?.();
            if (Array.isArray(obj.material)) {
              obj.material.forEach(m => m?.dispose?.());
            } else {
              obj.material?.dispose?.();
            }
          }
        );
      }
    },
  };
}
