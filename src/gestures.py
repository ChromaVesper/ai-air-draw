"""
gestures.py  —  AI Air Draw Easy & Natural Gesture Engine
=========================================================
Intuitive, fatigue-free air gestures:
  🤏 PINCH (Thumb + Index touching) → Natural Precision Drawing / Inking
  ☝  INDEX ONLY                    → Alternative Point-to-Draw
  ✌  PEACE (Two fingers up)         → Eraser
  🖐  OPEN PALM                    → Cursor Hover / Palette Trigger
  ✊  FIST                         → Pause / Commit
  👍  THUMBS UP                    → Instant Save
"""

import math
from typing import Optional, Tuple

GESTURE_IDLE       = "IDLE"
GESTURE_DRAW       = "DRAW"
GESTURE_PINCH_DRAW = "PINCH_DRAW"
GESTURE_ERASER     = "ERASER"
GESTURE_EYEDROP    = "EYEDROP"
GESTURE_FILL       = "FILL"
GESTURE_FIST       = "FIST"
GESTURE_PINCH      = "PINCH"
GESTURE_OPEN_HAND  = "OPEN_HAND"
GESTURE_THUMBS_UP  = "THUMBS_UP"

PINCH_THRESHOLD = 0.052

def _up(lm, tip: int, pip: int) -> bool:
    return lm[tip].y < lm[pip].y

def _thumb_up(lm) -> bool:
    return lm[4].y < lm[3].y

def _dist(lm, a: int, b: int) -> float:
    dx = lm[a].x - lm[b].x
    dy = lm[a].y - lm[b].y
    return math.sqrt(dx * dx + dy * dy)

def is_pinching(landmarks) -> bool:
    """Returns True if thumb and index tips are touching (natural pen grip)."""
    if landmarks is None: return False
    return _dist(landmarks.landmark, 4, 8) < PINCH_THRESHOLD

def recognise_gesture(landmarks, draw_style: str = "PINCH") -> str:
    """
    Evaluates hand configuration with emphasis on natural, strain-free use.
    If draw_style == 'PINCH':
      Pinch thumb + index = DRAW (zero accidental strokes while moving hand!)
      Peace = ERASER
      Open Hand = HOVER / PALETTE
    """
    if landmarks is None:
        return GESTURE_IDLE

    lm = landmarks.landmark

    idx_up = _up(lm, 8, 6)
    mid_up = _up(lm, 12, 10)
    rng_up = _up(lm, 16, 14)
    pnk_up = _up(lm, 20, 18)
    thm_up = _thumb_up(lm)
    pinched = _dist(lm, 4, 8) < PINCH_THRESHOLD

    # 1. Eraser (Peace sign ✌️)
    if idx_up and mid_up and not rng_up and not pnk_up and not pinched:
        return GESTURE_ERASER

    # 2. Pinch Drawing (Pen touch)
    if pinched:
        return GESTURE_PINCH_DRAW if draw_style == "PINCH" else GESTURE_PINCH

    # 3. Open Hand 🖐
    if idx_up and mid_up and rng_up and pnk_up:
        return GESTURE_OPEN_HAND

    # 4. Point-to-Draw (Index only)
    if idx_up and not mid_up and not rng_up and not pnk_up:
        return GESTURE_DRAW

    # 5. Middle only (optional Eyedrop)
    if not idx_up and mid_up and not rng_up and not pnk_up:
        return GESTURE_EYEDROP

    # 6. Ring only (optional Fill)
    if not idx_up and not mid_up and rng_up and not pnk_up:
        return GESTURE_FILL

    # 7. Thumbs up 👍
    if thm_up and not idx_up and not mid_up and not rng_up and not pnk_up:
        return GESTURE_THUMBS_UP

    # 8. Fist ✊
    if not idx_up and not mid_up and not rng_up and not pnk_up and not thm_up:
        return GESTURE_FIST

    return GESTURE_IDLE

def get_pinch_distance(landmarks) -> float:
    if landmarks is None: return 1.0
    return _dist(landmarks.landmark, 4, 8)

def get_palm_center(landmarks, frame_w: int, frame_h: int) -> Optional[Tuple[int, int]]:
    if landmarks is None: return None
    lm = landmarks.landmark
    cx = (lm[0].x + lm[5].x + lm[17].x) / 3.0
    cy = (lm[0].y + lm[5].y + lm[17].y) / 3.0
    return (int(cx * frame_w), int(cy * frame_h))

def get_finger_pressure(landmarks) -> float:
    if landmarks is None: return 1.0
    lm = landmarks.landmark
    rel_z = lm[8].z - lm[0].z
    pressure = 1.0 - (rel_z * 4.0)
    return max(0.40, min(2.0, pressure))

def is_hand_detected(landmarks) -> bool:
    return landmarks is not None
