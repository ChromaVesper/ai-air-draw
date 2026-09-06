"""
main.py
-------
AI Air Draw — Main entry point.

Run with:
    python src/main.py

Flow:
    Webcam frame
    → Flip (mirror)
    → MediaPipe hand detection   (hand_tracker.py)
    → Gesture recognition        (gestures.py)
    → Update drawing canvas      (drawing.py)
    → Render toolbar + overlays
    → Display combined window
    → Handle keyboard shortcuts
    → Repeat until Q / ESC
"""

import sys
import os
# Allow sibling modules (config, hand_tracker, etc.) to be imported
sys.path.insert(0, os.path.dirname(__file__))

import cv2
import numpy as np
import time
from typing import Optional, Tuple

import config
from hand_tracker import HandTracker
from drawing import DrawingCanvas
import gestures


# ─────────────────────────────────────────────────────────────────────────────
# Toolbar helpers
# ─────────────────────────────────────────────────────────────────────────────

# Button definitions: (label, key)
BUTTONS = [
    ("CLEAR",  "clear"),
    ("BLUE",   "blue"),
    ("GREEN",  "green"),
    ("RED",    "red"),
    ("YELLOW", "yellow"),
    ("ERASER", "eraser"),
    ("SAVE",   "save"),
]

# Colour preview swatches for each colour button (BGR)
COLOR_SWATCHES = {
    "blue":   config.COLORS["BLUE"],
    "green":  config.COLORS["GREEN"],
    "red":    config.COLORS["RED"],
    "yellow": config.COLORS["YELLOW"],
}


def build_toolbar(
    width: int,
    height: int,
    active_btn: str,
    current_color: Tuple[int, int, int],
    brush_size: int,
    mode_label: str,
    fps: float,
) -> np.ndarray:
    """
    Build and return the toolbar as a NumPy image (height × width, BGR).

    Parameters
    ----------
    width        : int   Toolbar width (matches frame width)
    height       : int   Toolbar height in pixels
    active_btn   : str   Key of the currently active button (e.g. "blue")
    current_color: tuple Current drawing colour (BGR)
    brush_size   : int   Current brush thickness
    mode_label   : str   "DRAW", "IDLE", or "ERASER"
    fps          : float Frames per second
    """
    toolbar = np.zeros((height, width, 3), dtype=np.uint8)
    toolbar[:] = config.TOOLBAR_BG_COLOR

    btn_w = config.BUTTON_WIDTH
    btn_h = height - 20
    margin = config.BUTTON_MARGIN
    x_offset = margin

    for label, key in BUTTONS:
        # Choose highlight colour if this button is active
        bg = config.BUTTON_ACTIVE_COLOR if key == active_btn else config.BUTTON_INACTIVE_COLOR

        # Draw button rectangle
        x1, y1 = x_offset, 10
        x2, y2 = x_offset + btn_w, 10 + btn_h
        cv2.rectangle(toolbar, (x1, y1), (x2, y2), bg, -1)
        cv2.rectangle(toolbar, (x1, y1), (x2, y2), (100, 100, 100), 1)  # Border

        # Small colour swatch inside colour buttons
        if key in COLOR_SWATCHES:
            swatch_x = x1 + 8
            swatch_y = y1 + 8
            cv2.rectangle(
                toolbar,
                (swatch_x, swatch_y),
                (swatch_x + 14, swatch_y + 14),
                COLOR_SWATCHES[key],
                -1,
            )

        # Button label text
        text_x = x1 + (btn_w - len(label) * 8) // 2
        cv2.putText(
            toolbar,
            label,
            (text_x, y1 + btn_h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            config.BUTTON_TEXT_COLOR,
            1,
            cv2.LINE_AA,
        )

        x_offset += btn_w + margin

    # ── Status info on the right side of the toolbar ──────────────────────
    right_x = width - 360
    info_y = 30

    # Mode
    mode_color = (0, 230, 80) if mode_label == "DRAW" else (0, 160, 230)
    if mode_label == "ERASER":
        mode_color = (0, 80, 230)
    cv2.putText(
        toolbar,
        f"Mode: {mode_label}",
        (right_x, info_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        mode_color,
        2,
        cv2.LINE_AA,
    )

    # Brush size
    cv2.putText(
        toolbar,
        f"Brush: {brush_size}px",
        (right_x + 150, info_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        config.STATUS_TEXT_COLOR,
        1,
        cv2.LINE_AA,
    )

    # FPS
    cv2.putText(
        toolbar,
        f"FPS: {fps:.1f}",
        (right_x, info_y + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        config.FPS_TEXT_COLOR,
        2,
        cv2.LINE_AA,
    )

    # Colour preview circle
    cv2.circle(toolbar, (width - 40, height // 2), 18, current_color, -1)
    cv2.circle(toolbar, (width - 40, height // 2), 18, (200, 200, 200), 1)

    return toolbar


# ─────────────────────────────────────────────────────────────────────────────
# Fingertip indicator
# ─────────────────────────────────────────────────────────────────────────────

def draw_fingertip_indicator(
    frame: np.ndarray,
    tip: Optional[Tuple[int, int]],
    color: Tuple[int, int, int],
    is_drawing: bool,
    is_eraser: bool,
    brush_size: int,
) -> None:
    """Draw a circle around the fingertip on the webcam feed for visual feedback."""
    if tip is None:
        return
    indicator_color = (255, 255, 255) if is_eraser else color
    radius = (config.ERASER_SIZE // 2) if is_eraser else max(brush_size + 4, 12)
    thickness = 3 if is_drawing else 1
    cv2.circle(frame, tip, radius, indicator_color, thickness)
    # Small dot at exact tip
    cv2.circle(frame, tip, 3, indicator_color, -1)


# ─────────────────────────────────────────────────────────────────────────────
# Toolbar click detection
# ─────────────────────────────────────────────────────────────────────────────

def get_clicked_button(
    tip: Optional[Tuple[int, int]],
    toolbar_height: int,
) -> Optional[str]:
    """
    If the fingertip is inside the toolbar area, return the button key it hovers over.
    Returns None if no button is hovered or fingertip is below the toolbar.
    """
    if tip is None:
        return None

    tx, ty = tip
    if ty > toolbar_height:
        return None   # Below toolbar

    btn_w = config.BUTTON_WIDTH
    margin = config.BUTTON_MARGIN
    x_offset = margin

    for _, key in BUTTONS:
        if x_offset <= tx <= x_offset + btn_w:
            return key
        x_offset += btn_w + margin

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── Initialise webcam ────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print(
            "\n[ERROR] Could not open webcam.\n"
            "  • Make sure no other app is using the camera.\n"
            "  • Grant camera permission to Terminal in System Preferences → Privacy.\n"
            "  • Try changing VideoCapture(0) to VideoCapture(1) in main.py.\n"
        )
        sys.exit(1)

    # Request a specific resolution; camera will fall back if unsupported.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

    # Read actual resolution the camera gave us (may differ from requested)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Webcam opened at {actual_w}×{actual_h}")

    # ── Initialise modules ───────────────────────────────────────────────────
    tracker = HandTracker()
    canvas = DrawingCanvas(actual_w, actual_h)

    # ── Application state ────────────────────────────────────────────────────
    current_color_name: str = config.DEFAULT_COLOR_NAME
    current_color: Tuple[int, int, int] = config.COLORS[current_color_name]
    brush_size: int = config.DEFAULT_BRUSH_SIZE
    is_eraser: bool = False
    active_btn: str = current_color_name.lower()

    # FPS tracking
    fps: float = 0.0
    prev_time: float = time.time()

    # Debounce toolbar clicks (require hand to leave toolbar before re-clicking)
    was_in_toolbar: bool = False

    print("[INFO] AI Air Draw started.")
    print("  Raise your index finger to draw.")
    print("  Keyboard: Q/ESC=quit  C=clear  B/G/R/Y=colour  E=eraser  S=save  +/-=brush size")

    # ── Main loop ────────────────────────────────────────────────────────────
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARNING] Dropped frame — retrying...")
            continue

        # Mirror the frame so the user sees a natural reflection
        frame = cv2.flip(frame, 1)

        # ── Hand detection ───────────────────────────────────────────────────
        tracker.process_frame(frame)
        tip = tracker.get_index_fingertip(actual_w, actual_h)

        # Determine gesture
        drawing_mode = gestures.is_index_finger_raised(tracker.current_landmarks)

        # If hand disappeared, reset previous point to prevent jump lines
        if not gestures.is_hand_detected(tracker.current_landmarks):
            canvas.reset_previous_point()

        # ── Toolbar click via fingertip ──────────────────────────────────────
        clicked = get_clicked_button(tip, config.TOOLBAR_HEIGHT)
        if clicked and not was_in_toolbar:
            was_in_toolbar = True
            if clicked == "clear":
                canvas.clear()
            elif clicked == "save":
                path = canvas.save()
                print(f"[INFO] Drawing saved → {path}")
            elif clicked == "eraser":
                is_eraser = True
                active_btn = "eraser"
            elif clicked in COLOR_SWATCHES:
                is_eraser = False
                current_color = COLOR_SWATCHES[clicked]
                current_color_name = clicked.upper()
                active_btn = clicked
        elif not clicked:
            was_in_toolbar = False

        # ── Update canvas (only draw below toolbar) ──────────────────────────
        if tip is not None:
            tx, ty = tip
            if ty > config.TOOLBAR_HEIGHT:
                # Valid drawing area — update canvas
                canvas.update(tx, ty, current_color, brush_size, drawing_mode, is_eraser)
            else:
                # Fingertip is inside toolbar — do not draw
                canvas.reset_previous_point()
        else:
            canvas.reset_previous_point()

        # ── Draw skeleton on webcam feed ─────────────────────────────────────
        tracker.draw_landmarks(frame)

        # ── Fingertip ring indicator ─────────────────────────────────────────
        draw_fingertip_indicator(frame, tip, current_color, drawing_mode, is_eraser, brush_size)

        # ── Blend canvas onto webcam feed ────────────────────────────────────
        # Pixels on the canvas that are NOT pure white get drawn on the webcam
        canvas_img = canvas.image
        # Create a mask: True wherever the canvas has non-white content
        gray_canvas = cv2.cvtColor(canvas_img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray_canvas, 250, 255, cv2.THRESH_BINARY_INV)
        # Apply drawing pixels onto webcam frame
        frame[mask > 0] = canvas_img[mask > 0]

        # ── FPS calculation ───────────────────────────────────────────────────
        now = time.time()
        fps = 1.0 / (now - prev_time + 1e-9)
        prev_time = now

        # ── Build toolbar ────────────────────────────────────────────────────
        if is_eraser:
            mode_label = "ERASER"
        elif drawing_mode:
            mode_label = "DRAW"
        else:
            mode_label = "IDLE"

        toolbar = build_toolbar(
            actual_w,
            config.TOOLBAR_HEIGHT,
            active_btn,
            current_color,
            brush_size,
            mode_label,
            fps,
        )

        # ── Stack toolbar on top of frame ────────────────────────────────────
        combined = np.vstack([toolbar, frame])

        # ── Display window ────────────────────────────────────────────────────
        cv2.imshow("AI Air Draw", combined)

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), 27):              # Q or ESC — quit
            break
        elif key == ord("c"):                  # Clear
            canvas.clear()
        elif key == ord("b"):                  # Blue
            is_eraser = False
            current_color = config.COLORS["BLUE"]
            current_color_name = "BLUE"
            active_btn = "blue"
        elif key == ord("g"):                  # Green
            is_eraser = False
            current_color = config.COLORS["GREEN"]
            current_color_name = "GREEN"
            active_btn = "green"
        elif key == ord("r"):                  # Red
            is_eraser = False
            current_color = config.COLORS["RED"]
            current_color_name = "RED"
            active_btn = "red"
        elif key == ord("y"):                  # Yellow
            is_eraser = False
            current_color = config.COLORS["YELLOW"]
            current_color_name = "YELLOW"
            active_btn = "yellow"
        elif key == ord("e"):                  # Eraser
            is_eraser = True
            active_btn = "eraser"
        elif key == ord("s"):                  # Save
            path = canvas.save()
            print(f"[INFO] Drawing saved → {path}")
        elif key == ord("+") or key == ord("="):   # Bigger brush
            brush_size = min(brush_size + 2, config.MAX_BRUSH_SIZE)
        elif key == ord("-"):                  # Smaller brush
            brush_size = max(brush_size - 2, config.MIN_BRUSH_SIZE)

    # ── Clean up ──────────────────────────────────────────────────────────────
    cap.release()
    tracker.release()
    cv2.destroyAllWindows()
    print("[INFO] AI Air Draw closed cleanly.")


if __name__ == "__main__":
    main()
