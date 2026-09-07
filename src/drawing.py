"""
drawing.py
----------
DrawingCanvas manages the white digital canvas that the user draws on.

Responsibilities:
  - Maintain a NumPy array (the canvas image).
  - Draw smooth, anti-aliased lines between consecutive points.
  - Erase areas.
  - Clear the entire canvas.
  - Save the canvas as a PNG file.
  - Track the previous point so we can draw lines, not just dots.
  - Apply coordinate smoothing to reduce shaky motion.
"""

import cv2
import numpy as np
import os
from datetime import datetime
from typing import Optional, Tuple

import sys
sys.path.insert(0, os.path.dirname(__file__))
import config


class DrawingCanvas:
    """
    A white drawing surface stored as a BGR NumPy array.

    How drawing works
    -----------------
    OpenCV's cv2.line() connects two (x, y) pixel positions with a coloured
    segment.  We store the *previous* fingertip position so we can connect it
    to the *current* position, creating a smooth stroke.  When the user lifts
    their finger or leaves drawing mode, we reset the previous point to None,
    which prevents a connecting line from appearing the next time they start
    drawing.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        # Start with a pure-white canvas (255, 255, 255 in BGR)
        self._canvas: np.ndarray = np.ones((height, width, 3), dtype=np.uint8) * 255

        # Smoothed fingertip position (updated each frame during drawing)
        self._smooth_x: float = 0.0
        self._smooth_y: float = 0.0

        # Previous point used to draw lines between frames
        self._prev_point: Optional[Tuple[int, int]] = None

    # ── Public interface ──────────────────────────────────────────────────────

    def update(
        self,
        raw_x: int,
        raw_y: int,
        color: Tuple[int, int, int],
        brush_size: int,
        drawing_mode: bool,
        is_eraser: bool = False,
    ) -> None:
        """
        Called every frame.  Draws a line segment if drawing mode is active.

        Parameters
        ----------
        raw_x, raw_y  : int
            Current fingertip pixel position (before smoothing).
        color         : tuple  (B, G, R)
            The current drawing colour.
        brush_size    : int
            Thickness of the drawn line.
        drawing_mode  : bool
            True = user is drawing, False = user is idle (no lines drawn).
        is_eraser     : bool
            If True, paint white (erasing) instead of the selected colour.
        """
        if not drawing_mode:
            # Reset previous point so no line appears when drawing resumes
            self.reset_previous_point()
            return

        # ── Apply exponential moving-average smoothing ───────────────────────
        alpha = config.SMOOTHING_ALPHA
        if self._prev_point is None:
            # First frame of a new stroke — initialise smoother at current pos
            self._smooth_x = float(raw_x)
            self._smooth_y = float(raw_y)
        else:
            self._smooth_x = alpha * raw_x + (1 - alpha) * self._smooth_x
            self._smooth_y = alpha * raw_y + (1 - alpha) * self._smooth_y

        current_point = (int(self._smooth_x), int(self._smooth_y))

        # ── Draw ─────────────────────────────────────────────────────────────
        if self._prev_point is not None:
            draw_color = (255, 255, 255) if is_eraser else color
            thickness = config.ERASER_SIZE if is_eraser else brush_size

            cv2.line(
                self._canvas,
                self._prev_point,
                current_point,
                draw_color,
                thickness,
                lineType=cv2.LINE_AA,   # Anti-aliased for smoother look
            )
        else:
            # Very first point of a new stroke — draw a dot so there's no gap
            draw_color = (255, 255, 255) if is_eraser else color
            thickness = config.ERASER_SIZE if is_eraser else brush_size
            cv2.circle(self._canvas, current_point, thickness // 2, draw_color, -1)

        self._prev_point = current_point

    def reset_previous_point(self) -> None:
        """
        Call this whenever drawing should NOT continue from the last point.
        Examples: hand disappears, user switches to idle mode.
        Prevents unwanted 'jump lines' across the canvas.
        """
        self._prev_point = None

    def clear(self) -> None:
        """Reset the canvas to plain white."""
        self._canvas[:] = 255

    def save(self) -> str:
        """
        Save the current canvas as a PNG inside the configured drawings folder.
        Returns the full file path of the saved image.

        The drawings folder is always resolved relative to the project root
        (the parent directory of this file's src/ folder), so the correct
        folder is used regardless of which directory the user runs from.
        """
        # Project root = parent of src/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        drawings_dir = os.path.join(project_root, config.DRAWINGS_DIR)
        os.makedirs(drawings_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"drawing_{timestamp}.png"
        filepath = os.path.join(drawings_dir, filename)
        cv2.imwrite(filepath, self._canvas)
        return filepath

    @property
    def image(self) -> np.ndarray:
        """Return the raw canvas NumPy array (read-only by convention)."""
        return self._canvas
