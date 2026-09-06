# AI Air Draw ✋🎨

> Draw in the air with your index finger — no mouse, no tablet, just your hand and a webcam.

---

## Description

AI Air Draw is a real-time computer-vision application that turns your webcam into a digital drawing board. It detects your hand using MediaPipe, tracks the index fingertip, and lets you paint on a virtual canvas by simply pointing your finger. Raise your index finger to draw; lower it to pause.

---

## Features

- 🖐 Real-time hand tracking via MediaPipe Hands
- ✏️ Index-finger drawing with smooth strokes
- 🎨 Four drawing colours: Blue, Green, Red, Yellow
- 🧹 Eraser tool
- 🗑 One-key canvas clear
- 💾 Save drawing as PNG (timestamped filename)
- 📏 Adjustable brush size (`+` / `-`)
- 📊 Live FPS display
- 🔀 Coordinate smoothing to reduce shaky lines
- ⌨️ Keyboard shortcuts for everything
- 🖱 Toolbar buttons controllable by fingertip hover

---

## Demo

> _Add a GIF or screenshot here after recording a session._
>
> ![Demo GIF](assets/demo.gif)

---

## How It Works

```
Webcam
  → Flip frame (mirror effect)
  → Hand Detection      (MediaPipe Hands)
  → Hand Landmarks      (21 key points on the hand)
  → Index Finger Tip    (Landmark #8)
  → Gesture Recognition (is index finger raised?)
  → Coordinate Tracking (pixel position of the tip)
  → Drawing Canvas      (line drawn between previous & current point)
  → Blend onto webcam   (paint only non-white canvas pixels onto feed)
  → Display UI          (toolbar + mode + FPS)
```

---

## Technologies

| Library | Purpose |
|---|---|
| Python 3.9+ | Core language |
| OpenCV (`opencv-python`) | Webcam access, image drawing, UI window |
| MediaPipe | Hand detection & landmark estimation |
| NumPy | Fast array operations for canvas |

---

## Installation

### 1 — Clone / download the project

```bash
git clone <your-github-url>
cd "hand drow"
```

### 2 — Create a virtual environment (macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Project

```bash
source .venv/bin/activate   # if not already activated
python src/main.py
```

A window titled **AI Air Draw** will open showing your webcam feed with a toolbar at the top.

---

## Keyboard Controls

| Key | Action |
|---|---|
| `Q` or `ESC` | Quit the application |
| `C` | Clear the canvas |
| `B` | Switch to Blue |
| `G` | Switch to Green |
| `R` | Switch to Red |
| `Y` | Switch to Yellow |
| `E` | Activate Eraser |
| `S` | Save drawing as PNG |
| `+` or `=` | Increase brush size |
| `-` | Decrease brush size |

---

## Project Structure

```
hand drow/
│
├── src/
│   ├── main.py          # Entry point — ties everything together
│   ├── hand_tracker.py  # HandTracker class (MediaPipe wrapper)
│   ├── drawing.py       # DrawingCanvas class (canvas management)
│   ├── gestures.py      # Gesture-detection functions
│   └── config.py        # All configurable values in one place
│
├── assets/              # Screenshots / GIFs for README
├── drawings/            # Auto-created; saved PNG files land here
├── requirements.txt     # Python dependencies
├── .gitignore
├── LICENSE
└── README.md
```

### File responsibilities

| File | Responsibility |
|---|---|
| `config.py` | Central settings (colours, sizes, paths) |
| `hand_tracker.py` | MediaPipe initialisation, landmark extraction |
| `gestures.py` | Is the index finger raised? |
| `drawing.py` | Canvas creation, line drawing, save, clear, erase |
| `main.py` | Webcam loop, UI, keyboard, coordination |

---

## Troubleshooting

### Webcam won't open
- Grant **Terminal** camera permission: *System Settings → Privacy & Security → Camera*
- Quit other apps (Zoom, FaceTime) that may have locked the camera
- Try `VideoCapture(1)` instead of `VideoCapture(0)` in `main.py`

### MediaPipe import error
- Make sure your virtual environment is **activated** before running
- Re-install: `pip install mediapipe --upgrade`

### Very low FPS
- Close other apps to free CPU
- Lower `FRAME_WIDTH` / `FRAME_HEIGHT` in `config.py` (e.g. 640×480)
- Reduce `MAX_NUM_HANDS` (already 1)

### Lines appear when not drawing
- Make sure your **index finger is clearly raised** and **middle finger is down**
- Increase `DETECTION_CONFIDENCE` in `config.py` for a stricter detector

---

## Future Improvements

- ↩️ Undo / Redo support
- 🔷 Shape recognition (circle, rectangle)
- 🤚 Multi-hand support
- ✍️ Handwriting-to-text (OCR)
- 🎨 Custom colour picker
- 🖼 Better UI with semi-transparent overlays
- 🤖 AI drawing recognition (e.g. QuickDraw)

---

## License

MIT — see [LICENSE](LICENSE) for details.
