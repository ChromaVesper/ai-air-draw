"""
config.py
---------
Central configuration file for AI Air Draw.
Change values here to customize the application without touching other files.
"""

# ── Window / Canvas ──────────────────────────────────────────────────────────
FRAME_WIDTH: int = 1280   # Width of the webcam frame (pixels)
FRAME_HEIGHT: int = 720   # Height of the webcam frame (pixels)
CANVAS_WIDTH: int = FRAME_WIDTH
CANVAS_HEIGHT: int = FRAME_HEIGHT

# ── Toolbar ──────────────────────────────────────────────────────────────────
TOOLBAR_HEIGHT: int = 80          # Height of the top toolbar (pixels)
BUTTON_WIDTH: int = 120           # Width of each toolbar button
BUTTON_MARGIN: int = 10           # Gap between buttons

# ── Colors ───────────────────────────────────────────────────────────────────
# Colors are stored as BGR tuples (OpenCV uses BGR, not RGB)
COLORS: dict = {
    "BLUE":   (255, 100,   0),
    "GREEN":  (  0, 200,   0),
    "RED":    (  0,   0, 220),
    "YELLOW": (  0, 220, 220),
}

# Default drawing color
DEFAULT_COLOR_NAME: str = "BLUE"

# ── Brush Sizes ───────────────────────────────────────────────────────────────
DEFAULT_BRUSH_SIZE: int = 8       # Default pen thickness (pixels)
ERASER_SIZE: int = 40             # Default eraser radius (pixels)
MIN_BRUSH_SIZE: int = 2
MAX_BRUSH_SIZE: int = 40

# ── Smoothing ────────────────────────────────────────────────────────────────
# Exponential moving-average factor (0 = no movement, 1 = no smoothing)
SMOOTHING_ALPHA: float = 0.5

# ── MediaPipe ────────────────────────────────────────────────────────────────
MAX_NUM_HANDS: int = 1            # Track only one hand for simplicity
DETECTION_CONFIDENCE: float = 0.7
TRACKING_CONFIDENCE: float = 0.5

# ── File Paths ────────────────────────────────────────────────────────────────
DRAWINGS_DIR: str = "drawings"    # Folder where saved PNGs are stored

# ── UI Colors (BGR) ──────────────────────────────────────────────────────────
TOOLBAR_BG_COLOR: tuple = (30, 30, 30)         # Dark toolbar background
BUTTON_ACTIVE_COLOR: tuple = (70, 130, 180)    # Highlighted button (steel blue)
BUTTON_INACTIVE_COLOR: tuple = (60, 60, 60)    # Inactive button
BUTTON_TEXT_COLOR: tuple = (240, 240, 240)     # White text on buttons
STATUS_TEXT_COLOR: tuple = (220, 220, 220)     # Gray text for status bar
FPS_TEXT_COLOR: tuple = (0, 255, 100)          # Bright green FPS counter
