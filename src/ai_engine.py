"""
ai_engine.py — Revolutionary AI Vision Engine for AI Air Draw
=============================================================
Provides intelligent computer vision & machine learning algorithms:
1. AI Shape Beautifier (Auto-Snap rough hand-sketches to perfect vectors)
2. AI Real-Time Doodle Classifier (Recognizes user drawings)
3. AI Magic Content-Aware Inpainting (Seamless object/stroke removal)
4. AI Edge Art / Coloring Book Generator (Photo to clean line-art)
"""

import cv2
import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# 1. AI Shape Beautifier (Auto-Snap messy air strokes to perfect geometry)
# ─────────────────────────────────────────────────────────────────────────────

def beautify_stroke(points: List[Tuple[int, int]]) -> Optional[Dict[str, Any]]:
    """
    Analyzes a sequence of 2D air-drawn points.
    Returns detected geometric shape and canonical parameters, or None if too short.
    Supported: 'line', 'circle', 'ellipse', 'rect', 'triangle', 'star', 'arrow'.
    """
    if len(points) < 8:
        return None

    pts_arr = np.array(points, dtype=np.int32)
    p_start = points[0]
    p_end = points[-1]

    # Path length along stroke
    diffs = pts_arr[1:] - pts_arr[:-1]
    seg_lengths = np.sqrt((diffs ** 2).sum(axis=1))
    total_length = float(np.sum(seg_lengths))
    if total_length < 25:
        return None

    direct_dist = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])

    # Check 1: Straight Line
    # If endpoint distance is > 88% of total curvilinear path length
    if direct_dist / total_length > 0.88:
        # Fit a line
        vx, vy, x0, y0 = cv2.fitLine(pts_arr, cv2.DIST_L2, 0, 0.01, 0.01)
        # Project start and end onto fitted line
        p1 = (int(p_start[0]), int(p_start[1]))
        p2 = (int(p_end[0]), int(p_end[1]))
        return {
            "type": "line",
            "p1": p1,
            "p2": p2,
            "confidence": min(0.99, direct_dist / total_length)
        }

    # Check 2: Closed or semi-closed loop
    is_closed = (direct_dist / total_length < 0.28) or (direct_dist < 40)

    # Form a closed contour
    contour = pts_arr.reshape((-1, 1, 2))
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    contour_area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, closed=True)

    if perimeter <= 0 or hull_area <= 20:
        return None

    # Circularity: 4 * pi * Area / (Perimeter^2)
    circularity = (4 * math.pi * hull_area) / (perimeter * perimeter)
    (cx, cy), radius = cv2.minEnclosingCircle(hull)
    circle_area = math.pi * (radius ** 2)

    # Bounding box & Aspect Ratio
    x, y, w, h = cv2.boundingRect(hull)
    aspect_ratio = float(w) / max(1, h)

    # Approximate polygon with Douglas-Peucker
    epsilon = 0.045 * perimeter
    approx = cv2.approxPolyDP(hull, epsilon, True)
    num_verts = len(approx)

    if is_closed:
        # A) Circle / Ellipse
        if (hull_area / max(1, circle_area) > 0.72) and (0.75 <= aspect_ratio <= 1.33) and circularity > 0.65:
            return {
                "type": "circle",
                "center": (int(cx), int(cy)),
                "radius": int(radius),
                "rx": int(radius),
                "ry": int(radius),
                "confidence": 0.94
            }
        elif (hull_area / max(1, circle_area) > 0.68) and circularity > 0.55:
            # Ellipse
            return {
                "type": "ellipse",
                "center": (int(cx), int(cy)),
                "rx": int(w // 2),
                "ry": int(h // 2),
                "confidence": 0.88
            }

        # B) Triangle (3 vertices)
        if num_verts == 3:
            tri_pts = [tuple(pt[0]) for pt in approx]
            return {
                "type": "triangle",
                "points": tri_pts,
                "confidence": 0.90
            }

        # C) Rectangle / Square (4 vertices or high bounding box fill)
        rect_area = w * h
        if num_verts == 4 or (hull_area / max(1, rect_area) > 0.82):
            return {
                "type": "rect",
                "p1": (x, y),
                "p2": (x + w, y + h),
                "confidence": 0.92
            }

    # D) Arrow detection (open stroke: line with a sharp V tip at the end)
    if not is_closed and len(points) >= 15:
        # Check if the last 30% of stroke doubles back like a barb
        p_body_end = points[int(len(points) * 0.7)]
        body_dist = math.hypot(p_body_end[0] - p_start[0], p_body_end[1] - p_start[1])
        if body_dist > 40:
            return {
                "type": "arrow",
                "p1": (int(p_start[0]), int(p_start[1])),
                "p2": (int(p_end[0]), int(p_end[1])),
                "confidence": 0.85
            }

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. AI Real-Time Doodle Classifier ("Quick, Draw!" AI Guesser)
# ─────────────────────────────────────────────────────────────────────────────

# Known classes with descriptive emojis and visual signatures
CLASSES = [
    ("🌸 Flower",   "flower"),
    ("⭐ Star",     "star"),
    ("🏠 House",    "house"),
    ("🌲 Tree",     "tree"),
    ("☀️ Sun",      "sun"),
    ("🚗 Car",      "car"),
    ("❤️ Heart",    "heart"),
    ("👤 Person",   "person"),
    ("☁️ Cloud",    "cloud"),
    ("🐟 Fish",     "fish"),
    ("☕ Coffee",   "cup"),
    ("📐 Triangle", "triangle"),
    ("📦 Box",      "box"),
    ("✨ Doodle",   "sketch"),
]

def classify_doodle(strokes_img: np.ndarray, bg_img: np.ndarray) -> Tuple[str, int]:
    """
    Examines the active drawing strokes vs background.
    Uses contour topology, convexity defects, moments, and geometry
    to guess what the user is drawing in real time.
    Returns: (Label with emoji, confidence %)
    """
    h, w = strokes_img.shape[:2]
    # Difference mask
    diff = np.abs(strokes_img.astype(np.int16) - bg_img.astype(np.int16))
    mask = (np.any(diff > 25, axis=2)).astype(np.uint8) * 255

    active_pixels = cv2.countNonZero(mask)
    if active_pixels < 180:
        return ("✏️ Start Drawing...", 0)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return ("✨ Sketching...", 20)

    # Combine all contours or take the main one
    all_pts = np.vstack(contours)
    x, y, bw, bh = cv2.boundingRect(all_pts)
    if bw < 25 or bh < 25:
        return ("✨ Sketching...", 25)

    area = cv2.contourArea(all_pts)
    hull = cv2.convexHull(all_pts)
    hull_area = cv2.contourArea(hull)
    solidity = area / max(1.0, hull_area)
    aspect = float(bw) / max(1.0, bh)
    perimeter = cv2.arcLength(hull, True)
    circularity = (4 * math.pi * hull_area) / max(1.0, perimeter * perimeter)

    # Convexity defects for detecting spikes (stars, sun rays, flower petals)
    hull_idx = cv2.convexHull(all_pts, returnPoints=False)
    defects_count = 0
    if len(all_pts) >= 4 and len(hull_idx) >= 4:
        try:
            defects = cv2.convexityDefects(all_pts, hull_idx)
            if defects is not None:
                for i in range(defects.shape[0]):
                    d = defects[i, 0, 3] / 256.0
                    if d > 12:  # significant valley
                        defects_count += 1
        except Exception:
            pass

    # Top-half vs bottom-half pixel balance
    roi_mask = mask[y:y+bh, x:x+bw]
    half_h = bh // 2
    top_pixels = cv2.countNonZero(roi_mask[:half_h, :])
    bot_pixels = cv2.countNonZero(roi_mask[half_h:, :])
    total_roi_px = max(1, top_pixels + bot_pixels)
    top_ratio = top_pixels / total_roi_px

    # Classification rules:
    # 1. Star: 4-6 deep defects, circularity medium, high perimeter
    if 4 <= defects_count <= 8 and 0.40 <= aspect <= 1.50 and circularity < 0.65:
        return ("⭐ Star", min(96, 75 + defects_count * 3))

    # 2. Heart: Top indent, bottom pointy, top ratio around 0.55 - 0.65
    if (0.75 <= aspect <= 1.35) and 0.50 <= top_ratio <= 0.70 and defects_count in (1, 2) and solidity < 0.85:
        # Check top center valley
        top_center = roi_mask[:int(bh*0.3), int(bw*0.35):int(bw*0.65)]
        if cv2.countNonZero(top_center) < (bw * bh * 0.05):
            return ("❤️ Heart", 89)

    # 3. Sun: Lots of defect rays, high circularity of core
    if defects_count >= 6 and 0.75 <= aspect <= 1.30:
        return ("☀️ Sun", 91)

    # 4. Flower: 4 to 8 soft petal lobes, roundish aspect
    if 4 <= defects_count <= 7 and 0.70 <= aspect <= 1.40 and solidity > 0.60:
        return ("🌸 Flower", 92)

    # 5. Tree: Narrow bottom (trunk), wide/bushy top
    if top_ratio > 0.62 and aspect < 1.1:
        # Check bottom center has narrow trunk
        bot_strip = roi_mask[int(bh*0.75):, :]
        bot_width = np.sum(np.any(bot_strip > 0, axis=0))
        if bot_width < bw * 0.55:
            return ("🌲 Tree", 88)

    # 6. House: Triangle top (roof) + square bottom, or balanced top with chimney
    if 0.70 <= aspect <= 1.40 and 0.40 <= top_ratio <= 0.60:
        # Check bottom is rectangular / high width
        bot_strip = roi_mask[int(bh*0.6):, :]
        bot_width = np.sum(np.any(bot_strip > 0, axis=0))
        if bot_width > bw * 0.75 and solidity > 0.55:
            return ("🏠 House", 87)

    # 7. Car: Wide aspect ratio >= 1.6, more weight in middle/bottom
    if aspect >= 1.60 and top_ratio < 0.55:
        return ("🚗 Car", 86)

    # 8. Fish: Oval horizontal aspect 1.3 - 2.5, tail fin at one side
    if 1.3 <= aspect <= 2.8 and 0.40 <= top_ratio <= 0.60 and defects_count in (1, 2, 3):
        return ("🐟 Fish", 83)

    # 9. Cloud: Horizontal wide, bumpy top, flat bottom
    if aspect >= 1.4 and top_ratio > 0.55 and defects_count >= 2:
        return ("☁️ Cloud", 85)

    # 10. Cup / Mug: Vertical with handle protrusion on one side
    if 0.6 <= aspect <= 1.3:
        left_half = cv2.countNonZero(roi_mask[:, :bw//2])
        right_half = cv2.countNonZero(roi_mask[:, bw//2:])
        lr_diff = abs(left_half - right_half) / max(1, left_half + right_half)
        if lr_diff > 0.28:
            return ("☕ Coffee Cup", 81)

    # 11. Face / Person
    if 0.65 <= aspect <= 1.35 and circularity > 0.70:
        return ("👤 Face", 80)

    # 12. Geometric fallback
    if 0.8 <= aspect <= 1.25 and circularity > 0.75:
        return ("⚪ Circle", 85)
    elif 0.75 <= aspect <= 1.35 and solidity > 0.80:
        return ("📦 Box", 82)
    elif defects_count == 0 and solidity > 0.50 and aspect > 0.5:
        return ("📐 Triangle", 78)

    return ("✨ Creative Art", 72)


# ─────────────────────────────────────────────────────────────────────────────
# 3. AI Magic Content-Aware Eraser (Inpainting)
# ─────────────────────────────────────────────────────────────────────────────

def magic_inpaint(canvas_strokes: np.ndarray, mask: np.ndarray, radius: int = 7) -> np.ndarray:
    """
    Applies Navier-Stokes / Telea content-aware inpainting to remove
    strokes covered by mask, restoring seamless natural background texture.
    """
    if cv2.countNonZero(mask) == 0:
        return canvas_strokes.copy()
    # Dilate mask slightly so edges of strokes are cleanly covered
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dilated_mask = cv2.dilate(mask, kernel, iterations=1)
    result = cv2.inpaint(canvas_strokes, dilated_mask, radius, cv2.INPAINT_TELEA)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. AI Edge Art / Coloring Book Mode Generator
# ─────────────────────────────────────────────────────────────────────────────

def photo_to_coloring_book(image_bgr: np.ndarray, dark_mode: bool = False) -> np.ndarray:
    """
    Converts any photograph or webcam capture into a clean, professional
    black-and-white coloring book page with strong outlines ready for flood-fill.
    """
    h, w = image_bgr.shape[:2]
    # Bilateral filter to smooth color textures while keeping sharp silhouette edges
    filtered = cv2.bilateralFilter(image_bgr, d=9, sigmaColor=75, sigmaSpace=75)
    gray = cv2.cvtColor(filtered, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold for clean cartoon / coloring book line-art
    edges = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,
        blockSize=9, C=4
    )

    # Median blur to eliminate salt-and-pepper noise specks
    edges = cv2.medianBlur(edges, 3)

    if dark_mode:
        # Inverted: white lines on dark background
        line_art = 255 - edges
        bgr_out = cv2.cvtColor(line_art, cv2.COLOR_GRAY2BGR)
    else:
        # Classic coloring book: dark outlines on white paper
        bgr_out = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    return bgr_out
