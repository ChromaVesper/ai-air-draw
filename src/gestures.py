"""
gestures.py
-----------
Gesture-recognition logic for AI Air Draw.

Design goal: keep this file simple and easy to modify.
Each gesture check is a small, focused function that receives
MediaPipe landmarks and returns a boolean.

MediaPipe 21-point hand landmark reference:
  0  = Wrist
  1  = Thumb CMC  |  2  = Thumb MCP  |  3  = Thumb IP  |  4  = Thumb Tip
  5  = Index MCP  |  6  = Index PIP  |  7  = Index DIP  |  8  = Index Tip
  9  = Middle MCP | 10  = Middle PIP | 11  = Middle DIP | 12  = Middle Tip
  13 = Ring MCP   | 14  = Ring PIP   | 15  = Ring DIP   | 16  = Ring Tip
  17 = Pinky MCP  | 18  = Pinky PIP  | 19  = Pinky DIP  | 20  = Pinky Tip
"""

from typing import Optional


def is_index_finger_raised(landmarks) -> bool:
    """
    Return True when only the index finger is clearly raised (pointing up).

    Logic
    -----
    We compare Y-coordinates (remember: Y increases *downward* in image space,
    so a raised fingertip has a *smaller* Y than the knuckle).

    Condition: index fingertip (8) is above its first knuckle (6)
               AND the middle fingertip (12) is NOT clearly above its knuckle (10).
               This helps distinguish "one finger up" from "peace sign".

    This is intentionally simple — good enough for a drawing app and easy
    to understand for beginners.

    Parameters
    ----------
    landmarks : mediapipe.framework.formats.landmark_pb2.NormalizedLandmarkList
        The hand landmarks returned by MediaPipe (21 points).

    Returns
    -------
    bool
        True = drawing mode, False = idle mode.
    """
    if landmarks is None:
        return False

    lm = landmarks.landmark  # Shorthand alias

    # Index finger: tip (8) vs first knuckle just above palm (6)
    index_raised = lm[8].y < lm[6].y

    # Middle finger: tip (12) vs its knuckle (10)
    # We check that the middle finger is NOT raised (helps reduce accidental triggers)
    middle_raised = lm[12].y < lm[10].y

    return index_raised and not middle_raised


def is_hand_detected(landmarks) -> bool:
    """Simple null-check — True when a hand is currently being tracked."""
    return landmarks is not None
