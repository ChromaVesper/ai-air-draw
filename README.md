# AI Air Draw — Revolutionary MS Paint AI Edition ✋🎨🤖

> The world's most advanced touchless digital painting studio — combining the complete feature set of classic Microsoft Paint with futuristic AI computer vision and augmented reality gestures.

---

## 🌟 What's New in the MS Paint AI Edition

### 🎨 Complete Classic & Modern MS Paint Suite
- **16 Precision Vector Shapes:**
  - Freehand, Line, Bézier Curve (3-point quadratic arc), Rectangle, Rounded Rectangle, Ellipse/Circle, Isosceles Triangle, Right Triangle, Diamond, 5-Point Star, 4-Point Star, Directional Arrow, Heart, Lightning Bolt, Comic Speech Callout, and N-gon Polygon (3 to 12 sides).
- **Shape Fill Styles:**
  - Choose between **Outline Only**, **Solid Fill**, or **Outline + Fill** (classic MS Paint styling).
- **9 Media & Artistic Brushes:**
  - **Pencil** (crisp 1px pixel-art), **Calligraphy Nib** (45° chisel pen), **Pen** (anti-aliased ballpoint), **Marker** (translucent highlighter), **Crayon** (textured wax chalk), **Spray** (airbrush splatter), **Drip** (gravity paint drops), **Neon** (cyberpunk glowing edges), and **Sparkle** (magic glitter particles).
- **Color 1 (Foreground) & Color 2 (Background/Fill):**
  - Dual color slots just like MS Paint! Switch with `TAB` or quick-tap. 16 extended studio swatches with custom color picker support.
- **Paint Tools:**
  - 🪣 **Flood Fill (Paint Bucket):** Fills bounded regions instantly.
  - 🔍 **4x Magnifier Eyedropper Loupe:** Live floating 4x zoom loupe with crosshair, RGB values, and Hex color code readout.
  - 🔤 **Text Placement Tool:** Click, aim with finger, type text with live cursor preview, and commit with `ENTER`.
  - 🔲 **Rectangular & Freeform Lasso Selection:** Select arbitrary regions, move, copy, cut, paste, crop, or delete.
  - ✂️ **Crop to Selection & Transparent Selection Toggle:** Crop canvas directly to active selection or paste with background transparency.
  - 📐 **View Options:** Toggleable pixel-accurate **Rulers** and subtle **Gridlines**.

---

### 🤖 Revolutionary AI Vision Superpowers
- **AI Auto-Shape Beautifier (`🤖SNAP`):**
  - Draw rough wobbly shapes in thin air — the AI automatically classifies your stroke geometry (circle, line, rectangle, triangle, arrow) and morphs it into a razor-sharp mathematical vector shape!
- **AI Real-Time Doodle Classifier ("Quick, Draw!" Engine):**
  - Live AI vision continuously classifies your artwork in real-time, displaying a floating holographic badge: e.g. `🤖 AI: [🌸 Flower 92%]`, `[⭐ Star 95%]`, `[🏠 House 88%]`, `[❤️ Heart 89%]`, `[🚗 Car 86%]`.
- **AI Magic Content-Aware Inpainting (`✨INPNT`):**
  - Select unwanted scribbles or objects, and Navier-Stokes / Telea content-aware inpainting seamlessly restores the canvas texture without leaving blank holes.
- **AI Edge Art / Coloring Book Mode (`📖BOOK`):**
  - Converts any photo, webcam snapshot, or drawing into clean, high-contrast coloring book line-art ready for the paint bucket.
- **Holographic Left-Hand AR Palette (`🔮HOLO`):**
  - Hold up your non-dominant hand — an interactive circular cyberpunk AR color wheel floats directly over your palm! Tap nodes with your index finger to switch colors on the fly.
- **3D Depth Pressure-Sensitive Stylus (`🎚️PRES`):**
  - Push your finger closer to the webcam to naturally increase line thickness and ink saturation in 3D air space.

---

## ✋ Air Gestures

| Gesture | Pose | Action |
|---|---|---|
| ☝ | **Index Finger Raised** | Draw / Paint / Shape drag |
| ✌ | **Peace Sign (Index + Middle)** | Eraser |
| 💉 | **Middle Finger Only** | Eyedropper Loupe (color picker) |
| 💍 | **Ring Finger Only** | Flood Fill (paint bucket) |
| ✊ | **Fist** | Pause / Commit Shape |
| 🤏 | **Pinch (Thumb + Index)** | Dynamic Brush Resize |
| 🖐 | **Open Hand (Hold 0.6s)** | Clear Canvas |
| 👍 | **Thumbs Up (Hold 0.4s)** | Save Masterpiece (PNG) |
| 🔮 | **Open Left Palm** | Holographic AR Color Wheel |

---

## ⌨️ Keyboard Shortcuts

| Key | Function |
|---|---|
| `TAB` | Swap active Color 1 & Color 2 |
| `0` - `6` | Shapes: Freehand, Line, Circle, Rect, Rounded Rect, Tri, Polygon |
| `F` / `I` / `T` / `U` | Flood Fill, Eyedropper, Text, Select |
| `M` | Cycle Brush (Pencil → Callig → Pen → Marker → Crayon → Spray → Drip → Neon → Sparkle) |
| `B` | Toggle AI Auto-Shape Beautifier |
| `W` | Crop canvas to selection |
| `G` / `Y` / `K` | Toggle Gridlines / Cycle Symmetry / Cycle Backgrounds |
| `[` / `]` / `/` | Flip Horizontal / Flip Vertical / Rotate 90° CW |
| `Z` / `X` / `C` | Undo / Cut (or Redo) / Clear Canvas |
| `V` | Paste at cursor (or Invert Colors) |
| `S` / `L` | Save PNG / Load Image |
| `+` / `-` | Increase / Decrease Brush Size |
| `Q` / `ESC` | Exit Studio |

---

## 🚀 Quick Start

```bash
# 1. Activate Virtual Environment
source .venv/bin/activate

# 2. Run the Studio
python src/main.py
```
