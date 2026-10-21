#!/usr/bin/env python3
"""Generate a NextUI-style theme for spruceOS (PyUI).

Usage: python3 build_theme.py <stock SPRUCE theme dir> <font.ttf> <out dir>
"""
import json, os, shutil, sys
from PIL import Image, ImageDraw, ImageFont, ImageChops

if __name__ == "__main__" or len(sys.argv) > 3:
    STOCK, FONT_SRC, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
else:  # imported as a module (e.g. by make_accent_templates.py); caller sets these
    STOCK = FONT_SRC = OUT = None
VARIANT = sys.argv[4] if len(sys.argv) > 4 else "White"
ACCENT_HEX = sys.argv[5] if len(sys.argv) > 5 else "#FFFFFF"
FONT_NAME = "nextui.ttf"

# NextUI-ish palette
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
PILL = (34, 36, 40, 255)        # dark status / hint pill
PANEL = (24, 24, 26, 245)       # popup panels
GRAY = (130, 130, 130, 255)     # unselected icons
RED = (230, 70, 70, 255)
ACCENT = tuple(int(ACCENT_HEX[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
# black text on light accents, white text on dark ones
_lum = 0.2126 * ACCENT[0] + 0.7152 * ACCENT[1] + 0.0722 * ACCENT[2]
SEL_TEXT_HEX = "#000000" if _lum > 150 else "#FFFFFF"
SEL_TEXT = BLACK if _lum > 150 else WHITE

RESOLUTIONS = [(640, 480), (720, 480), (720, 720), (752, 560),
               (960, 720), (1024, 768), (1280, 720), (480, 800)]

SS = 4  # supersampling for smooth edges


def font(px):
    return ImageFont.truetype(FONT_SRC, max(8, px))


def canvas(w, h, fill=(0, 0, 0, 0)):
    return Image.new("RGBA", (w * SS, h * SS), fill)


def done(im, w, h):
    # box filter = exact pixel-coverage averaging of the supersampled drawing. Unlike
    # LANCZOS it never overshoots, so every pixel stays a linear mix of the accent,
    # which lets accent_engine.py recolour these images exactly on the device.
    return im.resize((w, h), Image.BOX)


def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([v * SS for v in box], radius=r * SS, fill=fill,
                        outline=outline, width=width * SS)


def _rel_lum(c):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def midtone(c, target=0.18):
    """Darken a light accent to mid luminance, where both black and white text read (~4.5:1).

    Used for the large highlight, which spruce also uses as the keyboard's text box:
    the keyboard draws white text on it, detailed lists draw black/white text on it."""
    c = tuple(c[:3])
    if _rel_lum(c) <= target:
        return c + (255,)
    lo, hi = 0.0, 1.0
    for _ in range(24):
        m = (lo + hi) / 2
        if _rel_lum(tuple(v * m for v in c)) < target:
            lo = m
        else:
            hi = m
    return tuple(int(round(v * lo)) for v in c) + (255,)


def tab(w, h, color, x0=0, x1=None, cw=None, ch=None):
    """Highlight with a rounded left end and a square right end.

    spruce reuses one highlight image across screens: Settings stretches it to the
    full width, while the system/game lists cut it off where the icon/box art starts.
    A square right end looks the same in both cases."""
    cw = cw or w
    ch = ch or h
    x1 = cw if x1 is None else x1
    im = canvas(cw, ch)
    d = ImageDraw.Draw(im)
    y0 = (ch - h) / 2
    rrect(d, (x0, y0, x1, y0 + h), h / 2, fill=color)
    d.rectangle([(x1 - h) * SS, y0 * SS, x1 * SS, (y0 + h) * SS], fill=color)
    return done(im, cw, ch)


def pill(w, h, color, x0=0, x1=None, cw=None, ch=None):
    cw = cw or w
    ch = ch or h
    x1 = w if x1 is None else x1
    im = canvas(cw, ch)
    d = ImageDraw.Draw(im)
    y0 = (ch - h) / 2
    rrect(d, (x0, y0, x1, y0 + h), h / 2, fill=color)
    return done(im, cw, ch)


def text_w(f, s):
    b = f.getbbox(s)
    return b[2] - b[0]


def draw_text_center_y(d, x, cy, s, f, fill):
    """Draw text (in SS space) vertically centred on cy using cap height."""
    asc = f.getbbox("H")
    th = asc[3] - asc[1]
    d.text((x, cy - th / 2 - asc[1]), s, font=f, fill=fill)


def battery(w, h, frac, charging=False):
    im = canvas(w, h)
    d = ImageDraw.Draw(im)
    nub = max(2, round(w * 0.08))
    body = (0, 0, w - nub - 1, h - 1)
    stroke = max(2, round(h * 0.12))
    rrect(d, body, h * 0.22, outline=WHITE, width=stroke)
    d.rectangle([(w - nub) * SS, h * 0.3 * SS, w * SS, h * 0.7 * SS], fill=WHITE)
    pad = stroke * 2
    inner_w = (w - nub - 1) - pad * 2
    color = RED if frac <= 0.2 and not charging else WHITE
    if frac > 0:
        rrect(d, (pad, pad, pad + max(2, inner_w * frac), h - 1 - pad),
              h * 0.08, fill=color)
    if charging:
        cx, cy = (w - nub) / 2, h / 2
        s = h * 0.42
        bolt = [(cx + s * .15, cy - s), (cx - s * .55, cy + s * .12), (cx - s * .02, cy + s * .12),
                (cx - s * .15, cy + s), (cx + s * .55, cy - s * .12), (cx + s * .02, cy - s * .12)]
        d.polygon([(x * SS, y * SS) for x, y in bolt], fill=BLACK if frac > 0.5 else WHITE,
                  outline=WHITE if frac > 0.5 else None)
    return done(im, w, h)


def volume_icon(w, h, level):
    """Dark pill: speaker glyph + 20-step level bar."""
    gap = 8  # keep clear of the battery pill
    im = canvas(w, h)
    d = ImageDraw.Draw(im)
    rrect(d, (0, 0, w - gap, h), h / 2, fill=PILL)
    w -= gap
    # speaker
    sx, cy, s = h * 0.45, h / 2, h * 0.22
    spk = [(sx, cy - s * .5), (sx + s * .6, cy - s * .5), (sx + s * 1.3, cy - s * 1.1),
           (sx + s * 1.3, cy + s * 1.1), (sx + s * .6, cy + s * .5), (sx, cy + s * .5)]
    d.polygon([(x * SS, y * SS) for x, y in spk], fill=WHITE if level else GRAY)
    if level == 0:
        x0 = sx + s * 1.8
        d.line([(x0 * SS, (cy - s * .6) * SS), ((x0 + s) * SS, (cy + s * .6) * SS)], fill=GRAY, width=int(h * .07 * SS))
        d.line([(x0 * SS, (cy + s * .6) * SS), ((x0 + s) * SS, (cy - s * .6) * SS)], fill=GRAY, width=int(h * .07 * SS))
    # bar
    bx0, bx1 = h * 1.25, w - h * 0.5
    bh = h * 0.16
    rrect(d, (bx0, cy - bh / 2, bx1, cy + bh / 2), bh / 2, fill=(70, 72, 78, 255))
    if level:
        rrect(d, (bx0, cy - bh / 2, bx0 + (bx1 - bx0) * level / 20, cy + bh / 2), bh / 2, fill=ACCENT)
    return done(im, w + gap, h)


def hint_strip(w, h, s, hints, align="right"):
    """One dark pill with NextUI-style [circle letter] LABEL pairs."""
    f_btn = font(round(15 * s * SS))
    f_lbl = font(round(15 * s * SS))
    circ = h * 0.72
    gap_in = 8 * s       # circle -> label
    gap_pair = 16 * s    # between pairs
    padx = (h - circ) / 2
    widths = []
    for key, lbl in hints:
        widths.append(circ + gap_in + text_w(f_lbl, lbl) / SS)
    pw = padx * 2 + sum(widths) + gap_pair * (len(hints) - 1) + 6 * s
    im = canvas(w, h)
    d = ImageDraw.Draw(im)
    x0 = w - pw if align == "right" else 0
    rrect(d, (x0, 0, x0 + pw, h), h / 2, fill=PILL)
    x = x0 + padx
    cy = h / 2
    for (key, lbl), pw_i in zip(hints, widths):
        rrect(d, (x, cy - circ / 2, x + circ, cy + circ / 2), circ / 2, fill=ACCENT)  # accent circle, like NextUI
        kw = text_w(f_btn, key) / SS
        draw_text_center_y(d, (x + (circ - kw) / 2) * SS, cy * SS, key, f_btn, SEL_TEXT)
        draw_text_center_y(d, (x + circ + gap_in) * SS, cy * SS, lbl, f_lbl, WHITE)
        x += pw_i + gap_pair
    return done(im, w, h)


def outline_box(w, h, r, stroke, fill=None):
    im = canvas(w, h)
    d = ImageDraw.Draw(im)
    rrect(d, (stroke / 2, stroke / 2, w - stroke / 2, h - stroke / 2), r, fill=fill,
          outline=ACCENT, width=stroke)
    return done(im, w, h)


def panel(w, h, r, color):
    im = canvas(w, h)
    rrect(ImageDraw.Draw(im), (0, 0, w, h), min(r, h / 2, w / 2), fill=color)
    return done(im, w, h)


def tint(im, color):
    """Keep alpha, replace colour (white silhouette)."""
    im = im.convert("RGBA")
    a = im.getchannel("A")
    solid = Image.new("RGBA", im.size, color)
    solid.putalpha(ImageChops.multiply(a, Image.new("L", im.size, color[3])))
    return solid


SELECTED_HINTS = ("-f.png", "-sel.png", "-f-GREEN.png", "selected", "-s.png")
PANELISH = {"app_loading_bg.png", "background-small.png", "background.1.png", "pop-bg.png",
            "preview-bg.png", "thumb-default.png", "statbg.png", "navbg.png", "barbg.png",
            "menu-sub-bg.png", "bg-gamelist.png", "bg-input.png", "input.png", "save-default.png",
            "bg-button-nor.png", "bg-button-f.png", "btn-OK.png", "btn-OK-f.png", "loading-bg.png",
            "value-frame-n.png", "value-frame-f.png", "num-bg.png", "menu-sub-title-bg.png",
            "bg-btn-01-n.png", "bg-btn-01-f.png", "bg-btn-02-n.png", "bg-btn-02-f.png",
            "bg-btn-nor.png", "bg-btn-sel.png", "bg-btn-shift-active.png", "bg-ra-list-item.png",
            "preview-nameFrame.png", "bg-pop-menu-1.png", "bg-pop-menu-2.png", "bg-pop-menu-3.png",
            "bg-pop-menu-4.png", "menu-5line-bg.png", "menu-6line-bg.png", "menu-bg-6.png",
            "menu-bg-7.png", "loading-progress-left.png", "loading-progress-mid.png",
            "loading-progress-right.png", "list-num.png"}
FULLSCREEN_DIM = {"menu-5line-bg.png", "menu-6line-bg.png", "menu-bg-6.png", "menu-bg-7.png",
                  "app_loading_bg.png", "background-small.png", "background.1.png"}
WHITE_PANELS = {"loading-progress-left.png", "loading-progress-mid.png", "loading-progress-right.png"}
OUTLINED_KEYS = {"bg-btn-sel.png", "bg-btn-01-f.png", "bg-btn-02-f.png", "bg-button-f.png",
                 "btn-OK-f.png", "value-frame-f.png", "bg-btn-shift-active.png"}
DROP = {"grid-game-selected.png"}  # regenerated below


def restyle_stock(src_dir, dst_dir, s):
    """Copy every stock skin image, recoloured to the NextUI look."""
    for f in sorted(os.listdir(src_dir)):
        if not f.endswith(".png") or f in DROP:
            continue
        im = Image.open(os.path.join(src_dir, f)).convert("RGBA")
        w, h = im.size
        if f in PANELISH:
            if f in FULLSCREEN_DIM:
                out = Image.new("RGBA", (w, h), (0, 0, 0, 215))
            elif f in WHITE_PANELS:
                out = panel(w, h, min(w, h) / 2, ACCENT)
            elif f in OUTLINED_KEYS:
                out = outline_box(w, h, min(w, h) / 4, max(2, round(3 * s)), fill=PILL)
            else:
                out = panel(w, h, 14 * s, PANEL if w * h > 20000 else PILL)
        elif w * h <= 1:
            out = im
        elif f.endswith("-n.png") and f.startswith(("ic-", "nav-")):
            out = tint(im, GRAY)
        else:
            out = tint(im, WHITE)
        out.save(os.path.join(dst_dir, f), optimize=True)


def build_skin(skin_dir, W, H, stock_skin):
    s = min(W / 640, H / 480)
    os.makedirs(skin_dir, exist_ok=True)
    restyle_stock(stock_skin, skin_dir, s)
    sv = lambda f, im: im.save(os.path.join(skin_dir, f), optimize=True)

    top_h = round(48 * s)
    bot_h = round(48 * s)
    row = round(54 * s)

    sv("background.png", Image.new("RGBA", (W, H), BLACK))
    sv("background-small.png", Image.new("RGBA", (W, H), BLACK))

    # --- selection pills (row height == pill height, like NextUI) ---
    # ends just before the right-hand image column (spruce crops the pill there),
    # so both ends stay rounded in the system and game lists
    sv("bg-list-s.png", tab(W, row, ACCENT, x0=10))
    # large highlight doubles as the on-screen keyboard's text box: mid-tone so typed text reads
    sv("bg-list-l.png", tab(W, round(90 * s), midtone(ACCENT), x0=10, ch=round(90 * s)))
    pw = round(320 * s)
    sv("bg-list-s2.png", tab(pw, row, ACCENT, x0=4))
    sv("list-item-select-bg-short.png", tab(pw, row, ACCENT, x0=4))

    # --- top bar: transparent, dark status pill on the right ---
    bw, bh = round(34 * s), round(18 * s)
    pad = 14
    tb = canvas(W, top_h)
    ph = round(36 * s)
    x0 = W - 20 - bw - pad
    rrect(ImageDraw.Draw(tb), (x0, (top_h - ph) / 2, W - 6, (top_h + ph) / 2), ph / 2, fill=PILL)
    sv("bg-title.png", done(tb, W, top_h))

    for name, frac in [("power-full-icon.png", 1.0), ("power-80%-icon.png", .8),
                       ("power-50%-icon.png", .5), ("power-20%-icon.png", .2), ("power-0%-icon.png", .05)]:
        sv(name, battery(bw, bh, frac))
    for name, frac in [("ic-power-charge-100%.png", 1.0), ("ic-power-charge-75%.png", .75),
                       ("ic-power-charge-50%.png", .5), ("ic-power-charge-25%.png", .25),
                       ("ic-power-charge-0%.png", .05)]:
        sv(name, battery(bw, bh, frac, charging=True))

    vw, vh = round(150 * s), ph
    for lvl in range(21):
        sv(f"icon-volume-{lvl:02d}.png", volume_icon(vw, vh, lvl))

    # --- bottom bar: transparent; hints baked into the confirm icon ---
    sv("tips-bar-bg.png", Image.new("RGBA", (W, bot_h), (0, 0, 0, 0)))
    hh = round(36 * s)
    # bottom-left: spruce draws the page counter (05/11) in the bottom-right corner
    sv("icon-A-54.png", hint_strip(W - 10 - 1, hh, s, [("B", "BACK"), ("A", "OPEN")], align="left"))
    sv("icon-B-54.png", Image.new("RGBA", (1, 1), (0, 0, 0, 0)))

    # favourite / achievement marks shown inline on game rows: neutral grey reads on any pill
    mk = round(26 * s)
    for name in ("ic-favorite-mark.png", "ic-cheevos-mark.png"):
        src = Image.open(os.path.join(stock_skin, name)).convert("RGBA").resize((mk, mk), Image.LANCZOS)
        sv(name, tint(src, (128, 128, 128, 255)))

    # --- popups ---
    sv("bg-pop-menu-4.png", panel(pw, round(250 * s), 18 * s, PANEL))
    sv("menu-6line-bg.png", panel(pw, round(420 * s), 18 * s, PANEL))

    # --- grid fallbacks (if the user switches view type) ---
    st = max(3, round(4 * s))
    # spruce draws this as the keyboard background (scaled to fit, not stretched): transparent,
    # so the keyboard sits on plain black like NextUI
    sv("bg-grid-s.png", Image.new("RGBA", (round(156 * s), round(176 * s)), (0, 0, 0, 0)))
    sv("bg-game-item-f.png", outline_box(round(154 * s), round(170 * s), 16 * s, st))
    sv("grid-game-selected.png", outline_box(round(140 * s), round(140 * s), 16 * s, st))
    sv("grid-system-selected.png", outline_box(round(140 * s), round(140 * s), 16 * s, st))
    return s




STOCK_EXTRAS = {"recents": "ic-recent-f.png", "favorites": "ic-favorite-f.png",
                "collections": "ic-collection-f.png", "apps": "ic-app-f.png", "settings": "ic-setting-f.png"}


def _best_stock(rel_candidates):
    """Return the largest existing stock image among the theme's resolution folders."""
    best = None
    for d in sorted(os.listdir(STOCK)):
        for rel in rel_candidates:
            p = os.path.join(STOCK, d, rel)
            if os.path.isfile(p):
                im = Image.open(p)
                if best is None or im.size[0] * im.size[1] > best[0]:
                    best = (im.size[0] * im.size[1], p)
                break
    return best[1] if best else None


def stock_icon_on_canvas(path, size):
    """spruce's own full-colour icon, centred on a square canvas, never upscaled much."""
    im = Image.open(path).convert("RGBA")
    box = round(size * 0.85)
    scale = min(box / im.width, box / im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return out


def build_icons(out, W, H, s, base):
    """icons/<sys>.png = spruce's stock colour icon shown on the right for the selected system;
    icons/sel/<sys>.png = blank, so no extra icon is drawn inline beside the name."""
    folder = os.path.join(out, "icons" if base else f"icons_{W}x{H}")
    os.makedirs(os.path.join(folder, "sel"), exist_ok=True)
    size = round(250 * s)
    blank = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    names = sorted(f[:-4] for f in os.listdir(os.path.join(STOCK, "icons")) if f.endswith(".png"))
    for name in names:
        src = _best_stock([f"sel/{name}.png", f"{name}.png"])
        stock_icon_on_canvas(src, size).save(os.path.join(folder, f"{name}.png"), optimize=True)
        blank.save(os.path.join(folder, "sel", f"{name}.png"))
    for name, skin_file in STOCK_EXTRAS.items():
        src = _best_stock([skin_file])
        stock_icon_on_canvas(src, size).save(os.path.join(folder, f"{name}.png"), optimize=True)
        blank.save(os.path.join(folder, "sel", f"{name}.png"))
    stock_app = os.path.join(STOCK, "icons" if base else f"icons_{W}x{H}", "app")
    if os.path.isdir(stock_app):
        shutil.copytree(stock_app, os.path.join(folder, "app"))


def igm_config():
    """spruce in-game menu (RetroArch IGM) styled to match: flat, black, accent highlight."""
    return {
        "name": f"NextUI Style {VARIANT}",
        "colors": {
            "dim_bg": "#000000E6",
            "panel_bg": "#00000000",
            "selection": ACCENT_HEX + "FF",
            "accent": ACCENT_HEX + "FF",
            "title_line": "#FFFFFF33",
            "text": "#FFFFFFFF",
            "text_selected": SEL_TEXT_HEX + "FF",
            "text_title": "#8A8A8AFF",
            "text_shadow": "#00000000",
            "battery": "#FFFFFFFF",
        },
        # no title row (NextUI has none); flat rows, no side bar, no shadows
        "layout": {"accent_bar": False, "shadow": False, "separator_h_px": 0, "title_h_pct": 0.0},
        "font": {"path": FONT_NAME},
        "text": {"title": ""},
    }


def config(W, H, s):
    r = lambda v: round(v * s)
    f = FONT_NAME
    return {
        "name": f"NextUI Style {VARIANT}",
        "author": "Diego Mussi",
        "description": "Black, minimal, pill-highlight list theme in the spirit of NextUI/MinUI. "
                       "Icons restyled from the spruce SPRUCE theme (CC BY-NC 4.0); font M PLUS Rounded 1c (OFL).",
        "batteryPercentage": {"color": "#FFFFFF", "font": f, "size": r(18)},
        "title": {"font": f, "size": r(24), "color": "#FFFFFF"},
        "hint": {"font": f, "size": r(18), "color": "#FFFFFF"},
        "currentpage": {"font": f, "size": r(20), "color": "#FFFFFF"},
        "total": {"font": f, "size": r(20), "color": "#8A8A8A"},
        "grid": {"font": f, "grid1x4": r(24), "grid3x4": r(18), "color": "#8A8A8A", "selectedcolor": "#FFFFFF"},  # tabs + keyboard text: white reads everywhere
        "list": {"font": f, "size": r(28), "color": "#FFFFFF", "selectedcolor": SEL_TEXT_HEX},
        "descListFontSize": r(24),
        "descriptionFontSize": r(18),
        "messageFontSize": r(24),
        "batteryPercentFontSize": r(18),

        # NextUI layout: one flat text list, no icons, no main-menu tabs
        "skipMainMenu": True,
        "showExtrasInSystemSelectMenu": True,
        "mainMenuViewType": "TEXT_ONLY",
        # list on the left, big system icon / box art of the selection on the right
        "systemSelectViewType": "TEXT_AND_IMAGE",
        "gameSelectionViewType": "TEXT_AND_IMAGE",
        "textAndImageListViewMode": "TEXT_LEFT_IMAGE_RIGHT",
        "listGameSelectImgWidth": r(250),
        "listGameSelectImgHeight": r(300),
        "listSystemSelectImgWidth": r(250),
        "listSystemSelectImgHeight": r(300),
        "appMenuViewType": "TEXT_ONLY",
        "useTextForLineHeight": False,
        "scrollRomSelectionText": False,  # spruce scrolls even short names; off keeps rows still
        "recentsEnabled": True,
        "favoritesEnabled": True,
        "collectionsEnabled": True,
        "appsEnabled": True,
        "settingsEnabled": True,

        # bars
        "showTopBarText": False,
        "showClock": False,
        "displayBatteryIcon": True,
        "displayBatteryPercent": False,
        "displayVolumeNumbers": False,
        "showBottomBarButtons": False,
        "topBarInitialXOffset": r(20),
        "setTopBarTextToGameSelection": False,
        "bindOverMiyooTheme": True,
        "mainMenuTitle": "",
        "fullScreenGridGameMenuResizeType": "FIT",

        "screensaver": {
            "bgColor": "#000000",
            "screensaverTimeoutSec": 60,
            "widgets": [
                {"type": "clock", "x": 0.5, "y": 0.42, "fontSize": r(82), "color": "#FFFFFF", "enabled": True, "font": f},
                {"type": "date", "x": 0.5, "y": 0.58, "fontSize": r(22), "color": "#8A8A8A"},
                {"type": "battery", "x": 0.5, "y": 0.7, "fontSize": r(18), "color": "#FFFFFF"},
            ],
        },
    }


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copy(FONT_SRC, os.path.join(OUT, FONT_NAME))
    with open(os.path.join(OUT, "igm.json"), "w") as fh:
        json.dump(igm_config(), fh, indent=4)
    os.makedirs(os.path.join(OUT, "sound"))
    shutil.copy(os.path.join(STOCK, "sound", "change.wav"), os.path.join(OUT, "sound", "change.wav"))

    for W, H in RESOLUTIONS:
        base = (W, H) == (640, 480)
        skin = "skin" if base else f"skin_{W}x{H}"
        stock_skin = os.path.join(STOCK, skin if os.path.isdir(os.path.join(STOCK, skin)) else "skin")
        s = build_skin(os.path.join(OUT, skin), W, H, stock_skin)
        cfg = "config.json" if base else f"config_{W}x{H}.json"
        with open(os.path.join(OUT, cfg), "w") as fh:
            json.dump(config(W, H, s), fh, indent=4)
        build_icons(OUT, W, H, s, base)
        if base:  # spruce looks for config_<W>x<H>.json first; avoid the auto-patcher
            with open(os.path.join(OUT, "config_640x480.json"), "w") as fh:
                json.dump(config(W, H, s), fh, indent=4)
        print("built", W, H)



if __name__ == "__main__":
    main()
