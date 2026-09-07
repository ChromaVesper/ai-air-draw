"""
main.py  —  AI Air Draw  •  Revolutionary MS Paint AI Edition
=============================================================
Complete MS-Paint suite + Cutting-Edge AI Vision Features:
- 16 Vector Shapes (Line, Bézier Curve, Rect, R-Rect, Circle, Tri, R-Tri, Diamond, Star 5/4, Arrow, Heart, Lightning, Callout, Polygon)
- Shape Fill Styles (Outline Only, Solid Fill, Outline + Fill)
- 9 Dynamic Brushes (Pencil, Callig, Pen, Marker, Crayon, Spray, Drip, Neon, Sparkle)
- Color 1 & Color 2 dual swatches + 16 Extended Studio Palette
- Flood Fill Bucket, 4x Magnifier Loupe Eyedropper, Text, Rect & Lasso Select, Crop, Transparent Sel
- AI Auto-Shape Beautifier (Snaps rough hand-sketches to perfect geometry)
- AI Real-Time Doodle Classifier (Live "Quick, Draw!" prediction badge)
- AI Magic Content-Aware Inpainting (Seamless object eraser)
- AI Edge Art Coloring Book Generator (Photo to clean line-art)
- Holographic AR Left-Hand Floating Palette
- 3D Air Depth / Pressure-Sensitive Stylus
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import cv2
import numpy as np
import time
import math
from collections import deque
from typing import Optional, Tuple, List, Dict

import config
from hand_tracker import HandTracker
from drawing import DrawingCanvas
import gestures

# ── Native File Dialog (Zero Cocoa Conflicts) ─────────────────────────────────
def _open_file_dialog() -> Optional[str]:
    """Uses native macOS AppleScript file chooser to prevent Cocoa NSApplication conflicts with OpenCV."""
    import subprocess
    cmd = """osascript -e 'set theFile to choose file with prompt "Open Image for AI Air Draw:" of type {"public.image"}' -e 'POSIX path of theFile'"""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            path = res.stdout.strip()
            return path if path else None
    except Exception:
        pass

    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        path = filedialog.askopenfilename(
            title="Open Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp *.tiff"), ("All Files", "*.*")]
        )
        root.destroy()
        return path or None
    except Exception:
        return None

# ── Layout Dimensions ─────────────────────────────────────────────────────────
R1H = config.TOOLBAR_ROW1_H   # 46
R2H = config.TOOLBAR_ROW2_H   # 52
R3H = config.TOOLBAR_ROW3_H   # 52
TH  = config.TOOLBAR_HEIGHT   # 150

BW = config.BTN_W   # 50
BH = config.BTN_H   # 40
BM = config.BTN_M   # 3

SWATCH_W   = 23
SWATCH_GAP = 2
SWATCHES   = list(config.COLORS.keys())   # 16 colours

# ── Toast Notification System ─────────────────────────────────────────────────
class Toast:
    DURATION = 2.4

    def __init__(self):
        self._msg = ""; self._color = (255, 255, 255); self._t = 0.

    def show(self, msg, color=(255, 255, 255)):
        self._msg = msg; self._color = color; self._t = time.time()

    def draw(self, frame):
        if not self._msg: return
        e = time.time() - self._t
        if e > self.DURATION: return
        alpha = max(0., 1. - e / self.DURATION)
        h, w = frame.shape[:2]
        sc, th = 0.75, 2
        (tw, _), _ = cv2.getTextSize(self._msg, cv2.FONT_HERSHEY_SIMPLEX, sc, th)
        x, y = (w - tw) // 2, h - 50
        ov = frame.copy()
        cv2.rectangle(ov, (x - 16, y - 28), (x + tw + 16, y + 10), (12, 12, 22), -1)
        cv2.addWeighted(ov, alpha * 0.82, frame, 1.0 - alpha * 0.82, 0, frame)
        ov2 = frame.copy()
        cv2.putText(ov2, self._msg, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), th + 1, cv2.LINE_AA)
        cv2.putText(ov2, self._msg, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, self._color, th, cv2.LINE_AA)
        cv2.addWeighted(ov2, alpha, frame, 1.0 - alpha, 0, frame)


# ─────────────────────────────────────────────────────────────────────────────
# UI Drawing Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _rr(img, x1, y1, x2, y2, color, r=6, filled=True):
    if x2 <= x1 or y2 <= y1: return
    t = -1 if filled else 1
    r = min(r, (x2 - x1) // 2, (y2 - y1) // 2)
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, t)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, t)
    for cx_, cy_ in [(x1 + r, y1 + r), (x2 - r, y1 + r), (x1 + r, y2 - r), (x2 - r, y2 - r)]:
        cv2.circle(img, (cx_, cy_), r, color, t)

def _btn(img, x, y, w, h, label, active=False, dim=False, group="normal"):
    if dim:
        bg = (24, 24, 34); tc = (65, 65, 75)
    elif active and group == "tool":
        bg = config.BUTTON_TOOL_COLOR; tc = (255, 230, 90)
    elif active and group == "ai":
        bg = config.BUTTON_AI_COLOR; tc = (255, 220, 255)
    elif active:
        bg = config.BUTTON_ACTIVE_COLOR; tc = (255, 220, 80)
    elif group == "ai":
        bg = (55, 30, 65); tc = (225, 185, 245)
    else:
        bg = config.BUTTON_INACTIVE_COLOR; tc = config.BUTTON_TEXT_COLOR
    _rr(img, x, y, x + w, y + h, bg, r=5)
    _rr(img, x, y, x + w, y + h, (75, 75, 90), r=5, filled=False)
    s = 0.35
    (tw, th_), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, s, 1)
    tx = x + (w - tw) // 2; ty = y + (h + th_) // 2
    cv2.putText(img, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, s, tc, 1, cv2.LINE_AA)

def _sec_label(img, x, y, text):
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.26, (115, 115, 135), 1, cv2.LINE_AA)

def _divider(img, x, y1, y2):
    cv2.line(img, (x, y1), (x, y2), (55, 55, 72), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Toolbar Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_toolbar(
    W: int,
    active_color_name: str,
    color1: Tuple[int, int, int],
    color2: Tuple[int, int, int],
    active_color_slot: int,
    is_eraser: bool,
    active_brush: str,
    active_shape: str,
    shape_fill_mode: str,
    active_paint_tool: str,
    active_sym: str,
    active_bg: str,
    rainbow: bool,
    dark_mode: bool,
    show_grid: bool,
    show_rulers: bool,
    trans_sel: bool,
    auto_snap: bool,
    holo_active: bool,
    pressure_active: bool,
    current_color: Tuple[int, int, int],
    brush_size: int,
    mode_label: str,
    fps: float,
    undo_count: int,
    redo_count: int,
    polygon_sides: int,
    text_mode: bool,
    sel_active: bool,
    ai_doodle_label: str,
    ai_doodle_conf: int,
) -> np.ndarray:

    tb = np.zeros((TH, W, 3), np.uint8)
    tb[:R1H] = config.TOOLBAR_BG_COLOR
    tb[R1H:R1H + R2H] = config.TOOLBAR_R2_BG
    tb[R1H + R2H:] = config.TOOLBAR_R3_BG
    cv2.line(tb, (0, R1H), (W, R1H), (50, 50, 68), 1)
    cv2.line(tb, (0, R1H + R2H), (W, R1H + R2H), (50, 50, 68), 1)

    # ── ROW 1: Title, AI Guesser, Color 1 & 2, 16 Swatches, Status, FPS ───────
    cv2.putText(tb, "AI AIR DRAW", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52, config.ACCENT, 2, cv2.LINE_AA)
    cv2.putText(tb, "MS PAINT AI REVOLUTION", (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.26, (140, 140, 160), 1, cv2.LINE_AA)

    # AI Real-time Doodle Classifier badge
    ai_bx = 175
    ai_bw = 145
    _rr(tb, ai_bx, 6, ai_bx + ai_bw, 40, (40, 22, 50), r=6)
    _rr(tb, ai_bx, 6, ai_bx + ai_bw, 40, (160, 60, 180), r=6, filled=False)
    cv2.putText(tb, "AI VISION GUESS", (ai_bx + 8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (210, 160, 255), 1, cv2.LINE_AA)
    conf_str = f"({ai_doodle_conf}%)" if ai_doodle_conf > 0 else ""
    cv2.putText(tb, f"{ai_doodle_label} {conf_str}", (ai_bx + 8, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (255, 240, 255), 1, cv2.LINE_AA)

    # Color 1 & Color 2 Boxes
    c1_x = ai_bx + ai_bw + 12
    # Color 1 (Foreground)
    c1_act = (active_color_slot == 1)
    _rr(tb, c1_x, 6, c1_x + 36, 40, (180, 140, 30) if c1_act else (50, 50, 65), r=5)
    _rr(tb, c1_x + 3, 9, c1_x + 33, 37, color1, r=4)
    cv2.putText(tb, "1", (c1_x + 12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 0) if np.mean(color1) > 130 else (255, 255, 255), 1, cv2.LINE_AA)

    # Color 2 (Background / Fill)
    c2_x = c1_x + 40
    c2_act = (active_color_slot == 2)
    _rr(tb, c2_x, 6, c2_x + 36, 40, (180, 140, 30) if c2_act else (50, 50, 65), r=5)
    _rr(tb, c2_x + 3, 9, c2_x + 33, 37, color2, r=4)
    cv2.putText(tb, "2", (c2_x + 12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 0) if np.mean(color2) > 130 else (255, 255, 255), 1, cv2.LINE_AA)

    # Swap button
    sw_x = c2_x + 40
    _btn(tb, sw_x, 9, 32, 28, "SWP", active=False)

    # 16 Color Swatches
    sx = sw_x + 38
    for name in SWATCHES:
        bgr = config.COLORS[name]
        is_cur = (name == active_color_name) and not is_eraser
        sy = 7; sh = 30
        if is_cur:
            _rr(tb, sx - 2, sy - 2, sx + SWATCH_W + 2, sy + sh + 2, config.ACCENT, r=4)
        _rr(tb, sx, sy, sx + SWATCH_W, sy + sh, bgr, r=3)
        if name in ("WHITE", "YELLOW"):
            cv2.rectangle(tb, (sx, sy), (sx + SWATCH_W, sy + sh), (140, 140, 140), 1)
        sx += SWATCH_W + SWATCH_GAP

    # Right side: Status, Brush Size, FPS
    rx = W - 265
    mc = {
        "DRAW": (0, 200, 80), "ERASER": (0, 100, 255), "FILL": (255, 120, 0),
        "EYEDROP": (0, 210, 210), "PAUSE": (50, 50, 220), "PINCH": (255, 175, 0),
        "TEXT": (80, 200, 255), "SELECT": (255, 80, 150), "LASSO": (220, 60, 180),
        "IDLE": (110, 110, 120)
    }.get(mode_label, (140, 140, 140))
    _rr(tb, rx, 7, rx + 105, 39, mc, r=6)
    cv2.putText(tb, mode_label, (rx + 8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 2, cv2.LINE_AA)

    bx2 = rx + 112; by2 = 9; bw2 = 90
    cv2.rectangle(tb, (bx2, by2), (bx2 + bw2, by2 + 10), (42, 42, 55), -1)
    fill = int(bw2 * (brush_size - config.MIN_BRUSH_SIZE) / (config.MAX_BRUSH_SIZE - config.MIN_BRUSH_SIZE + 1e-3))
    cv2.rectangle(tb, (bx2, by2), (bx2 + fill, by2 + 10), current_color, -1)
    cv2.putText(tb, f"{brush_size}px", (bx2 + bw2 + 5, by2 + 9), cv2.FONT_HERSHEY_SIMPLEX, 0.36, config.STATUS_TEXT_COLOR, 1, cv2.LINE_AA)
    cv2.putText(tb, f"FPS {fps:4.1f}", (bx2, by2 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.36, config.FPS_TEXT_COLOR, 1, cv2.LINE_AA)

    # Active color disc
    cv2.circle(tb, (W - 22, R1H // 2), 17, current_color, -1)
    cv2.circle(tb, (W - 22, R1H // 2), 17, config.ACCENT if not is_eraser else (80, 80, 255), 2)

    # ── ROW 2: Brushes | MS Paint Shapes | Fill Mode | View Toggles ───────────
    y2 = R1H + (R2H - BH) // 2
    bx = 6
    _sec_label(tb, bx, R1H + 9, "BRUSH")
    for lbl, mode in zip(config.BRUSH_LABELS, config.BRUSH_MODES):
        _btn(tb, bx, y2, BW, BH, lbl, active=(mode == active_brush and not is_eraser and not active_paint_tool))
        bx += BW + BM
    bx += 3; _divider(tb, bx, R1H + 5, R1H + R2H - 5); bx += 7

    _sec_label(tb, bx, R1H + 9, "SHAPES (MS PAINT)")
    for lbl, shape in zip(config.SHAPE_LABELS, config.SHAPE_TOOLS):
        act = (shape == active_shape and not is_eraser and not active_paint_tool)
        _btn(tb, bx, y2, BW, BH, lbl, active=act)
        bx += BW + BM
    bx += 3; _divider(tb, bx, R1H + 5, R1H + R2H - 5); bx += 7

    _sec_label(tb, bx, R1H + 9, "STYLE")
    for lbl, fmode in zip(config.SHAPE_FILL_LABELS, config.SHAPE_FILL_MODES):
        _btn(tb, bx, y2, 44, BH, lbl, active=(fmode == shape_fill_mode))
        bx += 44 + BM
    bx += 3; _divider(tb, bx, R1H + 5, R1H + R2H - 5); bx += 7

    _sec_label(tb, bx, R1H + 9, "VIEW & MODES")
    for lbl, act, dim in [
        ("SYM", active_sym != "none", False),
        ("RNBW", rainbow, False),
        ("DARK", dark_mode, False),
        ("GRID", show_grid, False),
        ("RULE", show_rulers, False),
    ]:
        _btn(tb, bx, y2, 42, BH, lbl, active=act, dim=dim)
        bx += 42 + BM

    # ── ROW 3: Paint Tools | AI Superpowers | Transforms | File/History ───────
    y3 = R1H + R2H + (R3H - BH) // 2
    bx = 6
    _sec_label(tb, bx, R1H + R2H + 9, "PAINT TOOLS")
    for lbl, tool in zip(config.PAINT_LABELS, config.PAINT_TOOLS):
        act = (tool == active_paint_tool)
        spec_act = (tool == "text" and text_mode) or (tool in ("select", "lasso") and sel_active)
        _btn(tb, bx, y3, BW + 4, BH, lbl, active=(act or spec_act), group="tool")
        bx += BW + 4 + BM
    _btn(tb, bx, y3, 46, BH, "TRANS", active=trans_sel, group="tool")
    bx += 46 + BM
    bx += 3; _divider(tb, bx, R1H + R2H + 4, TH - 4); bx += 7

    _sec_label(tb, bx, R1H + R2H + 9, "AI SUPERPOWERS")
    ai_buttons = [
        ("🤖SNAP", auto_snap),
        ("✨INPNT", False),
        ("📖BOOK", False),
        ("🔮HOLO", holo_active),
        ("🎚️PRES", pressure_active),
    ]
    for lbl, act in ai_buttons:
        _btn(tb, bx, y3, BW + 6, BH, lbl, active=act, group="ai")
        bx += BW + 6 + BM
    bx += 3; _divider(tb, bx, R1H + R2H + 4, TH - 4); bx += 7

    _sec_label(tb, bx, R1H + R2H + 9, "TRANSFORM")
    for lbl in ["FLP↔", "FLP↕", "ROT↻", "INVRT", "GRAY"]:
        _btn(tb, bx, y3, 44, BH, lbl)
        bx += 44 + BM
    bx += 3; _divider(tb, bx, R1H + R2H + 4, TH - 4); bx += 7

    _sec_label(tb, bx, R1H + R2H + 9, "FILE & HISTORY")
    for lbl, dim in [("OPEN", False), ("SAVE", False), ("UNDO", undo_count == 0), ("REDO", redo_count == 0), ("CLR", False)]:
        _btn(tb, bx, y3, 44, BH, lbl, dim=dim)
        bx += 44 + BM

    return tb


# ─────────────────────────────────────────────────────────────────────────────
# Hit Testing
# ─────────────────────────────────────────────────────────────────────────────

def _hit(tb_tip) -> Optional[str]:
    if tb_tip is None: return None
    tx, ty = tb_tip
    if ty >= TH: return None

    # ── Row 1 ─────────────────────────────────────────────────────────────────
    if ty < R1H:
        ai_bx = 175; ai_bw = 145
        c1_x = ai_bx + ai_bw + 12
        if c1_x <= tx <= c1_x + 36: return "slot:1"
        c2_x = c1_x + 40
        if c2_x <= tx <= c2_x + 36: return "slot:2"
        sw_x = c2_x + 40
        if sw_x <= tx <= sw_x + 32: return "slot:swap"

        sx = sw_x + 38
        for name in SWATCHES:
            if sx <= tx <= sx + SWATCH_W: return f"color:{name}"
            sx += SWATCH_W + SWATCH_GAP
        return None

    # ── Row 2 ─────────────────────────────────────────────────────────────────
    if R1H <= ty < R1H + R2H:
        bx = 6
        for mode in config.BRUSH_MODES:
            if bx <= tx <= bx + BW: return f"brush:{mode}"
            bx += BW + BM
        bx += 10
        for shape in config.SHAPE_TOOLS:
            if bx <= tx <= bx + BW: return f"shape:{shape}"
            bx += BW + BM
        bx += 10
        for fmode in config.SHAPE_FILL_MODES:
            if bx <= tx <= bx + 44: return f"fillmode:{fmode}"
            bx += 44 + BM
        bx += 10
        for key in ["sym", "rnbw", "dark", "grid", "rule"]:
            if bx <= tx <= bx + 42: return f"toggle:{key}"
            bx += 42 + BM
        return None

    # ── Row 3 ─────────────────────────────────────────────────────────────────
    bx = 6
    for tool in config.PAINT_TOOLS:
        if bx <= tx <= bx + BW + 4: return f"paint:{tool}"
        bx += BW + 4 + BM
    if bx <= tx <= bx + 46: return "toggle:trans_sel"
    bx += 46 + BM
    bx += 10
    for ai_key in ["ai_snap", "ai_inpaint", "ai_book", "ai_holo", "ai_pressure"]:
        if bx <= tx <= bx + BW + 6: return f"ai:{ai_key}"
        bx += BW + 6 + BM
    bx += 10
    for tr in ["flph", "flpv", "rot", "invt", "gray"]:
        if bx <= tx <= bx + 44: return f"transform:{tr}"
        bx += 44 + BM
    bx += 10
    for act in ["open", "save", "undo", "redo", "clr"]:
        if bx <= tx <= bx + 44: return f"action:{act}"
        bx += 44 + BM
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 4x Magnifier Eyedropper Loupe
# ─────────────────────────────────────────────────────────────────────────────

def draw_magnifier_loupe(frame, canvas_img, tip_canvas, tip_frame):
    """Renders a circular 4x zoom loupe with crosshair, RGB and Hex code."""
    if tip_canvas is None or tip_frame is None: return
    cx, cy = tip_canvas
    h, w = canvas_img.shape[:2]
    if not (0 <= cx < w and 0 <= cy < h): return

    loupe_r = 44
    patch_size = 22
    px1, px2 = max(0, cx - patch_size // 2), min(w, cx + patch_size // 2)
    py1, py2 = max(0, cy - patch_size // 2), min(h, cy + patch_size // 2)
    patch = canvas_img[py1:py2, px1:px2]
    if patch.shape[0] < 4 or patch.shape[1] < 4: return

    zoomed = cv2.resize(patch, (loupe_r * 2, loupe_r * 2), interpolation=cv2.INTER_NEAREST)

    # Position loupe offset from fingertip
    lx = tip_frame[0]
    ly = max(TH + loupe_r + 20, tip_frame[1] - loupe_r - 30)

    # Mask to circle
    mask = np.zeros((loupe_r * 2, loupe_r * 2), np.uint8)
    cv2.circle(mask, (loupe_r, loupe_r), loupe_r - 2, 255, -1)

    y1, y2 = max(0, ly - loupe_r), min(frame.shape[0], ly + loupe_r)
    x1, x2 = max(0, lx - loupe_r), min(frame.shape[1], lx + loupe_r)
    if y2 - y1 == loupe_r * 2 and x2 - x1 == loupe_r * 2:
        target_roi = frame[y1:y2, x1:x2]
        target_roi[mask > 0] = zoomed[mask > 0]
        # Crosshairs
        cv2.drawMarker(frame, (lx, ly), (0, 255, 255), cv2.MARKER_CROSS, 16, 1)
        cv2.circle(frame, (lx, ly), loupe_r, (255, 255, 255), 2, lineType=cv2.LINE_AA)

        b, g, r = canvas_img[cy, cx]
        hex_code = f"#{r:02X}{g:02X}{b:02X}"
        cv2.rectangle(frame, (lx - 40, ly + loupe_r + 4), (lx + 40, ly + loupe_r + 22), (20, 20, 30), -1)
        cv2.putText(frame, hex_code, (lx - 34, ly + loupe_r + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# Holographic AR Left-Hand Palette (Iron Man Palm HUD)
# ─────────────────────────────────────────────────────────────────────────────

HOLO_PALETTE_COLORS = [
    ("RED", config.COLORS["RED"]),
    ("ORANGE", config.COLORS["ORANGE"]),
    ("YELLOW", config.COLORS["YELLOW"]),
    ("GREEN", config.COLORS["GREEN"]),
    ("CYAN", config.COLORS["CYAN"]),
    ("BLUE", config.COLORS["BLUE"]),
    ("PURPLE", config.COLORS["PURPLE"]),
    ("WHITE", config.COLORS["WHITE"]),
]

def draw_holographic_palm_palette(frame, palm_center) -> List[Tuple[Tuple[int, int], str, Tuple[int, int, int]]]:
    """Projects futuristic circular AR color wheel over the user's palm."""
    if palm_center is None: return []
    cx, cy = palm_center
    rad = 68
    # Rotating holographic ring
    t = time.time() * 2.0
    ov = frame.copy()
    cv2.circle(ov, (cx, cy), rad + 14, (160, 40, 220), 1, lineType=cv2.LINE_AA)
    cv2.circle(ov, (cx, cy), rad - 12, (220, 80, 255), 1, lineType=cv2.LINE_AA)
    cv2.circle(ov, (cx, cy), 18, (30, 10, 45), -1)
    cv2.putText(ov, "HOLO", (cx - 14, cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (255, 200, 255), 1, cv2.LINE_AA)
    cv2.addWeighted(ov, 0.65, frame, 0.35, 0, frame)

    interactive_nodes = []
    num_nodes = len(HOLO_PALETTE_COLORS)
    for i, (cname, bgr) in enumerate(HOLO_PALETTE_COLORS):
        ang = t + (2.0 * math.pi * i / num_nodes)
        nx = int(cx + rad * math.cos(ang))
        ny = int(cy + rad * math.sin(ang))
        cv2.circle(frame, (nx, ny), 12, (20, 20, 30), -1)
        cv2.circle(frame, (nx, ny), 10, bgr, -1)
        cv2.circle(frame, (nx, ny), 12, (255, 255, 255), 1, lineType=cv2.LINE_AA)
        interactive_nodes.append(((nx, ny), cname, bgr))

    return interactive_nodes


# ─────────────────────────────────────────────────────────────────────────────
# Fingertip Trail & Gesture HUD
# ─────────────────────────────────────────────────────────────────────────────

_TRAIL: deque = deque(maxlen=10)

def draw_tip(frame, tip, color, gesture, brush_size):
    if tip is None: _TRAIL.clear(); return
    _TRAIL.append(tip)
    for i, pt in enumerate(_TRAIL):
        a = (i + 1) / len(_TRAIL)
        cv2.circle(frame, pt, max(1, int(5 * a)), tuple(int(c * a * 0.65) for c in color), -1)

    if gesture == gestures.GESTURE_ERASER:
        r, rc, t = config.ERASER_SIZE // 2, (80, 80, 255), 2
    elif gesture == gestures.GESTURE_DRAW:
        r, rc, t = max(brush_size + 6, 14), color, 3
    elif gesture == gestures.GESTURE_FIST:
        r, rc, t = 20, (50, 50, 220), 2
    elif gesture == gestures.GESTURE_PINCH:
        r, rc, t = 16, (255, 175, 0), 2
    elif gesture == gestures.GESTURE_FILL:
        r, rc, t = 22, (255, 120, 0), 2
    elif gesture == gestures.GESTURE_EYEDROP:
        r, rc, t = 18, (0, 210, 210), 2
    else:
        r, rc, t = 12, (140, 140, 140), 1
    cv2.circle(frame, tip, r, rc, t, lineType=cv2.LINE_AA)
    cv2.circle(frame, tip, 4, rc, -1)

def draw_sym_guide(frame, mode, toolbar_h):
    if mode == "none": return
    h, w = frame.shape[:2]; cx, cy = w // 2, (h + toolbar_h) // 2; c = (55, 55, 170)
    if mode in ("mirror_h", "quad", "radial_4", "radial_8", "radial_12"):
        cv2.line(frame, (cx, toolbar_h), (cx, h), c, 1)
    if mode in ("mirror_v", "quad", "radial_4", "radial_8", "radial_12"):
        cv2.line(frame, (0, cy), (w, cy), c, 1)
    if mode in ("radial_8", "radial_12"):
        for d in [45, 135]:
            rad = math.radians(d); dx, dy = math.cos(rad) * max(w, h), math.sin(rad) * max(w, h)
            cv2.line(frame, (int(cx - dx), int(cy - dy)), (int(cx + dx), int(cy + dy)), c, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Main Application Loop
# ─────────────────────────────────────────────────────────────────────────────

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Camera not available."); sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Camera initialized {W}×{H}")

    tracker = HandTracker()
    canvas = DrawingCanvas(W, H, dark_mode=config.DEFAULT_DARK_CANVAS)
    toast = Toast()

    # ── State ─────────────────────────────────────────────────────────────────
    color_name = config.DEFAULT_COLOR_NAME
    color1 = config.COLORS[color_name]
    color2 = config.COLORS[config.DEFAULT_COLOR2_NAME]
    active_slot = 1   # 1=Color 1 (Foreground), 2=Color 2 (Background/Fill)

    brush_size = config.DEFAULT_BRUSH_SIZE
    is_eraser = False
    show_hud = config.SHOW_HUD

    # Tool state
    paint_tool = ""
    auto_snap = True
    holo_active = True
    pressure_active = True

    # Performance
    fps = 0.0; prev_time = time.time()
    was_in_bar = False

    # Gestures & Hold timers
    prev_g = gestures.GESTURE_IDLE
    prev_g_raw = gestures.GESTURE_IDLE
    open_t = 0.0; thumb_t = 0.0
    OPEN_HOLD = 0.60; THUMB_HOLD = 0.40

    # Pinch resize
    in_pinch = False; pb_dist = 1.0; pb_size = brush_size
    in_pinch2 = False; pb2_dist = 1.0; pb2_size = brush_size

    # Shape state
    shape_drawing = False

    # Selection drag
    sel_drag_start = None
    sel_drag_offset = (0, 0)
    lasso_drawing = False
    lasso_points: List[Tuple[int, int]] = []

    print("[INFO] AI Air Draw — Revolutionary MS Paint AI Edition Launched!")

    while True:
        ret, frame = cap.read()
        if not ret: continue
        frame = cv2.flip(frame, 1)

        tracker.process_frame(frame)
        lm0 = tracker.get_landmarks(0)
        lm1 = tracker.get_landmarks(1)

        tip0_raw = tracker.get_index_fingertip(hand_idx=0)
        tip1_raw = tracker.get_index_fingertip(hand_idx=1)

        g0 = gestures.recognise_gesture(lm0)
        g1 = gestures.recognise_gesture(lm1) if lm1 else gestures.GESTURE_IDLE

        # Route fingertip based on gesture
        if g0 == gestures.GESTURE_EYEDROP:
            tip0 = tracker.get_landmark_pixel(12, hand_idx=0)  # Middle finger
        elif g0 == gestures.GESTURE_FILL:
            tip0 = tracker.get_landmark_pixel(16, hand_idx=0)  # Ring finger
        else:
            tip0 = tip0_raw

        tip1 = tip1_raw

        # Calculate 3D virtual stylus pressure
        pressure = gestures.get_finger_pressure(lm0) if pressure_active else 1.0

        # Current working color
        active_color = color1 if active_slot == 1 else color2

        # ── Pinch Resize ──────────────────────────────────────────────────────
        if g0 == gestures.GESTURE_PINCH:
            d = gestures.get_pinch_distance(lm0)
            if not in_pinch: in_pinch, pb_dist, pb_size = True, d, brush_size
            else:
                r = pb_dist / max(d, 0.001)
                brush_size = max(config.MIN_BRUSH_SIZE, min(config.MAX_BRUSH_SIZE, int(pb_size * r)))
        else: in_pinch = False

        if lm1 and g1 == gestures.GESTURE_PINCH:
            d2 = gestures.get_pinch_distance(lm1)
            if not in_pinch2: in_pinch2, pb2_dist, pb2_size = True, d2, brush_size
            else:
                r2 = pb2_dist / max(d2, 0.001)
                brush_size = max(config.MIN_BRUSH_SIZE, min(config.MAX_BRUSH_SIZE, int(pb2_size * r2)))
        else: in_pinch2 = False

        # ── Gesture Triggers ──────────────────────────────────────────────────
        g_just_started = (g0 != prev_g_raw)

        # EYEDROP gesture
        if g0 == gestures.GESTURE_EYEDROP and g_just_started and tip0 and tip0[1] > TH:
            p = canvas.pick_color(tip0[0], tip0[1] - TH)
            if p:
                if active_slot == 1: color1 = p
                else: color2 = p
                is_eraser = False; paint_tool = ""
                toast.show(f"Color {active_slot} picked!", p)

        # FILL gesture
        if g0 == gestures.GESTURE_FILL and g_just_started and tip0 and tip0[1] > TH:
            canvas.flood_fill(tip0[0], tip0[1] - TH, active_color)
            toast.show("Bucket Filled!", active_color)

        # ERASER gesture
        if g0 == gestures.GESTURE_ERASER: is_eraser = True
        elif g0 == gestures.GESTURE_DRAW: is_eraser = False

        # OPEN HAND → Clear hold
        if g0 == gestures.GESTURE_OPEN_HAND:
            if prev_g != gestures.GESTURE_OPEN_HAND: open_t = time.time()
            elif time.time() - open_t >= OPEN_HOLD:
                canvas.clear(); open_t = time.time() + 9999; toast.show("Canvas cleared!", (80, 80, 255))

        # THUMBS UP → Save hold
        if g0 == gestures.GESTURE_THUMBS_UP:
            if prev_g != gestures.GESTURE_THUMBS_UP: thumb_t = time.time()
            elif time.time() - thumb_t >= THUMB_HOLD:
                path = canvas.save(); thumb_t = time.time() + 9999
                toast.show("Masterpiece Saved!", (0, 230, 80))

        prev_g = g0; prev_g_raw = g0

        # ── Holographic Hand Palette Interaction ──────────────────────────────
        palm_nodes = []
        if holo_active and lm1:
            palm_pt = gestures.get_palm_center(lm1, W, H)
            palm_nodes = draw_holographic_palm_palette(frame, palm_pt)
            if tip0 and palm_nodes:
                for (nx, ny), cname, bgr in palm_nodes:
                    if math.hypot(tip0[0] - nx, tip0[1] - ny) < 18:
                        if active_slot == 1: color1 = bgr; color_name = cname
                        else: color2 = bgr
                        is_eraser = False
                        toast.show(f"Holo Palette: {cname}", bgr)

        # ── Toolbar Hit-Testing ───────────────────────────────────────────────
        hit = _hit(tip0) if tip0 and tip0[1] < TH else None
        if hit and not was_in_bar:
            was_in_bar = True
            if hit.startswith("color:"):
                name = hit[6:]
                col = config.COLORS[name]
                if active_slot == 1: color1 = col; color_name = name
                else: color2 = col
                is_eraser = False; paint_tool = ""
                toast.show(f"Color {active_slot}: {name}", col)
            elif hit == "slot:1":
                active_slot = 1; toast.show("Color 1 (Foreground) Active", color1)
            elif hit == "slot:2":
                active_slot = 2; toast.show("Color 2 (Background/Fill) Active", color2)
            elif hit == "slot:swap":
                color1, color2 = color2, color1
                toast.show("Colors 1 & 2 Swapped!", color1)
            elif hit.startswith("brush:"):
                canvas.brush_mode = hit[6:]; is_eraser = False; paint_tool = ""
                canvas.shape_tool = "freehand"
                toast.show(f"Brush: {canvas.brush_mode.upper()}", config.ACCENT)
            elif hit.startswith("shape:"):
                canvas.shape_tool = hit[6:]; is_eraser = False; paint_tool = ""
                toast.show(f"Shape: {canvas.shape_tool.upper()}", config.ACCENT2)
            elif hit.startswith("fillmode:"):
                canvas.shape_fill_mode = hit[9:]
                toast.show(f"Fill Style: {canvas.shape_fill_mode.upper()}", config.ACCENT)
            elif hit.startswith("paint:"):
                tool = hit[6:]
                paint_tool = "" if paint_tool == tool else tool
                if tool == "text" and paint_tool == "text":
                    canvas.start_text(W // 2, H // 2, active_color)
                    toast.show("TEXT: type then Enter", config.ACCENT2)
                elif tool == "crop":
                    if canvas.crop_to_selection(): toast.show("Cropped to selection!", config.ACCENT)
                    else: toast.show("Make a selection first", (80, 80, 255))
                    paint_tool = ""
                else:
                    toast.show(f"Tool: {tool.upper()}", config.BUTTON_TOOL_COLOR[::-1])
            elif hit.startswith("ai:"):
                ai_k = hit[3:]
                if ai_k == "ai_snap":
                    auto_snap = not auto_snap
                    canvas.auto_beautify = auto_snap
                    toast.show("AI Auto-Beautifier ON" if auto_snap else "AI Auto-Beautifier OFF", config.BUTTON_AI_COLOR[::-1])
                elif ai_k == "ai_inpaint":
                    if canvas.magic_inpaint_selection(): toast.show("AI Magic Inpainted!", (240, 140, 255))
                    else: toast.show("Select an area to inpaint first", (80, 80, 255))
                elif ai_k == "ai_book":
                    canvas.convert_to_coloring_book()
                    toast.show("AI Coloring Book Generated!", config.ACCENT)
                elif ai_k == "ai_holo":
                    holo_active = not holo_active
                    toast.show("Holographic Palette ON" if holo_active else "Holo Palette OFF", (220, 120, 255))
                elif ai_k == "ai_pressure":
                    pressure_active = not pressure_active
                    toast.show("3D Pressure Stylus ON" if pressure_active else "Pressure OFF", config.ACCENT2)
            elif hit.startswith("toggle:"):
                k = hit[7:]
                if k == "sym":
                    syms = config.SYMMETRY_MODES
                    canvas.symmetry_mode = syms[(syms.index(canvas.symmetry_mode) + 1) % len(syms)]
                    toast.show(f"Symmetry: {canvas.symmetry_mode.upper()}", (200, 150, 255))
                elif k == "rnbw":
                    canvas.rainbow_mode = not canvas.rainbow_mode
                    toast.show("Rainbow ON" if canvas.rainbow_mode else "Rainbow OFF", (255, 80, 200))
                elif k == "dark":
                    canvas.toggle_dark_mode()
                    toast.show("Dark Canvas" if canvas.dark_mode else "Light Canvas", (200, 180, 100))
                elif k == "grid":
                    canvas.show_gridlines = not canvas.show_gridlines
                    toast.show("Gridlines ON" if canvas.show_gridlines else "Gridlines OFF", (180, 180, 180))
                elif k == "rule":
                    canvas.show_rulers = not canvas.show_rulers
                    toast.show("Rulers ON" if canvas.show_rulers else "Rulers OFF", (180, 180, 180))
                elif k == "trans_sel":
                    canvas.transparent_sel = not canvas.transparent_sel
                    toast.show("Transparent Sel ON" if canvas.transparent_sel else "Transparent Sel OFF", (255, 160, 40))
            elif hit.startswith("transform:"):
                t = hit[10:]
                if t == "flph": canvas.flip_horizontal(); toast.show("Flipped ↔", (150, 200, 255))
                elif t == "flpv": canvas.flip_vertical(); toast.show("Flipped ↕", (150, 200, 255))
                elif t == "rot": canvas.rotate_90(); toast.show("Rotated ↻", (150, 200, 255))
                elif t == "invt": canvas.invert_colors(); toast.show("Inverted", (200, 200, 100))
                elif t == "gray": canvas.grayscale(); toast.show("Grayscale", (180, 180, 180))
            elif hit.startswith("action:"):
                a = hit[7:]
                if a == "open":
                    path = _open_file_dialog()
                    if path and canvas.open_image(path): toast.show("Image loaded!", (0, 230, 80))
                    elif path: toast.show("Could not load file", (80, 80, 255))
                elif a == "save":
                    path = canvas.save(); toast.show("Saved!", (0, 230, 80))
                elif a == "undo":
                    if canvas.undo(): toast.show("Undo", (200, 200, 255))
                elif a == "redo":
                    if canvas.redo(): toast.show("Redo", (200, 255, 200))
                elif a == "clr":
                    canvas.clear(); toast.show("Cleared!", (80, 80, 255))
        elif not hit: was_in_bar = False

        # ── Canvas Coordinate Translation ─────────────────────────────────────
        def on_canvas(tip):
            if tip is None: return None
            tx, ty = tip
            if ty <= TH: return None
            return (tx, ty - TH)

        cp0 = on_canvas(tip0)
        drawing_active = g0 in (gestures.GESTURE_DRAW, gestures.GESTURE_ERASER) and cp0 is not None

        # ── Paint Tools Dispatch ──────────────────────────────────────────────
        if paint_tool == "fill" and g0 == gestures.GESTURE_DRAW and g_just_started and cp0:
            canvas.flood_fill(cp0[0], cp0[1], active_color)
            toast.show("Filled!", active_color)

        elif paint_tool == "eyedrop" and g0 == gestures.GESTURE_DRAW and g_just_started and cp0:
            p = canvas.pick_color(cp0[0], cp0[1])
            if p:
                if active_slot == 1: color1 = p
                else: color2 = p
                is_eraser = False; toast.show(f"Color {active_slot} picked!", p)

        elif paint_tool == "text":
            if g0 == gestures.GESTURE_DRAW and g_just_started and cp0:
                canvas.start_text(cp0[0], cp0[1], active_color, 1.1)
                toast.show("Type text, Enter=commit, Esc=cancel", config.ACCENT2)

        elif paint_tool == "lasso":
            if g0 == gestures.GESTURE_DRAW and cp0:
                if not lasso_drawing:
                    lasso_drawing = True
                    lasso_points = [cp0]
                else:
                    lasso_points.append(cp0)
            else:
                if lasso_drawing and len(lasso_points) > 4:
                    canvas.set_lasso_points(lasso_points)
                    toast.show("Freeform Lasso Selected!", (220, 60, 180))
                lasso_drawing = False

        elif paint_tool == "select":
            if g0 == gestures.GESTURE_DRAW and cp0:
                sel_r = canvas.get_selection_rect()
                if sel_r and not shape_drawing:
                    x1, y1, x2, y2 = sel_r
                    if x1 <= cp0[0] <= x2 and y1 <= cp0[1] <= y2:
                        if sel_drag_start is None:
                            sel_drag_start = cp0
                            sel_drag_offset = (cp0[0] - x1, cp0[1] - y1)
                    else:
                        if not shape_drawing:
                            canvas._shape_start = (cp0[0], cp0[1])
                            shape_drawing = True
                else:
                    if not shape_drawing:
                        canvas._shape_start = (cp0[0], cp0[1])
                        shape_drawing = True
                    canvas._shape_preview_end = cp0

                if sel_drag_start and sel_drag_offset:
                    new_x = cp0[0] - sel_drag_offset[0]
                    new_y = cp0[1] - sel_drag_offset[1]
                    canvas.move_selection(new_x, new_y)
            else:
                if shape_drawing and canvas._shape_start and canvas._shape_preview_end:
                    a = canvas._shape_start; b = canvas._shape_preview_end
                    canvas.set_selection(a[0], a[1], b[0], b[1])
                    toast.show("Selection made — C=Copy, X=Cut, V=Paste, Del=Clear", (255, 80, 150))
                shape_drawing = False
                canvas._shape_start = None; canvas._shape_preview_end = None
                sel_drag_start = None; sel_drag_offset = (0, 0)

        # ── Shape Tools ───────────────────────────────────────────────────────
        elif canvas.shape_tool != "freehand" and not is_eraser and paint_tool == "":
            if drawing_active and cp0:
                if not shape_drawing:
                    shape_drawing = True
                    canvas.begin_shape(cp0[0], cp0[1], active_color, brush_size)
                else:
                    canvas.update_shape_preview(cp0[0], cp0[1])
            else:
                if shape_drawing:
                    if g0 == gestures.GESTURE_FIST:
                        canvas.cancel_shape(); toast.show("Shape cancelled", (200, 100, 100))
                    else:
                        canvas.commit_shape()
                shape_drawing = False

        # ── Freehand Stroke ───────────────────────────────────────────────────
        elif paint_tool == "":
            if cp0:
                canvas.update(cp0[0], cp0[1], active_color, brush_size, drawing_active, is_eraser, pressure=pressure)
            else:
                canvas.reset_previous_point()

        if cp0 is None: canvas.reset_previous_point()

        # ── Landmark Skeleton ─────────────────────────────────────────────────
        tracker.draw_all_landmarks(frame)

        # ── Canvas to Frame Blending ──────────────────────────────────────────
        disp = canvas.display_image
        if disp.shape[:2] != frame.shape[:2]:
            disp = cv2.resize(disp, (frame.shape[1], frame.shape[0]))
        roi = frame[TH:, :]
        droi = disp[TH:, :]
        bg_r = canvas._bg[TH:, :]
        if bg_r.shape[:2] != droi.shape[:2]:
            bg_r = cv2.resize(canvas._bg, (frame.shape[1], frame.shape[0]))[TH:, :]
        diff = np.abs(droi.astype(np.int16) - bg_r.astype(np.int16))
        mask = np.any(diff > 18, axis=2)
        blend = cv2.addWeighted(droi, 0.85, roi, 0.15, 0)
        roi[mask] = blend[mask]

        # ── Real-time AI Vision Doodle Classification ─────────────────────────
        ai_doodle_label, ai_doodle_conf = canvas.check_ai_doodle()

        # ── Live Overlays ─────────────────────────────────────────────────────
        draw_sym_guide(frame, canvas.symmetry_mode, TH)

        # 4x Magnifier Loupe during Eyedropper
        if (paint_tool == "eyedrop" or g0 == gestures.GESTURE_EYEDROP) and tip0:
            draw_magnifier_loupe(frame, canvas._strokes, cp0, tip0)

        # Freeform Lasso live path
        if paint_tool == "lasso" and lasso_drawing and len(lasso_points) > 1:
            for i in range(len(lasso_points) - 1):
                p1 = (lasso_points[i][0], lasso_points[i][1] + TH)
                p2 = (lasso_points[i + 1][0], lasso_points[i + 1][1] + TH)
                cv2.line(frame, p1, p2, (220, 60, 180), 2, lineType=cv2.LINE_AA)

        # Fingertip Reticle & Particles
        draw_tip(frame, tip0, active_color, g0, brush_size)
        if tip1:
            cv2.circle(frame, tip1, 10, (200, 200, 80), 2)
            cv2.circle(frame, tip1, 3, (200, 200, 80), -1)

        # Text mode prompt
        if canvas.text_mode:
            cv2.putText(frame, "TEXT MODE: Type text then press ENTER", (TH, TH + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, config.ACCENT2, 2, cv2.LINE_AA)

        # Particle systems
        canvas.update_confetti(frame)
        toast.draw(frame)

        # ── FPS ───────────────────────────────────────────────────────────────
        now = time.time(); fps = 0.9 * fps + 0.1 / (now - prev_time + 1e-9); prev_time = now

        # Mode label
        if canvas.text_mode: mode_label = "TEXT"
        elif paint_tool == "select": mode_label = "SELECT"
        elif paint_tool == "lasso": mode_label = "LASSO"
        elif paint_tool == "fill" or g0 == gestures.GESTURE_FILL: mode_label = "FILL"
        elif paint_tool == "eyedrop" or g0 == gestures.GESTURE_EYEDROP: mode_label = "EYEDROP"
        elif g0 == gestures.GESTURE_ERASER: mode_label = "ERASER"
        elif g0 == gestures.GESTURE_DRAW: mode_label = "DRAW"
        elif g0 == gestures.GESTURE_FIST: mode_label = "PAUSE"
        elif g0 == gestures.GESTURE_PINCH: mode_label = "PINCH"
        else: mode_label = "IDLE"

        # Assemble UI Frame
        toolbar = build_toolbar(
            W,
            active_color_name=color_name,
            color1=color1,
            color2=color2,
            active_color_slot=active_slot,
            is_eraser=is_eraser,
            active_brush=canvas.brush_mode,
            active_shape=canvas.shape_tool,
            shape_fill_mode=canvas.shape_fill_mode,
            active_paint_tool=paint_tool,
            active_sym=canvas.symmetry_mode,
            active_bg=canvas.bg_preset,
            rainbow=canvas.rainbow_mode,
            dark_mode=canvas.dark_mode,
            show_grid=canvas.show_gridlines,
            show_rulers=canvas.show_rulers,
            trans_sel=canvas.transparent_sel,
            auto_snap=auto_snap,
            holo_active=holo_active,
            pressure_active=pressure_active,
            current_color=active_color,
            brush_size=brush_size,
            mode_label=mode_label,
            fps=fps,
            undo_count=canvas.undo_count,
            redo_count=canvas.redo_count,
            polygon_sides=canvas.polygon_sides,
            text_mode=canvas.text_mode,
            sel_active=canvas.get_selection_rect() is not None,
            ai_doodle_label=ai_doodle_label,
            ai_doodle_conf=ai_doodle_conf,
        )
        combined = np.vstack([toolbar, frame])
        cv2.imshow("AI Air Draw — Revolutionary MS Paint AI Edition", combined)

        # ── Keyboard Shortcuts ────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF

        if canvas.text_mode:
            if key == 13: canvas.commit_text(); toast.show("Text placed!", config.ACCENT)
            elif key == 27: canvas.cancel_text(); toast.show("Text cancelled", (180, 100, 100))
            elif key == 8 and canvas.text_buffer: canvas.text_buffer = canvas.text_buffer[:-1]
            elif 32 <= key <= 126: canvas.text_buffer += chr(key)
            continue

        if key in (ord("q"), 27): break
        elif key == 9:  # TAB key: switch active color slot
            active_slot = 2 if active_slot == 1 else 1
            toast.show(f"Color {active_slot} Active", color1 if active_slot == 1 else color2)
        elif key == ord("c"): canvas.clear(); toast.show("Cleared!", (80, 80, 255))
        elif key == ord("z"):
            if canvas.undo(): toast.show("Undo", (200, 200, 255))
        elif key == ord("x"):
            if canvas.get_selection_rect():
                canvas.cut_selection(); toast.show("Cut", (200, 200, 255))
            elif canvas.redo(): toast.show("Redo", (200, 255, 200))
        elif key == ord("v"):
            sr = canvas.get_selection_rect()
            if sr and canvas._sel_buf is not None:
                canvas.paste_at(cp0[0] if cp0 else sr[0], cp0[1] if cp0 else sr[1])
                toast.show("Pasted", (200, 255, 200))
            else:
                canvas.invert_colors(); toast.show("Inverted", (200, 200, 100))
        elif key == 127 or key == 8:
            if canvas.get_selection_rect():
                canvas.clear_selection_area(); toast.show("Selection deleted", (200, 100, 100))
        elif key == ord("s"): path = canvas.save(); toast.show("Saved!", (0, 230, 80))
        elif key == ord("l"):
            path = _open_file_dialog()
            if path and canvas.open_image(path): toast.show("Image loaded!", (0, 230, 80))
        elif key == ord("e"): is_eraser = True; paint_tool = ""; toast.show("Eraser ON", (100, 100, 255))
        elif key == ord("d"): canvas.toggle_dark_mode(); toast.show("Canvas toggled", (200, 180, 100))
        elif key == ord("h"): show_hud = not show_hud
        elif key == ord("n"):
            canvas.rainbow_mode = not canvas.rainbow_mode
            toast.show("Rainbow ON" if canvas.rainbow_mode else "Rainbow OFF", (255, 80, 200))
        elif key == ord("m"):
            modes = config.BRUSH_MODES
            canvas.brush_mode = modes[(modes.index(canvas.brush_mode) + 1) % len(modes)]
            toast.show(f"Brush: {canvas.brush_mode.upper()}", config.ACCENT)
        elif key == ord("y"):
            syms = config.SYMMETRY_MODES
            canvas.symmetry_mode = syms[(syms.index(canvas.symmetry_mode) + 1) % len(syms)]
            toast.show(f"Sym: {canvas.symmetry_mode.upper()}", (200, 150, 255))
        elif key == ord("k"):
            r = canvas.cycle_bg(); toast.show(f"BG: {r.upper()}", config.ACCENT)
        # AI Shortcuts
        elif key == ord("b"):
            auto_snap = not auto_snap
            canvas.auto_beautify = auto_snap
            toast.show("AI Auto-Beautifier ON" if auto_snap else "AI Auto-Beautifier OFF", config.BUTTON_AI_COLOR[::-1])
        elif key == ord("i") or key == ord("f"):
            if key == ord("i"): paint_tool = "eyedrop"
            else: paint_tool = "fill"
            canvas.shape_tool = "freehand"
            toast.show(f"Tool: {paint_tool.upper()}", config.ACCENT)
        elif key == ord("t"):
            paint_tool = "text"; canvas.shape_tool = "freehand"
            toast.show("TEXT: Aim finger, DRAW to place", config.ACCENT2)
        elif key == ord("u"):
            paint_tool = "select"; canvas.shape_tool = "freehand"
            toast.show("Select tool", (255, 80, 150))
        elif key == ord("w"):
            if canvas.crop_to_selection(): toast.show("Cropped to Selection!", config.ACCENT)
        elif key == ord("g"):
            canvas.show_gridlines = not canvas.show_gridlines
            toast.show("Gridlines toggled", (180, 180, 180))
        # Brush size
        elif key in (ord("+"), ord("=")):
            brush_size = min(brush_size + 2, config.MAX_BRUSH_SIZE)
        elif key == ord("-"):
            brush_size = max(brush_size - 2, config.MIN_BRUSH_SIZE)

    cap.release(); tracker.release(); cv2.destroyAllWindows()
    print("[INFO] AI Air Draw closed cleanly.")


if __name__ == "__main__":
    main()
