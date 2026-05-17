# 3D Mascot (VRM / GLB)

Swap the 2D Ghosty SVG for a 3D character — a VRoid avatar, a Mixamo rig,
or any `.glb` you have.

## Quick start

1. **Install runtime deps** (only needed once you actually want 3D):

   ```bash
   pnpm --filter eversilver-app add three @pixiv/three-vrm
   pnpm --filter eversilver-app add -D @types/three
   ```

2. **Drop your model** at `app/public/mascot.vrm` (or `.glb`).

3. **Configure** the environment variable in `.env`:

   ```bash
   VITE_MASCOT_MODEL_URL=/mascot.vrm
   ```

4. **Use it** anywhere the Ghosty SVG is used:

   ```tsx
   import { VrmMascot } from './features/human/Mascot/vrm';

   <VrmMascot face={mascotFace} viseme={currentViseme} />
   ```

   When `VITE_MASCOT_MODEL_URL` is empty, `<VrmMascot>` automatically falls
   back to the SVG `<YellowMascot>` — so it is safe to use everywhere.

## Where to get a model

| Source | Format | Cost | Notes |
|---|---|---|---|
| [VRoid Studio](https://vroid.com/en/studio) | `.vrm` | Free | Best for "child with white hair / white eyes" — anime-style with full expressions |
| [Ready Player Me](https://readyplayer.me/) | `.glb` | Free | Web creator, exports avatars |
| [Mixamo](https://www.mixamo.com/) | `.fbx` → convert | Free | Need to convert to `.glb` with Blender |
| [Meshy.ai](https://www.meshy.ai/) | `.glb` | Free tier | AI-generated 3D |
| Commission a 3D artist | any | $50–$300 | Fiverr / Upwork — ask for VRM with VRM1.0 expressions |

## State → expression mapping

The component maps the existing `MascotFace` state machine to VRM expression
presets, so the agent's "I'm thinking" or "I'm speaking" signals drive the
character automatically:

| MascotFace | VRM expression |
|---|---|
| `sleep` | `relaxed` |
| `happy` | `happy` |
| `thinking` / `confused` | `sad` |
| `speaking` | `neutral` (drive `viseme` prop for lip-sync) |
| `listening` / `idle` / `normal` | `neutral` |

## Lip-sync

Pass the active viseme to drive mouth shapes:

```tsx
<VrmMascot face="speaking" viseme="A" />
```

The mapping is:

| Viseme | VRM expression |
|---|---|
| `A` | `aa` (open mouth) |
| `E` | `ee` (smile) |
| `I` | `ih` (slight) |
| `O` | `oh` (round) |
| `U` | `ou` (puckered) |

VRoid avatars include all five by default. Custom GLBs need blendshapes named
`aa`, `ee`, `ih`, `oh`, `ou`.

## Performance

- The three.js + three-vrm bundle is **lazy-loaded** — only fetched when
  `VITE_MASCOT_MODEL_URL` is non-empty.
- Auto-blink runs at 3-second intervals on the render loop.
- `ResizeObserver` keeps the canvas matched to the container.
- `VRMUtils.removeUnnecessaryJoints` runs at load time to shrink draw call count.
- The renderer uses `alpha: true` when `background: 'transparent'` (default)
  so the canvas composites cleanly over any UI.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Falls back to SVG every time | Check the network tab — 404 on the model URL? Path wrong in `.env`? |
| Model loads but expressions don't change | Your VRM doesn't include the standard expression presets. Re-export from VRoid Studio with "Default expressions" enabled. |
| Model is rotated wrong | Some VRMs face +Z, others -Z. Tweak `vrmInstance.scene.rotation.y` in `vrmLoader.ts`. |
| Lip-sync silent | Confirm the model has `aa`/`ee`/`ih`/`oh`/`ou` blendshapes — Mixamo rigs usually don't. |
