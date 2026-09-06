"""
hand_tracker.py
---------------
Wraps MediaPipe's hand-detection solution in a clean, reusable class.
Responsibilities:
  - Initialise MediaPipe Hands once at startup.
  - Accept a BGR OpenCV frame and return processed landmarks.
  - Expose a simple helper to get the index-fingertip pixel position.
  - Handle the 'no hand detected' case gracefully.
"""

import cv2
import mediapipe as mp
from typing import Optional, Tuple

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import config


class HandTracker:
    """Detects and tracks a single hand using MediaPipe Hands."""

    # Index-fingertip is landmark 8 in MediaPipe's 21-point hand model.
    INDEX_FINGER_TIP = 8

    def __init__(self) -> None:
        self._mp_hands = mp.solutions.hands
        self._mp_draw = mp.solutions.drawing_utils
        self._mp_draw_styles = mp.solutions.drawing_styles

        # Initialise the MediaPipe Hands solution.
        self.hands = self._mp_hands.Hands(
            static_image_mode=False,           # Optimised for video (tracks across frames)
            max_num_hands=config.MAX_NUM_HANDS,
            min_detection_confidence=config.DETECTION_CONFIDENCE,
            min_tracking_confidence=config.TRACKING_CONFIDENCE,
        )

        # Holds the most-recently detected landmarks (or None).
        self.current_landmarks = None

    def process_frame(self, bgr_frame) -> None:
        """
        Run MediaPipe on a single BGR frame.
        Updates self.current_landmarks with the first detected hand's landmarks,
        or sets it to None if no hand is found.

        Parameters
        ----------
        bgr_frame : np.ndarray
            The raw webcam frame in BGR colour order.
        """
        # MediaPipe expects RGB, so convert before processing.
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

        # Improve performance: mark the frame as non-writeable before passing it.
        rgb_frame.flags.writeable = False
        results = self.hands.process(rgb_frame)
        rgb_frame.flags.writeable = True

        if results.multi_hand_landmarks:
            # Take only the first detected hand (we configured max_num_hands=1)
            self.current_landmarks = results.multi_hand_landmarks[0]
        else:
            self.current_landmarks = None

    def get_index_fingertip(
        self, frame_width: int, frame_height: int
    ) -> Optional[Tuple[int, int]]:
        """
        Return the pixel (x, y) coordinates of the index-fingertip landmark.

        MediaPipe stores landmark coordinates as normalised fractions (0.0–1.0)
        relative to the frame dimensions, so we multiply by width/height to get
        actual pixel positions.

        Returns None if no hand is currently detected.
        """
        if self.current_landmarks is None:
            return None

        # Landmark 8 = index fingertip
        tip = self.current_landmarks.landmark[self.INDEX_FINGER_TIP]
        x = int(tip.x * frame_width)
        y = int(tip.y * frame_height)
        return (x, y)

    def draw_landmarks(self, frame) -> None:
        """
        Overlay the hand skeleton on *frame* in-place.
        This is purely for visual feedback inside the webcam view.
        Only draws when a hand is detected.
        """
        if self.current_landmarks is None:
            return

        self._mp_draw.draw_landmarks(
            frame,
            self.current_landmarks,
            self._mp_hands.HAND_CONNECTIONS,
            self._mp_draw_styles.get_default_hand_landmarks_style(),
            self._mp_draw_styles.get_default_hand_connections_style(),
        )

    def release(self) -> None:
        """Free MediaPipe resources."""
        self.hands.close()
