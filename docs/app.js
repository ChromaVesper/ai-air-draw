/**
 * AI Air Draw — Revolutionary MS Paint AI Edition  v4.0
 * Advanced Gesture Recognition & Protected Interaction Architecture
 * 
 * Features:
 * - Rotation-invariant geometric 3D hand gesture recognition
 * - Temporal gesture stabilization (5-frame majority voting)
 * - Protected Hold-to-Save command system (1.2s intentional hold + 3s cooldown)
 * - Complete elimination of accidental downloads / false triggers
 * - Adaptive dual-speed EMA cursor smoothing (jitter-free air drawing)
 * - Live Glassmorphism Gesture HUD status panel
 * - Interactive Gesture Calibration & Sensitivity settings modal
 * - 9 Brushes · 16 Vector Shapes · Symmetry · AI Tools · Full Undo/Redo
 */

'use strict';

// ═══════════════════════════════════════════════════════════
// PALETTE & GLOBAL STATE
// ═══════════════════════════════════════════════════════════
const PALETTE = [
  '#000000', '#FFFFFF', '#7F7F7F', '#C3C3C3',
  '#880015', '#B97A57', '#ED1C24', '#FFAEC9',
  '#FF7F27', '#FFC90E', '#FFF200', '#EFE4B0',
  '#22B14C', '#B5E61D', '#00A2E8', '#99D9EA',
  '#3F48CC', '#7092BE', '#A349A4', '#C8BFE7'
];

// Active drawing and tool states
let COLOR1 = '#ED1C24';       // Stroke / Foreground color
let COLOR2 = '#FFFFFF';       // Fill / Background color
let BRUSH_SIZE = 8;
let OPACITY = 1.0;
let CURRENT_TOOL = 'pen';
let SHAPE_FILL = 'outline';   // 'outline' | 'fill' | 'both'
let SYMMETRY = 'none';        // 'none' | 'mirror_h' | 'mirror_v' | 'quad' | 'radial4' | 'radial8'
let BACKGROUND = 'white';
let RAINBOW_MODE = false;
let AI_SNAP_LIVE = false;
let rainbowHue = 0;

// Stroke & pointer state
let isDrawing = false;
let startX = 0, startY = 0;
let lastX = 0, lastY = 0;
let strokePoints = [];
let lassoPoints = [];
let dripParticles = [];
let curveControl = null;
let textPending = null;
const polygonSides = 6;
const magnifierZoom = 3;

// ═══════════════════════════════════════════════════════════
// CALIBRATION & SENSITIVITY CONFIGURATION (with LocalStorage)
// ═══════════════════════════════════════════════════════════
const CONFIG = {
  pinchSensitivity: 3,        // 1 (tight) to 5 (wide), default 3
  cursorSmoothing: 3,         // 1 (instant) to 5 (ultra-smooth), default 3
  holdDurationMs: 1200,       // Duration required to confirm protected commands (ms)
  saveCooldownMs: 3000        // Mandatory delay before another save can execute (ms)
};

function loadUserPreferences() {
  try {
    const saved = localStorage.getItem('ai_air_draw_config');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed.pinchSensitivity) CONFIG.pinchSensitivity = parsed.pinchSensitivity;
      if (parsed.cursorSmoothing)  CONFIG.cursorSmoothing  = parsed.cursorSmoothing;
      if (parsed.holdDurationMs)   CONFIG.holdDurationMs   = parsed.holdDurationMs;
    }
  } catch (e) {
    console.warn('Preferences load error:', e);
  }
}

function saveUserPreferences() {
  try {
    localStorage.setItem('ai_air_draw_config', JSON.stringify(CONFIG));
  } catch (e) {
    console.warn('Preferences save error:', e);
  }
}

// ═══════════════════════════════════════════════════════════
// GESTURE STATE MACHINE & TIMING ENGINE
// ═══════════════════════════════════════════════════════════
const GESTURE_STATE = {
  NO_HAND: 'NO_HAND',
  NEUTRAL: 'NEUTRAL',
  HOVER: 'HOVER',
  DRAWING: 'DRAWING',
  ERASER: 'ERASER',
  COMMAND_PENDING: 'COMMAND_PENDING',
  COMMAND_CONFIRMED: 'COMMAND_CONFIRMED',
  COOLDOWN: 'COOLDOWN'
};

let currentGestureState = GESTURE_STATE.NO_HAND;
let activeGestureName = 'NO_HAND';
let activeConfidence = 0.0;
let gestureHistory = [];      // 5-frame temporal buffer
const GESTURE_HISTORY_SIZE = 5;

// Protected Command Latch (Guarantees zero accidental downloads)
let commandHoldStartTime = 0;
let commandCooldownUntil = 0;
let saveCommandLatched = false; // requires releasing gesture before next save

// Adaptive cursor smoothing
let smoothCursorX = 0, smoothCursorY = 0;
let prevRawCursorX = 0, prevRawCursorY = 0;
let lastFrameTimestamp = performance.now();

// MediaPipe & Camera instance handles
let handsInstance = null;
let cameraInstance = null;
let cameraActive = false;
let handMode = true;

// Undo / Redo history
const UNDO_MAX = 40;
let undoStack = [];
let redoStack = [];

// Canvas layers
let canvasBg, ctxBg;
let canvasDraw, ctxDraw;
let canvasOverlay, ctxOverlay;
let canvasW = 0, canvasH = 0;

// ═══════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════
window.addEventListener('DOMContentLoaded', () => {
  loadUserPreferences();
  buildColorPalette();
  bindCamScreenButtons();
  bindKeyboardShortcuts();
  initColorWheel();
  initCalibrationControls();
});

function buildColorPalette() {
  const container = document.getElementById('color-discs');
  if (!container) return;
  container.innerHTML = '';
  PALETTE.forEach(hex => {
    const d = document.createElement('div');
    d.className = 'color-disc';
    d.style.background = hex;
    d.title = `Color: ${hex} (Left-click: Stroke, Right-click: Fill)`;
    d.addEventListener('click', () => setColor1(hex));
    d.addEventListener('contextmenu', e => { e.preventDefault(); setColor2(hex); });
    container.appendChild(d);
  });
}

function bindCamScreenButtons() {
  const btnStartCam = document.getElementById('btn-start-cam');
  const btnNoCam = document.getElementById('btn-no-cam');
  const camScreen = document.getElementById('cam-screen');
  const app = document.getElementById('app');

  if (btnStartCam) {
    btnStartCam.addEventListener('click', () => {
      camScreen.style.display = 'none';
      app.style.display = 'flex';
      initStudio(true);
    });
  }
  if (btnNoCam) {
    btnNoCam.addEventListener('click', () => {
      camScreen.style.display = 'none';
      app.style.display = 'flex';
      initStudio(false);
    });
  }
}

function initStudio(withCamera) {
  canvasBg = document.getElementById('canvas-bg');
  canvasDraw = document.getElementById('canvas-draw');
  canvasOverlay = document.getElementById('canvas-overlay');

  ctxBg = canvasBg.getContext('2d');
  ctxDraw = canvasDraw.getContext('2d', { willReadFrequently: true });
  ctxOverlay = canvasOverlay.getContext('2d');

  resizeCanvases();
  window.addEventListener('resize', debounce(resizeCanvases, 120));
  renderBackground();

  bindToolbarControls();
  bindCanvasPointerEvents();
  updateColorSwatches();
  pushUndo();

  if (withCamera) {
    handMode = true;
    startHandTracking();
  } else {
    handMode = false;
    updateHUD('Camera Inactive', 'Inactive', 'MOUSE / TOUCH', 1.0, 'Neutral', 'Mouse mode active');
    document.getElementById('btn-cam-toggle').textContent = '📷 Camera OFF';
    document.getElementById('btn-mouse-mode').classList.add('active');
    document.getElementById('btn-hand-mode').classList.remove('active');
  }

  showToast('🎨 AI Air Draw Studio Ready!');
}

function resizeCanvases() {
  if (!canvasBg) return;
  const studio = document.getElementById('studio');
  canvasW = studio.clientWidth || window.innerWidth;
  canvasH = studio.clientHeight || (window.innerHeight - 94);

  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = canvasW;
  tempCanvas.height = canvasH;
  const tempCtx = tempCanvas.getContext('2d');
  if (canvasDraw && canvasDraw.width > 0 && canvasDraw.height > 0) {
    tempCtx.drawImage(canvasDraw, 0, 0);
  }

  [canvasBg, canvasDraw, canvasOverlay].forEach(c => {
    c.width = canvasW;
    c.height = canvasH;
  });

  renderBackground();
  if (canvasDraw && tempCanvas.width > 0) {
    ctxDraw.drawImage(tempCanvas, 0, 0);
  }
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// ═══════════════════════════════════════════════════════════
// TOOLBAR & CONTROLS BINDING
// ═══════════════════════════════════════════════════════════
function bindToolbarControls() {
  document.querySelectorAll('[data-tool]').forEach(btn => {
    btn.addEventListener('click', () => selectTool(btn.dataset.tool));
  });

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => { p.style.display = 'none'; });
      btn.classList.add('active');
      const panel = document.getElementById('tab-panel-' + btn.dataset.tab);
      if (panel) panel.style.display = 'flex';
    });
  });

  // Size slider — live sync
  const sizeSlider = document.getElementById('size-slider');
  const sizeVal = document.getElementById('size-val');
  function onSizeChange(val) {
    BRUSH_SIZE = Math.max(1, Math.min(80, parseInt(val, 10)));
    sizeSlider.value = BRUSH_SIZE;
    sizeVal.textContent = BRUSH_SIZE;
  }
  sizeSlider.addEventListener('input', e => onSizeChange(e.target.value));
  sizeSlider.addEventListener('change', e => onSizeChange(e.target.value));

  // Opacity slider
  const opSlider = document.getElementById('opacity-slider');
  const opVal = document.getElementById('opacity-val');
  opSlider.addEventListener('input', e => {
    OPACITY = parseInt(e.target.value, 10) / 100;
    opVal.textContent = e.target.value;
  });

  // Action buttons (Normal Clickable Actions)
  document.getElementById('btn-undo').addEventListener('click', undo);
  document.getElementById('btn-redo').addEventListener('click', redo);
  document.getElementById('btn-clear').addEventListener('click', clearCanvas);
  document.getElementById('btn-save').addEventListener('click', () => {
    executeExplicitSave('Toolbar button clicked');
  });

  // Color Swatches
  document.getElementById('color1-swatch').addEventListener('click', () => openColorPicker('fg'));
  document.getElementById('color2-swatch').addEventListener('click', () => openColorPicker('bg'));
  document.getElementById('btn-custom-color').addEventListener('click', () => openColorPicker('fg'));

  // Shape style
  document.querySelectorAll('.sfill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sfill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      SHAPE_FILL = btn.dataset.fill;
      showToast('Shape style: ' + SHAPE_FILL);
    });
  });

  // AI Suite buttons
  document.getElementById('btn-ai-snap').addEventListener('click', runAIShapeSnap);
  document.getElementById('btn-ai-classify').addEventListener('click', runAIDoodleClassifier);
  document.getElementById('btn-ai-coloring').addEventListener('click', runAIColoringBook);
  document.getElementById('btn-ai-inpaint').addEventListener('click', runAIInpaint);
  document.getElementById('btn-ai-style').addEventListener('click', runAIStyleTransfer);
  document.getElementById('ai-snap-realtime').addEventListener('change', e => { AI_SNAP_LIVE = e.target.checked; });
  document.getElementById('ai-rainbow').addEventListener('change', e => { RAINBOW_MODE = e.target.checked; });

  // Effects & Filters
  const fxList = [
    ['btn-fx-invert', 'invert'], ['btn-fx-gray', 'grayscale'], ['btn-fx-blur', 'blur'],
    ['btn-fx-sharpen', 'sharpen'], ['btn-fx-sepia', 'sepia'], ['btn-fx-emboss', 'emboss'],
    ['btn-fx-fliph', 'fliph'], ['btn-fx-flipv', 'flipv'], ['btn-fx-rot90', 'rot90']
  ];
  fxList.forEach(([id, fx]) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', () => applyFX(fx));
  });

  // Canvas backgrounds
  document.querySelectorAll('.bg-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      BACKGROUND = btn.dataset.bg;
      renderBackground();
      showToast('Background: ' + BACKGROUND);
    });
  });

  // Symmetry modes
  document.querySelectorAll('.sym-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sym-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      SYMMETRY = btn.dataset.sym;
      showToast('Symmetry: ' + SYMMETRY);
    });
  });

  // Camera toggle
  document.getElementById('btn-cam-toggle').addEventListener('click', toggleCamera);

  // Mode toggles
  document.getElementById('btn-hand-mode').addEventListener('click', () => {
    handMode = true;
    document.getElementById('btn-hand-mode').classList.add('active');
    document.getElementById('btn-mouse-mode').classList.remove('active');
    if (!cameraActive) startHandTracking();
  });
  document.getElementById('btn-mouse-mode').addEventListener('click', () => {
    handMode = false;
    document.getElementById('btn-mouse-mode').classList.add('active');
    document.getElementById('btn-hand-mode').classList.remove('active');
    updateHUD('Camera Off', 'Inactive', 'MOUSE MODE', 1.0, 'Neutral', 'Mouse/Touch active');
  });

  // Gesture guide drawer
  document.getElementById('btn-show-hint').addEventListener('click', () => {
    document.getElementById('gesture-hint').style.display = 'flex';
  });
  document.getElementById('btn-close-hint').addEventListener('click', () => {
    document.getElementById('gesture-hint').style.display = 'none';
  });

  // Calibration modal trigger
  document.getElementById('btn-calibrate').addEventListener('click', openCalibrationModal);
  document.getElementById('btn-close-calib').addEventListener('click', closeCalibrationModal);

  // Color picker modal buttons
  document.getElementById('picker-fg').addEventListener('click', () => { applyPickedColor('fg'); closeColorPicker(); });
  document.getElementById('picker-bg').addEventListener('click', () => { applyPickedColor('bg'); closeColorPicker(); });
  document.getElementById('picker-cancel').addEventListener('click', closeColorPicker);
  ['ph', 'ps', 'pl'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateColorPickerPreview);
  });

  // Floating text tool
  document.getElementById('btn-text-cancel').addEventListener('click', () => {
    document.getElementById('text-input-wrap').style.display = 'none';
    textPending = null;
  });

  // AI Classification close
  document.getElementById('btn-ai-result-close').addEventListener('click', () => {
    document.getElementById('ai-result').style.display = 'none';
  });
}

function updateColorSwatches() {
  const c1 = document.getElementById('color1-swatch');
  const c2 = document.getElementById('color2-swatch');
  if (c1) c1.style.background = COLOR1;
  if (c2) c2.style.background = COLOR2;
}

function setColor1(hex) {
  COLOR1 = hex;
  updateColorSwatches();
}
function setColor2(hex) {
  COLOR2 = hex;
  updateColorSwatches();
}

// ═══════════════════════════════════════════════════════════
// TOOL SELECTION & CURSORS
// ═══════════════════════════════════════════════════════════
function selectTool(tool) {
  CURRENT_TOOL = tool;
  document.querySelectorAll('[data-tool]').forEach(b => b.classList.remove('tool-active'));
  document.querySelectorAll(`[data-tool="${tool}"]`).forEach(b => b.classList.add('tool-active'));

  const textWrap = document.getElementById('text-input-wrap');
  if (textWrap) textWrap.style.display = (tool === 'text') ? 'flex' : 'none';

  if (canvasOverlay) canvasOverlay.style.cursor = getToolCursor(tool);
  showToast('Tool: ' + tool);
}

function getToolCursor(tool) {
  const cursors = {
    pen: 'crosshair', pencil: 'crosshair', marker: 'crosshair', calligraphy: 'crosshair',
    crayon: 'crosshair', spray: 'crosshair', neon: 'crosshair', drip: 'crosshair', sparkle: 'crosshair',
    eraser: 'cell', fill: 'cell', eyedropper: 'crosshair', text: 'text', magnifier: 'zoom-in',
    'select-rect': 'default', lasso: 'default', crop: 'crosshair',
    line: 'crosshair', rect: 'crosshair', rndrect: 'crosshair', circle: 'crosshair',
    triangle: 'crosshair', diamond: 'crosshair', star5: 'crosshair', star4: 'crosshair',
    arrow: 'crosshair', heart: 'crosshair', lightning: 'crosshair', callout: 'crosshair',
    hexagon: 'crosshair', curve: 'crosshair', polygon: 'crosshair', freehand: 'crosshair'
  };
  return cursors[tool] || 'crosshair';
}

// ═══════════════════════════════════════════════════════════
// SHARED CANVAS DRAWING ENGINE (Isolated from Toolbar Actions)
// ═══════════════════════════════════════════════════════════
function bindCanvasPointerEvents() {
  const el = canvasOverlay;

  el.addEventListener('mousedown', e => {
    if (handMode && cameraActive) return; // In hand mode with camera on, hand gestures own the canvas
    if (e.button === 2) {
      if (CURRENT_TOOL === 'eyedropper') pickColorAt(e.offsetX, e.offsetY, 2);
      return;
    }
    onPointerDown(e.offsetX, e.offsetY);
  });

  el.addEventListener('mousemove', e => {
    if (handMode && cameraActive) return;
    onPointerMove(e.offsetX, e.offsetY);
  });

  el.addEventListener('mouseup', () => {
    if (handMode && cameraActive) return;
    onPointerUp();
  });

  el.addEventListener('mouseleave', () => {
    if (handMode && cameraActive) return;
    onPointerUp();
  });

  el.addEventListener('contextmenu', e => e.preventDefault());

  // Mobile Touch Support
  el.addEventListener('touchstart', e => {
    e.preventDefault();
    if (handMode && cameraActive) return;
    const r = el.getBoundingClientRect();
    const t = e.touches[0];
    onPointerDown(t.clientX - r.left, t.clientY - r.top);
  }, { passive: false });

  el.addEventListener('touchmove', e => {
    e.preventDefault();
    if (handMode && cameraActive) return;
    const r = el.getBoundingClientRect();
    const t = e.touches[0];
    onPointerMove(t.clientX - r.left, t.clientY - r.top);
  }, { passive: false });

  el.addEventListener('touchend', () => {
    if (handMode && cameraActive) return;
    onPointerUp();
  });
}

const SHAPE_TOOL_SET = new Set([
  'line', 'rect', 'rndrect', 'circle', 'triangle', 'diamond',
  'star5', 'star4', 'arrow', 'heart', 'lightning', 'callout',
  'hexagon', 'curve', 'polygon', 'freehand', 'select-rect', 'lasso', 'crop'
]);

function onPointerDown(x, y) {
  if (CURRENT_TOOL === 'eyedropper') { pickColorAt(x, y, 1); return; }
  if (CURRENT_TOOL === 'fill')       { floodFill(x, y); return; }
  if (CURRENT_TOOL === 'magnifier')  { showMagnifier(x, y); return; }
  if (CURRENT_TOOL === 'text')       { prepareTextPlacement(x, y); return; }

  pushUndo();
  isDrawing = true;
  startX = x; startY = y;
  lastX = x;  lastY = y;
  strokePoints = [[x, y]];
  lassoPoints  = [[x, y]];
  dripParticles = [];

  if (!SHAPE_TOOL_SET.has(CURRENT_TOOL)) {
    applyBrush(ctxDraw, x, y, x + 0.1, y + 0.1);
    applySymmetry(x, y, x + 0.1, y + 0.1);
  }
}

function onPointerMove(x, y) {
  if (!isDrawing) return;
  strokePoints.push([x, y]);

  if (SHAPE_TOOL_SET.has(CURRENT_TOOL)) {
    ctxOverlay.clearRect(0, 0, canvasW, canvasH);
    drawShapePreview(ctxOverlay, startX, startY, x, y, false);
    if (CURRENT_TOOL === 'lasso' || CURRENT_TOOL === 'freehand') {
      lassoPoints.push([x, y]);
    }
  } else {
    applyBrush(ctxDraw, lastX, lastY, x, y);
    applySymmetry(lastX, lastY, x, y);
  }

  lastX = x;
  lastY = y;
}

function onPointerUp() {
  if (!isDrawing) return;
  isDrawing = false;
  ctxOverlay.clearRect(0, 0, canvasW, canvasH);

  if (SHAPE_TOOL_SET.has(CURRENT_TOOL)) {
    drawShapePreview(ctxDraw, startX, startY, lastX, lastY, true);
  }

  if (AI_SNAP_LIVE && strokePoints.length > 5) {
    runAIShapeSnap();
  }
}

// ═══════════════════════════════════════════════════════════
// 9 PROFESSIONAL BRUSH IMPLEMENTATIONS
// ═══════════════════════════════════════════════════════════
function getActiveColor(alpha = 1) {
  if (RAINBOW_MODE) {
    rainbowHue = (rainbowHue + 1.8) % 360;
    return `hsla(${rainbowHue}, 100%, 50%, ${alpha})`;
  }
  const r = parseInt(COLOR1.slice(1, 3), 16) || 0;
  const g = parseInt(COLOR1.slice(3, 5), 16) || 0;
  const b = parseInt(COLOR1.slice(5, 7), 16) || 0;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function applyBrush(ctx, x1, y1, x2, y2) {
  ctx.save();
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = OPACITY;
  ctx.strokeStyle = getActiveColor(1);
  ctx.fillStyle   = getActiveColor(1);
  ctx.lineJoin = 'round';
  ctx.lineCap  = 'round';

  switch (CURRENT_TOOL) {
    case 'pen':
      ctx.lineWidth = BRUSH_SIZE;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      break;

    case 'pencil': {
      ctx.lineWidth = Math.max(1, BRUSH_SIZE * 0.45);
      ctx.globalAlpha = OPACITY * 0.75;
      for (let i = 0; i < 3; i++) {
        const jitter = (Math.random() - 0.5) * (BRUSH_SIZE * 0.4);
        ctx.beginPath();
        ctx.moveTo(x1 + jitter, y1 + jitter);
        ctx.lineTo(x2 + jitter, y2 + jitter);
        ctx.stroke();
      }
      break;
    }

    case 'marker': {
      ctx.lineWidth = BRUSH_SIZE * 2.5;
      ctx.globalAlpha = OPACITY * 0.4;
      ctx.lineCap = 'square';
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      break;
    }

    case 'calligraphy': {
      const angle = Math.PI / 4;
      const cosA = Math.cos(angle) * BRUSH_SIZE * 0.8;
      const sinA = Math.sin(angle) * BRUSH_SIZE * 0.8;
      ctx.beginPath();
      ctx.moveTo(x1 - cosA, y1 - sinA);
      ctx.lineTo(x1 + cosA, y1 + sinA);
      ctx.lineTo(x2 + cosA, y2 + sinA);
      ctx.lineTo(x2 - cosA, y2 - sinA);
      ctx.closePath();
      ctx.fill();
      break;
    }

    case 'crayon': {
      ctx.globalAlpha = OPACITY * 0.15;
      const count = Math.max(20, BRUSH_SIZE * 4);
      for (let i = 0; i < count; i++) {
        const t = Math.random();
        const rx = x1 + (x2 - x1) * t + (Math.random() - 0.5) * BRUSH_SIZE * 1.8;
        const ry = y1 + (y2 - y1) * t + (Math.random() - 0.5) * BRUSH_SIZE * 1.8;
        ctx.fillRect(rx, ry, 1.8, 1.8);
      }
      break;
    }

    case 'spray': {
      ctx.globalAlpha = OPACITY * 0.1;
      const sprayRadius = BRUSH_SIZE * 1.8;
      const drops = Math.max(30, BRUSH_SIZE * 6);
      for (let i = 0; i < drops; i++) {
        const ang = Math.random() * Math.PI * 2;
        const dist = Math.random() * sprayRadius;
        ctx.fillRect(x2 + Math.cos(ang) * dist, y2 + Math.sin(ang) * dist, 1.5, 1.5);
      }
      break;
    }

    case 'neon': {
      const layers = [
        { width: BRUSH_SIZE * 5, alpha: 0.05 },
        { width: BRUSH_SIZE * 2.5, alpha: 0.2 },
        { width: BRUSH_SIZE * 0.7, alpha: 1.0 }
      ];
      layers.forEach(l => {
        ctx.globalAlpha = OPACITY * l.alpha;
        ctx.lineWidth = l.width;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      });
      break;
    }

    case 'drip': {
      ctx.lineWidth = BRUSH_SIZE;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();

      if (Math.random() < 0.1) {
        dripParticles.push({ x: x2, y: y2, length: 0, maxLength: BRUSH_SIZE * (3 + Math.random() * 8) });
      }
      ctx.lineWidth = Math.max(1, BRUSH_SIZE * 0.5);
      dripParticles.forEach(dp => {
        dp.length += 2.5;
        ctx.globalAlpha = OPACITY * Math.max(0, 1 - dp.length / dp.maxLength);
        ctx.beginPath();
        ctx.moveTo(dp.x, dp.y);
        ctx.lineTo(dp.x, dp.y + dp.length);
        ctx.stroke();
      });
      dripParticles = dripParticles.filter(dp => dp.length < dp.maxLength);
      break;
    }

    case 'sparkle': {
      const sparkles = Math.max(3, Math.ceil(BRUSH_SIZE / 2));
      for (let i = 0; i < sparkles; i++) {
        const sx = x2 + (Math.random() - 0.5) * BRUSH_SIZE * 3.5;
        const sy = y2 + (Math.random() - 0.5) * BRUSH_SIZE * 3.5;
        const r = Math.random() * 2.5 + 0.5;
        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        ctx.fill();
      }
      break;
    }

    case 'eraser': {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.globalAlpha = 1;
      ctx.lineWidth = BRUSH_SIZE * 2.2;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      break;
    }
  }

  ctx.restore();
}

// ═══════════════════════════════════════════════════════════
// 16 PRECISION VECTOR SHAPES
// ═══════════════════════════════════════════════════════════
function drawShapePreview(ctx, x1, y1, x2, y2, commit) {
  const tool = CURRENT_TOOL;
  ctx.save();
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = commit ? OPACITY : OPACITY * 0.75;
  ctx.strokeStyle = getActiveColor(1);
  ctx.fillStyle   = COLOR2;
  ctx.lineWidth   = BRUSH_SIZE;
  ctx.lineJoin    = 'round';
  ctx.lineCap     = 'round';

  const w = x2 - x1, h = y2 - y1;
  const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
  const radius = Math.min(Math.abs(w), Math.abs(h)) / 2;

  ctx.beginPath();
  switch (tool) {
    case 'line':
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      strokeShape(ctx);
      break;

    case 'rect':
      ctx.rect(x1, y1, w, h);
      renderFillStroke(ctx);
      break;

    case 'rndrect': {
      const cornerR = Math.min(Math.abs(w), Math.abs(h)) * 0.15;
      if (ctx.roundRect) ctx.roundRect(x1, y1, w, h, cornerR);
      else ctx.rect(x1, y1, w, h);
      renderFillStroke(ctx);
      break;
    }

    case 'circle':
      ctx.ellipse(cx, cy, Math.abs(w) / 2, Math.abs(h) / 2, 0, 0, Math.PI * 2);
      renderFillStroke(ctx);
      break;

    case 'triangle':
      ctx.moveTo(cx, y1);
      ctx.lineTo(x2, y2);
      ctx.lineTo(x1, y2);
      ctx.closePath();
      renderFillStroke(ctx);
      break;

    case 'diamond':
      ctx.moveTo(cx, y1);
      ctx.lineTo(x2, cy);
      ctx.lineTo(cx, y2);
      ctx.lineTo(x1, cy);
      ctx.closePath();
      renderFillStroke(ctx);
      break;

    case 'star5':
      drawStarPath(ctx, cx, cy, 5, radius, radius * 0.42);
      renderFillStroke(ctx);
      break;

    case 'star4':
      drawStarPath(ctx, cx, cy, 4, radius, radius * 0.38);
      renderFillStroke(ctx);
      break;

    case 'hexagon':
      drawPolygonPath(ctx, cx, cy, 6, radius);
      renderFillStroke(ctx);
      break;

    case 'polygon':
      drawPolygonPath(ctx, cx, cy, polygonSides, radius);
      renderFillStroke(ctx);
      break;

    case 'arrow':
      drawArrowPath(ctx, x1, y1, x2, y2, BRUSH_SIZE * 2.8);
      strokeShape(ctx);
      break;

    case 'heart':
      drawHeartPath(ctx, cx, cy, radius);
      renderFillStroke(ctx);
      break;

    case 'lightning':
      drawLightningPath(ctx, x1, y1, x2, y2);
      strokeShape(ctx);
      break;

    case 'callout':
      drawCalloutPath(ctx, x1, y1, w, h);
      renderFillStroke(ctx);
      break;

    case 'curve':
      if (!curveControl) curveControl = { x: cx, y: y1 };
      ctx.moveTo(x1, y1);
      ctx.quadraticCurveTo(curveControl.x, curveControl.y, x2, y2);
      strokeShape(ctx);
      if (commit) curveControl = null;
      break;

    case 'freehand':
    case 'lasso':
      if (strokePoints.length > 1) {
        ctx.moveTo(strokePoints[0][0], strokePoints[0][1]);
        strokePoints.forEach(p => ctx.lineTo(p[0], p[1]));
        ctx.closePath();
        renderFillStroke(ctx);
      }
      break;

    case 'select-rect':
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = '#00aaff';
      ctx.fillStyle   = 'rgba(0, 170, 255, 0.08)';
      ctx.lineWidth   = 2;
      ctx.rect(x1, y1, w, h);
      renderFillStroke(ctx);
      ctx.setLineDash([]);
      break;

    case 'crop':
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = '#ff7700';
      ctx.lineWidth   = 2;
      ctx.rect(x1, y1, w, h);
      strokeShape(ctx);
      ctx.setLineDash([]);
      if (commit) applyCrop(x1, y1, x2, y2);
      break;
  }

  ctx.restore();
}

function strokeShape(ctx) {
  if (SHAPE_FILL === 'fill') ctx.fill();
  else ctx.stroke();
}

function renderFillStroke(ctx) {
  if (SHAPE_FILL === 'fill' || SHAPE_FILL === 'both') ctx.fill();
  if (SHAPE_FILL === 'outline' || SHAPE_FILL === 'both') ctx.stroke();
}

function drawStarPath(ctx, cx, cy, points, outer, inner) {
  for (let i = 0; i < points * 2; i++) {
    const r = (i % 2 === 0) ? outer : inner;
    const a = (i * Math.PI / points) - Math.PI / 2;
    if (i === 0) ctx.moveTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
    else ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
  }
  ctx.closePath();
}

function drawPolygonPath(ctx, cx, cy, sides, r) {
  for (let i = 0; i < sides; i++) {
    const a = (i * 2 * Math.PI / sides) - Math.PI / 2;
    if (i === 0) ctx.moveTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
    else ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
  }
  ctx.closePath();
}

function drawArrowPath(ctx, x1, y1, x2, y2, headSize) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - headSize * Math.cos(angle - Math.PI / 6), y2 - headSize * Math.sin(angle - Math.PI / 6));
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - headSize * Math.cos(angle + Math.PI / 6), y2 - headSize * Math.sin(angle + Math.PI / 6));
}

function drawHeartPath(ctx, cx, cy, r) {
  ctx.moveTo(cx, cy + r * 0.35);
  ctx.bezierCurveTo(cx - r * 2, cy - r * 1.2, cx - r * 2, cy + r * 0.5, cx, cy + r * 1.25);
  ctx.bezierCurveTo(cx + r * 2, cy + r * 0.5, cx + r * 2, cy - r * 1.2, cx, cy + r * 0.35);
}

function drawLightningPath(ctx, x1, y1, x2, y2) {
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  const dx = (x2 - x1) * 0.3, dy = (y2 - y1) * 0.3;
  ctx.moveTo(x1, y1);
  ctx.lineTo(mx + dy, my - dx);
  ctx.lineTo(mx - dy * 0.5, my + dx * 0.5);
  ctx.lineTo(x2, y2);
}

function drawCalloutPath(ctx, x1, y1, w, h) {
  const cornerR = 10;
  if (ctx.roundRect) ctx.roundRect(x1, y1, w, h, cornerR);
  else ctx.rect(x1, y1, w, h);
  const tailY = y1 + h + Math.abs(h) * 0.3;
  ctx.moveTo(x1 + Math.abs(w) * 0.2, y1 + h);
  ctx.lineTo(x1, tailY);
  ctx.lineTo(x1 + Math.abs(w) * 0.4, y1 + h);
}

// ═══════════════════════════════════════════════════════════
// SYMMETRY MIRRORING & MANDALAS
// ═══════════════════════════════════════════════════════════
function applySymmetry(x1, y1, x2, y2) {
  if (SYMMETRY === 'none') return;
  const W = canvasW, H = canvasH;
  const cx = W / 2, cy = H / 2;

  if (SYMMETRY === 'mirror_h' || SYMMETRY === 'quad') {
    applyBrush(ctxDraw, W - x1, y1, W - x2, y2);
  }
  if (SYMMETRY === 'mirror_v' || SYMMETRY === 'quad') {
    applyBrush(ctxDraw, x1, H - y1, x2, H - y2);
  }
  if (SYMMETRY === 'quad') {
    applyBrush(ctxDraw, W - x1, H - y1, W - x2, H - y2);
  }
  if (SYMMETRY === 'radial4' || SYMMETRY === 'radial8') {
    const steps = (SYMMETRY === 'radial4') ? 4 : 8;
    for (let i = 1; i < steps; i++) {
      const ang = (Math.PI * 2 / steps) * i;
      const cosA = Math.cos(ang), sinA = Math.sin(ang);
      const rx1 = cx + (x1 - cx) * cosA - (y1 - cy) * sinA;
      const ry1 = cy + (x1 - cx) * sinA + (y1 - cy) * cosA;
      const rx2 = cx + (x2 - cx) * cosA - (y2 - cy) * sinA;
      const ry2 = cy + (x2 - cx) * sinA + (y2 - cy) * cosA;
      applyBrush(ctxDraw, rx1, ry1, rx2, ry2);
    }
  }
}

// ═══════════════════════════════════════════════════════════
// PAINT BUCKET, EYEDROPPER, TEXT, MAGNIFIER & CROP
// ═══════════════════════════════════════════════════════════
function floodFill(startX, startY) {
  pushUndo();
  const imgData = ctxDraw.getImageData(0, 0, canvasW, canvasH);
  const data = imgData.data;

  const sx = Math.max(0, Math.min(canvasW - 1, Math.round(startX)));
  const sy = Math.max(0, Math.min(canvasH - 1, Math.round(startY)));
  const idx = (sy * canvasW + sx) * 4;
  const tr = data[idx], tg = data[idx + 1], tb = data[idx + 2], ta = data[idx + 3];

  const cr = parseInt(COLOR1.slice(1, 3), 16) || 0;
  const cg = parseInt(COLOR1.slice(3, 5), 16) || 0;
  const cb = parseInt(COLOR1.slice(5, 7), 16) || 0;
  const ca = Math.round(OPACITY * 255);

  if (tr === cr && tg === cg && tb === cb && ta === ca) return;

  const stack = [[sx, sy]];
  const visited = new Uint8Array(canvasW * canvasH);
  const THRESHOLD = 28;

  function matchesTarget(i) {
    return Math.abs(data[i] - tr) +
           Math.abs(data[i + 1] - tg) +
           Math.abs(data[i + 2] - tb) +
           Math.abs(data[i + 3] - ta) <= THRESHOLD;
  }

  while (stack.length > 0) {
    const [x, y] = stack.pop();
    if (x < 0 || x >= canvasW || y < 0 || y >= canvasH) continue;
    const pixelIndex = y * canvasW + x;
    if (visited[pixelIndex]) continue;
    const i4 = pixelIndex * 4;
    if (!matchesTarget(i4)) continue;

    visited[pixelIndex] = 1;
    data[i4]     = cr;
    data[i4 + 1] = cg;
    data[i4 + 2] = cb;
    data[i4 + 3] = ca;

    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }

  ctxDraw.putImageData(imgData, 0, 0);
  showToast('🪣 Flood fill complete');
}

function pickColorAt(x, y, buttonNum) {
  const pixel = ctxDraw.getImageData(Math.round(x), Math.round(y), 1, 1).data;
  const hex = '#' + [pixel[0], pixel[1], pixel[2]]
    .map(v => v.toString(16).padStart(2, '0')).join('');
  if (buttonNum === 2) setColor2(hex);
  else setColor1(hex);
  showToast('Picked: ' + hex);
}

function prepareTextPlacement(x, y) {
  const wrap = document.getElementById('text-input-wrap');
  wrap.style.display = 'flex';
  const inp = document.getElementById('text-input');
  inp.focus();
  textPending = { x, y };
  inp.onkeydown = e => {
    if (e.key === 'Enter') commitTextPlacement();
  };
}

function commitTextPlacement() {
  if (!textPending) return;
  const inp = document.getElementById('text-input');
  const font = document.getElementById('font-select').value;
  const text = inp.value.trim();
  if (!text) return;

  pushUndo();
  ctxDraw.save();
  ctxDraw.font        = `${BRUSH_SIZE * 3.5}px "${font}"`;
  ctxDraw.fillStyle   = getActiveColor(1);
  ctxDraw.globalAlpha = OPACITY;
  ctxDraw.fillText(text, textPending.x, textPending.y);
  ctxDraw.restore();

  inp.value = '';
  textPending = null;
  document.getElementById('text-input-wrap').style.display = 'none';
  showToast('Text placed');
}

function showMagnifier(x, y) {
  const size = 110;
  ctxOverlay.clearRect(0, 0, canvasW, canvasH);
  ctxOverlay.save();
  ctxOverlay.beginPath();
  ctxOverlay.arc(x, y - size - 15, size / 2, 0, Math.PI * 2);
  ctxOverlay.clip();
  ctxOverlay.drawImage(canvasDraw,
    x - size / (magnifierZoom * 2), y - size / (magnifierZoom * 2),
    size / magnifierZoom, size / magnifierZoom,
    x - size / 2, y - size - 15 - size / 2, size, size);
  ctxOverlay.restore();

  ctxOverlay.strokeStyle = '#00d4ff';
  ctxOverlay.lineWidth   = 2.5;
  ctxOverlay.beginPath();
  ctxOverlay.arc(x, y - size - 15, size / 2, 0, Math.PI * 2);
  ctxOverlay.stroke();
}

function applyCrop(x1, y1, x2, y2) {
  pushUndo();
  const cw = Math.abs(x2 - x1);
  const ch = Math.abs(y2 - y1);
  const ox = Math.min(x1, x2);
  const oy = Math.min(y1, y2);
  if (cw < 4 || ch < 4) return;
  const croppedData = ctxDraw.getImageData(ox, oy, cw, ch);
  ctxDraw.clearRect(0, 0, canvasW, canvasH);
  ctxDraw.putImageData(croppedData, ox, oy);
  showToast('Cropped to selection');
}

// ═══════════════════════════════════════════════════════════
// PROTECTED SAVE & DOWNLOAD SYSTEM (ZERO FALSE TRIGGERS)
// ═══════════════════════════════════════════════════════════
function executeExplicitSave(reason = 'User command') {
  const now = performance.now();
  if (now < commandCooldownUntil) {
    const remaining = ((commandCooldownUntil - now) / 1000).toFixed(1);
    showToast(`⏳ Save on cooldown (${remaining}s remaining)`);
    return;
  }

  // Lock cooldown for at least 3 seconds
  commandCooldownUntil = now + CONFIG.saveCooldownMs;
  saveCommandLatched = true;

  // Execute image merge and file download
  const merged = document.createElement('canvas');
  merged.width = canvasW;
  merged.height = canvasH;
  const mc = merged.getContext('2d');
  mc.drawImage(canvasBg, 0, 0);
  mc.drawImage(canvasDraw, 0, 0);

  merged.toBlob(blob => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ai-air-draw-${Date.now()}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`💾 Saved Artwork! (${reason})`);
  }, 'image/png');

  // Trigger visual confirmed pulse
  showCommandConfirmationPulse('✅ ARTWORK SAVED');
}

function showCommandConfirmationPulse(text) {
  const overlay = document.getElementById('command-confirm-overlay');
  const label = document.getElementById('confirm-label');
  const countdown = document.getElementById('confirm-countdown');
  const icon = document.getElementById('confirm-icon');

  if (overlay && label && countdown && icon) {
    overlay.style.display = 'flex';
    icon.textContent = '✅';
    label.textContent = text;
    countdown.textContent = 'SAVED';
    setTimeout(() => {
      overlay.style.display = 'none';
      icon.textContent = '💾';
      label.textContent = 'HOLD TO SAVE';
    }, 1200);
  }
}

// ═══════════════════════════════════════════════════════════
// ROTATION-INVARIANT 3D GESTURE RECOGNITION ENGINE
// ═══════════════════════════════════════════════════════════
function analyzeHandGeometry(lm) {
  // 1. Compute palm metrics
  const wrist = lm[0];
  const middleMcp = lm[9];
  const palmScale = Math.hypot(middleMcp.x - wrist.x, middleMcp.y - wrist.y);

  if (palmScale < 0.04) {
    return { valid: false }; // Hand too far or degenerate landmarks
  }

  // 2. Compute individual finger extension states (Rotation Invariant)
  // Indices: Thumb: 4, Index: 8, Middle: 12, Ring: 16, Pinky: 20
  function isFingerExtended(tipIdx, pipIdx, mcpIdx) {
    const tip = lm[tipIdx];
    const pip = lm[pipIdx];
    const mcp = lm[mcpIdx];
    const distTipWrist = Math.hypot(tip.x - wrist.x, tip.y - wrist.y);
    const distPipWrist = Math.hypot(pip.x - wrist.x, pip.y - wrist.y);
    const distTipMcp   = Math.hypot(tip.x - mcp.x, tip.y - mcp.y);

    // Finger is straight when tip is significantly further from wrist and MCP
    return (distTipWrist > distPipWrist * 1.18) && (distTipMcp > palmScale * 0.65);
  }

  const indexExtended  = isFingerExtended(8, 6, 5);
  const middleExtended = isFingerExtended(12, 10, 9);
  const ringExtended   = isFingerExtended(16, 14, 13);
  const pinkyExtended  = isFingerExtended(20, 18, 17);

  // 3. Thumb Extension Analysis
  const thumbTip = lm[4];
  const thumbIp  = lm[3];
  const thumbMcp = lm[2];
  const pinkyMcp = lm[17];
  const distThumbPinky = Math.hypot(thumbTip.x - pinkyMcp.x, thumbTip.y - pinkyMcp.y);
  const distIpPinky    = Math.hypot(thumbIp.x - pinkyMcp.x, thumbIp.y - pinkyMcp.y);
  const thumbExtended  = (distThumbPinky > distIpPinky * 1.15) &&
                         (Math.hypot(thumbTip.x - thumbMcp.x, thumbTip.y - thumbMcp.y) > palmScale * 0.45);

  // 4. Normalized Pinch Distance (Scale-Invariant)
  const pinchDistNormalized = Math.hypot(thumbTip.x - lm[8].x, thumbTip.y - lm[8].y) / palmScale;

  // Calibrated Pinch Thresholds
  // Slider 1 (tight = 0.20) to 5 (wide = 0.36), default 3 = 0.28
  const calibEnter = 0.16 + (CONFIG.pinchSensitivity * 0.04);
  const calibExit  = calibEnter + 0.10; // Hysteresis

  const isPinching = isDrawing ? (pinchDistNormalized < calibExit) : (pinchDistNormalized < calibEnter);

  // 5. Thumb-Up Pose Verification (Dedicated for Protected Save)
  // Must have: Thumb clearly pointing up, all other 4 fingers curled tightly, and upright hand orientation
  const isUprightThumb = (thumbTip.y < thumbIp.y - 0.03) && (thumbTip.y < wrist.y - 0.12);
  const otherFingersCurled = (!indexExtended && !middleExtended && !ringExtended && !pinkyExtended);
  const isProtectedSavePose = isUprightThumb && otherFingersCurled && thumbExtended;

  // 6. Classification Decision Tree
  let gesture = 'NEUTRAL';
  let confidence = 0.75;

  if (otherFingersCurled) {
    if (isProtectedSavePose) gesture = 'SAVE_INTENT';
    else gesture = 'FIST';
    confidence = 0.95;
  } else if (isPinching) {
    gesture = 'PINCH';
    confidence = 0.96;
  } else if (indexExtended && middleExtended && !ringExtended && !pinkyExtended) {
    gesture = 'PEACE';
    confidence = 0.92;
  } else if (indexExtended && !middleExtended && !ringExtended && !pinkyExtended) {
    gesture = 'INDEX_AIM';
    confidence = 0.93;
  } else if (indexExtended && middleExtended && ringExtended && pinkyExtended) {
    gesture = 'OPEN_PALM';
    confidence = 0.90;
  } else {
    gesture = 'AMBIGUOUS';
    confidence = 0.60;
  }

  return {
    valid: true,
    gesture,
    confidence,
    isPinching,
    fingers: {
      thumb: thumbExtended,
      index: indexExtended,
      middle: middleExtended,
      ring: ringExtended,
      pinky: pinkyExtended
    },
    palmScale,
    thumbTip,
    indexTip: lm[8]
  };
}

// ═══════════════════════════════════════════════════════════
// TEMPORAL GESTURE STABILIZER & STATE MACHINE
// ═══════════════════════════════════════════════════════════
function processStabilizedGestures(landmarks) {
  const analysis = analyzeHandGeometry(landmarks);
  if (!analysis.valid) {
    updateHUD('Camera Active', 'Searching...', 'NO HAND', 0.0, 'Neutral', 'Hand out of view');
    if (isDrawing) onPointerUp();
    resetSaveConfirmationHUD();
    return;
  }

  // Update calibration tester if modal is open
  updateCalibrationTester(analysis, landmarks);

  // 1. Maintain 5-frame temporal sliding window
  gestureHistory.push(analysis.gesture);
  if (gestureHistory.length > GESTURE_HISTORY_SIZE) {
    gestureHistory.shift();
  }

  // 2. Compute majority gesture
  const counts = {};
  gestureHistory.forEach(g => { counts[g] = (counts[g] || 0) + 1; });
  let dominantGesture = analysis.gesture;
  let maxCount = 0;
  for (const [g, count] of Object.entries(counts)) {
    if (count > maxCount) {
      maxCount = count;
      dominantGesture = g;
    }
  }

  const temporalConsistency = maxCount / gestureHistory.length;
  activeConfidence = analysis.confidence * temporalConsistency;
  activeGestureName = dominantGesture;

  // 3. Compute Mirrored Coordinates with Adaptive Low-Pass Filter
  const now = performance.now();
  const dt = Math.max(1, (now - lastFrameTimestamp)) / 1000;
  lastFrameTimestamp = now;

  // Aim point: mid-point of index and thumb tips
  const rawAimX = (1 - (analysis.indexTip.x + analysis.thumbTip.x) / 2) * canvasW;
  const rawAimY = ((analysis.indexTip.y + analysis.thumbTip.y) / 2) * canvasH;

  // Adaptive smoothing: high smoothing at low velocity (tremor removal), low smoothing at high velocity (zero lag)
  const speed = Math.hypot(rawAimX - prevRawCursorX, rawAimY - prevRawCursorY) / dt;
  prevRawCursorX = rawAimX;
  prevRawCursorY = rawAimY;

  // Smoothing sensitivity: 1 (fast/0.45) to 5 (ultra-smooth/0.18), default 3 = 0.28
  const baseAlpha = 0.42 - (CONFIG.cursorSmoothing * 0.05);
  const adaptiveAlpha = Math.min(0.92, Math.max(baseAlpha, baseAlpha + (speed / 900)));

  smoothCursorX = adaptiveAlpha * rawAimX + (1 - adaptiveAlpha) * smoothCursorX;
  smoothCursorY = adaptiveAlpha * rawAimY + (1 - adaptiveAlpha) * smoothCursorY;

  // Update visual hand cursor
  updateVirtualCursor(smoothCursorX, smoothCursorY);

  // 4. Ambiguity Guard: if confidence is low, ignore actions and instruct user
  if (activeConfidence < 0.68) {
    updateHUD('Camera Active', 'Detected ✋', dominantGesture, activeConfidence, 'Stabilizing', 'Gesture unclear — hold hand steady');
    resetSaveConfirmationHUD();
    return;
  }

  // 5. Execute Stabilized State Machine
  executeGestureStateMachine(dominantGesture);
}

function executeGestureStateMachine(gesture) {
  const now = performance.now();

  // Reset latch if user releases the save pose
  if (gesture !== 'SAVE_INTENT') {
    saveCommandLatched = false;
    resetSaveConfirmationHUD();
  }

  switch (gesture) {
    case 'PINCH':
      currentGestureState = GESTURE_STATE.DRAWING;
      updateHUD('Camera Active', 'Detected ✋', 'PINCH (DRAWING)', activeConfidence, 'Draw', 'Drawing ink on canvas');
      if (!isDrawing) {
        onPointerDown(smoothCursorX, smoothCursorY);
      } else {
        onPointerMove(smoothCursorX, smoothCursorY);
      }
      break;

    case 'INDEX_AIM':
      currentGestureState = GESTURE_STATE.HOVER;
      if (isDrawing) onPointerUp();
      updateHUD('Camera Active', 'Detected ✋', 'INDEX (AIMING)', activeConfidence, 'Hover', 'Aiming virtual cursor');
      break;

    case 'OPEN_PALM':
      currentGestureState = GESTURE_STATE.HOVER;
      if (isDrawing) onPointerUp();
      updateHUD('Camera Active', 'Detected ✋', 'OPEN PALM', activeConfidence, 'Hover', 'Drawing paused / Hovering');
      break;

    case 'FIST':
      currentGestureState = GESTURE_STATE.NEUTRAL;
      if (isDrawing) onPointerUp();
      updateHUD('Camera Active', 'Detected ✋', 'FIST (NEUTRAL)', activeConfidence, 'Neutral', 'Safe stop / No action');
      break;

    case 'PEACE':
      currentGestureState = GESTURE_STATE.ERASER;
      if (isDrawing) onPointerUp();
      selectTool('eraser');
      updateHUD('Camera Active', 'Detected ✋', 'PEACE (ERASER)', activeConfidence, 'Tool', 'Eraser tool selected');
      break;

    case 'SAVE_INTENT':
      if (isDrawing) onPointerUp();

      // Check if on cooldown or already latched
      if (now < commandCooldownUntil) {
        const remaining = ((commandCooldownUntil - now) / 1000).toFixed(1);
        updateHUD('Camera Active', 'Detected ✋', 'SAVE (COOLDOWN)', activeConfidence, 'Protected', `Cooldown active (${remaining}s)`);
        resetSaveConfirmationHUD();
        return;
      }

      if (saveCommandLatched) {
        updateHUD('Camera Active', 'Detected ✋', 'SAVE (LATCHED)', activeConfidence, 'Protected', 'Release gesture before saving again');
        resetSaveConfirmationHUD();
        return;
      }

      // Initiate or progress the intentional 1.2s countdown
      handleProtectedSaveHold(now);
      break;

    default:
      if (isDrawing) onPointerUp();
      updateHUD('Camera Active', 'Detected ✋', gesture, activeConfidence, 'Neutral', 'Hold steady');
      break;
  }
}

// ═══════════════════════════════════════════════════════════
// PROTECTED HOLD-TO-SAVE COUNTDOWN ENGINE
// ═══════════════════════════════════════════════════════════
function handleProtectedSaveHold(now) {
  if (commandHoldStartTime === 0) {
    commandHoldStartTime = now;
  }

  const elapsed = now - commandHoldStartTime;
  const progress = Math.min(1.0, elapsed / CONFIG.holdDurationMs);
  const remaining = Math.max(0, (CONFIG.holdDurationMs - elapsed) / 1000).toFixed(1);

  // Update Live Circular Hold-to-Save HUD
  const overlay = document.getElementById('command-confirm-overlay');
  const arc = document.getElementById('confirm-arc');
  const countdown = document.getElementById('confirm-countdown');

  if (overlay && arc && countdown) {
    overlay.style.display = 'flex';
    countdown.textContent = `${remaining}s`;
    const circumference = 263.89;
    arc.style.strokeDashoffset = circumference * (1 - progress);
  }

  updateHUD('Camera Active', 'Detected ✋', 'HOLD TO SAVE', activeConfidence, 'Confirming', `Holding intentional save (${remaining}s)`);

  if (progress >= 1.0) {
    // Command confirmed! Execute save exactly once
    resetSaveConfirmationHUD();
    executeExplicitSave('Held intentional save pose');
  }
}

function resetSaveConfirmationHUD() {
  commandHoldStartTime = 0;
  const overlay = document.getElementById('command-confirm-overlay');
  const arc = document.getElementById('confirm-arc');
  if (overlay) overlay.style.display = 'none';
  if (arc) arc.style.strokeDashoffset = 263.89;
}

// ═══════════════════════════════════════════════════════════
// LIVE GESTURE HUD STATUS PANEL UPDATER
// ═══════════════════════════════════════════════════════════
function updateHUD(camText, handText, gestureName, confidence, mode, guidance) {
  const dot = document.getElementById('hud-cam-dot');
  const handState = document.getElementById('hud-hand-state');
  const gestureEl = document.getElementById('hud-gesture-name');
  const confBar = document.getElementById('hud-confidence-bar');
  const confVal = document.getElementById('hud-confidence-val');
  const modeVal = document.getElementById('hud-mode-val');
  const guidanceEl = document.getElementById('hud-guidance');

  if (dot) dot.className = `hud-status-dot ${cameraActive ? 'active' : ''}`;
  if (handState) handState.textContent = handText;
  if (gestureEl) gestureEl.textContent = gestureName;

  const pct = Math.round(confidence * 100);
  if (confBar) confBar.style.width = `${pct}%`;
  if (confVal) confVal.textContent = `${pct}%`;
  if (modeVal) modeVal.textContent = mode;
  if (guidanceEl) guidanceEl.textContent = guidance;

  // Bottom compact tracker status bar
  const tText = document.getElementById('tracker-text');
  const tIcon = document.getElementById('tracker-icon');
  if (tText) tText.textContent = `${gestureName} · ${guidance}`;
  if (tIcon) tIcon.textContent = (mode === 'Draw') ? '✏️' : (mode === 'Hover') ? '🖐' : '👁️';
}

function updateVirtualCursor(x, y) {
  const dot = document.getElementById('cursor-dot');
  if (dot) {
    dot.style.display = 'block';
    dot.style.left = `${x}px`;
    dot.style.top  = `${y}px`;
  }
}

function hideVirtualCursor() {
  const dot = document.getElementById('cursor-dot');
  if (dot) dot.style.display = 'none';
}

// ═══════════════════════════════════════════════════════════
// SKELETON & SECONDARY HAND PALETTE
// ═══════════════════════════════════════════════════════════
const SKELETON_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17]
];

function drawSkeletonOverlay(ctx, landmarks) {
  ctx.save();
  ctx.strokeStyle = 'rgba(0, 212, 255, 0.65)';
  ctx.lineWidth   = 2.2;
  ctx.lineCap     = 'round';

  function mapLm(lm) {
    return { x: (1 - lm.x) * canvasW, y: lm.y * canvasH };
  }

  SKELETON_CONNECTIONS.forEach(([i, j]) => {
    const p1 = mapLm(landmarks[i]);
    const p2 = mapLm(landmarks[j]);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  });

  ctx.fillStyle = 'rgba(0, 212, 255, 0.95)';
  landmarks.forEach(lm => {
    const p = mapLm(lm);
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.restore();
}

function drawHolographicPalette(ctx, landmarks) {
  const palm = { x: (1 - landmarks[0].x) * canvasW, y: landmarks[0].y * canvasH };
  const paletteRadius = 75;
  ctx.save();

  const paletteColors = PALETTE.slice(0, 8);
  paletteColors.forEach((hex, i) => {
    const ang = (i / paletteColors.length) * Math.PI * 2 - Math.PI / 2;
    const px = palm.x + paletteRadius * Math.cos(ang);
    const py = palm.y + paletteRadius * Math.sin(ang);

    ctx.beginPath();
    ctx.arc(px, py, 14, 0, Math.PI * 2);
    ctx.fillStyle = hex;
    ctx.fill();
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    if (Math.hypot(smoothCursorX - px, smoothCursorY - py) < 18) {
      setColor1(hex);
      showToast('🎨 Palette selected: ' + hex);
    }
  });

  ctx.restore();
}

// ═══════════════════════════════════════════════════════════
// MEDIAPIPE HAND TRACKING & WEBCAM PIPELINE
// ═══════════════════════════════════════════════════════════
async function startHandTracking() {
  updateHUD('Starting...', 'Initializing', 'AI BOOT', 0.5, 'Init', 'Connecting camera...');

  try {
    if (typeof Hands === 'undefined') {
      throw new Error('MediaPipe Hands library not loaded from CDN.');
    }

    if (!handsInstance) {
      handsInstance = new Hands({
        locateFile: file => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
      });

      handsInstance.setOptions({
        maxNumHands: 2,
        modelComplexity: 1,
        minDetectionConfidence: 0.55,
        minTrackingConfidence: 0.55
      });

      handsInstance.onResults(onHandResults);
      await handsInstance.initialize();
    }

    const videoElement = document.getElementById('webcam');
    if (!cameraInstance) {
      cameraInstance = new Camera(videoElement, {
        onFrame: async () => {
          if (cameraActive && handsInstance) {
            try {
              await handsInstance.send({ image: videoElement });
            } catch (err) {
              console.warn('Frame send warning:', err);
            }
          }
        },
        width: 1280,
        height: 720
      });
    }

    await cameraInstance.start();

    videoElement.style.display = 'block';
    cameraActive = true;
    handMode = true;

    document.getElementById('btn-cam-toggle').textContent = '📷 Camera ON';
    document.getElementById('btn-hand-mode').classList.add('active');
    document.getElementById('btn-mouse-mode').classList.remove('active');

    updateHUD('Camera Active', 'Searching...', 'WAITING', 0.8, 'Ready', 'Show your hand to camera');
    showToast('✋ Live Air Draw Active! Pinch to Draw.');

  } catch (err) {
    console.error('Camera/AI start failure:', err);
    const isPermDenied = err.name === 'NotAllowedError';
    const errorText = isPermDenied ? 'Camera permission denied' : (err.message || 'AI initialization error');

    updateHUD('Error', 'Unavailable', 'ERROR', 0.0, 'Fallback', errorText);
    showToast('⚠️ ' + errorText + ' — using mouse mode');
    fallbackToMouseMode();
  }
}

function onHandResults(results) {
  if (!cameraActive) return;

  ctxOverlay.clearRect(0, 0, canvasW, canvasH);

  if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
    if (isDrawing) onPointerUp();
    hideVirtualCursor();
    resetSaveConfirmationHUD();
    updateHUD('Camera Active', 'No Hand Detected', 'NO HAND', 0.0, 'Neutral', 'Place hand in camera frame');
    return;
  }

  // Draw overlay skeleton on primary hand
  const primaryLandmarks = results.multiHandLandmarks[0];
  drawSkeletonOverlay(ctxOverlay, primaryLandmarks);

  // Secondary hand activates holographic AR color wheel
  if (results.multiHandLandmarks.length > 1) {
    const secondaryLandmarks = results.multiHandLandmarks[1];
    drawSkeletonOverlay(ctxOverlay, secondaryLandmarks);
    drawHolographicPalette(ctxOverlay, secondaryLandmarks);
  }

  if (handMode) {
    processStabilizedGestures(primaryLandmarks);
  }
}

function fallbackToMouseMode() {
  handMode = false;
  document.getElementById('btn-mouse-mode').classList.add('active');
  document.getElementById('btn-hand-mode').classList.remove('active');
}

function toggleCamera() {
  if (cameraActive) {
    const video = document.getElementById('webcam');
    if (video.srcObject) {
      video.srcObject.getTracks().forEach(t => t.stop());
      video.srcObject = null;
    }
    video.style.display = 'none';
    cameraActive = false;
    handMode = false;
    if (isDrawing) onPointerUp();
    ctxOverlay.clearRect(0, 0, canvasW, canvasH);
    hideVirtualCursor();
    resetSaveConfirmationHUD();
    document.getElementById('btn-cam-toggle').textContent = '📷 Camera OFF';
    updateHUD('Camera Inactive', 'Inactive', 'MOUSE MODE', 1.0, 'Neutral', 'Mouse/Touch active');
    fallbackToMouseMode();
  } else {
    startHandTracking();
  }
}

// ═══════════════════════════════════════════════════════════
// GESTURE CALIBRATION MODAL & TESTER
// ═══════════════════════════════════════════════════════════
function initCalibrationControls() {
  const pinchSlider = document.getElementById('calib-pinch-slider');
  const smoothSlider = document.getElementById('calib-smooth-slider');
  const holdSlider = document.getElementById('calib-hold-slider');

  const pinchVal = document.getElementById('calib-pinch-val');
  const smoothVal = document.getElementById('calib-smooth-val');
  const holdVal = document.getElementById('calib-hold-val');

  const pinchLabels = ['', 'Very Tight', 'Tight', 'Normal (Default)', 'Wide', 'Very Wide'];
  const smoothLabels = ['', 'Instant (Low)', 'Responsive', 'Adaptive (Default)', 'Smooth', 'Ultra-Smooth'];

  if (pinchSlider) {
    pinchSlider.value = CONFIG.pinchSensitivity;
    pinchVal.textContent = pinchLabels[CONFIG.pinchSensitivity] || 'Normal';
    pinchSlider.addEventListener('input', e => {
      CONFIG.pinchSensitivity = parseInt(e.target.value, 10);
      pinchVal.textContent = pinchLabels[CONFIG.pinchSensitivity];
    });
  }

  if (smoothSlider) {
    smoothSlider.value = CONFIG.cursorSmoothing;
    smoothVal.textContent = smoothLabels[CONFIG.cursorSmoothing] || 'Adaptive';
    smoothSlider.addEventListener('input', e => {
      CONFIG.cursorSmoothing = parseInt(e.target.value, 10);
      smoothVal.textContent = smoothLabels[CONFIG.cursorSmoothing];
    });
  }

  if (holdSlider) {
    holdSlider.value = Math.round(CONFIG.holdDurationMs / 100);
    holdVal.textContent = `${(CONFIG.holdDurationMs / 1000).toFixed(1)}s`;
    holdSlider.addEventListener('input', e => {
      CONFIG.holdDurationMs = parseInt(e.target.value, 10) * 100;
      holdVal.textContent = `${(CONFIG.holdDurationMs / 1000).toFixed(1)}s`;
    });
  }

  document.getElementById('btn-save-calib').addEventListener('click', () => {
    saveUserPreferences();
    closeCalibrationModal();
    showToast('⚙️ Preferences saved!');
  });

  document.getElementById('btn-reset-calib').addEventListener('click', () => {
    CONFIG.pinchSensitivity = 3;
    CONFIG.cursorSmoothing = 3;
    CONFIG.holdDurationMs = 1200;
    if (pinchSlider) { pinchSlider.value = 3; pinchVal.textContent = 'Normal (Default)'; }
    if (smoothSlider) { smoothSlider.value = 3; smoothVal.textContent = 'Adaptive (Default)'; }
    if (holdSlider) { holdSlider.value = 12; holdVal.textContent = '1.2s'; }
    saveUserPreferences();
    showToast('Reset to default calibration');
  });
}

function openCalibrationModal() {
  document.getElementById('calibration-modal').style.display = 'flex';
}
function closeCalibrationModal() {
  document.getElementById('calibration-modal').style.display = 'none';
}

function updateCalibrationTester(analysis, lm) {
  const modal = document.getElementById('calibration-modal');
  if (!modal || modal.style.display !== 'flex') return;

  const canvas = document.getElementById('calib-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Draw mini hand skeleton
  ctx.save();
  ctx.strokeStyle = '#00d4ff';
  ctx.lineWidth = 1.8;
  function mapCalib(p) {
    return { x: (1 - p.x) * canvas.width, y: p.y * canvas.height };
  }
  SKELETON_CONNECTIONS.forEach(([i, j]) => {
    const p1 = mapCalib(lm[i]), p2 = mapCalib(lm[j]);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  });
  ctx.restore();

  // Update pills & labels
  const gesEl = document.getElementById('calib-detected-gesture');
  const confEl = document.getElementById('calib-confidence');
  if (gesEl) gesEl.textContent = analysis.gesture;
  if (confEl) confEl.textContent = `${Math.round(analysis.confidence * 100)}%`;

  const fingers = ['thumb', 'index', 'middle', 'ring', 'pinky'];
  fingers.forEach(f => {
    const pill = document.getElementById(`f-${f}`);
    if (pill) {
      if (analysis.fingers[f]) pill.classList.add('up');
      else pill.classList.remove('up');
    }
  });
}

// ═══════════════════════════════════════════════════════════
// CUSTOM COLOR PICKER
// ═══════════════════════════════════════════════════════════
let colorPickerTarget = 'fg';

function openColorPicker(target) {
  colorPickerTarget = target;
  document.getElementById('color-picker-modal').style.display = 'flex';
  updateColorPickerPreview();
}

function closeColorPicker() {
  document.getElementById('color-picker-modal').style.display = 'none';
}

function applyPickedColor(target) {
  const h = document.getElementById('ph').value;
  const s = document.getElementById('ps').value;
  const l = document.getElementById('pl').value;
  const hex = hslToHex(h, s, l);
  if (target === 'fg') setColor1(hex);
  else setColor2(hex);
}

function updateColorPickerPreview() {
  const ph = document.getElementById('ph');
  const ps = document.getElementById('ps');
  const pl = document.getElementById('pl');
  if (!ph) return;
  const hex = hslToHex(ph.value, ps.value, pl.value);
  const preview = document.getElementById('picker-preview');
  const phex = document.getElementById('phex');
  if (preview) preview.style.background = hex;
  if (phex) phex.value = hex;
}

function initColorWheel() {
  const c = document.getElementById('color-wheel-canvas');
  if (!c) return;
  const ctx = c.getContext('2d');
  const cx = c.width / 2, cy = c.height / 2, r = cx - 6;
  for (let angle = 0; angle < 360; angle++) {
    const a1 = (angle - 1) * Math.PI / 180;
    const a2 = (angle + 1) * Math.PI / 180;
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    grad.addColorStop(0, 'white');
    grad.addColorStop(1, `hsl(${angle}, 100%, 50%)`);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, a1, a2);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
  }

  c.addEventListener('click', e => {
    const rect = c.getBoundingClientRect();
    const x = e.clientX - rect.left - cx;
    const y = e.clientY - rect.top - cy;
    const angle = ((Math.atan2(y, x) * 180 / Math.PI) + 360) % 360;
    const dist = Math.min(Math.hypot(x, y) / r, 1);
    document.getElementById('ph').value = Math.round(angle);
    document.getElementById('ps').value = Math.round(dist * 100);
    updateColorPickerPreview();
  });
}

function hslToHex(h, s, l) {
  h = +h; s = +s / 100; l = +l / 100;
  const a = s * Math.min(l, 1 - l);
  const f = n => {
    const k = (n + h / 30) % 12;
    const c = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * c).toString(16).padStart(2, '0');
  };
  return '#' + f(0) + f(8) + f(4);
}

function hexToHsl(hex) {
  if (!hex || hex.length < 7) return null;
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0, l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h *= 60;
  }
  return { h: Math.round(h), s: Math.round(s * 100), l: Math.round(l * 100) };
}

// ═══════════════════════════════════════════════════════════
// BACKGROUND PRESETS
// ═══════════════════════════════════════════════════════════
function renderBackground() {
  if (!ctxBg) return;
  ctxBg.clearRect(0, 0, canvasW, canvasH);
  switch (BACKGROUND) {
    case 'white':
      ctxBg.fillStyle = '#FFFFFF';
      ctxBg.fillRect(0, 0, canvasW, canvasH);
      break;

    case 'black':
      ctxBg.fillStyle = '#0a0a0f';
      ctxBg.fillRect(0, 0, canvasW, canvasH);
      break;

    case 'grid':
      ctxBg.fillStyle = '#FFFFFF';
      ctxBg.fillRect(0, 0, canvasW, canvasH);
      ctxBg.strokeStyle = '#e0e0e0';
      ctxBg.lineWidth = 0.5;
      for (let x = 0; x < canvasW; x += 20) {
        ctxBg.beginPath(); ctxBg.moveTo(x, 0); ctxBg.lineTo(x, canvasH); ctxBg.stroke();
      }
      for (let y = 0; y < canvasH; y += 20) {
        ctxBg.beginPath(); ctxBg.moveTo(0, y); ctxBg.lineTo(canvasW, y); ctxBg.stroke();
      }
      break;

    case 'dotgrid':
      ctxBg.fillStyle = '#FFFFFF';
      ctxBg.fillRect(0, 0, canvasW, canvasH);
      ctxBg.fillStyle = '#b0b0b0';
      for (let x = 0; x < canvasW; x += 22) {
        for (let y = 0; y < canvasH; y += 22) {
          ctxBg.fillRect(x - 1, y - 1, 2, 2);
        }
      }
      break;

    case 'stars':
      ctxBg.fillStyle = '#050515';
      ctxBg.fillRect(0, 0, canvasW, canvasH);
      ctxBg.fillStyle = '#FFFFFF';
      for (let i = 0; i < 350; i++) {
        const sx = (Math.sin(i * 997) * 0.5 + 0.5) * canvasW;
        const sy = (Math.cos(i * 631) * 0.5 + 0.5) * canvasH;
        const sr = (i % 3 === 0) ? 1.5 : 0.8;
        ctxBg.beginPath(); ctxBg.arc(sx, sy, sr, 0, Math.PI * 2); ctxBg.fill();
      }
      break;

    case 'blueprint':
      ctxBg.fillStyle = '#0b2644';
      ctxBg.fillRect(0, 0, canvasW, canvasH);
      ctxBg.strokeStyle = 'rgba(100, 180, 255, 0.2)';
      ctxBg.lineWidth = 0.5;
      for (let x = 0; x < canvasW; x += 25) {
        ctxBg.beginPath(); ctxBg.moveTo(x, 0); ctxBg.lineTo(x, canvasH); ctxBg.stroke();
      }
      for (let y = 0; y < canvasH; y += 25) {
        ctxBg.beginPath(); ctxBg.moveTo(0, y); ctxBg.lineTo(canvasW, y); ctxBg.stroke();
      }
      ctxBg.strokeStyle = 'rgba(100, 180, 255, 0.6)';
      ctxBg.lineWidth = 1;
      for (let x = 0; x < canvasW; x += 125) {
        ctxBg.beginPath(); ctxBg.moveTo(x, 0); ctxBg.lineTo(x, canvasH); ctxBg.stroke();
      }
      for (let y = 0; y < canvasH; y += 125) {
        ctxBg.beginPath(); ctxBg.moveTo(0, y); ctxBg.lineTo(canvasW, y); ctxBg.stroke();
      }
      break;

    case 'canvas':
      ctxBg.fillStyle = '#f6edd9';
      ctxBg.fillRect(0, 0, canvasW, canvasH);
      ctxBg.strokeStyle = 'rgba(160, 130, 90, 0.1)';
      ctxBg.lineWidth = 1;
      for (let x = 0; x < canvasW; x += 4) {
        ctxBg.beginPath(); ctxBg.moveTo(x, 0); ctxBg.lineTo(x, canvasH); ctxBg.stroke();
      }
      for (let y = 0; y < canvasH; y += 4) {
        ctxBg.beginPath(); ctxBg.moveTo(0, y); ctxBg.lineTo(canvasW, y); ctxBg.stroke();
      }
      break;

    case 'gradient': {
      const grad = ctxBg.createLinearGradient(0, 0, canvasW, canvasH);
      grad.addColorStop(0, '#15002b');
      grad.addColorStop(0.5, '#06203a');
      grad.addColorStop(1, '#00261a');
      ctxBg.fillStyle = grad;
      ctxBg.fillRect(0, 0, canvasW, canvasH);
      break;
    }
  }
}

// ═══════════════════════════════════════════════════════════
// FILTERS & IMAGE EFFECTS
// ═══════════════════════════════════════════════════════════
function applyFX(fx) {
  pushUndo();

  if (fx === 'fliph') {
    const tmp = document.createElement('canvas');
    tmp.width = canvasW; tmp.height = canvasH;
    tmp.getContext('2d').drawImage(canvasDraw, 0, 0);
    ctxDraw.clearRect(0, 0, canvasW, canvasH);
    ctxDraw.save();
    ctxDraw.translate(canvasW, 0);
    ctxDraw.scale(-1, 1);
    ctxDraw.drawImage(tmp, 0, 0);
    ctxDraw.restore();
    showToast('↔️ Flipped Horizontally');
    return;
  }
  if (fx === 'flipv') {
    const tmp = document.createElement('canvas');
    tmp.width = canvasW; tmp.height = canvasH;
    tmp.getContext('2d').drawImage(canvasDraw, 0, 0);
    ctxDraw.clearRect(0, 0, canvasW, canvasH);
    ctxDraw.save();
    ctxDraw.translate(0, canvasH);
    ctxDraw.scale(1, -1);
    ctxDraw.drawImage(tmp, 0, 0);
    ctxDraw.restore();
    showToast('↕️ Flipped Vertically');
    return;
  }
  if (fx === 'rot90') {
    const tmp = document.createElement('canvas');
    tmp.width = canvasH; tmp.height = canvasW;
    const tc = tmp.getContext('2d');
    tc.translate(canvasH, 0);
    tc.rotate(Math.PI / 2);
    tc.drawImage(canvasDraw, 0, 0);
    ctxDraw.clearRect(0, 0, canvasW, canvasH);
    ctxDraw.drawImage(tmp, 0, 0, canvasW, canvasH);
    showToast('🔃 Rotated 90°');
    return;
  }

  const imgData = ctxDraw.getImageData(0, 0, canvasW, canvasH);
  const d = imgData.data;

  if (fx === 'invert') {
    for (let i = 0; i < d.length; i += 4) {
      d[i]   = 255 - d[i];
      d[i+1] = 255 - d[i+1];
      d[i+2] = 255 - d[i+2];
    }
  } else if (fx === 'grayscale') {
    for (let i = 0; i < d.length; i += 4) {
      const g = 0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2];
      d[i] = d[i+1] = d[i+2] = g;
    }
  } else if (fx === 'sepia') {
    for (let i = 0; i < d.length; i += 4) {
      const r = d[i], g = d[i+1], b = d[i+2];
      d[i]   = Math.min(255, r * 0.393 + g * 0.769 + b * 0.189);
      d[i+1] = Math.min(255, r * 0.349 + g * 0.686 + b * 0.168);
      d[i+2] = Math.min(255, r * 0.272 + g * 0.534 + b * 0.131);
    }
  } else if (fx === 'emboss' || fx === 'blur' || fx === 'sharpen') {
    const src = new Uint8ClampedArray(d);
    const W = canvasW;
    const kernels = {
      emboss:  [-2, -1, 0, -1, 1, 1, 0, 1, 2],
      blur:    [1, 2, 1, 2, 4, 2, 1, 2, 1],
      sharpen: [0, -1, 0, -1, 5, -1, 0, -1, 0]
    };
    const ksums = { emboss: 1, blur: 16, sharpen: 1 };
    const koffs = { emboss: 128, blur: 0, sharpen: 0 };
    const kern = kernels[fx], ksum = ksums[fx], koff = koffs[fx];

    for (let y = 1; y < canvasH - 1; y++) {
      for (let x = 1; x < W - 1; x++) {
        let r = 0, g = 0, b = 0;
        for (let ky = -1; ky <= 1; ky++) {
          for (let kx = -1; kx <= 1; kx++) {
            const i4 = ((y + ky) * W + (x + kx)) * 4;
            const k = kern[(ky + 1) * 3 + (kx + 1)];
            r += src[i4] * k;
            g += src[i4 + 1] * k;
            b += src[i4 + 2] * k;
          }
        }
        const i4 = (y * W + x) * 4;
        d[i4]   = Math.min(255, Math.max(0, r / ksum + koff));
        d[i4+1] = Math.min(255, Math.max(0, g / ksum + koff));
        d[i4+2] = Math.min(255, Math.max(0, b / ksum + koff));
      }
    }
  }

  ctxDraw.putImageData(imgData, 0, 0);
  showToast('✨ Filter: ' + fx);
}

// ═══════════════════════════════════════════════════════════
// AI STUDIO SUITE
// ═══════════════════════════════════════════════════════════
function runAIShapeSnap() {
  if (strokePoints.length < 3) {
    showToast('Draw a freehand shape first!');
    return;
  }
  const xs = strokePoints.map(p => p[0]);
  const ys = strokePoints.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = maxX - minX, h = maxY - minY;
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;

  const perimeter = strokePoints.reduce((acc, p, i, arr) => {
    if (i === 0) return 0;
    return acc + Math.hypot(p[0] - arr[i - 1][0], p[1] - arr[i - 1][1]);
  }, 0);
  const circularity = (4 * Math.PI * w * h) / (perimeter * perimeter + 0.001);

  const first = strokePoints[0];
  const last = strokePoints[strokePoints.length - 1];
  const isClosed = Math.hypot(first[0] - last[0], first[1] - last[1]) < Math.max(w, h) * 0.35;

  let detected = 'line';
  if (isClosed && circularity > 0.48) detected = 'circle';
  else if (isClosed && circularity < 0.28 && strokePoints.length > 5) detected = 'triangle';
  else if (isClosed) detected = 'rectangle';

  pushUndo();
  ctxDraw.clearRect(minX - 6, minY - 6, w + 12, h + 12);
  ctxDraw.save();
  ctxDraw.strokeStyle = getActiveColor(1);
  ctxDraw.fillStyle   = COLOR2;
  ctxDraw.lineWidth   = BRUSH_SIZE;
  ctxDraw.lineJoin    = 'round';
  ctxDraw.beginPath();

  switch (detected) {
    case 'circle':
      ctxDraw.ellipse(cx, cy, w / 2, h / 2, 0, 0, Math.PI * 2);
      break;
    case 'rectangle':
      ctxDraw.rect(minX, minY, w, h);
      break;
    case 'triangle':
      ctxDraw.moveTo(cx, minY);
      ctxDraw.lineTo(maxX, maxY);
      ctxDraw.lineTo(minX, maxY);
      ctxDraw.closePath();
      break;
    case 'line':
      ctxDraw.moveTo(first[0], first[1]);
      ctxDraw.lineTo(last[0], last[1]);
      break;
  }
  renderFillStroke(ctxDraw);
  ctxDraw.restore();

  showToast('🎯 AI Shape Snapped: ' + detected);
}

function runAIDoodleClassifier() {
  if (strokePoints.length < 3) {
    showToast('Draw a doodle first!');
    return;
  }
  const xs = strokePoints.map(p => p[0]);
  const ys = strokePoints.map(p => p[1]);
  const w = Math.max(...xs) - Math.min(...xs);
  const h = Math.max(...ys) - Math.min(...ys);
  const ar = w / (h + 0.001);

  const perimeter = strokePoints.reduce((acc, p, i, arr) => {
    if (i === 0) return 0;
    return acc + Math.hypot(p[0] - arr[i - 1][0], p[1] - arr[i - 1][1]);
  }, 0);
  const circularity = (4 * Math.PI * w * h) / (perimeter * perimeter + 0.001);

  const first = strokePoints[0];
  const last = strokePoints[strokePoints.length - 1];
  const closed = Math.hypot(first[0] - last[0], first[1] - last[1]) < Math.max(w, h) * 0.35;

  const candidates = [];
  if (circularity > 0.55) candidates.push({ label: 'Circle / Clock / Moon 🌕', conf: circularity });
  if (ar > 1.6 && !closed) candidates.push({ label: 'Horizontal Line / Horizon ➖', conf: 0.85 });
  if (ar < 0.45 && !closed) candidates.push({ label: 'Tree Trunk / Tower 🗼', conf: 0.85 });
  if (closed && circularity < 0.3) candidates.push({ label: 'Mountain / Triangle ⛰️', conf: 0.78 });
  if (closed && circularity >= 0.3 && ar > 0.7 && ar < 1.4) candidates.push({ label: 'House / Box / Screen 📦', conf: 0.8 });
  if (strokePoints.length > 50 && !closed) candidates.push({ label: 'Lightning / River ⚡', conf: 0.65 });
  if (closed && strokePoints.length > 70) candidates.push({ label: 'Creative Artwork 🎨', conf: 0.6 });
  if (candidates.length === 0) candidates.push({ label: 'Abstract Air Drawing ✨', conf: 0.5 });

  candidates.sort((a, b) => b.conf - a.conf);
  const best = candidates[0];

  const resultCard = document.getElementById('ai-result');
  document.getElementById('ai-result-text').textContent =
    `🤖 AI Prediction: ${best.label} (${Math.round(best.conf * 100)}% match)`;
  resultCard.style.display = 'flex';
  showToast('🔍 Classified: ' + best.label);
}

function runAIColoringBook() {
  pushUndo();
  const imgData = ctxDraw.getImageData(0, 0, canvasW, canvasH);
  const d = imgData.data;
  const src = new Uint8ClampedArray(d);
  const W = canvasW;

  for (let y = 1; y < canvasH - 1; y++) {
    for (let x = 1; x < W - 1; x++) {
      const gx = -src[((y - 1) * W + (x - 1)) * 4] - 2 * src[(y * W + (x - 1)) * 4] - src[((y + 1) * W + (x - 1)) * 4]
                 + src[((y - 1) * W + (x + 1)) * 4] + 2 * src[(y * W + (x + 1)) * 4] + src[((y + 1) * W + (x + 1)) * 4];
      const gy = -src[((y - 1) * W + (x - 1)) * 4] - 2 * src[((y - 1) * W + x) * 4] - src[((y - 1) * W + (x + 1)) * 4]
                 + src[((y + 1) * W + (x - 1)) * 4] + 2 * src[((y + 1) * W + x) * 4] + src[((y + 1) * W + (x + 1)) * 4];
      const mag = Math.hypot(gx, gy);
      const i4 = (y * W + x) * 4;
      const isEdge = mag > 35;
      d[i4]     = isEdge ? 0 : 255;
      d[i4 + 1] = isEdge ? 0 : 255;
      d[i4 + 2] = isEdge ? 0 : 255;
      d[i4 + 3] = isEdge ? 255 : 0;
    }
  }
  ctxDraw.putImageData(imgData, 0, 0);
  BACKGROUND = 'white';
  renderBackground();
  showToast('📖 Coloring Book Mode Generated!');
}

function runAIInpaint() {
  if (lassoPoints.length < 3) {
    showToast('Select an area with Lasso or Freehand first!');
    return;
  }
  pushUndo();
  const imgData = ctxDraw.getImageData(0, 0, canvasW, canvasH);
  const d = imgData.data;
  let rSum = 0, gSum = 0, bSum = 0, count = 0;

  lassoPoints.forEach(p => {
    const x = Math.max(0, Math.min(canvasW - 1, Math.round(p[0])));
    const y = Math.max(0, Math.min(canvasH - 1, Math.round(p[1])));
    const i4 = (y * canvasW + x) * 4;
    rSum += d[i4];
    gSum += d[i4 + 1];
    bSum += d[i4 + 2];
    count++;
  });

  const avgR = Math.round(rSum / count);
  const avgG = Math.round(gSum / count);
  const avgB = Math.round(bSum / count);

  const xs = lassoPoints.map(p => p[0]);
  const ys = lassoPoints.map(p => p[1]);
  const minX = Math.max(0, Math.round(Math.min(...xs)));
  const minY = Math.max(0, Math.round(Math.min(...ys)));
  const maxX = Math.min(canvasW - 1, Math.round(Math.max(...xs)));
  const maxY = Math.min(canvasH - 1, Math.round(Math.max(...ys)));

  for (let y = minY; y <= maxY; y++) {
    for (let x = minX; x <= maxX; x++) {
      const i4 = (y * canvasW + x) * 4;
      const noise = (Math.random() - 0.5) * 16;
      d[i4]     = Math.min(255, Math.max(0, avgR + noise));
      d[i4 + 1] = Math.min(255, Math.max(0, avgG + noise));
      d[i4 + 2] = Math.min(255, Math.max(0, avgB + noise));
      d[i4 + 3] = 255;
    }
  }

  ctxDraw.putImageData(imgData, 0, 0);
  showToast('🪄 Inpainting complete');
}

function runAIStyleTransfer() {
  pushUndo();
  const imgData = ctxDraw.getImageData(0, 0, canvasW, canvasH);
  const d = imgData.data;
  const levels = 4;
  const step = 256 / levels;

  for (let i = 0; i < d.length; i += 4) {
    d[i]     = Math.round(d[i] / step) * step;
    d[i + 1] = Math.round(d[i + 1] / step) * step;
    d[i + 2] = Math.round(d[i + 2] / step) * step;
    d[i]     = Math.min(255, d[i] + 20);
    d[i + 2] = Math.max(0, d[i + 2] - 15);
  }
  ctxDraw.putImageData(imgData, 0, 0);
  showToast('🖼️ Style Transfer complete!');
}

// ═══════════════════════════════════════════════════════════
// UNDO, REDO & CLEAR
// ═══════════════════════════════════════════════════════════
function pushUndo() {
  if (!canvasDraw) return;
  if (undoStack.length >= UNDO_MAX) undoStack.shift();
  undoStack.push(canvasDraw.toDataURL());
  redoStack = [];
}

function undo() {
  if (undoStack.length === 0) {
    showToast('Nothing to undo');
    return;
  }
  redoStack.push(canvasDraw.toDataURL());
  const prevSnapshot = undoStack.pop();
  const img = new Image();
  img.src = prevSnapshot;
  img.onload = () => {
    ctxDraw.clearRect(0, 0, canvasW, canvasH);
    ctxDraw.drawImage(img, 0, 0);
  };
  showToast('↩️ Undo');
}

function redo() {
  if (redoStack.length === 0) {
    showToast('Nothing to redo');
    return;
  }
  undoStack.push(canvasDraw.toDataURL());
  const nextSnapshot = redoStack.pop();
  const img = new Image();
  img.src = nextSnapshot;
  img.onload = () => {
    ctxDraw.clearRect(0, 0, canvasW, canvasH);
    ctxDraw.drawImage(img, 0, 0);
  };
  showToast('↪️ Redo');
}

function clearCanvas() {
  pushUndo();
  ctxDraw.clearRect(0, 0, canvasW, canvasH);
  showToast('🗑️ Canvas cleared');
}

// ═══════════════════════════════════════════════════════════
// KEYBOARD SHORTCUTS
// ═══════════════════════════════════════════════════════════
function bindKeyboardShortcuts() {
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
      return;
    }

    if (e.ctrlKey || e.metaKey) {
      switch (e.key.toLowerCase()) {
        case 'z': e.preventDefault(); undo(); break;
        case 'y': e.preventDefault(); redo(); break;
        case 's': e.preventDefault(); executeExplicitSave('Ctrl+S keyboard shortcut'); break;
      }
      return;
    }

    switch (e.key.toLowerCase()) {
      case 'p': selectTool('pen'); break;
      case 'e': selectTool('eraser'); break;
      case 'f': selectTool('fill'); break;
      case 'i': selectTool('eyedropper'); break;
      case 't': selectTool('text'); break;
      case 'l': selectTool('lasso'); break;
      case 'm': selectTool('magnifier'); break;
      case '[': {
        BRUSH_SIZE = Math.max(1, BRUSH_SIZE - 2);
        document.getElementById('size-slider').value = BRUSH_SIZE;
        document.getElementById('size-val').textContent = BRUSH_SIZE;
        break;
      }
      case ']': {
        BRUSH_SIZE = Math.min(80, BRUSH_SIZE + 2);
        document.getElementById('size-slider').value = BRUSH_SIZE;
        document.getElementById('size-val').textContent = BRUSH_SIZE;
        break;
      }
      case 'delete':
      case 'backspace':
        clearCanvas();
        break;
    }
  });
}

// ═══════════════════════════════════════════════════════════
// UI TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════
let toastTimeoutId = null;

function showToast(message) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('visible');
  if (toastTimeoutId) clearTimeout(toastTimeoutId);
  toastTimeoutId = setTimeout(() => {
    toast.classList.remove('visible');
  }, 2500);
}
