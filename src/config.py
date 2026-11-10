"""
config.py  —  AI Air Draw  •  Easy & Revolutionary MS Paint AI Edition
All configuration and constants in one place.
"""

import os

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAWINGS_DIR: str = os.path.join(PROJECT_ROOT, "drawings")

# ── Camera & Canvas Dimensions ────────────────────────────────────────────────
FRAME_WIDTH:  int = 1280
FRAME_HEIGHT: int = 720

# ── Modern Spacious 2-Row Studio Toolbar ──────────────────────────────────────
TOOLBAR_ROW1_H: int = 56    # Main Action Bar: Draw, Eraser, Fill, Quick Colors, Save, Clear
TOOLBAR_ROW2_H: int = 50    # Sub-Bar / Tab Panels: Shapes, Brushes, AI Superpowers
TOOLBAR_HEIGHT: int = TOOLBAR_ROW1_H + TOOLBAR_ROW2_H  # 106 px (leaves more canvas space!)

BTN_W: int = 68   # Larger, much easier to hit!
BTN_H: int = 42   # Comfortable height
BTN_M: int = 4    # Clean gap

# Dwell Hover Click Duration (seconds)
DWELL_CLICK_TIME: float = 0.35

# ── Quick Vibrant Studio Colors (BGR) ─────────────────────────────────────────
QUICK_COLORS = [
    ("BLACK",   (  0,   0,   0)),
    ("WHITE",   (255, 255, 255)),
    ("RED",     ( 30,  30, 235)),
    ("ORANGE",  (  0, 140, 255)),
    ("YELLOW",  (  0, 230, 245)),
    ("GREEN",   ( 20, 200,  30)),
    ("CYAN",    (245, 220,  15)),
    ("BLUE",    (235,  80,  20)),
    ("PURPLE",  (210,  30, 160)),
    ("PINK",    (190,  90, 255)),
]

COLORS: dict = {
    "BLACK":    (  0,   0,   0),
    "DKGRAY":   ( 70,  70,  70),
    "GRAY":     (150, 150, 150),
    "WHITE":    (255, 255, 255),
    "RED":      ( 30,  30, 235),
    "ORANGE":   (  0, 140, 255),
    "YELLOW":   (  0, 230, 245),
    "LIME":     ( 30, 240, 100),
    "GREEN":    ( 20, 200,  30),
    "CYAN":     (245, 220,  15),
    "SKY":      (245, 165,  45),
    "BLUE":     (235,  80,  20),
    "PURPLE":   (210,  30, 160),
    "PINK":     (190,  90, 255),
    "MAGENTA":  (170,   0, 230),
    "BROWN":    ( 35,  65, 125),
}
DEFAULT_COLOR_NAME:  str = "RED"
DEFAULT_COLOR2_NAME: str = "WHITE"

# ── Brush Settings ────────────────────────────────────────────────────────────
DEFAULT_BRUSH_SIZE: int = 6
MIN_BRUSH_SIZE:     int = 2
MAX_BRUSH_SIZE:     int = 60
ERASER_SIZE:        int = 45

# Brush Modes
BRUSH_MODES = [
    "pen",       # Smooth ballpoint pen
    "marker",    # Semi-transparent highlighter
    "callig",    # Calligraphy chisel nib
    "crayon",    # Wax crayon / chalk texture
    "spray",     # Airbrush spray
    "drip",      # Paint drip physics
    "neon",      # Cyberpunk glowing line
    "sparkle",   # Magic fairy glitter
]
BRUSH_LABELS = [
    "PEN", "MARK", "CLIG", "CRAY", "SPRY", "DRIP", "NEON", "SPRK"
]
DEFAULT_BRUSH_MODE: str = "pen"

# ── MS Paint Shapes Suite ─────────────────────────────────────────────────────
SHAPE_TOOLS = [
    "freehand",  # Freehand
    "line",      # Straight line
    "curve",     # Bézier curve
    "rect",      # Rectangle
    "rndrect",   # Rounded rectangle
    "circle",    # Ellipse / circle
    "triangle",  # Triangle
    "diamond",   # Diamond
    "star5",     # 5-pointed star
    "heart",     # Heart
    "arrow",     # Arrow
    "callout",   # Comic bubble
    "polygon",   # N-gon (3 to 12 sides)
]

SHAPE_LABELS = [
    "FREE", "LINE", "CURV", "RECT", "RRCT", "CIRC",
    "TRI", "DIAM", "STAR", "HART", "ARRW", "BUBL", "POLY"
]
DEFAULT_SHAPE: str = "freehand"
DEFAULT_POLYGON_SIDES: int = 6

SHAPE_FILL_MODES  = ["outline", "fill", "both"]
SHAPE_FILL_LABELS = ["OUTLN", "FILL", "BOTH"]

# ── MS Paint Special Tools ────────────────────────────────────────────────────
PAINT_TOOLS = [
    "fill",       # Flood fill paint bucket
    "eyedrop",    # Eyedropper with 4x live loupe
    "text",       # Text tool
    "select",     # Selection tool
    "crop",       # Crop to selection
]
PAINT_LABELS = [
    "BUCKET", "LOUPE", "TEXT", "SELECT", "CROP"
]

# ── Revolutionary AI Superpowers ──────────────────────────────────────────────
AI_TOOLS = [
    "ai_snap",      # AI Auto-Shape Beautifier (Snaps rough sketches to vectors)
    "ai_inpaint",   # AI Magic Content-Aware Eraser
    "ai_book",      # AI Edge Art / Coloring Book mode
    "ai_holo",      # Holographic AR Left-Hand Palette
    "ai_pressure",  # 3D Depth Pressure Stylus
]
AI_LABELS = [
    "🤖SNAP", "✨INPNT", "📖BOOK", "🔮HOLO", "🎚️PRES"
]

# ── Toolbar Tab Categories ────────────────────────────────────────────────────
TAB_MODES = ["BRUSHES", "SHAPES", "AI_TOOLS", "TRANSFORM"]

# ── Symmetry ──────────────────────────────────────────────────────────────────
SYMMETRY_MODES  = ["none", "mirror_h", "mirror_v", "quad", "radial_4", "radial_8"]
SYMMETRY_LABELS = ["SY:NO", "SY:LR", "SY:UD", "SY:4", "SY:R4", "SY:R8"]

# ── Background Presets ────────────────────────────────────────────────────────
BG_PRESETS = ["white", "black", "grid", "dotgrid", "starfield", "blueprint", "canvas"]
BG_LABELS  = ["BG:W", "BG:K", "BG:G", "BG:DOT", "BG:STR", "BG:BP", "BG:CANV"]

# ── Canvas View Features ──────────────────────────────────────────────────────
SHOW_GRIDLINES:  bool = False
SHOW_RULERS:     bool = False
TRANSPARENT_SEL: bool = False
CANVAS_ZOOM:     int  = 1

# ── Ultra-Smooth Smoothing Alpha ──────────────────────────────────────────────
# 0.72 provides buttery smooth digital ink with zero jitter
SMOOTHING_ALPHA: float = 0.72
MAX_UNDO_STEPS:  int   = 40

# ── Particles ─────────────────────────────────────────────────────────────────
MAX_PARTICLES:  int = 1000
CONFETTI_COUNT: int = 200

# ── MediaPipe Hand Tracking ───────────────────────────────────────────────────
MAX_NUM_HANDS:        int   = 2
DETECTION_CONFIDENCE: float = 0.70
TRACKING_CONFIDENCE:  float = 0.55

# ── UI Theme (BGR) ────────────────────────────────────────────────────────────
TOOLBAR_BG_COLOR:      tuple = (18,  18,  28)
TOOLBAR_R2_BG:         tuple = (13,  13,  22)
BUTTON_ACTIVE_COLOR:   tuple = (180, 120,  30)
BUTTON_INACTIVE_COLOR: tuple = (38,   38,  52)
BUTTON_TEXT_COLOR:     tuple = (240, 240, 240)
BUTTON_TOOL_COLOR:     tuple = (35,  100, 185)
BUTTON_AI_COLOR:       tuple = (150,  45, 175)
STATUS_TEXT_COLOR:     tuple = (200, 200, 200)
FPS_TEXT_COLOR:        tuple = (0,   240, 110)
ACCENT:                tuple = (255, 185,  40)    # Gold
ACCENT2:               tuple = (110, 215, 255)    # Ice Blue
SELECTION_COLOR:       tuple = (0,   160, 255)

SHOW_HUD:            bool = True
DEFAULT_DARK_CANVAS: bool = False
DEFAULT_DRAW_STYLE:  str  = "PINCH"   # "PINCH" (touch thumb+index to draw) or "POINT" (point index)
