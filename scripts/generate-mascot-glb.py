"""
Procedural Eversilver mascot generator.

Builds a stylized "moonlight spirit" child silhouette from primitive geometry
and exports it as `app/public/mascot.glb`. Drop-in placeholder for the user
who hasn't sourced or commissioned a real VRoid avatar yet.

Design intent:
- White-haired, white-eyed child silhouette to match the cosmic logo aesthetic
- Pure silvery-white PBR material so it reads on dark Eversilver chrome
- Child-friendly proportions (head ~40% of body height, oversized features)
- Minimalist — implied form, no anatomical detail
- Lightweight (~50 KB GLB) so it streams instantly

To replace with a real model:
  1. Get a `.vrm` or `.glb` from VRoid Studio, Ready Player Me, Mixamo, or
     commission one on Fiverr.
  2. Drop it at `app/public/mascot.vrm` (or `.glb`)
  3. Set VITE_MASCOT_MODEL_URL=/mascot.vrm in your .env
  4. Delete this script if you don't want the placeholder anymore.

Run: python scripts/generate-mascot-glb.py
"""
from __future__ import annotations
import math
from pathlib import Path

import numpy as np
import trimesh
from trimesh.creation import box, cylinder, icosphere, uv_sphere

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "app" / "public" / "mascot.glb"

# Silvery / moonlit PBR material — matches the Eversilver palette.
BODY_COLOR = (0.78, 0.81, 0.90, 1.0)   # cool silver
HAIR_COLOR = (0.96, 0.97, 1.00, 1.0)   # near-white
EYE_COLOR = (1.0, 1.0, 1.0, 1.0)        # pure white, emissive
DARK_COLOR = (0.06, 0.07, 0.10, 1.0)   # subtle shadow accents


def make_material(rgba: tuple[float, float, float, float],
                  *,
                  metallic: float = 0.1,
                  roughness: float = 0.4,
                  emissive: tuple[float, float, float] | None = None
                  ) -> trimesh.visual.material.PBRMaterial:
    mat = trimesh.visual.material.PBRMaterial(
        baseColorFactor=rgba,
        metallicFactor=metallic,
        roughnessFactor=roughness,
    )
    if emissive is not None:
        mat.emissiveFactor = emissive
    return mat


def paint(mesh: trimesh.Trimesh,
          material: trimesh.visual.material.PBRMaterial
          ) -> trimesh.Trimesh:
    # Use vertex colors so the GLB exporter actually attaches the color data
    # — trimesh's TextureVisuals path skips PBR factors on primitive geometry.
    rgba = (np.array(material.baseColorFactor) * 255).astype(np.uint8)
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=rgba)
    return mesh


def translate(mesh: trimesh.Trimesh, x: float = 0, y: float = 0, z: float = 0) -> trimesh.Trimesh:
    mesh.apply_translation([x, y, z])
    return mesh


def scale(mesh: trimesh.Trimesh, sx: float, sy: float, sz: float) -> trimesh.Trimesh:
    mesh.apply_transform(trimesh.transformations.scale_matrix(1, np.zeros(3), None))
    mesh.apply_transform(np.diag([sx, sy, sz, 1.0]))
    return mesh


def rotate(mesh: trimesh.Trimesh, axis: tuple[float, float, float], angle_deg: float) -> trimesh.Trimesh:
    rot = trimesh.transformations.rotation_matrix(math.radians(angle_deg), axis)
    mesh.apply_transform(rot)
    return mesh


def build_mascot() -> trimesh.Scene:
    scene = trimesh.Scene()
    body_mat = make_material(BODY_COLOR, metallic=0.0, roughness=0.5)
    hair_mat = make_material(HAIR_COLOR, metallic=0.0, roughness=0.3,
                              emissive=(0.05, 0.06, 0.10))
    eye_mat = make_material(EYE_COLOR, metallic=0.0, roughness=0.1,
                             emissive=(0.7, 0.75, 0.85))
    accent_mat = make_material(DARK_COLOR, metallic=0.0, roughness=0.6)

    # ── Body (tapered torso) ────────────────────────────────────────────────
    torso = uv_sphere(radius=0.28, count=[32, 24])
    torso.apply_transform(np.diag([1.0, 1.0, 0.7, 1.0]))  # flatten depth
    torso.apply_transform(np.diag([0.85, 1.2, 1.0, 1.0]))  # narrow + tall
    translate(torso, y=0.55)
    scene.add_geometry(paint(torso, body_mat), node_name="torso")

    # ── Head (sphere, oversized for child proportions) ──────────────────────
    head = uv_sphere(radius=0.34, count=[40, 28])
    translate(head, y=1.05)
    scene.add_geometry(paint(head, body_mat), node_name="head")

    # ── Hair (slightly larger sphere over the head; the silver head fills
    #         the lower hemisphere visually so it reads as a hair cap) ──────
    hair_cap = uv_sphere(radius=0.355, count=[40, 28])
    # squash the lower hemisphere so it does not poke through the chin
    hair_cap.apply_transform(np.diag([1.0, 1.05, 1.0, 1.0]))
    translate(hair_cap, y=1.08)
    scene.add_geometry(paint(hair_cap, hair_mat), node_name="hair_cap")

    # forehead tuft (small angled triangular sliver)
    bangs = uv_sphere(radius=0.18, count=[20, 14])
    bangs.apply_transform(np.diag([1.3, 0.35, 0.8, 1.0]))
    translate(bangs, y=1.15, z=0.27)
    scene.add_geometry(paint(bangs, hair_mat), node_name="bangs")

    # twin side locks
    for side in (-1, 1):
        lock = uv_sphere(radius=0.10, count=[16, 12])
        lock.apply_transform(np.diag([0.7, 2.0, 0.7, 1.0]))
        translate(lock, x=side * 0.27, y=0.85, z=0.05)
        scene.add_geometry(paint(lock, hair_mat), node_name=f"sidelock_{side}")

    # ── Eyes (two flat white discs, slight emission for glow) ───────────────
    for side in (-1, 1):
        eye = uv_sphere(radius=0.08, count=[18, 14])
        eye.apply_transform(np.diag([1.0, 1.1, 0.5, 1.0]))
        translate(eye, x=side * 0.13, y=1.02, z=0.30)
        scene.add_geometry(paint(eye, eye_mat), node_name=f"eye_{side}")

    # ── Arms (short slim cylinders, slightly inset to torso) ────────────────
    for side in (-1, 1):
        arm = cylinder(radius=0.07, height=0.45, sections=18)
        rotate(arm, axis=(0, 0, 1), angle_deg=side * 18)
        translate(arm, x=side * 0.30, y=0.55)
        scene.add_geometry(paint(arm, body_mat), node_name=f"arm_{side}")
        # hand
        hand = uv_sphere(radius=0.085, count=[14, 12])
        translate(hand, x=side * 0.40, y=0.32)
        scene.add_geometry(paint(hand, body_mat), node_name=f"hand_{side}")

    # ── Legs ────────────────────────────────────────────────────────────────
    for side in (-1, 1):
        leg = cylinder(radius=0.085, height=0.45, sections=20)
        translate(leg, x=side * 0.12, y=0.06)
        scene.add_geometry(paint(leg, body_mat), node_name=f"leg_{side}")
        foot = uv_sphere(radius=0.10, count=[14, 12])
        foot.apply_transform(np.diag([1.0, 0.5, 1.4, 1.0]))
        translate(foot, x=side * 0.12, y=-0.15, z=0.05)
        scene.add_geometry(paint(foot, accent_mat), node_name=f"foot_{side}")

    # ── Ground ring (subtle cosmic halo at feet, optional accent) ───────────
    halo = trimesh.creation.annulus(r_min=0.25, r_max=0.32, height=0.005,
                                     sections=48)
    rotate(halo, axis=(1, 0, 0), angle_deg=90)
    translate(halo, y=-0.20)
    halo_mat = make_material((0.85, 0.88, 0.95, 0.45),
                              metallic=0.0, roughness=0.6,
                              emissive=(0.25, 0.27, 0.32))
    scene.add_geometry(paint(halo, halo_mat), node_name="halo")

    return scene


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    scene = build_mascot()
    glb_bytes = scene.export(file_type="glb")
    OUT_PATH.write_bytes(glb_bytes)
    size_kb = len(glb_bytes) / 1024
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
