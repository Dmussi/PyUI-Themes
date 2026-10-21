#!/usr/bin/env python3
"""Turn a built NextUI Style theme into a recolourable one.

Usage: python3 make_accent_templates.py <stock SPRUCE dir> <font.ttf> <theme dir>

For every resolution, the skin is rendered three times with probe colours
(accent black/white, selected-text black/white). Files that differ between the
probes depend on the accent; for those we solve, per pixel, the premultiplied
colour as  c0 + k_accent*ACCENT/255 + k_seltext*SELTEXT/255  and store it as a
small palette-indexed template for accent_engine.py to recolour on the device.
"""
import json, os, shutil, struct, sys, tempfile, zlib
import numpy as np
from PIL import Image

STOCK, FONT, THEME = sys.argv[1], sys.argv[2], sys.argv[3]
sys.argv = [sys.argv[0]]  # build_theme must not see our args
import build_theme as bt  # noqa: E402

bt.STOCK, bt.FONT_SRC = STOCK, FONT


REAL_MIDTONE = bt.midtone
MIDTONE_FILES = ["bg-list-l.png"]   # drawn in midtone(accent); the engine passes that colour in


def set_probe(acc, sel, probing=True):
    bt.ACCENT = acc + (255,)
    bt.SEL_TEXT = sel + (255,)
    # while probing, midtone() must pass the probe colour straight through so the
    # template stays linear in it; the engine applies midtone() itself at recolour time
    bt.midtone = (lambda c, target=0.18: tuple(c[:3]) + (255,)) if probing else REAL_MIDTONE


def render_skin(dest, W, H):
    base = (W, H) == (640, 480)
    skin = "skin" if base else f"skin_{W}x{H}"
    stock_skin = os.path.join(STOCK, skin if os.path.isdir(os.path.join(STOCK, skin)) else "skin")
    bt.build_skin(dest, W, H, stock_skin)
    return skin


def premult(path):
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float64)
    alpha = a[..., 3:4]
    return a[..., :3] * alpha / 255.0, a[..., 3]


def make_template(p0, pa, ps):
    c0, al0 = premult(p0)
    ca, ala = premult(pa)
    cs, als = premult(ps)
    if max(np.abs(al0 - ala).max(), np.abs(al0 - als).max()) > 2:
        raise ValueError("alpha depends on the accent")
    ka = (ca - c0).mean(axis=2)   # white probe: same coefficient on every channel
    ks = (cs - c0).mean(axis=2)
    h, w = al0.shape
    # quantise; coarsen until the palette fits in 256 entries
    for step in (1, 2, 3, 4, 6, 8, 12, 16):
        q = lambda v: np.clip(np.round(v / step) * step, 0, 255).astype(np.uint8)
        tup = np.stack([np.clip(np.round(al0), 0, 255).astype(np.uint8) if step == 1 else q(al0),
                        q(c0[..., 0]), q(c0[..., 1]), q(c0[..., 2]), q(ka), q(ks)], axis=-1).reshape(-1, 6)
        tup[tup[:, 0] == 0] = 0                       # all fully transparent pixels share one entry
        uniq, inv = np.unique(tup, axis=0, return_inverse=True)
        if len(uniq) <= 256:
            break
    else:
        raise ValueError("too many colours for a template")
    header = b"NUTP" + struct.pack("<HHH", w, h, len(uniq)) + uniq.astype(np.uint8).tobytes()
    return header + zlib.compress(inv.astype(np.uint8).reshape(-1).tobytes(), 9), step


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "accent_app"))
    import accent_engine as eng

    manifest = {"templates": {}, "midtone": MIDTONE_FILES}
    tmp = tempfile.mkdtemp()
    black, white = (0, 0, 0), (255, 255, 255)
    for W, H in bt.RESOLUTIONS:
        dirs = {}
        for key, acc, sel in (("p0", black, black), ("pa", white, black), ("ps", black, white)):
            set_probe(acc, sel)
            dirs[key] = os.path.join(tmp, key, f"{W}x{H}")
            skin = render_skin(dirs[key], W, H)
        names = []
        for f in sorted(os.listdir(dirs["p0"])):
            b = [open(os.path.join(dirs[k], f), "rb").read() for k in ("p0", "pa", "ps")]
            if b[0] != b[1] or b[0] != b[2]:
                names.append(f)
        os.makedirs(os.path.join(THEME, "accent", skin), exist_ok=True)
        steps = []
        for f in names:
            data, step = make_template(*(os.path.join(dirs[k], f) for k in ("p0", "pa", "ps")))
            steps.append(step)
            with open(os.path.join(THEME, "accent", skin, f + ".tpl"), "wb") as fh:
                fh.write(data)
        manifest["templates"][skin] = names
        print(f"{W}x{H}: {len(names)} accent images, quantise step max {max(steps)}")

    with open(os.path.join(THEME, "accent", "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    # --- verify: engine output vs. the real builder, for several accents ---
    worst = 0
    for hexv in ("#9B2257", "#F5C518", "#2F7DE1", "#3DBE6B", "#FFFFFF", "#123456", "#FF00FF"):
        acc = eng.parse_hex(hexv)
        sel = eng.selected_text_color(acc)
        set_probe(acc, sel, probing=False)
        for W, H in ((640, 480), (1280, 720)):
            ref = os.path.join(tmp, "ref", hexv[1:], f"{W}x{H}")
            skin = render_skin(ref, W, H)
            for f in manifest["templates"][skin]:
                slot = eng.midtone(acc) if f in MIDTONE_FILES else acc
                png = eng.render_tpl(os.path.join(THEME, "accent", skin, f + ".tpl"), slot, sel)
                got = np.asarray(Image.open(__import__("io").BytesIO(png)).convert("RGBA"), dtype=np.int32)
                exp = np.asarray(Image.open(os.path.join(ref, f)).convert("RGBA"), dtype=np.int32)
                vis = exp[..., 3] > 24                      # colour only matters where visible
                d_rgb = np.abs(got[..., :3] - exp[..., :3])[vis].max() if vis.any() else 0
                d_a = np.abs(got[..., 3] - exp[..., 3]).max()
                worst = max(worst, int(d_rgb), int(d_a))
                if d_rgb > 12 or d_a > 6:
                    print(f"  MISMATCH {hexv} {skin}/{f}: rgb {d_rgb} alpha {d_a}")
    print("verification worst channel error:", worst)
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
