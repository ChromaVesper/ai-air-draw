"""
hand_tracker.py  —  AI Air Draw Advanced
Supports up to 2 hands simultaneously.
Exposes per-hand landmarks, fingertip positions, and handedness.
"""

import cv2
import mediapipe as mp
from typing import Optional, Tuple, List

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import config


class HandTracker:
    """
    Tracks up to 2 hands using MediaPipe Hands.

    Attributes
    ----------
    all_landmarks  : list of NormalizedLandmarkList  (one per hand detected)
    all_handedness : list of ClassificationList       (one per hand detected)
    current_landmarks : first hand's landmarks (for backward compat)
    """

    INDEX_FINGER_TIP = 8

    def __init__(self) -> None:
        self._mp_hands       = mp.solutions.hands
        self._mp_draw        = mp.solutions.drawing_utils
        self._mp_draw_styles = mp.solutions.drawing_styles

        self.hands = self._mp_hands.Hands(
            static_image_mode      = False,
            max_num_hands          = config.MAX_NUM_HANDS,
            min_detection_confidence = config.DETECTION_CONFIDENCE,
            min_tracking_confidence  = config.TRACKING_CONFIDENCE,
        )

        self.all_landmarks:  List = []
        self.all_handedness: List = []
        self.current_landmarks = None   # first hand (back-compat)

        # Cached frame dimensions (set on first process_frame call)
        self._fw: int = config.FRAME_WIDTH
        self._fh: int = config.FRAME_HEIGHT

    # ── Core ─────────────────────────────────────────────────────────────────

    def process_frame(self, bgr_frame) -> None:
        """
        Run MediaPipe on the BGR frame.
        Populates all_landmarks, all_handedness, and current_landmarks.
        """
        self._fh, self._fw = bgr_frame.shape[:2]

        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.hands.process(rgb)
        rgb.flags.writeable = True

        if results.multi_hand_landmarks:
            self.all_landmarks  = results.multi_hand_landmarks
            self.all_handedness = results.multi_handedness or []
            self.current_landmarks = self.all_landmarks[0]
        else:
            self.all_landmarks  = []
            self.all_handedness = []
            self.current_landmarks = None

    # ── Per-hand helpers ──────────────────────────────────────────────────────

    def get_hand_count(self) -> int:
        return len(self.all_landmarks)

    def get_landmarks(self, hand_idx: int = 0):
        """Return landmark list for hand_idx, or None if not tracked."""
        if hand_idx >= len(self.all_landmarks):
            return None
        return self.all_landmarks[hand_idx]

    def get_handedness(self, hand_idx: int = 0) -> Optional[str]:
        """
        Return 'Left' or 'Right' for given hand index (as seen on the
        FLIPPED frame, so 'Left' on screen = user's right hand).
        """
        if hand_idx >= len(self.all_handedness):
            return None
        return self.all_handedness[hand_idx].classification[0].label

    def get_landmark_pixel(
        self, landmark_idx: int, hand_idx: int = 0
    ) -> Optional[Tuple[int, int]]:
        """Return pixel coords of any landmark for a given hand."""
        lm_list = self.get_landmarks(hand_idx)
        if lm_list is None:
            return None
        lm = lm_list.landmark[landmark_idx]
        return (int(lm.x * self._fw), int(lm.y * self._fh))

    def get_index_fingertip(
        self, frame_width: int = 0, frame_height: int = 0, hand_idx: int = 0
    ) -> Optional[Tuple[int, int]]:
        """Return pixel (x, y) of the index fingertip for given hand."""
        return self.get_landmark_pixel(self.INDEX_FINGER_TIP, hand_idx)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw_landmarks(self, frame, hand_idx: int = 0) -> None:
        """Draw hand skeleton for specified hand onto frame in-place."""
        lm = self.get_landmarks(hand_idx)
        if lm is None:
            return
        self._mp_draw.draw_landmarks(
            frame, lm,
            self._mp_hands.HAND_CONNECTIONS,
            self._mp_draw_styles.get_default_hand_landmarks_style(),
            self._mp_draw_styles.get_default_hand_connections_style(),
        )

    def draw_all_landmarks(self, frame) -> None:
        """Draw skeletons for all detected hands."""
        for i in range(self.get_hand_count()):
            self.draw_landmarks(frame, i)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def release(self) -> None:
        self.hands.close()
