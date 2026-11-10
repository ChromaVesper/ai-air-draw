"""
main.py  —  AI Air Draw  •  Easy & Revolutionary MS Paint AI Edition
===================================================================
Engineered for effortless, natural, fatigue-free digital painting:
- 🤏 PINCH-TO-DRAW: Touch thumb + index together to ink; release to hover!
- ⏱️ DWELL-CLICK: Hover over any button for 0.35s to activate (no accidental clicks!)
- 🧲 MAGNETIC SNAP: Cursor stabilizes on buttons for effortless targeting
- 🎨 CATEGORY TABS: Organized into BRUSHES, SHAPES, AI STUDIO, TRANSFORM
- ✌️ PEACE ERASER: Immediate two-finger eraser gesture
- 🤖 REAL-TIME AI: Instant doodle recognition & auto-shape beautifier
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
    import subprocess
    cmd = """osascript -e 'set theFile to choose file with prompt "Open Image for AI Air Draw:" of type {"public.image"}' -e 'POSIX path of theFile'"""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            path = res.stdout.strip()
            return path if path else None
    except Exception:
        pass
    return None

# ── Dimensions ────────────────────────────────────────────────────────────────
R1H = config.TOOLBAR_ROW1_H   # 56
R2H = config.TOOLBAR_ROW2_H   # 50
TH  = config.TOOLBAR_HEIGHT   # 106

BTN_W = config.BTN_W          # 68
BTN_H = config.BTN_H          # 42
BTN_M = config.BTN_M          # 4

# ── Toast Notifications ───────────────────────────────────────────────────────
class Toast:
    DURATION = 2.0

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
        sc, th = 0.72, 2
        (tw, _), _ = cv2.getTextSize(self._msg, cv2.FONT_HERSHEY_SIMPLEX, sc, th)
        x, y = (w - tw) // 2, h - 45
        ov = frame.copy()
        cv2.rectangle(ov, (x - 16, y - 26), (x + tw + 16, y + 10), (15, 15, 25), -1)
        cv2.addWeighted(ov, alpha * 0.85, frame, 1.0 - alpha * 0.85, 0, frame)
        ov2 = frame.copy()
        cv2.putText(ov2, self._msg, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), th + 1, cv2.LINE_AA)
        cv2.putText(ov2, self._msg, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, self._color, th, cv2.LINE_AA)
        cv2.addWeighted(ov2, alpha, frame, 1.0 - alpha, 0, frame)


# ── Rounded Rectangle & Button Graphics ───────────────────────────────────────

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
        bg = (24, 24, 34); tc = (75, 75, 85)
    elif active and group == "tab":
        bg = config.ACCENT; tc = (15, 15, 25)
    elif active and group == "tool":
        bg = config.BUTTON_TOOL_COLOR; tc = (255, 235, 100)
    elif active and group == "ai":
        bg = config.BUTTON_AI_COLOR; tc = (255, 220, 255)
    elif active:
        bg = config.BUTTON_ACTIVE_COLOR; tc = (255, 225, 80)
    elif group == "tab":
        bg = (40, 40, 58); tc = (200, 200, 220)
    elif group == "ai":
        bg = (55, 30, 68); tc = (220, 180, 245)
    else:
        bg = config.BUTTON_INACTIVE_COLOR; tc = config.BUTTON_TEXT_COLOR

    _rr(img, x, y, x + w, y + h, bg, r=6)
    _rr(img, x, y, x + w, y + h, (80, 80, 95), r=6, filled=False)
    s = 0.36
    (tw, th_), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, s, 1)
    tx = x + (w - tw) // 2; ty = y + (h + th_) // 2
    cv2.putText(img, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, s, tc, 1, cv2.LINE_AA)


# ── Active Hit-Target Registry ────────────────────────────────────────────────
_ACTIVE_BUTTONS: List[Tuple[int, int, int, int, str]] = []

def register_btn(x, y, w, h, action_code):
    _ACTIVE_BUTTONS.append((x, y, x + w, y + h, action_code))


# ── Toolbar Builder ───────────────────────────────────────────────────────────

def build_toolbar(
    W: int,
    active_color_name: str,
    color1: Tuple[int, int, int],
    is_eraser: bool,
    active_tab: str,
    active_brush: str,
    active_shape: str,
    active_paint_tool: str,
    draw_style: str,
    auto_snap: bool,
    holo_active: bool,
    pressure_active: bool,
    brush_size: int,
    mode_label: str,
    fps: float,
    undo_count: int,
    redo_count: int,
    ai_doodle_label: str,
    ai_doodle_conf: int,
) -> np.ndarray:

    global _ACTIVE_BUTTONS
    _ACTIVE_BUTTONS.clear()

    tb = np.zeros((TH, W, 3), np.uint8)
    tb[:R1H] = config.TOOLBAR_BG_COLOR
    tb[R1H:] = config.TOOLBAR_R2_BG
    cv2.line(tb, (0, R1H), (W, R1H), (55, 55, 75), 1)

    # ── ROW 1: Logo + AI Guesser + Primary Actions + Quick Colors ─────────────
    cv2.putText(tb, "AI AIR DRAW", (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.50, config.ACCENT, 2, cv2.LINE_AA)
    cv2.putText(tb, "EASY STUDIO", (8, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (140, 140, 160), 1, cv2.LINE_AA)

    # AI Real-time Doodle Classifier badge
    ai_x = 135; ai_w = 145
    _rr(tb, ai_x, 7, ai_x + ai_w, 47, (42, 22, 52), r=6)
    _rr(tb, ai_x, 7, ai_x + ai_w, 47, (160, 60, 180), r=6, filled=False)
    cv2.putText(tb, "AI GUESS", (ai_x + 8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (215, 165, 255), 1, cv2.LINE_AA)
    conf_str = f"({ai_doodle_conf}%)" if ai_doodle_conf > 0 else ""
    cv2.putText(tb, f"{ai_doodle_label} {conf_str}", (ai_x + 8, 39), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (255, 245, 255), 1, cv2.LINE_AA)

    # Main Action Quick-Buttons: Draw, Erase, Fill, Clear, Save
    bx = ai_x + ai_w + 10
    quick_tools = [
        ("DRAW", "tool:draw", (not is_eraser and active_paint_tool == "" and active_shape == "freehand")),
        ("ERASE", "tool:erase", is_eraser),
        ("FILL", "paint:fill", active_paint_tool == "fill"),
        ("CLEAR", "action:clr", False),
        ("SAVE", "action:save", False),
    ]
    for lbl, code, act in quick_tools:
        _btn(tb, bx, 7, BTN_W, BTN_H, lbl, active=act, group="tool")
        register_btn(bx, 7, BTN_W, BTN_H, code)
        bx += BTN_W + BTN_M

    # Draw Mode Toggle: Pinch vs Point
    pinch_lbl = "🤏PINCH" if draw_style == "PINCH" else "☝️POINT"
    _btn(tb, bx, 7, BTN_W + 6, BTN_H, pinch_lbl, active=True, group="tab")
    register_btn(bx, 7, BTN_W + 6, BTN_H, "toggle:draw_style")
    bx += BTN_W + 6 + BTN_M + 6

    # 10 Big Quick Color Discs
    for name, bgr in config.QUICK_COLORS:
        is_cur = (name == active_color_name) and not is_eraser
        cy = R1H // 2
        r = 15 if is_cur else 13
        if is_cur:
            cv2.circle(tb, (bx + 14, cy), r + 3, config.ACCENT, 2, lineType=cv2.LINE_AA)
        cv2.circle(tb, (bx + 14, cy), r, bgr, -1, lineType=cv2.LINE_AA)
        cv2.circle(tb, (bx + 14, cy), r, (100, 100, 100) if name in ("WHITE", "YELLOW") else (40, 40, 40), 1)
        register_btn(bx, 7, 28, BTN_H, f"color:{name}")
        bx += 31

    # Right side: Status & FPS
    rx = W - 170
    mc = (0, 200, 80) if "DRAW" in mode_label else (0, 100, 255) if "ERASE" in mode_label else (255, 140, 30)
    _rr(tb, rx, 8, rx + 90, 46, mc, r=6)
    cv2.putText(tb, mode_label, (rx + 8, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(tb, f"FPS {fps:4.1f}", (rx + 96, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.34, config.FPS_TEXT_COLOR, 1, cv2.LINE_AA)

    # ── ROW 2: Category Tabs & Content Panels ─────────────────────────────────
    y2 = R1H + (R2H - BTN_H) // 2
    tx = 8

    # Category Tab Selectors
    tabs = [
        ("BRUSHES", "tab:BRUSHES"),
        ("SHAPES", "tab:SHAPES"),
        ("AI STUDIO", "tab:AI_TOOLS"),
        ("TRANSFORM", "tab:TRANSFORM"),
    ]
    for tname, tcode in tabs:
        act = (active_tab == tname.replace(" ", "_"))
        _btn(tb, tx, y2, 82, BTN_H, tname, active=act, group="tab")
        register_btn(tx, y2, 82, BTN_H, tcode)
        tx += 82 + BTN_M

    tx += 10
    cv2.line(tb, (tx, R1H + 6), (tx, TH - 6), (65, 65, 80), 1)
    tx += 14

    # Tab Content
    if active_tab == "BRUSHES":
        for lbl, mode in zip(config.BRUSH_LABELS, config.BRUSH_MODES):
            act = (mode == active_brush and not is_eraser)
            _btn(tb, tx, y2, 58, BTN_H, lbl, active=act)
            register_btn(tx, y2, 58, BTN_H, f"brush:{mode}")
            tx += 58 + BTN_M

    elif active_tab == "SHAPES":
        for lbl, shape in zip(config.SHAPE_LABELS, config.SHAPE_TOOLS):
            act = (shape == active_shape and not is_eraser)
            _btn(tb, tx, y2, 54, BTN_H, lbl, active=act)
            register_btn(tx, y2, 54, BTN_H, f"shape:{shape}")
            tx += 54 + BTN_M

    elif active_tab == "AI_TOOLS":
        ai_buttons = [
            ("🤖SNAP", "ai:ai_snap", auto_snap),
            ("✨INPNT", "ai:ai_inpaint", False),
            ("📖BOOK", "ai:ai_book", False),
            ("🔮HOLO", "ai:ai_holo", holo_active),
            ("🎚️PRES", "ai:ai_pressure", pressure_active),
        ]
        for lbl, code, act in ai_buttons:
            _btn(tb, tx, y2, 70, BTN_H, lbl, active=act, group="ai")
            register_btn(tx, y2, 70, BTN_H, code)
            tx += 70 + BTN_M

    elif active_tab == "TRANSFORM":
        for lbl, code in [
            ("FLP↔", "transform:flph"),
            ("FLP↕", "transform:flpv"),
            ("ROT↻", "transform:rot"),
            ("INVRT", "transform:invt"),
            ("GRAY", "transform:gray"),
            ("OPEN", "action:open"),
            ("UNDO", "action:undo"),
            ("REDO", "action:redo"),
        ]:
            _btn(tb, tx, y2, 58, BTN_H, lbl)
            register_btn(tx, y2, 58, BTN_H, code)
            tx += 58 + BTN_M

    return tb


# ── Magnetic Dwell Hit Testing ────────────────────────────────────────────────

def find_hit_button(tx: int, ty: int) -> Optional[Tuple[Tuple[int, int], str]]:
    """Finds if (tx, ty) is inside or near any registered button."""
    for x1, y1, x2, y2, code in _ACTIVE_BUTTONS:
        if x1 <= tx <= x2 and y1 <= ty <= y2:
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
            return (center, code)
    return None


# ── On-Screen Friendly Gesture Card ───────────────────────────────────────────

def draw_help_card(frame: np.ndarray, draw_style: str):
    h, w = frame.shape[:2]
    cw, ch = 230, 115
    cx, cy = 10, h - ch - 10
    ov = frame.copy()
    cv2.rectangle(ov, (cx, cy), (cx + cw, cy + ch), (15, 15, 24), -1)
    cv2.addWeighted(ov, 0.72, frame, 0.28, 0, frame)
    cv2.rectangle(frame, (cx, cy), (cx + cw, cy + ch), (55, 55, 75), 1)

    draw_hint = "🤏 Pinch fingers = DRAW" if draw_style == "PINCH" else "☝️ Point index = DRAW"
    hints = [
        ("EASY GESTURES", config.ACCENT, 0.38, 1),
        (draw_hint, (0, 235, 100), 0.34, 1),
        ("✌️ Two fingers = ERASER", (80, 160, 255), 0.34, 1),
        ("🖐 Open hand = MOVE / HOVER", (200, 200, 220), 0.34, 1),
        ("👍 Thumbs up = SAVE", (255, 200, 50), 0.34, 1),
    ]
    cur_y = cy + 18
    for txt, col, sc, th in hints:
        cv2.putText(frame, txt, (cx + 8, cur_y), cv2.FONT_HERSHEY_SIMPLEX, sc, col, th, cv2.LINE_AA)
        cur_y += 22


# ── Main Event Loop ───────────────────────────────────────────────────────────

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

    # State
    color_name = config.DEFAULT_COLOR_NAME
    color1 = config.COLORS[color_name]
    is_eraser = False
    active_tab = "BRUSHES"
    active_paint_tool = ""
    draw_style = config.DEFAULT_DRAW_STYLE   # "PINCH" or "POINT"
    auto_snap = True
    holo_active = False
    pressure_active = True

    brush_size = config.DEFAULT_BRUSH_SIZE
    fps = 0.0; prev_time = time.time()

    # Dwell Click State
    hover_code: Optional[str] = None
    hover_start_time: float = 0.0
    DWELL_TIME = config.DWELL_CLICK_TIME

    # Gestures
    prev_g = gestures.GESTURE_IDLE
    open_t = 0.0; thumb_t = 0.0
    OPEN_HOLD = 0.65; THUMB_HOLD = 0.40

    shape_drawing = False

    print("[INFO] AI Air Draw Easy Studio Ready!")

    while True:
        ret, frame = cap.read()
        if not ret: continue
        frame = cv2.flip(frame, 1)

        tracker.process_frame(frame)
        lm0 = tracker.get_landmarks(0)
        tip0_raw = tracker.get_index_fingertip(hand_idx=0)
        thumb0_raw = tracker.get_landmark_pixel(4, hand_idx=0)

        g0 = gestures.recognise_gesture(lm0, draw_style=draw_style)

        # Cursor position: center between thumb & index when pinching, else index tip
        if g0 == gestures.GESTURE_PINCH_DRAW and thumb0_raw and tip0_raw:
            tip0 = ((thumb0_raw[0] + tip0_raw[0]) // 2, (thumb0_raw[1] + tip0_raw[1]) // 2)
        else:
            tip0 = tip0_raw

        pressure = gestures.get_finger_pressure(lm0) if pressure_active else 1.0

        # ── Drawing Mode Trigger ──────────────────────────────────────────────
        if draw_style == "PINCH":
            is_inking = (g0 == gestures.GESTURE_PINCH_DRAW)
        else:
            is_inking = (g0 == gestures.GESTURE_DRAW)

        # Eraser mode (Two fingers ✌️)
        if g0 == gestures.GESTURE_ERASER:
            is_eraser = True
        elif is_inking:
            is_eraser = False

        # Open Hand Clear
        if g0 == gestures.GESTURE_OPEN_HAND:
            if prev_g != gestures.GESTURE_OPEN_HAND: open_t = time.time()
            elif time.time() - open_t >= OPEN_HOLD:
                canvas.clear(); open_t = time.time() + 9999; toast.show("Canvas cleared!", (80, 80, 255))

        # Thumbs up Save
        if g0 == gestures.GESTURE_THUMBS_UP:
            if prev_g != gestures.GESTURE_THUMBS_UP: thumb_t = time.time()
            elif time.time() - thumb_t >= THUMB_HOLD:
                path = canvas.save(); thumb_t = time.time() + 9999
                toast.show("Saved!", (0, 230, 80))

        prev_g = g0

        # ── Dwell-Click on Toolbar Buttons ────────────────────────────────────
        dwell_progress = 0.0
        dwell_pt = tip0

        if tip0 and tip0[1] < TH:
            hit = find_hit_button(tip0[0], tip0[1])
            if hit:
                btn_center, code = hit
                dwell_pt = btn_center
                if hover_code != code:
                    hover_code = code
                    hover_start_time = time.time()
                else:
                    elapsed = time.time() - hover_start_time
                    dwell_progress = min(1.0, elapsed / DWELL_TIME)

                    if dwell_progress >= 1.0:
                        # TRIGGER BUTTON ACTION
                        hover_start_time = time.time() + 9999   # Lock until move away
                        dwell_progress = 0.0

                        if code.startswith("color:"):
                            cname = code[6:]
                            color_name = cname
                            color1 = config.COLORS[cname]
                            is_eraser = False; active_paint_tool = ""
                            toast.show(f"Color: {cname}", color1)
                        elif code == "tool:draw":
                            is_eraser = False; active_paint_tool = ""; canvas.shape_tool = "freehand"
                            toast.show("Pen Selected", color1)
                        elif code == "tool:erase":
                            is_eraser = True; active_paint_tool = ""
                            toast.show("Eraser Selected", (100, 100, 255))
                        elif code == "paint:fill":
                            active_paint_tool = "fill"; is_eraser = False; canvas.shape_tool = "freehand"
                            toast.show("Bucket Fill Mode", color1)
                        elif code == "toggle:draw_style":
                            draw_style = "POINT" if draw_style == "PINCH" else "PINCH"
                            toast.show(f"Draw Mode: {draw_style}", config.ACCENT)
                        elif code.startswith("tab:"):
                            active_tab = code[4:]
                            toast.show(f"Tab: {active_tab}", config.ACCENT2)
                        elif code.startswith("brush:"):
                            canvas.brush_mode = code[6:]
                            is_eraser = False; active_paint_tool = ""; canvas.shape_tool = "freehand"
                            toast.show(f"Brush: {canvas.brush_mode.upper()}", config.ACCENT)
                        elif code.startswith("shape:"):
                            canvas.shape_tool = code[6:]
                            is_eraser = False; active_paint_tool = ""
                            toast.show(f"Shape: {canvas.shape_tool.upper()}", config.ACCENT2)
                        elif code.startswith("ai:"):
                            aik = code[3:]
                            if aik == "ai_snap":
                                auto_snap = not auto_snap
                                canvas.auto_beautify = auto_snap
                                toast.show("AI Auto-Snap ON" if auto_snap else "AI Auto-Snap OFF", config.BUTTON_AI_COLOR[::-1])
                            elif aik == "ai_inpaint":
                                if canvas.magic_inpaint_selection(): toast.show("AI Inpainted!", (240, 140, 255))
                                else: toast.show("Select an area first", (80, 80, 255))
                            elif aik == "ai_book":
                                canvas.convert_to_coloring_book()
                                toast.show("Coloring Book Created!", config.ACCENT)
                            elif aik == "ai_holo":
                                holo_active = not holo_active
                                toast.show("Holo Palette ON" if holo_active else "Holo Palette OFF", (220, 120, 255))
                            elif aik == "ai_pressure":
                                pressure_active = not pressure_active
                                toast.show("3D Pressure ON" if pressure_active else "Pressure OFF", config.ACCENT2)
                        elif code.startswith("transform:"):
                            tr = code[10:]
                            if tr == "flph": canvas.flip_horizontal(); toast.show("Flipped ↔", (150, 200, 255))
                            elif tr == "flpv": canvas.flip_vertical(); toast.show("Flipped ↕", (150, 200, 255))
                            elif tr == "rot": canvas.rotate_90(); toast.show("Rotated ↻", (150, 200, 255))
                            elif tr == "invt": canvas.invert_colors(); toast.show("Inverted", (200, 200, 100))
                            elif tr == "gray": canvas.grayscale(); toast.show("Grayscale", (180, 180, 180))
                        elif code.startswith("action:"):
                            act = code[7:]
                            if act == "clr": canvas.clear(); toast.show("Cleared!", (80, 80, 255))
                            elif act == "save": path = canvas.save(); toast.show("Saved!", (0, 230, 80))
                            elif act == "open":
                                path = _open_file_dialog()
                                if path and canvas.open_image(path): toast.show("Image loaded!", (0, 230, 80))
                            elif act == "undo":
                                if canvas.undo(): toast.show("Undo", (200, 200, 255))
                            elif act == "redo":
                                if canvas.redo(): toast.show("Redo", (200, 255, 200))
            else:
                hover_code = None; dwell_progress = 0.0
        else:
            hover_code = None; dwell_progress = 0.0

        # ── Canvas Interaction ────────────────────────────────────────────────
        cp0 = (tip0[0], tip0[1] - TH) if (tip0 and tip0[1] > TH) else None
        drawing_active = (is_inking or is_eraser) and (cp0 is not None)

        if active_paint_tool == "fill" and is_inking and cp0:
            canvas.flood_fill(cp0[0], cp0[1], color1)
            toast.show("Bucket Filled!", color1)
            active_paint_tool = ""

        elif canvas.shape_tool != "freehand" and not is_eraser and active_paint_tool == "":
            if drawing_active and cp0:
                if not shape_drawing:
                    shape_drawing = True
                    canvas.begin_shape(cp0[0], cp0[1], color1, brush_size)
                else:
                    canvas.update_shape_preview(cp0[0], cp0[1])
            else:
                if shape_drawing:
                    canvas.commit_shape()
                shape_drawing = False

        else:
            if cp0:
                canvas.update(cp0[0], cp0[1], color1, brush_size, drawing_active, is_eraser, pressure=pressure)
            else:
                canvas.reset_previous_point()

        # ── Frame Blending & AI Check ─────────────────────────────────────────
        tracker.draw_all_landmarks(frame)

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

        ai_doodle_label, ai_doodle_conf = canvas.check_ai_doodle()

        # ── Cursor & Dwell Progress Graphic ───────────────────────────────────
        if tip0:
            c = (80, 80, 255) if is_eraser else color1
            # Reticle
            cv2.circle(frame, tip0, max(brush_size + 4, 12), c, 2, lineType=cv2.LINE_AA)
            cv2.circle(frame, tip0, 4, c, -1)

            # Dwell progress circular bar
            if dwell_progress > 0.0 and dwell_pt:
                dr = 24
                ang = int(dwell_progress * 360)
                cv2.ellipse(frame, dwell_pt, (dr, dr), -90, 0, ang, config.ACCENT, 4, lineType=cv2.LINE_AA)

        # Helpful on-screen gesture card
        draw_help_card(frame, draw_style)
        canvas.update_confetti(frame)
        toast.draw(frame)

        # Mode label
        if is_eraser: mode_label = "ERASER"
        elif is_inking: mode_label = "DRAW"
        elif active_paint_tool == "fill": mode_label = "FILL"
        else: mode_label = "HOVER"

        # Assemble UI
        toolbar = build_toolbar(
            W,
            active_color_name=color_name,
            color1=color1,
            is_eraser=is_eraser,
            active_tab=active_tab,
            active_brush=canvas.brush_mode,
            active_shape=canvas.shape_tool,
            active_paint_tool=active_paint_tool,
            draw_style=draw_style,
            auto_snap=auto_snap,
            holo_active=holo_active,
            pressure_active=pressure_active,
            brush_size=brush_size,
            mode_label=mode_label,
            fps=fps,
            undo_count=canvas.undo_count,
            redo_count=canvas.redo_count,
            ai_doodle_label=ai_doodle_label,
            ai_doodle_conf=ai_doodle_conf,
        )
        combined = np.vstack([toolbar, frame])
        cv2.imshow("AI Air Draw — Easy Studio", combined)

        now = time.time(); fps = 0.9 * fps + 0.1 / (now - prev_time + 1e-9); prev_time = now

        # Keyboard shortcuts
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27): break
        elif key == ord("c"): canvas.clear(); toast.show("Cleared!", (80, 80, 255))
        elif key == ord("z"):
            if canvas.undo(): toast.show("Undo", (200, 200, 255))
        elif key == ord("x"):
            if canvas.redo(): toast.show("Redo", (200, 255, 200))
        elif key == ord("s"): path = canvas.save(); toast.show("Saved!", (0, 230, 80))
        elif key == ord("e"): is_eraser = True; toast.show("Eraser ON", (100, 100, 255))
        elif key == ord("d"): is_eraser = False; toast.show("Draw ON", color1)
        elif key == ord("b"):
            auto_snap = not auto_snap
            canvas.auto_beautify = auto_snap
            toast.show("AI Auto-Snap ON" if auto_snap else "AI Auto-Snap OFF", config.BUTTON_AI_COLOR[::-1])
        elif key == ord("p"):
            draw_style = "POINT" if draw_style == "PINCH" else "PINCH"
            toast.show(f"Draw Mode: {draw_style}", config.ACCENT)
        elif key in (ord("+"), ord("=")): brush_size = min(brush_size + 2, config.MAX_BRUSH_SIZE)
        elif key == ord("-"): brush_size = max(brush_size - 2, config.MIN_BRUSH_SIZE)

    cap.release(); tracker.release(); cv2.destroyAllWindows()
    print("[INFO] Studio closed cleanly.")


if __name__ == "__main__":
    main()
