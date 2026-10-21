"""Accent Color picker for the NextUI Style theme (spruceOS / PyUI).

The app's launch.sh copies this file into PyUI's main-ui folder and starts it
through spruce's own PyUI launcher, so it gets the same display/input setup as
the main menu on every device. It draws RGB sliders with a live preview, then
recolours the theme with accent_engine.py and exits; spruce restarts the menu,
which loads the new colours.
"""
import os
import sys
import time

APP_DIR = os.environ.get("ACCENT_APP_DIR", "/mnt/SDCARD/App/AccentColor")
# append, not insert: PyUI finds its fonts and language files relative to sys.path[0]
sys.path.append(APP_DIR)

import mainui  # PyUI's own module: reuse its argument parsing and config bootstrap
from controller.controller import Controller
from controller.controller_inputs import ControllerInput
from devices.device import Device
from devices.device_factory import initialize_device
from devices.miyoo.user_config import UserConfig
from display.display import Display
from display.font_purpose import FontPurpose
from display.on_screen_keyboard import OnScreenKeyboard
from display.render_mode import RenderMode
from menus.language.language import Language
from themes.theme import Theme
from utils.cfw_system_config import CfwSystemConfig
from utils.logger import PyUiLogger
from utils.py_ui_config import PyUiConfig
from utils.py_ui_state import PyUiState

import accent_engine as eng

PRESETS = [("White", "#FFFFFF"), ("NextUI Red", "#9B2257"), ("Red", "#E5484D"), ("Orange", "#F28C28"),
           ("Yellow", "#F5C518"), ("Green", "#3DBE6B"), ("Teal", "#1FB5A8"), ("Blue", "#2F7DE1"),
           ("Purple", "#8E5BE8"), ("Pink", "#FF4FA3")]
ROWS = ["R", "G", "B", "HEX", "PRESET"]
WHITE, GRAY, DARK, TRACK = (255, 255, 255), (138, 138, 138), (34, 36, 40), (60, 62, 70)
CHANNEL = [(230, 70, 70), (70, 200, 110), (70, 140, 240)]


def log():
    return PyUiLogger.get_logger()


def init():
    # launch.sh passes exactly the arguments spruce gives the main menu
    args = mainui.parse_arguments()
    PyUiLogger.init(args.logDir, "AccentColor")
    mainui.verify_config_exists(args.pyUiConfig)
    PyUiConfig.init(args.pyUiConfig)
    UserConfig.reload_config()
    CfwSystemConfig.init(args.cfwConfig)
    Language.init()
    initialize_device(args.device, False)
    PyUiState.init(Device.get_device().get_state_path())
    theme_dir = os.path.join(PyUiConfig.get("themeDir"), Device.get_device().get_system_config().get_theme())
    Theme.init(theme_dir, Device.get_device().screen_width(), Device.get_device().screen_height())
    Display.init()
    Controller.init()
    return theme_dir


class Picker:
    def __init__(self, theme_dir):
        self.theme_dir = theme_dir
        self.saved = eng.current_accent(theme_dir)
        self.rgb = list(self.saved)
        self.row = 0
        self.preset = 0
        self.W = Device.get_device().screen_width()
        self.H = Device.get_device().screen_height()
        self.s = min(self.W / 640, self.H / 480)

    def px(self, v):
        return int(round(v * self.s))

    # ---------- drawing ----------
    def draw(self):
        Display.clear("", bottom_bar_text="<> ADJUST   L1/R1 x16   A APPLY   B CANCEL")
        W, s, px = self.W, self.s, self.px
        acc = tuple(self.rgb)
        sel = eng.selected_text_color(acc)
        bar_h = Display.get_top_bar_height()
        # cover the Games/Apps/Settings tabs spruce draws in the top bar; this screen has its own title
        Display.render_box((0, 0, 0), 0, 0, W - px(150), bar_h)
        Display.render_text("ACCENT COLOR", px(20), bar_h // 2, WHITE, FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)
        top = bar_h + px(4)
        row_h = px(54)
        y0 = top + px(10)
        label_x, track_x, track_w = px(24), px(100), px(250)

        for i, name in enumerate(ROWS):
            y = y0 + i * row_h
            cy = y + row_h // 2
            if i == self.row:  # tab-style marker: accent bar on the left of the row
                Display.render_box(acc, 0, y + px(6), px(8), row_h - px(12))
            color = WHITE if i == self.row else GRAY
            if i < 3:
                Display.render_text(name, label_x, cy, color, FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)
                th = px(14)
                Display.render_box(TRACK, track_x, cy - th // 2, track_w, th)
                fill = int(track_w * self.rgb[i] / 255)
                if fill > 0:
                    Display.render_box(CHANNEL[i], track_x, cy - th // 2, fill, th)
                kw = px(8)
                Display.render_box(WHITE, track_x + fill - kw // 2, cy - px(13), kw, px(26))
                Display.render_text(str(self.rgb[i]), track_x + track_w + px(64), cy, color,
                                    FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_RIGHT_ALIGNED)
            elif name == "HEX":
                Display.render_text("HEX", label_x, cy, color, FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)
                Display.render_text(eng.to_hex(acc) + ("   (A to type)" if i == self.row else ""), track_x, cy, color,
                                    FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)
            else:
                Display.render_text("PRESET", label_x, cy, color, FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)
                Display.render_text("< " + PRESETS[self.preset][0] + " >", track_x + px(20), cy, color,
                                    FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)

        # live preview on the right: a list row highlighted in the accent, plus a hint circle
        pv_x, pv_w = px(450), W - px(450) - px(16)
        pv_y = y0
        Display.render_box(DARK, pv_x, pv_y, pv_w, px(200))
        Display.render_text("Game Boy", pv_x + px(14), pv_y + px(30), WHITE, FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)
        Display.render_box(acc, pv_x + px(4), pv_y + px(58), pv_w - px(4), px(44))
        Display.render_text("GBA", pv_x + px(14), pv_y + px(80), sel, FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)
        Display.render_text("SNES", pv_x + px(14), pv_y + px(128), WHITE, FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_LEFT_ALIGNED)
        d = px(28)
        Display.render_box(acc, pv_x + px(14), pv_y + px(160), d, d)
        Display.render_text("A", pv_x + px(14) + d // 2, pv_y + px(160) + d // 2, sel, FontPurpose.DESCRIPTIVE_LIST_DESCRIPTION, RenderMode.MIDDLE_CENTER_ALIGNED)
        Display.render_text("OPEN", pv_x + px(52), pv_y + px(160) + d // 2, WHITE, FontPurpose.DESCRIPTIVE_LIST_DESCRIPTION, RenderMode.MIDDLE_LEFT_ALIGNED)
        Display.present()

    def draw_progress(self, done, total, label):
        Display.clear("", bottom_bar_text=" ")
        cy = self.H // 2
        Display.render_text(label, self.W // 2, cy - self.px(40), WHITE, FontPurpose.DESCRIPTIVE_LIST_TITLE, RenderMode.MIDDLE_CENTER_ALIGNED)
        bw, bh = self.px(400), self.px(16)
        x = (self.W - bw) // 2
        Display.render_box(TRACK, x, cy, bw, bh)
        if total:
            Display.render_box(tuple(self.rgb), x, cy, int(bw * done / total), bh)
        Display.present()

    # ---------- input ----------
    def adjust(self, delta):
        if self.row < 3:
            self.rgb[self.row] = max(0, min(255, self.rgb[self.row] + delta))
        elif ROWS[self.row] == "PRESET":
            self.preset = (self.preset + (1 if delta > 0 else -1)) % len(PRESETS)
            self.rgb = list(eng.parse_hex(PRESETS[self.preset][1]))

    def type_hex(self):
        text = OnScreenKeyboard().get_input("Hex color (RRGGBB)", eng.to_hex(self.rgb).lstrip("#"))
        if text:
            try:
                self.rgb = list(eng.parse_hex(text))
            except ValueError:
                Display.display_message("Not a hex color - use 6 digits, e.g. F5C518", 2000)

    def apply(self):
        # current screen's folder first so the colour you see next is ready soonest
        current = getattr(Theme, "_skin_folder", "skin")
        self.draw_progress(0, 1, "Applying " + eng.to_hex(self.rgb) + "...")
        eng.apply_accent(self.theme_dir, self.rgb, folders=[current],
                         progress=lambda d, t: self.draw_progress(d, t, "Applying " + eng.to_hex(self.rgb) + "..."))
        # then every other screen size, so the SD card looks right in other devices too
        others = [f for f in eng.template_folders(self.theme_dir) if f != current]
        eng.apply_accent(self.theme_dir, self.rgb, folders=others,
                         progress=lambda d, t: self.draw_progress(d, t, "Updating other screen sizes..."))

    def run(self):
        held_since, last = None, None
        while True:
            self.draw()
            if not Controller.get_input():
                held_since, last = None, None
                continue
            inp = Controller.last_input()
            # holding left/right speeds up after half a second
            now = time.time()
            if inp != last:
                held_since, last = now, inp
            step = 1 if now - held_since < 0.5 else 5
            if inp == ControllerInput.DPAD_UP:
                self.row = (self.row - 1) % len(ROWS)
            elif inp == ControllerInput.DPAD_DOWN:
                self.row = (self.row + 1) % len(ROWS)
            elif inp == ControllerInput.DPAD_LEFT:
                self.adjust(-step)
            elif inp == ControllerInput.DPAD_RIGHT:
                self.adjust(step)
            elif inp == ControllerInput.L1:
                self.adjust(-16)
            elif inp == ControllerInput.R1:
                self.adjust(16)
            elif inp == ControllerInput.A:
                if ROWS[self.row] == "HEX":
                    self.type_hex()
                else:
                    self.apply()
                    return True
            elif inp == ControllerInput.B:
                return False


def main():
    theme_dir = init()
    if not os.path.isfile(os.path.join(theme_dir, "accent", "manifest.json")):
        Display.display_message("Select the NextUI theme first (Settings > Theme).", 3500)
        return
    try:
        Picker(theme_dir).run()
    except Exception:
        log().exception("Accent picker failed")
        Display.display_message("Accent Color hit an error - see Saves/spruce logs.", 3500)


if __name__ == "__main__":
    main()
    os._exit(0)
