"""
gestures.py  —  AI Air Draw Revolutionary MS Paint AI Edition
=============================================================
High-precision 3D gesture recognizer with depth & palm kinematics.

Active Gestures:
  ☝  INDEX_ONLY   → DRAW (with primary Color 1)
  ✌  PEACE        → ERASER (index + middle)
  💉 MIDDLE_ONLY  → EYEDROPPER LOUPE (middle finger only)
  💍 RING_ONLY    → PAINT BUCKET FLOOD FILL (ring finger only)
  ✊  FIST         → PAUSE / Commit shape
  🤏  PINCH        → Dynamic Brush Resize (or 2-hand canvas zoom)
  🖐  OPEN_HAND    → Canvas Clear (hold 0.6s)
  👍  THUMBS_UP    → Instant Save
  🔮 PALM_OPEN     → Holographic AR Hand Palette trigger
"""

import math
from typing import Optional, Tuple

# ── Gesture identifiers ───────────────────────────────────────────────────────
GESTURE_IDLE       = "IDLE"
GESTURE_DRAW       = "DRAW"
GESTURE_ERASER     = "ERASER"
GESTURE_EYEDROP    = "EYEDROP"    # 💉 middle finger only
GESTURE_FILL       = "FILL"       # 💍 ring finger only
GESTURE_FIST       = "FIST"
GESTURE_PINCH      = "PINCH"
GESTURE_OPEN_HAND  = "OPEN_HAND"
GESTURE_THUMBS_UP  = "THUMBS_UP"

PINCH_THRESHOLD = 0.052

# ── Kinematic Landmark Helpers ────────────────────────────────────────────────

def _up(lm, tip: int, pip: int) -> bool:
    """Returns True if fingertip is higher on screen (lower Y) than PIP joint."""
    return lm[tip].y < lm[pip].y

def _thumb_up(lm) -> bool:
    return lm[4].y < lm[3].y

def _dist(lm, a: int, b: int) -> float:
    dx = lm[a].x - lm[b].x
    dy = lm[a].y - lm[b].y
    return math.sqrt(dx * dx + dy * dy)

def _dist_3d(lm, a: int, b: int) -> float:
    dx = lm[a].x - lm[b].x
    dy = lm[a].y - lm[b].y
    dz = lm[a].z - lm[b].z
    return math.sqrt(dx * dx + dy * dy + dz * dz)

# ── Gesture Recognizer ────────────────────────────────────────────────────────

def recognise_gesture(landmarks) -> str:
    """
    Evaluates hand configuration.
    Priority: PINCH > OPEN_HAND > ERASER > EYEDROP > FILL > DRAW > THUMBS_UP > FIST > IDLE
    """
    if landmarks is None:
        return GESTURE_IDLE

    lm = landmarks.landmark

    idx_up  = _up(lm, 8,  6)
    mid_up  = _up(lm, 12, 10)
    rng_up  = _up(lm, 16, 14)
    pnk_up  = _up(lm, 20, 18)
    thm_up  = _thumb_up(lm)
    pinch_d = _dist(lm, 4, 8)

    # 1. Pinch (Thumb + Index tip together)
    if pinch_d < PINCH_THRESHOLD:
        return GESTURE_PINCH

    # 2. All 4 fingers extended → Open Hand
    if idx_up and mid_up and rng_up and pnk_up:
        return GESTURE_OPEN_HAND

    # 3. Index + Middle raised → Eraser
    if idx_up and mid_up and not rng_up and not pnk_up:
        return GESTURE_ERASER

    # 4. Middle only → Eyedropper
    if not idx_up and mid_up and not rng_up and not pnk_up:
        return GESTURE_EYEDROP

    # 5. Ring only → Paint Bucket Fill
    if not idx_up and not mid_up and rng_up and not pnk_up:
        return GESTURE_FILL

    # 6. Index only → Draw
    if idx_up and not mid_up and not rng_up and not pnk_up:
        return GESTURE_DRAW

    # 7. Thumbs up only
    if thm_up and not idx_up and not mid_up and not rng_up and not pnk_up:
        return GESTURE_THUMBS_UP

    # 8. All fingers curled → Fist
    if not idx_up and not mid_up and not rng_up and not pnk_up and not thm_up:
        return GESTURE_FIST

    return GESTURE_IDLE


def get_pinch_distance(landmarks) -> float:
    if landmarks is None:
        return 1.0
    return _dist(landmarks.landmark, 4, 8)


def get_palm_center(landmarks, frame_w: int, frame_h: int) -> Optional[Tuple[int, int]]:
    """Calculates pixel coordinates of the palm center using wrist and MCP joints."""
    if landmarks is None:
        return None
    lm = landmarks.landmark
    # Average of wrist (0), index MCP (5), and pinky MCP (17)
    cx = (lm[0].x + lm[5].x + lm[17].x) / 3.0
    cy = (lm[0].y + lm[5].y + lm[17].y) / 3.0
    return (int(cx * frame_w), int(cy * frame_h))


def get_finger_pressure(landmarks) -> float:
    """
    Estimates 3D virtual stylus pressure from index fingertip Z-depth
    relative to the wrist and MCP base.
    Returns normalized pressure float between 0.3 (light) and 2.2 (deep press).
    """
    if landmarks is None:
        return 1.0
    lm = landmarks.landmark
    # Z coordinate is negative when closer to the camera
    rel_z = lm[8].z - lm[0].z
    # Typical rel_z ranges from -0.15 (very close / heavy press) to 0.05 (far)
    pressure = 1.0 - (rel_z * 4.0)
    return max(0.35, min(2.20, pressure))


def is_index_finger_raised(landmarks) -> bool:
    return recognise_gesture(landmarks) == GESTURE_DRAW

def is_hand_detected(landmarks) -> bool:
    return landmarks is not None
