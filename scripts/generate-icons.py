"""
Eversilver Icon Generator

Takes logo-source.png and generates the full Tauri/Windows/macOS/Linux icon set.
Run: python scripts/generate-icons.py
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Installing Pillow...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "Pillow"])
    from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "logo-source.png"
ICON_DIR = REPO_ROOT / "app" / "src-tauri" / "icons"

# (filename, size) — Tauri convention
PNG_TARGETS: list[tuple[str, int]] = [
    ("32x32.png", 32),
    ("128x128.png", 128),
    ("128x128@2x.png", 256),
    ("icon.png", 512),
    # Windows Store square logos
    ("Square30x30Logo.png", 30),
    ("Square44x44Logo.png", 44),
    ("Square71x71Logo.png", 71),
    ("Square89x89Logo.png", 89),
    ("Square107x107Logo.png", 107),
    ("Square142x142Logo.png", 142),
    ("Square150x150Logo.png", 150),
    ("Square284x284Logo.png", 284),
    ("Square310x310Logo.png", 310),
    ("StoreLogo.png", 50),
]

# .ico contains multiple resolutions in one file
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def main() -> int:
    if not SOURCE.exists():
        print(f"ERROR: source image not found at {SOURCE}")
        print("Save your logo to that path first, then re-run.")
        return 1

    ICON_DIR.mkdir(parents=True, exist_ok=True)
    src = Image.open(SOURCE).convert("RGBA")
    print(f"Source: {src.size[0]}x{src.size[1]} {src.mode}")

    # If source isn't square, center-pad to square first
    if src.size[0] != src.size[1]:
        side = max(src.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        offset = ((side - src.size[0]) // 2, (side - src.size[1]) // 2)
        square.paste(src, offset)
        src = square
        print(f"Squared to: {src.size[0]}x{src.size[1]}")

    # PNG variants
    for filename, size in PNG_TARGETS:
        out = ICON_DIR / filename
        resized = src.resize((size, size), Image.LANCZOS)
        resized.save(out, "PNG", optimize=True)
        print(f"  wrote {filename:32s} {size:4d}x{size}")

    # ICO (Windows)
    ico_images = [src.resize((s, s), Image.LANCZOS) for s in ICO_SIZES]
    ico_path = ICON_DIR / "icon.ico"
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=ico_images[1:],
    )
    print(f"  wrote icon.ico                       multi-res {ICO_SIZES}")

    # ICNS (macOS) — Pillow supports writing .icns since 9.x
    try:
        icns_path = ICON_DIR / "icon.icns"
        # Pillow needs specific power-of-two sizes for ICNS
        icns_src = src.resize((1024, 1024), Image.LANCZOS)
        icns_src.save(icns_path, format="ICNS")
        print(f"  wrote icon.icns                      1024x1024")
    except Exception as e:
        print(f"  WARN: could not write icon.icns ({e}); macOS build may need manual icon")

    # Also drop a top-level logo.png at repo root for README/usage
    src.resize((512, 512), Image.LANCZOS).save(REPO_ROOT / "logo.png", "PNG", optimize=True)
    print(f"  wrote logo.png (repo root)           512x512")

    print(f"\nGenerated {len(PNG_TARGETS) + 2} icon files in {ICON_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
