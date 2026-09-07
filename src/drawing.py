"""
drawing.py  —  AI Air Draw  •  Revolutionary MS Paint AI Edition
===============================================================
Comprehensive drawing engine with:
- MS Paint tools: Flood fill, Eyedropper, Text, Rect Select, Lasso Select
- 16 Shapes with Outline / Solid Fill / Both modes
- 9 Brushes (Pencil, Callig, Pen, Marker, Crayon, Spray, Drip, Neon, Sparkle)
- Color 1 (Foreground) & Color 2 (Background/Fill)
- AI Auto-Shape Snapping, Magic Inpainting, Coloring Book Line-Art
- Gridlines, Rulers, Transparent Selection, Crop-to-Selection
- Symmetry (Mirror-H, Mirror-V, Quad, Radial-4, Radial-8, Radial-12)
- Undo/Redo stack (40 steps), Confetti particle system
"""

import cv2
import numpy as np
import random
import time
import math
import os
from typing import Tuple, Optional, List, Dict, Any

import config
import ai_engine


# ── Particle Engine ───────────────────────────────────────────────────────────

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "color", "size", "decay", "gravity", "alpha")

    def __init__(self, x, y, color, size=2, vx=0.0, vy=0.0, decay=0.04, gravity=0.15):
        self.x = float(x); self.y = float(y)
        self.vx = float(vx); self.vy = float(vy)
        self.color = color; self.size = size
        self.decay = decay; self.gravity = gravity
        self.alpha = 1.0

    def update(self) -> bool:
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.alpha -= self.decay
        return self.alpha > 0.0

    def draw(self, frame: np.ndarray) -> None:
        if self.alpha <= 0: return
        h, w = frame.shape[:2]
        ix, iy = int(self.x), int(self.y)
        if 0 <= ix < w and 0 <= iy < h:
            c = tuple(int(ch * self.alpha) for ch in self.color)
            cv2.circle(frame, (ix, iy), max(1, int(self.size * self.alpha)), c, -1)


def _confetti_burst(cx: int, cy: int, count: int) -> List[Particle]:
    cols = list(config.COLORS.values())
    particles = []
    for _ in range(count):
        ang = random.uniform(0, 2 * math.pi)
        spd = random.uniform(3.5, 14.0)
        particles.append(Particle(
            cx, cy,
            color=random.choice(cols),
            size=random.randint(3, 7),
            vx=math.cos(ang) * spd,
            vy=math.sin(ang) * spd - random.uniform(2.0, 7.0),
            decay=random.uniform(0.015, 0.035),
            gravity=0.28
        ))
    return particles


# ── Background Presets ────────────────────────────────────────────────────────

def _bg_white(w, h):     return np.full((h, w, 3), 255, np.uint8)
def _bg_black(w, h):     return np.full((h, w, 3), 18,  np.uint8)

def _bg_grid(w, h):
    img = np.full((h, w, 3), 245, np.uint8)
    for x in range(0, w, 35): cv2.line(img, (x, 0), (x, h), (218, 218, 218), 1)
    for y in range(0, h, 35): cv2.line(img, (0, y), (w, y), (218, 218, 218), 1)
    return img

def _bg_dotgrid(w, h):
    img = np.full((h, w, 3), 240, np.uint8)
    for x in range(0, w, 28):
        for y in range(0, h, 28):
            img[y, x] = (165, 165, 165)
    return img

def _bg_starfield(w, h):
    img = np.full((h, w, 3), 10, np.uint8)
    rng = random.Random(42)
    for _ in range(350):
        sx = rng.randint(0, w - 1); sy = rng.randint(0, h - 1)
        b = rng.randint(140, 255)
        cv2.circle(img, (sx, sy), rng.choice([1, 1, 2]), (b, b, b), -1)
    return img

def _bg_blueprint(w, h):
    img = np.full((h, w, 3), (120, 50, 15), np.uint8)
    for x in range(0, w, 25): cv2.line(img, (x, 0), (x, h), (145, 75, 30), 1)
    for y in range(0, h, 25): cv2.line(img, (0, y), (w, y), (145, 75, 30), 1)
    for x in range(0, w, 100): cv2.line(img, (x, 0), (x, h), (175, 105, 50), 1)
    for y in range(0, h, 100): cv2.line(img, (0, y), (w, y), (175, 105, 50), 1)
    return img

def _bg_canvas(w, h):
    # Textured warm artist parchment paper
    img = np.full((h, w, 3), (225, 238, 245), np.uint8)
    rng = np.random.RandomState(1337)
    noise = rng.randint(-12, 13, (h, w, 3), dtype=np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

_BG_FACTORIES = {
    "white": _bg_white, "black": _bg_black, "grid": _bg_grid,
    "dotgrid": _bg_dotgrid, "starfield": _bg_starfield,
    "blueprint": _bg_blueprint, "canvas": _bg_canvas,
}


# ─────────────────────────────────────────────────────────────────────────────
# DrawingCanvas
# ─────────────────────────────────────────────────────────────────────────────

class DrawingCanvas:
    def __init__(self, width: int, height: int, dark_mode: bool = False) -> None:
        self.width  = width
        self.height = height
        self.dark_mode = dark_mode

        # Layers
        self._bg_preset = "black" if dark_mode else "white"
        self._bg = self._make_bg(self._bg_preset)
        self._strokes = self._bg.copy()

        # Undo / Redo
        self._undo: List[np.ndarray] = []
        self._redo: List[np.ndarray] = []

        # Brushes & Modes
        self.brush_mode = config.DEFAULT_BRUSH_MODE
        self.symmetry_mode = "none"
        self.rainbow_mode = False
        self._hue = 0.0

        # Colors
        self.color1 = config.COLORS[config.DEFAULT_COLOR_NAME]    # Primary
        self.color2 = config.COLORS[config.DEFAULT_COLOR2_NAME]   # Secondary / Fill
        self.active_color_slot = 1   # 1 or 2

        # Shapes & Fill mode
        self.shape_tool = config.DEFAULT_SHAPE
        self.shape_fill_mode = "outline"   # "outline", "fill", "both"
        self.polygon_sides = config.DEFAULT_POLYGON_SIDES
        self._shape_start: Optional[Tuple[int, int]] = None
        self._shape_preview_end: Optional[Tuple[int, int]] = None
        self._shape_color: Tuple[int, int, int] = (0, 0, 0)
        self._shape_size: int = config.DEFAULT_BRUSH_SIZE

        # Bézier Curve state (3-point quadratic Bézier)
        self._curve_phase = 0  # 0=idle, 1=dragging line, 2=bending curve
        self._curve_p0: Optional[Tuple[int, int]] = None
        self._curve_p1: Optional[Tuple[int, int]] = None  # control point
        self._curve_p2: Optional[Tuple[int, int]] = None

        # Text tool
        self.text_mode: bool = False
        self.text_buffer: str = ""
        self.text_anchor: Optional[Tuple[int, int]] = None
        self.text_color: Tuple[int, int, int] = (0, 0, 0)
        self.text_size: float = 1.2

        # Selection (Rectangular & Lasso)
        self._sel_rect: Optional[Tuple[int, int, int, int]] = None
        self._sel_buf: Optional[np.ndarray] = None
        self._sel_mask: Optional[np.ndarray] = None
        self.transparent_sel: bool = config.TRANSPARENT_SEL

        # Freeform Lasso tool
        self._lasso_active = False
        self._lasso_points: List[Tuple[int, int]] = []

        # View settings
        self.show_gridlines = config.SHOW_GRIDLINES
        self.show_rulers = config.SHOW_RULERS
        self.zoom_level = config.CANVAS_ZOOM

        # AI & Stroke history
        self.auto_beautify: bool = True
        self._active_stroke_points: List[Tuple[int, int]] = []
        self._last_ai_doodle_label: str = "✏️ Start Drawing..."
        self._last_ai_doodle_conf: int = 0
        self._last_ai_check_time: float = 0.0

        # Smoothing & Particles
        self._prev_point: Optional[Tuple[int, int]] = None
        self.confetti: List[Particle] = []
        self.drip_particles: List[Particle] = []

    # ── Background ────────────────────────────────────────────────────────────

    def _make_bg(self, preset: str) -> np.ndarray:
        fn = _BG_FACTORIES.get(preset, _bg_white)
        return fn(self.width, self.height)

    def _rebuild_bg(self) -> None:
        self._bg = self._make_bg(self._bg_preset)

    @property
    def bg_preset(self) -> str:
        return self._bg_preset

    def cycle_bg(self) -> str:
        self._push_undo()
        presets = config.BG_PRESETS
        idx = (presets.index(self._bg_preset) + 1) % len(presets)
        self._bg_preset = presets[idx]
        self._rebuild_bg()
        self._strokes = self._bg.copy()
        return self._bg_preset

    def set_bg(self, preset: str) -> None:
        if preset in _BG_FACTORIES:
            self._push_undo()
            self._bg_preset = preset
            self._rebuild_bg()
            self._strokes = self._bg.copy()

    def toggle_dark_mode(self) -> None:
        self.dark_mode = not self.dark_mode
        self.set_bg("black" if self.dark_mode else "white")

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def _push_undo(self) -> None:
        self._undo.append(self._strokes.copy())
        if len(self._undo) > config.MAX_UNDO_STEPS:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo: return False
        self._redo.append(self._strokes.copy())
        self._strokes = self._undo.pop()
        self.reset_previous_point()
        return True

    def redo(self) -> bool:
        if not self._redo: return False
        self._undo.append(self._strokes.copy())
        self._strokes = self._redo.pop()
        self.reset_previous_point()
        return True

    @property
    def undo_count(self) -> int: return len(self._undo)
    @property
    def redo_count(self) -> int: return len(self._redo)

    # ── Rainbow & Symmetry ────────────────────────────────────────────────────

    def _rainbow_color(self) -> Tuple[int, int, int]:
        self._hue = (self._hue + 1.8) % 180
        hsv = np.uint8([[[int(self._hue), 235, 245]]])
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
        return (int(bgr[0]), int(bgr[1]), int(bgr[2]))

    def _sym_pairs(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        mode = self.symmetry_mode
        if mode == "none":
            return [(p1, p2)]

        w, h = self.width, self.height
        cx, cy = w / 2.0, h / 2.0

        def rot(x: float, y: float, deg: float) -> Tuple[int, int]:
            rad = math.radians(deg)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            dx, dy = x - cx, y - cy
            return (int(cx + dx * cos_a - dy * sin_a), int(cy + dx * sin_a + dy * cos_a))

        x1, y1 = p1; x2, y2 = p2

        if mode == "mirror_h":
            return [(p1, p2), ((w - x1, y1), (w - x2, y2))]
        elif mode == "mirror_v":
            return [(p1, p2), ((x1, h - y1), (x2, h - y2))]
        elif mode == "quad":
            return [
                (p1, p2),
                ((w - x1, y1), (w - x2, y2)),
                ((x1, h - y1), (x2, h - y2)),
                ((w - x1, h - y1), (w - x2, h - y2)),
            ]
        elif mode == "radial_4":
            return [((rot(x1, y1, d)), (rot(x2, y2, d))) for d in (0, 90, 180, 270)]
        elif mode == "radial_8":
            return [((rot(x1, y1, d)), (rot(x2, y2, d))) for d in range(0, 360, 45)]
        elif mode == "radial_12":
            return [((rot(x1, y1, d)), (rot(x2, y2, d))) for d in range(0, 360, 30)]

        return [(p1, p2)]

    # ── 9 Brushes Implementation ──────────────────────────────────────────────

    def _pencil(self, p1, p2, color, size):
        # 1px sharp pixel-art stroke
        cv2.line(self._strokes, p1, p2, color, max(1, size // 3), lineType=cv2.LINE_4)

    def _callig(self, p1, p2, color, size):
        # Calligraphy chisel nib angled at 45 degrees
        nib_len = max(3, size * 2)
        dx = int(nib_len * 0.707)
        dy = int(nib_len * 0.707)
        pts1 = np.array([p1[0] - dx, p1[1] - dy, p1[0] + dx, p1[1] + dy], np.int32)
        pts2 = np.array([p2[0] - dx, p2[1] - dy, p2[0] + dx, p2[1] + dy], np.int32)
        quad = np.array([
            [p1[0] - dx, p1[1] - dy],
            [p1[0] + dx, p1[1] + dy],
            [p2[0] + dx, p2[1] + dy],
            [p2[0] - dx, p2[1] - dy]
        ], np.int32)
        cv2.fillConvexPoly(self._strokes, quad, color, lineType=cv2.LINE_AA)

    def _pen(self, p1, p2, color, size):
        cv2.line(self._strokes, p1, p2, color, size, lineType=cv2.LINE_AA)
        cv2.circle(self._strokes, p2, size // 2, color, -1, lineType=cv2.LINE_AA)

    def _marker(self, p1, p2, color, size):
        # Translucent highlighter
        s = max(8, size * 2)
        ov = self._strokes.copy()
        cv2.line(ov, p1, p2, color, s, lineType=cv2.LINE_AA)
        cv2.addWeighted(ov, 0.42, self._strokes, 0.58, 0, self._strokes)

    def _crayon(self, p1, p2, color, size):
        # Wax crayon / chalk with grainy textured stippling
        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        steps = max(1, int(dist / 2))
        for i in range(steps):
            t = i / steps
            cx = int(p1[0] + (p2[0] - p1[0]) * t)
            cy = int(p1[1] + (p2[1] - p1[1]) * t)
            for _ in range(max(2, size // 2)):
                rx = cx + random.randint(-size, size)
                ry = cy + random.randint(-size, size)
                if 0 <= rx < self.width and 0 <= ry < self.height:
                    cv2.circle(self._strokes, (rx, ry), 1, color, -1)

    def _spray(self, p2, color, size):
        count = max(12, size * 3)
        rad = max(4, size * 2)
        for _ in range(count):
            r = random.gauss(0, rad / 2.2)
            th = random.uniform(0, 2 * math.pi)
            sx = int(p2[0] + r * math.cos(th))
            sy = int(p2[1] + r * math.sin(th))
            if 0 <= sx < self.width and 0 <= sy < self.height:
                self._strokes[sy, sx] = color

    def _drip(self, p1, p2, color, size):
        # Normal stroke + gravity paint drips
        cv2.line(self._strokes, p1, p2, color, size, lineType=cv2.LINE_AA)
        if random.random() < 0.25:
            # Spawn a slow downward paint drip
            self.drip_particles.append(Particle(
                p2[0], p2[1], color, size=max(2, size // 2),
                vx=random.uniform(-0.3, 0.3), vy=random.uniform(0.8, 2.5),
                decay=0.012, gravity=0.08
            ))

    def _neon(self, p1, p2, color, size):
        core = tuple(min(255, int(c * 1.5 + 40)) for c in color)
        cv2.line(self._strokes, p1, p2, color, size + 8, lineType=cv2.LINE_AA)
        cv2.line(self._strokes, p1, p2, core, max(1, size // 2), lineType=cv2.LINE_AA)

    def _sparkle(self, p1, p2, color, size):
        cv2.line(self._strokes, p1, p2, color, max(1, size // 2), lineType=cv2.LINE_AA)
        if random.random() < 0.55:
            self.confetti.append(Particle(
                p2[0], p2[1], color, size=random.randint(2, 5),
                vx=random.uniform(-2.5, 2.5), vy=random.uniform(-2.5, 2.5),
                decay=0.06, gravity=0.05
            ))

    def _do_stroke(self, p1, p2, color, size, is_eraser):
        if is_eraser:
            eraser_size = config.ERASER_SIZE
            cv2.line(self._strokes, p1, p2, (0, 0, 0), eraser_size, lineType=cv2.LINE_AA)
            cv2.circle(self._strokes, p2, eraser_size // 2, (0, 0, 0), -1, lineType=cv2.LINE_AA)
            # Restore background under eraser
            diff = self._strokes == (0, 0, 0)
            self._strokes[diff] = self._bg[diff]
            return

        m = self.brush_mode
        if m == "pencil":   self._pencil(p1, p2, color, size)
        elif m == "callig": self._callig(p1, p2, color, size)
        elif m == "marker": self._marker(p1, p2, color, size)
        elif m == "crayon": self._crayon(p1, p2, color, size)
        elif m == "spray":  self._spray(p2, color, size)
        elif m == "drip":   self._drip(p1, p2, color, size)
        elif m == "neon":   self._neon(p1, p2, color, size)
        elif m == "sparkle":self._sparkle(p1, p2, color, size)
        else:               self._pen(p1, p2, color, size)

    # ── Extended MS Paint Shapes Rendering ────────────────────────────────────

    def _draw_shape_on(self, tgt, start, end, color, size, dashed=False):
        x1, y1 = start; x2, y2 = end
        tool = self.shape_tool
        fill_mode = self.shape_fill_mode
        fill_color = self.color2

        # Helper: handle fill & outline according to shape_fill_mode
        def apply_poly(points):
            pts = np.array(points, np.int32).reshape((-1, 1, 2))
            if fill_mode in ("fill", "both"):
                fcol = fill_color if fill_mode == "both" else color
                cv2.fillPoly(tgt, [pts], fcol, lineType=cv2.LINE_AA)
            if fill_mode in ("outline", "both"):
                if dashed:
                    for i in range(len(points)):
                        self._dashed_line(tgt, points[i], points[(i + 1) % len(points)], color, size)
                else:
                    cv2.polylines(tgt, [pts], True, color, size, lineType=cv2.LINE_AA)

        # 1. Line
        if tool == "line":
            if dashed: self._dashed_line(tgt, start, end, color, size)
            else: cv2.line(tgt, start, end, color, size, lineType=cv2.LINE_AA)

        # 2. Curve (Quadratic Bézier Curve)
        elif tool == "curve":
            p0 = self._curve_p0 or start
            p2 = self._curve_p2 or end
            p1 = self._curve_p1 or ((p0[0] + p2[0]) // 2, (p0[1] + p2[1]) // 2)
            pts = []
            for step in range(35):
                t = step / 34.0
                bx = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + (t ** 2) * p2[0]
                by = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + (t ** 2) * p2[1]
                pts.append((int(bx), int(by)))
            for i in range(len(pts) - 1):
                if dashed and (i % 2 == 0): continue
                cv2.line(tgt, pts[i], pts[i + 1], color, size, lineType=cv2.LINE_AA)

        # 3. Rectangle
        elif tool == "rect":
            rx1, rx2 = sorted([x1, x2])
            ry1, ry2 = sorted([y1, y2])
            if fill_mode in ("fill", "both"):
                fcol = fill_color if fill_mode == "both" else color
                cv2.rectangle(tgt, (rx1, ry1), (rx2, ry2), fcol, -1)
            if fill_mode in ("outline", "both"):
                if dashed: self._dashed_rect(tgt, (rx1, ry1), (rx2, ry2), color, size)
                else: cv2.rectangle(tgt, (rx1, ry1), (rx2, ry2), color, size, lineType=cv2.LINE_AA)

        # 4. Rounded Rectangle
        elif tool == "rndrect":
            rx1, rx2 = sorted([x1, x2]); ry1, ry2 = sorted([y1, y2])
            r = min(25, max(4, abs(rx2 - rx1) // 6), max(4, abs(ry2 - ry1) // 6))
            if fill_mode in ("fill", "both"):
                fcol = fill_color if fill_mode == "both" else color
                cv2.rectangle(tgt, (rx1 + r, ry1), (rx2 - r, ry2), fcol, -1)
                cv2.rectangle(tgt, (rx1, ry1 + r), (rx2, ry2 - r), fcol, -1)
                for cx_, cy_ in [(rx1 + r, ry1 + r), (rx2 - r, ry1 + r),
                                 (rx2 - r, ry2 - r), (rx1 + r, ry2 - r)]:
                    cv2.circle(tgt, (cx_, cy_), r, fcol, -1)
            if fill_mode in ("outline", "both"):
                if dashed: self._dashed_rounded_rect(tgt, rx1, ry1, rx2, ry2, color, size, r)
                else: self._rounded_rect_draw(tgt, rx1, ry1, rx2, ry2, color, size, r)

        # 5. Circle / Ellipse
        elif tool == "circle":
            cx_ = (x1 + x2) // 2; cy_ = (y1 + y2) // 2
            rx = abs(x2 - x1) // 2; ry = abs(y2 - y1) // 2
            if fill_mode in ("fill", "both"):
                fcol = fill_color if fill_mode == "both" else color
                cv2.ellipse(tgt, (cx_, cy_), (max(1, rx), max(1, ry)), 0, 0, 360, fcol, -1, lineType=cv2.LINE_AA)
            if fill_mode in ("outline", "both"):
                cv2.ellipse(tgt, (cx_, cy_), (max(1, rx), max(1, ry)), 0, 0, 360, color, size, lineType=cv2.LINE_AA)

        # 6. Triangle (Isosceles)
        elif tool == "triangle":
            pts = [((x1 + x2) // 2, y1), (x1, y2), (x2, y2)]
            apply_poly(pts)

        # 7. Right-Angle Triangle
        elif tool == "rtriangle":
            pts = [(x1, y1), (x1, y2), (x2, y2)]
            apply_poly(pts)

        # 8. Diamond (Rhombus)
        elif tool == "diamond":
            cx_ = (x1 + x2) // 2; cy_ = (y1 + y2) // 2
            pts = [(cx_, y1), (x2, cy_), (cx_, y2), (x1, cy_)]
            apply_poly(pts)

        # 9. 5-Point Star
        elif tool == "star5":
            cx_ = (x1 + x2) // 2; cy_ = (y1 + y2) // 2
            r_out = max(6, int(math.hypot(x2 - cx_, y2 - cy_)))
            r_in = int(r_out * 0.40)
            pts = []
            for i in range(10):
                ang = i * math.pi / 5.0 - math.pi / 2.0
                rad = r_out if (i % 2 == 0) else r_in
                pts.append((int(cx_ + rad * math.cos(ang)), int(cy_ + rad * math.sin(ang))))
            apply_poly(pts)

        # 10. 4-Point Star
        elif tool == "star4":
            cx_ = (x1 + x2) // 2; cy_ = (y1 + y2) // 2
            r_out = max(6, int(math.hypot(x2 - cx_, y2 - cy_)))
            r_in = int(r_out * 0.30)
            pts = []
            for i in range(8):
                ang = i * math.pi / 4.0 - math.pi / 2.0
                rad = r_out if (i % 2 == 0) else r_in
                pts.append((int(cx_ + rad * math.cos(ang)), int(cy_ + rad * math.sin(ang))))
            apply_poly(pts)

        # 11. Arrow
        elif tool == "arrow":
            rx1, rx2 = sorted([x1, x2]); ry1, ry2 = sorted([y1, y2])
            w = max(10, rx2 - rx1); h = max(10, ry2 - ry1)
            # Pointing right
            shaft_h = h // 3
            pts = [
                (rx1, ry1 + shaft_h), (rx1 + int(w * 0.6), ry1 + shaft_h),
                (rx1 + int(w * 0.6), ry1), (rx2, ry1 + h // 2),
                (rx1 + int(w * 0.6), ry2), (rx1 + int(w * 0.6), ry2 - shaft_h),
                (rx1, ry2 - shaft_h)
            ]
            apply_poly(pts)

        # 12. Heart
        elif tool == "heart":
            cx_ = (x1 + x2) // 2; cy_ = (y1 + y2) // 2
            scale = max(0.4, min(abs(x2 - x1), abs(y2 - y1)) / 36.0)
            pts = []
            for step in range(50):
                t = step * 2.0 * math.pi / 50.0
                hx = 16 * (math.sin(t) ** 3)
                hy = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
                pts.append((int(cx_ + hx * scale), int(cy_ + hy * scale)))
            apply_poly(pts)

        # 13. Lightning Bolt
        elif tool == "lightning":
            rx1, rx2 = sorted([x1, x2]); ry1, ry2 = sorted([y1, y2])
            w = max(10, rx2 - rx1); h = max(10, ry2 - ry1)
            pts = [
                (rx1 + int(w * 0.55), ry1), (rx1 + int(w * 0.20), ry1 + int(h * 0.55)),
                (rx1 + int(w * 0.45), ry1 + int(h * 0.55)), (rx1 + int(w * 0.35), ry2),
                (rx2, ry1 + int(h * 0.42)), (rx1 + int(w * 0.65), ry1 + int(h * 0.42)),
            ]
            apply_poly(pts)

        # 14. Speech Callout
        elif tool == "callout":
            rx1, rx2 = sorted([x1, x2]); ry1, ry2 = sorted([y1, y2])
            bubble_bottom = ry2 - int((ry2 - ry1) * 0.25)
            r = min(15, (rx2 - rx1) // 8)
            pts = [
                (rx1 + r, ry1), (rx2 - r, ry1), (rx2, ry1 + r),
                (rx2, bubble_bottom - r), (rx2 - r, bubble_bottom),
                (rx1 + int((rx2 - rx1) * 0.45), bubble_bottom),
                (rx1 + int((rx2 - rx1) * 0.20), ry2),
                (rx1 + int((rx2 - rx1) * 0.30), bubble_bottom),
                (rx1 + r, bubble_bottom), (rx1, bubble_bottom - r),
                (rx1, ry1 + r)
            ]
            apply_poly(pts)

        # 15. Polygon (Regular N-gon)
        elif tool == "polygon":
            cx_ = (x1 + x2) // 2; cy_ = (y1 + y2) // 2
            rad = max(5, int(math.hypot(x2 - cx_, y2 - cy_)))
            N = self.polygon_sides
            pts = [
                (int(cx_ + rad * math.cos(2 * math.pi * k / N - math.pi / 2)),
                 int(cy_ + rad * math.sin(2 * math.pi * k / N - math.pi / 2)))
                for k in range(N)
            ]
            apply_poly(pts)

    def _rounded_rect_draw(self, tgt, x1, y1, x2, y2, color, size, r):
        cv2.rectangle(tgt, (x1 + r, y1), (x2 - r, y2), color, size, lineType=cv2.LINE_AA)
        cv2.rectangle(tgt, (x1, y1 + r), (x2, y2 - r), color, size, lineType=cv2.LINE_AA)
        for cx_, cy_, s, e in [
            (x1 + r, y1 + r, 180, 270), (x2 - r, y1 + r, 270, 360),
            (x2 - r, y2 - r, 0, 90), (x1 + r, y2 - r, 90, 180)
        ]:
            cv2.ellipse(tgt, (cx_, cy_), (r, r), 0, s, e, color, size, lineType=cv2.LINE_AA)

    def _dashed_line(self, tgt, p1, p2, color, size, dash=12, gap=8):
        x1, y1 = p1; x2, y2 = p2
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist < 1: return
        ux, uy = (x2 - x1) / dist, (y2 - y1) / dist
        d = 0.0; draw = True
        while d < dist:
            end = min(d + (dash if draw else gap), dist)
            if draw:
                a = (int(x1 + ux * d), int(y1 + uy * d))
                b_ = (int(x1 + ux * end), int(y1 + uy * end))
                cv2.line(tgt, a, b_, color, size, lineType=cv2.LINE_AA)
            d = end; draw = not draw

    def _dashed_rect(self, tgt, p1, p2, color, size):
        x1, y1 = p1; x2, y2 = p2
        for a, b in [
            ((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
            ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))
        ]:
            self._dashed_line(tgt, a, b, color, size)

    def _dashed_rounded_rect(self, tgt, x1, y1, x2, y2, color, size, r):
        edges = [
            ((x1 + r, y1), (x2 - r, y1)), ((x2, y1 + r), (x2, y2 - r)),
            ((x2 - r, y2), (x1 + r, y2)), ((x1, y2 - r), (x1, y1 + r))
        ]
        for a, b in edges: self._dashed_line(tgt, a, b, color, size)

    # ── Shape Lifecycle ───────────────────────────────────────────────────────

    def begin_shape(self, x, y, color, size):
        self._push_undo()
        self._shape_start = (x, y)
        self._shape_preview_end = (x, y)
        self._shape_color = color
        self._shape_size = size

        if self.shape_tool == "curve":
            if self._curve_phase == 0:
                self._curve_phase = 1
                self._curve_p0 = (x, y)
                self._curve_p2 = (x, y)
            elif self._curve_phase == 1:
                self._curve_phase = 2
                self._curve_p1 = (x, y)

    def update_shape_preview(self, x, y):
        self._shape_preview_end = (x, y)
        if self.shape_tool == "curve":
            if self._curve_phase == 1:
                self._curve_p2 = (x, y)
            elif self._curve_phase == 2:
                self._curve_p1 = (x, y)

    def commit_shape(self):
        if self.shape_tool == "curve" and self._curve_phase == 1:
            # Curve needs second click to bend
            return
        if self._shape_start and self._shape_preview_end:
            self._draw_shape_on(self._strokes, self._shape_start, self._shape_preview_end,
                                self._shape_color, self._shape_size)
        self.cancel_shape()

    def cancel_shape(self):
        self._shape_start = None
        self._shape_preview_end = None
        self._curve_phase = 0
        self._curve_p0 = None
        self._curve_p1 = None
        self._curve_p2 = None

    def has_active_shape(self) -> bool:
        return self._shape_start is not None

    # ── Freehand Stroke & Smoothing ───────────────────────────────────────────

    def update(
        self,
        raw_x: int,
        raw_y: int,
        color: Tuple[int, int, int],
        brush_size: int,
        drawing_mode: bool,
        is_eraser: bool = False,
        pressure: float = 1.0,
    ) -> None:
        if not drawing_mode:
            if self._active_stroke_points and self.auto_beautify and not is_eraser:
                self._try_beautify_active_stroke(color, brush_size)
            self._active_stroke_points.clear()
            self.reset_previous_point()
            return

        alpha = config.SMOOTHING_ALPHA
        if self._prev_point is None:
            smooth_x, smooth_y = raw_x, raw_y
            self._push_undo()
        else:
            smooth_x = int(alpha * raw_x + (1.0 - alpha) * self._prev_point[0])
            smooth_y = int(alpha * raw_y + (1.0 - alpha) * self._prev_point[1])

        pt = (smooth_x, smooth_y)
        self._active_stroke_points.append(pt)

        # Apply 3D pressure scaling
        effective_size = max(1, int(brush_size * pressure))
        eff_color = self._rainbow_color() if (self.rainbow_mode and not is_eraser) else color

        if self._prev_point is not None:
            pairs = self._sym_pairs(self._prev_point, pt)
            for p1, p2 in pairs:
                self._do_stroke(p1, p2, eff_color, effective_size, is_eraser)

        self._prev_point = pt

    def reset_previous_point(self):
        self._prev_point = None

    # ── AI Auto-Beautify Current Stroke ───────────────────────────────────────

    def _try_beautify_active_stroke(self, color, size):
        """Snaps messy air stroke to clean vector shape."""
        if len(self._active_stroke_points) < 8:
            return
        res = ai_engine.beautify_stroke(self._active_stroke_points)
        if not res:
            return

        stype = res["type"]
        self._push_undo()

        if stype == "line":
            cv2.line(self._strokes, res["p1"], res["p2"], color, size, lineType=cv2.LINE_AA)
        elif stype == "circle":
            cv2.circle(self._strokes, res["center"], res["radius"], color, size, lineType=cv2.LINE_AA)
        elif stype == "ellipse":
            cv2.ellipse(self._strokes, res["center"], (res["rx"], res["ry"]), 0, 0, 360, color, size, lineType=cv2.LINE_AA)
        elif stype == "rect":
            cv2.rectangle(self._strokes, res["p1"], res["p2"], color, size, lineType=cv2.LINE_AA)
        elif stype == "triangle":
            pts = np.array(res["points"], np.int32).reshape((-1, 1, 2))
            cv2.polylines(self._strokes, [pts], True, color, size, lineType=cv2.LINE_AA)
        elif stype == "arrow":
            cv2.arrowedLine(self._strokes, res["p1"], res["p2"], color, size, tipLength=0.25)

        self.confetti += _confetti_burst(self._active_stroke_points[-1][0],
                                         self._active_stroke_points[-1][1], 25)

    # ── AI Real-Time Doodle Classifier ────────────────────────────────────────

    def check_ai_doodle(self) -> Tuple[str, int]:
        now = time.time()
        if now - self._last_ai_check_time > 0.45:
            self._last_ai_check_time = now
            label, conf = ai_engine.classify_doodle(self._strokes, self._bg)
            self._last_ai_doodle_label = label
            self._last_ai_doodle_conf = conf
        return (self._last_ai_doodle_label, self._last_ai_doodle_conf)

    # ── AI Magic Content-Aware Eraser ─────────────────────────────────────────

    def magic_inpaint_selection(self) -> bool:
        """Applies content-aware AI inpainting to the active selection."""
        if not self._sel_rect: return False
        x1, y1, x2, y2 = self._sel_rect
        self._push_undo()

        # Build inpainting mask
        mask = np.zeros((self.height, self.width), np.uint8)
        mask[y1:y2, x1:x2] = 255
        self._strokes = ai_engine.magic_inpaint(self._strokes, mask, radius=7)
        self.deselect()
        return True

    # ── AI Edge Art / Coloring Book ───────────────────────────────────────────

    def convert_to_coloring_book(self) -> None:
        """Transforms current canvas or loaded photo into a clean coloring book outline."""
        self._push_undo()
        self._strokes = ai_engine.photo_to_coloring_book(self._strokes, dark_mode=self.dark_mode)

    # ── MS-Paint Tools ────────────────────────────────────────────────────────

    def flood_fill(self, x: int, y: int, color: Tuple[int, int, int]) -> None:
        x = max(0, min(x, self.width - 1))
        y = max(0, min(y, self.height - 1))
        self._push_undo()
        mask = np.zeros((self.height + 2, self.width + 2), np.uint8)
        fill_col = tuple(int(c) for c in color)
        cv2.floodFill(
            self._strokes, mask, (x, y), fill_col,
            loDiff=(32, 32, 32, 0), upDiff=(32, 32, 32, 0),
            flags=4 | cv2.FLOODFILL_FIXED_RANGE,
        )

    def pick_color(self, x: int, y: int) -> Optional[Tuple[int, int, int]]:
        if 0 <= x < self.width and 0 <= y < self.height:
            bgr = self._strokes[y, x]
            return (int(bgr[0]), int(bgr[1]), int(bgr[2]))
        return None

    # ── Text Tool ─────────────────────────────────────────────────────────────

    def start_text(self, x: int, y: int, color, size: float = 1.1):
        self.text_mode = True
        self.text_buffer = ""
        self.text_anchor = (x, y)
        self.text_color = color
        self.text_size = size

    def commit_text(self):
        if self.text_buffer and self.text_anchor:
            self._push_undo()
            cv2.putText(self._strokes, self.text_buffer, self.text_anchor,
                        cv2.FONT_HERSHEY_SIMPLEX, self.text_size,
                        self.text_color, 2, cv2.LINE_AA)
        self.text_mode = False
        self.text_buffer = ""
        self.text_anchor = None

    def cancel_text(self):
        self.text_mode = False
        self.text_buffer = ""
        self.text_anchor = None

    # ── Selection & Clipboard ─────────────────────────────────────────────────

    def set_selection(self, x1, y1, x2, y2):
        ax1, ax2 = sorted([x1, x2]); ay1, ay2 = sorted([y1, y2])
        ax1 = max(0, ax1); ay1 = max(0, ay1)
        ax2 = min(self.width - 1, ax2); ay2 = min(self.height - 1, ay2)
        if ax2 <= ax1 or ay2 <= ay1:
            self._sel_rect = None; return
        self._sel_rect = (ax1, ay1, ax2, ay2)
        self._sel_buf = self._strokes[ay1:ay2, ax1:ax2].copy()

    def set_lasso_points(self, points: List[Tuple[int, int]]):
        if len(points) < 3: return
        self._lasso_points = points
        xs = [p[0] for p in points]; ys = [p[1] for p in points]
        x1, x2 = max(0, min(xs)), min(self.width - 1, max(xs))
        y1, y2 = max(0, min(ys)), min(self.height - 1, max(ys))
        self._sel_rect = (x1, y1, x2, y2)
        # Create polygon mask
        mask = np.zeros((y2 - y1, x2 - x1), np.uint8)
        poly = np.array([(p[0] - x1, p[1] - y1) for p in points], np.int32)
        cv2.fillPoly(mask, [poly], 255)
        self._sel_mask = mask
        self._sel_buf = self._strokes[y1:y2, x1:x2].copy()

    def clear_selection_area(self):
        if not self._sel_rect: return
        x1, y1, x2, y2 = self._sel_rect
        self._push_undo()
        self._strokes[y1:y2, x1:x2] = self._bg[y1:y2, x1:x2]
        self.deselect()

    def copy_selection(self):
        if self._sel_rect and self._sel_buf is None:
            x1, y1, x2, y2 = self._sel_rect
            self._sel_buf = self._strokes[y1:y2, x1:x2].copy()

    def cut_selection(self):
        if not self._sel_rect: return
        x1, y1, x2, y2 = self._sel_rect
        self._sel_buf = self._strokes[y1:y2, x1:x2].copy()
        self.clear_selection_area()

    def paste_at(self, x: int, y: int):
        if self._sel_buf is None: return
        self._push_undo()
        bh, bw = self._sel_buf.shape[:2]
        x2, y2 = min(x + bw, self.width), min(y + bh, self.height)
        sw, sh = x2 - x, y2 - y
        if sw > 0 and sh > 0:
            if self.transparent_sel:
                # Transparent selection: pixels matching Color 2 or background are transparent
                src = self._sel_buf[:sh, :sw]
                tgt = self._strokes[y:y2, x:x2]
                trans_mask = np.all(np.abs(src.astype(np.int16) - np.array(self.color2, np.int16)) < 25, axis=2)
                tgt[~trans_mask] = src[~trans_mask]
            else:
                self._strokes[y:y2, x:x2] = self._sel_buf[:sh, :sw]
            self._sel_rect = (x, y, x2, y2)

    def move_selection(self, new_x: int, new_y: int):
        if not self._sel_rect: return
        x1, y1, x2, y2 = self._sel_rect
        buf = self._strokes[y1:y2, x1:x2].copy()
        self._strokes[y1:y2, x1:x2] = self._bg[y1:y2, x1:x2]
        bh, bw = buf.shape[:2]
        nx2, ny2 = min(new_x + bw, self.width), min(new_y + bh, self.height)
        sw, sh = nx2 - new_x, ny2 - new_y
        if sw > 0 and sh > 0:
            self._strokes[new_y:ny2, new_x:nx2] = buf[:sh, :sw]
        self._sel_rect = (new_x, new_y, nx2, ny2)
        self._sel_buf = buf

    def crop_to_selection(self) -> bool:
        if not self._sel_rect: return False
        x1, y1, x2, y2 = self._sel_rect
        cropped = self._strokes[y1:y2, x1:x2].copy()
        self._push_undo()
        # Scale to canvas
        self._strokes = cv2.resize(cropped, (self.width, self.height), interpolation=cv2.INTER_CUBIC)
        self.deselect()
        return True

    def deselect(self):
        self._sel_rect = None
        self._sel_buf = None
        self._sel_mask = None
        self._lasso_points.clear()

    def get_selection_rect(self):
        return self._sel_rect

    # ── Transforms ────────────────────────────────────────────────────────────

    def flip_horizontal(self):
        self._push_undo()
        self._strokes = cv2.flip(self._strokes, 1)

    def flip_vertical(self):
        self._push_undo()
        self._strokes = cv2.flip(self._strokes, 0)

    def rotate_90(self):
        self._push_undo()
        rotated = cv2.rotate(self._strokes, cv2.ROTATE_90_CLOCKWISE)
        self._strokes = cv2.resize(rotated, (self.width, self.height), interpolation=cv2.INTER_AREA)

    def invert_colors(self):
        self._push_undo()
        self._strokes = 255 - self._strokes

    def grayscale(self):
        self._push_undo()
        g = cv2.cvtColor(self._strokes, cv2.COLOR_BGR2GRAY)
        self._strokes = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)

    def open_image(self, path: str) -> bool:
        if not os.path.exists(path): return False
        img = cv2.imread(path)
        if img is None: return False
        self._push_undo()
        # Scale & center image on canvas
        ih, iw = img.shape[:2]
        scale = min(self.width / iw, self.height / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        scaled = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
        ox, oy = (self.width - nw) // 2, (self.height - nh) // 2
        self._strokes = self._bg.copy()
        self._strokes[oy:oy + nh, ox:ox + nw] = scaled
        return True

    def clear(self):
        self._push_undo()
        self._strokes = self._bg.copy()
        self.deselect()
        self.reset_previous_point()

    def save(self) -> str:
        d = os.path.abspath(config.DRAWINGS_DIR)
        os.makedirs(d, exist_ok=True)
        ts = int(time.time())
        fp = os.path.join(d, f"drawing_{ts}.png")
        cv2.imwrite(fp, self.display_image)
        self.confetti += _confetti_burst(self.width // 2, self.height // 2, config.CONFETTI_COUNT)
        return fp

    # ── Display Rendering & View Overlays ─────────────────────────────────────

    @property
    def display_image(self) -> np.ndarray:
        base = self._strokes

        # 1. Shape preview
        if self.has_active_shape():
            base = base.copy()
            self._draw_shape_on(base, self._shape_start, self._shape_preview_end,
                                self._shape_color, self._shape_size, dashed=True)

        # 2. Text preview
        if self.text_mode and self.text_anchor:
            base = base.copy() if base is self._strokes else base
            p_text = (self.text_buffer or "") + "|"
            cv2.putText(base, p_text, self.text_anchor,
                        cv2.FONT_HERSHEY_SIMPLEX, self.text_size,
                        self.text_color, 2, cv2.LINE_AA)

        # 3. Selection overlay
        if self._sel_rect is not None:
            base = base.copy() if base is self._strokes else base
            x1, y1, x2, y2 = self._sel_rect
            for a, b in [
                ((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
                ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))
            ]:
                self._dashed_line(base, a, b, config.SELECTION_COLOR, 2, dash=10, gap=6)

        # 4. Gridlines view overlay
        if self.show_gridlines:
            base = base.copy() if base is self._strokes else base
            grid_col = (180, 180, 180) if not self.dark_mode else (60, 60, 70)
            for gx in range(0, self.width, 30):
                cv2.line(base, (gx, 0), (gx, self.height), grid_col, 1)
            for gy in range(0, self.height, 30):
                cv2.line(base, (0, gy), (self.width, gy), grid_col, 1)

        # 5. Rulers view overlay
        if self.show_rulers:
            base = base.copy() if base is self._strokes else base
            ruler_bg = (235, 235, 235) if not self.dark_mode else (35, 35, 45)
            ruler_tc = (50, 50, 50) if not self.dark_mode else (200, 200, 200)
            # Top ruler
            cv2.rectangle(base, (0, 0), (self.width, 18), ruler_bg, -1)
            for x in range(0, self.width, 50):
                cv2.line(base, (x, 10), (x, 18), ruler_tc, 1)
                cv2.putText(base, str(x), (x + 2, 9), cv2.FONT_HERSHEY_SIMPLEX, 0.26, ruler_tc, 1)
            # Left ruler
            cv2.rectangle(base, (0, 0), (18, self.height), ruler_bg, -1)
            for y in range(0, self.height, 50):
                cv2.line(base, (10, y), (18, y), ruler_tc, 1)
                cv2.putText(base, str(y), (2, y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.24, ruler_tc, 1)

        return base

    @property
    def image(self) -> np.ndarray:
        return self._strokes

    def update_confetti(self, frame: np.ndarray) -> None:
        self.confetti = [p for p in self.confetti if p.update()]
        for p in self.confetti: p.draw(frame)

        self.drip_particles = [p for p in self.drip_particles if p.update()]
        for p in self.drip_particles:
            ix, iy = int(p.x), int(p.y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                cv2.circle(self._strokes, (ix, iy), int(p.size), p.color, -1)
