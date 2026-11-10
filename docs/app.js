/**
 * AI Air Draw — Revolutionary Web Studio
 * Full browser-based drawing engine with MediaPipe hand tracking
 * 9 Brushes · 16 Shapes · AI Tools · Symmetry · Effects
 */

'use strict';

// ═══════════════════════════════════════════════════════════
// GLOBALS
// ═══════════════════════════════════════════════════════════
const PALETTE = [
  '#000000','#FFFFFF','#FF0000','#00CC00','#0000FF','#FFFF00',
  '#FF8800','#FF00FF','#00FFFF','#8B4513','#808080','#C0C0C0',
  '#FF69B4','#7B68EE','#00FA9A','#FFD700','#FF6347','#4169E1',
  '#32CD32','#DC143C'
];

let COLOR1 = '#ff0000';   // foreground / stroke
let COLOR2 = '#ffffff';   // background / fill
let BRUSH_SIZE = 8;
let OPACITY = 1.0;
let CURRENT_TOOL = 'pen';
let SHAPE_FILL = 'outline';
let SYMMETRY = 'none';
let BACKGROUND = 'white';
let RAINBOW_MODE = false;
let AI_SNAP_LIVE = false;
let rainbowHue = 0;

let isDrawing = false;
let startX = 0, startY = 0;
let lastX = 0, lastY = 0;
let strokePoints = [];   // for AI snap
let lassoPoints = [];
let dripPoints = [];
let curveControl = null;
let textPending = null;
let polygonSides = 6;
let magnifierZoom = 3;

// Hand tracking
let handLandmarker = null;
let cameraActive = false;
let lastVideoTime = -1;
let handMode = true;
let pinchWasDown = false;
let dwellTarget = null;
let dwellStart = 0;
const DWELL_MS = 500;
const PINCH_THRESH = 0.055;

// undo/redo
const UNDO_MAX = 40;
let undoStack = [];
let redoStack = [];

// Canvas layers
let canvasBg, ctxBg;
let canvasDraw, ctxDraw;
let canvasOverlay, ctxOverlay;
let canvasW, canvasH;

// ═══════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════
window.addEventListener('DOMContentLoaded', () => {
  buildPalette();
  bindCamScreen();
  bindKeyboard();
});

function buildPalette() {
  const container = document.getElementById('color-discs');
  PALETTE.forEach(hex => {
    const d = document.createElement('div');
    d.className = 'color-disc';
    d.style.background = hex;
    d.title = hex;
    d.addEventListener('click', () => setColor1(hex));
    d.addEventListener('contextmenu', e => { e.preventDefault(); setColor2(hex); });
    container.appendChild(d);
  });
}

function bindCamScreen() {
  document.getElementById('btn-start-cam').addEventListener('click', () => {
    document.getElementById('cam-screen').style.display = 'none';
    document.getElementById('app').style.display = 'flex';
    initApp(true);
  });
  document.getElementById('btn-no-cam').addEventListener('click', () => {
    document.getElementById('cam-screen').style.display = 'none';
    document.getElementById('app').style.display = 'flex';
    initApp(false);
  });
}

function initApp(withCamera) {
  // Setup canvases
  canvasBg = document.getElementById('canvas-bg');
  canvasDraw = document.getElementById('canvas-draw');
  canvasOverlay = document.getElementById('canvas-overlay');
  ctxBg = canvasBg.getContext('2d');
  ctxDraw = canvasDraw.getContext('2d', { willReadFrequently: true });
  ctxOverlay = canvasOverlay.getContext('2d');

  resizeCanvases();
  window.addEventListener('resize', resizeCanvases);
  renderBackground();

  bindToolbar();
  bindCanvasEvents();

  if (withCamera) {
    handMode = true;
    startCamera();
  } else {
    handMode = false;
    setTrackerStatus('Mouse mode', '🖱️');
    document.getElementById('btn-cam-toggle').textContent = '📷 Camera OFF';
  }

  pushUndo();
  showToast('🎨 AI Air Draw Ready! ' + (withCamera ? 'Show your hand to start.' : 'Use mouse or touch to draw.'));
}

function resizeCanvases() {
  const studio = document.getElementById('studio');
  canvasW = studio.clientWidth;
  canvasH = studio.clientHeight;
  [canvasBg, canvasDraw, canvasOverlay].forEach(c => {
    c.width = canvasW;
    c.height = canvasH;
  });
  renderBackground();
}

// ═══════════════════════════════════════════════════════════
// TOOLBAR BINDING
// ═══════════════════════════════════════════════════════════
function bindToolbar() {
  // Tool buttons
  document.querySelectorAll('[data-tool]').forEach(btn => {
    btn.addEventListener('click', () => selectTool(btn.dataset.tool));
  });

  // Tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
      btn.classList.add('active');
      document.getElementById('tab-panel-' + btn.dataset.tab).style.display = 'flex';
    });
  });

  // Size slider
  const sizeSlider = document.getElementById('size-slider');
  sizeSlider.addEventListener('input', () => {
    BRUSH_SIZE = +sizeSlider.value;
    document.getElementById('size-val').textContent = BRUSH_SIZE;
  });

  // Opacity slider
  const opSlider = document.getElementById('opacity-slider');
  opSlider.addEventListener('input', () => {
    OPACITY = opSlider.value / 100;
    document.getElementById('opacity-val').textContent = opSlider.value;
  });

  // Undo / Redo / Clear / Save
  document.getElementById('btn-undo').addEventListener('click', undo);
  document.getElementById('btn-redo').addEventListener('click', redo);
  document.getElementById('btn-clear').addEventListener('click', clearCanvas);
  document.getElementById('btn-save').addEventListener('click', saveImage);

  // Color swatches
  document.getElementById('color1-swatch').addEventListener('click', () => openColorPicker('fg'));
  document.getElementById('color2-swatch').addEventListener('click', () => openColorPicker('bg'));

  // Custom color
  document.getElementById('btn-custom-color').addEventListener('click', () => openColorPicker('fg'));

  // Shape fill
  document.querySelectorAll('.sfill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sfill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      SHAPE_FILL = btn.dataset.fill;
    });
  });

  // AI buttons
  document.getElementById('btn-ai-snap').addEventListener('click', runAISnap);
  document.getElementById('btn-ai-classify').addEventListener('click', runAIClassify);
  document.getElementById('btn-ai-coloring').addEventListener('click', runColoringBook);
  document.getElementById('btn-ai-inpaint').addEventListener('click', runInpaint);
  document.getElementById('btn-ai-style').addEventListener('click', runStyleTransfer);
  document.getElementById('ai-snap-realtime').addEventListener('change', e => { AI_SNAP_LIVE = e.target.checked; });
  document.getElementById('ai-rainbow').addEventListener('change', e => { RAINBOW_MODE = e.target.checked; });

  // FX buttons
  document.getElementById('btn-fx-invert').addEventListener('click', () => applyFX('invert'));
  document.getElementById('btn-fx-gray').addEventListener('click', () => applyFX('grayscale'));
  document.getElementById('btn-fx-blur').addEventListener('click', () => applyFX('blur'));
  document.getElementById('btn-fx-sharpen').addEventListener('click', () => applyFX('sharpen'));
  document.getElementById('btn-fx-sepia').addEventListener('click', () => applyFX('sepia'));
  document.getElementById('btn-fx-emboss').addEventListener('click', () => applyFX('emboss'));
  document.getElementById('btn-fx-fliph').addEventListener('click', () => applyFX('fliph'));
  document.getElementById('btn-fx-flipv').addEventListener('click', () => applyFX('flipv'));
  document.getElementById('btn-fx-rot90').addEventListener('click', () => applyFX('rot90'));

  // Background
  document.querySelectorAll('.bg-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      BACKGROUND = btn.dataset.bg;
      renderBackground();
    });
  });

  // Symmetry
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

  // Hand / Mouse mode
  document.getElementById('btn-hand-mode').addEventListener('click', () => {
    handMode = true;
    document.getElementById('btn-hand-mode').classList.add('active');
    document.getElementById('btn-mouse-mode').classList.remove('active');
    if (!cameraActive) startCamera();
  });
  document.getElementById('btn-mouse-mode').addEventListener('click', () => {
    handMode = false;
    document.getElementById('btn-mouse-mode').classList.add('active');
    document.getElementById('btn-hand-mode').classList.remove('active');
    setTrackerStatus('Mouse mode', '🖱️');
  });

  // Gesture hint
  document.getElementById('btn-show-hint').addEventListener('click', () => {
    document.getElementById('gesture-hint').style.display = 'flex';
  });
  document.getElementById('btn-close-hint').addEventListener('click', () => {
    document.getElementById('gesture-hint').style.display = 'none';
  });

  // Color picker modal
  document.getElementById('picker-fg').addEventListener('click', () => { applyPickerColor('fg'); closeColorPicker(); });
  document.getElementById('picker-bg').addEventListener('click', () => { applyPickerColor('bg'); closeColorPicker(); });
  document.getElementById('picker-cancel').addEventListener('click', closeColorPicker);
  ['ph','ps','pl'].forEach(id => {
    document.getElementById(id).addEventListener('input', updatePickerPreview);
  });
  document.getElementById('phex').addEventListener('change', e => {
    const c = hexToHsl(e.target.value);
    if (c) {
      document.getElementById('ph').value = c.h;
      document.getElementById('ps').value = c.s;
      document.getElementById('pl').value = c.l;
      updatePickerPreview();
    }
  });
  drawColorWheel();

  // Text cancel
  document.getElementById('btn-text-cancel').addEventListener('click', () => {
    document.getElementById('text-input-wrap').style.display = 'none';
    textPending = null;
  });

  // AI result close
  document.getElementById('btn-ai-result-close').addEventListener('click', () => {
    document.getElementById('ai-result').style.display = 'none';
  });
}

// ═══════════════════════════════════════════════════════════
// TOOL SELECTION
// ═══════════════════════════════════════════════════════════
function selectTool(tool) {
  CURRENT_TOOL = tool;
  document.querySelectorAll('[data-tool]').forEach(b => b.classList.remove('tool-active'));
  document.querySelectorAll(`[data-tool="${tool}"]`).forEach(b => b.classList.add('tool-active'));

  // Show text input bar if text tool
  if (tool === 'text') {
    document.getElementById('text-input-wrap').style.display = 'flex';
  } else {
    document.getElementById('text-input-wrap').style.display = 'none';
  }

  canvasOverlay.style.cursor = getCursor(tool);
  showToast('Tool: ' + tool);
}

function getCursor(tool) {
  const map = {
    pen: 'crosshair', pencil: 'crosshair', marker: 'crosshair', calligraphy: 'crosshair',
    crayon: 'crosshair', spray: 'crosshair', neon: 'crosshair', drip: 'crosshair', sparkle: 'crosshair',
    eraser: 'cell', fill: 'cell', eyedropper: 'crosshair',
    text: 'text', magnifier: 'zoom-in',
    'select-rect': 'default', lasso: 'default', crop: 'crosshair',
    line: 'crosshair', rect: 'crosshair', rndrect: 'crosshair',
    circle: 'crosshair', triangle: 'crosshair', diamond: 'crosshair',
    star5: 'crosshair', star4: 'crosshair', arrow: 'crosshair',
    heart: 'crosshair', lightning: 'crosshair', callout: 'crosshair',
    hexagon: 'crosshair', curve: 'crosshair', polygon: 'crosshair', freehand: 'crosshair',
  };
  return map[tool] || 'crosshair';
}

// ═══════════════════════════════════════════════════════════
// CANVAS EVENTS (Mouse + Touch)
// ═══════════════════════════════════════════════════════════
function bindCanvasEvents() {
  const el = canvasOverlay;

  el.addEventListener('mousedown', e => { if (!handMode) onPointerDown(e.offsetX, e.offsetY, e.button); });
  el.addEventListener('mousemove', e => { if (!handMode) onPointerMove(e.offsetX, e.offsetY); });
  el.addEventListener('mouseup', () => { if (!handMode) onPointerUp(); });
  el.addEventListener('mouseleave', () => { if (!handMode) onPointerUp(); });
  el.addEventListener('contextmenu', e => e.preventDefault());

  el.addEventListener('touchstart', e => {
    e.preventDefault();
    if (!handMode) {
      const r = el.getBoundingClientRect();
      const t = e.touches[0];
      onPointerDown(t.clientX - r.left, t.clientY - r.top, 0);
    }
  }, { passive: false });
  el.addEventListener('touchmove', e => {
    e.preventDefault();
    if (!handMode) {
      const r = el.getBoundingClientRect();
      const t = e.touches[0];
      onPointerMove(t.clientX - r.left, t.clientY - r.top);
    }
  }, { passive: false });
  el.addEventListener('touchend', () => { if (!handMode) onPointerUp(); });
}

const SHAPE_TOOLS = new Set(['line','rect','rndrect','circle','triangle','diamond','star5','star4','arrow','heart','lightning','callout','hexagon','curve','polygon','freehand','select-rect','lasso','crop']);

function onPointerDown(x, y, button) {
  if (CURRENT_TOOL === 'eyedropper') { pickColor(x, y, button); return; }
  if (CURRENT_TOOL === 'fill') { floodFill(x, y); return; }
  if (CURRENT_TOOL === 'magnifier') { showMagnifier(x, y); return; }
  if (CURRENT_TOOL === 'text') { placeText(x, y); return; }

  pushUndo();
  isDrawing = true;
  startX = x; startY = y;
  lastX = x; lastY = y;
  strokePoints = [[x, y]];
  lassoPoints = [[x, y]];
  dripPoints = [];

  if (!SHAPE_TOOLS.has(CURRENT_TOOL)) {
    ctxDraw.beginPath();
    ctxDraw.moveTo(x, y);
  }
}

function onPointerMove(x, y) {
  if (!isDrawing) return;
  strokePoints.push([x, y]);

  if (SHAPE_TOOLS.has(CURRENT_TOOL)) {
    // Preview on overlay
    ctxOverlay.clearRect(0, 0, canvasW, canvasH);
    drawShapePreview(ctxOverlay, startX, startY, x, y, false);
    if (CURRENT_TOOL === 'lasso' || CURRENT_TOOL === 'freehand') {
      lassoPoints.push([x, y]);
    }
  } else {
    applyBrush(ctxDraw, lastX, lastY, x, y);
    applySymmetry(lastX, lastY, x, y);
  }

  lastX = x; lastY = y;
}

function onPointerUp() {
  if (!isDrawing) return;
  isDrawing = false;
  ctxOverlay.clearRect(0, 0, canvasW, canvasH);

  if (SHAPE_TOOLS.has(CURRENT_TOOL)) {
    drawShapePreview(ctxDraw, startX, startY, lastX, lastY, true);
  }

  if (AI_SNAP_LIVE && strokePoints.length > 5) {
    runAISnap();
  }

  drawCursorDot(lastX, lastY);
}

// ═══════════════════════════════════════════════════════════
// BRUSH ENGINE
// ═══════════════════════════════════════════════════════════
function getColor(alpha) {
  if (RAINBOW_MODE) {
    rainbowHue = (rainbowHue + 1.5) % 360;
    return `hsla(${rainbowHue},100%,55%,${alpha})`;
  }
  const r = parseInt(COLOR1.slice(1,3),16);
  const g = parseInt(COLOR1.slice(3,5),16);
  const b = parseInt(COLOR1.slice(5,7),16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function applyBrush(ctx, x1, y1, x2, y2) {
  const a = OPACITY;
  ctx.globalAlpha = a;
  ctx.strokeStyle = getColor(1);
  ctx.fillStyle = getColor(1);
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  switch (CURRENT_TOOL) {
    case 'pen':
      ctx.lineWidth = BRUSH_SIZE;
      ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
      break;

    case 'pencil': {
      ctx.lineWidth = BRUSH_SIZE * 0.5;
      ctx.globalAlpha = a * 0.7;
      // Slightly noisy
      for (let i = 0; i < 3; i++) {
        const nx = x2 + (Math.random()-0.5)*BRUSH_SIZE*0.4;
        const ny = y2 + (Math.random()-0.5)*BRUSH_SIZE*0.4;
        ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(nx,ny); ctx.stroke();
      }
      break;
    }

    case 'marker': {
      ctx.lineWidth = BRUSH_SIZE * 2.5;
      ctx.globalAlpha = a * 0.4;
      ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
      break;
    }

    case 'calligraphy': {
      const angle = Math.PI / 4;
      ctx.lineWidth = 1;
      ctx.globalAlpha = a;
      ctx.beginPath();
      ctx.moveTo(x1 + Math.cos(angle)*BRUSH_SIZE, y1 + Math.sin(angle)*BRUSH_SIZE);
      ctx.lineTo(x2 + Math.cos(angle)*BRUSH_SIZE, y2 + Math.sin(angle)*BRUSH_SIZE);
      ctx.lineTo(x2 - Math.cos(angle)*BRUSH_SIZE, y2 - Math.sin(angle)*BRUSH_SIZE);
      ctx.lineTo(x1 - Math.cos(angle)*BRUSH_SIZE, y1 - Math.sin(angle)*BRUSH_SIZE);
      ctx.closePath(); ctx.fill();
      break;
    }

    case 'crayon': {
      const r2 = BRUSH_SIZE;
      ctx.globalAlpha = a * 0.15;
      for (let i = 0; i < 40; i++) {
        const t = Math.random();
        const bx = x1 + (x2-x1)*t + (Math.random()-0.5)*r2*2;
        const by = y1 + (y2-y1)*t + (Math.random()-0.5)*r2*2;
        ctx.fillRect(bx, by, 1.5, 1.5);
      }
      break;
    }

    case 'spray': {
      ctx.globalAlpha = a * 0.1;
      const sr = BRUSH_SIZE * 1.5;
      for (let i = 0; i < 50; i++) {
        const ang = Math.random() * Math.PI * 2;
        const dist = Math.random() * sr;
        ctx.fillRect(x2 + Math.cos(ang)*dist, y2 + Math.sin(ang)*dist, 1.5, 1.5);
      }
      break;
    }

    case 'neon': {
      // Glow effect: 3 strokes, widest outermost
      [BRUSH_SIZE*4, BRUSH_SIZE*2, BRUSH_SIZE*0.5].forEach((w, i) => {
        ctx.globalAlpha = a * [0.05, 0.15, 1][i];
        ctx.lineWidth = w;
        ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
      });
      break;
    }

    case 'drip': {
      ctx.lineWidth = BRUSH_SIZE;
      ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
      // random drip extend
      if (Math.random() < 0.08) {
        dripPoints.push({x:x2, y:y2, len:0, maxLen: 20+Math.random()*60});
      }
      ctx.lineWidth = BRUSH_SIZE * 0.6;
      dripPoints.forEach(dp => {
        dp.len += 2;
        ctx.globalAlpha = a * (1 - dp.len/dp.maxLen);
        ctx.beginPath(); ctx.moveTo(dp.x, dp.y); ctx.lineTo(dp.x, dp.y + dp.len); ctx.stroke();
      });
      dripPoints = dripPoints.filter(dp => dp.len < dp.maxLen);
      break;
    }

    case 'sparkle': {
      ctx.globalAlpha = a;
      const spCount = Math.ceil(BRUSH_SIZE / 2);
      for (let i = 0; i < spCount; i++) {
        const sx = x2 + (Math.random()-0.5)*BRUSH_SIZE*3;
        const sy = y2 + (Math.random()-0.5)*BRUSH_SIZE*3;
        const sr2 = Math.random()*2+0.5;
        ctx.beginPath();
        ctx.arc(sx, sy, sr2, 0, Math.PI*2);
        ctx.fill();
      }
      break;
    }

    case 'eraser': {
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'destination-out';
      ctx.lineWidth = BRUSH_SIZE * 2;
      ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
      ctx.globalCompositeOperation = 'source-over';
      return;
    }
  }
  ctx.globalAlpha = 1;
}

// ═══════════════════════════════════════════════════════════
// SHAPE DRAWING
// ═══════════════════════════════════════════════════════════
function drawShapePreview(ctx, x1, y1, x2, y2, commit) {
  const tool = CURRENT_TOOL;
  ctx.save();
  ctx.globalAlpha = commit ? OPACITY : OPACITY * 0.8;
  ctx.strokeStyle = getColor(1);
  ctx.fillStyle = COLOR2;
  ctx.lineWidth = BRUSH_SIZE;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  const w = x2 - x1, h = y2 - y1;
  const cx = (x1+x2)/2, cy = (y1+y2)/2;

  ctx.beginPath();
  switch(tool) {
    case 'line':
      ctx.moveTo(x1,y1); ctx.lineTo(x2,y2);
      _stroke(ctx);
      break;
    case 'rect':
      ctx.rect(x1,y1,w,h);
      _fillStroke(ctx);
      break;
    case 'rndrect': {
      const r = Math.min(Math.abs(w),Math.abs(h))*0.15;
      ctx.roundRect ? ctx.roundRect(x1,y1,w,h,r) : ctx.rect(x1,y1,w,h);
      _fillStroke(ctx);
      break;
    }
    case 'circle':
      ctx.ellipse(cx,cy,Math.abs(w)/2,Math.abs(h)/2,0,0,Math.PI*2);
      _fillStroke(ctx);
      break;
    case 'triangle':
      ctx.moveTo(cx,y1); ctx.lineTo(x2,y2); ctx.lineTo(x1,y2); ctx.closePath();
      _fillStroke(ctx);
      break;
    case 'diamond':
      ctx.moveTo(cx,y1); ctx.lineTo(x2,cy); ctx.lineTo(cx,y2); ctx.lineTo(x1,cy); ctx.closePath();
      _fillStroke(ctx);
      break;
    case 'star5':
      _starPath(ctx, cx, cy, 5, Math.min(Math.abs(w),Math.abs(h))/2, Math.min(Math.abs(w),Math.abs(h))/4.5);
      _fillStroke(ctx);
      break;
    case 'star4':
      _starPath(ctx, cx, cy, 4, Math.min(Math.abs(w),Math.abs(h))/2, Math.min(Math.abs(w),Math.abs(h))/4);
      _fillStroke(ctx);
      break;
    case 'hexagon':
      _polygonPath(ctx, cx, cy, 6, Math.min(Math.abs(w),Math.abs(h))/2);
      _fillStroke(ctx);
      break;
    case 'polygon':
      _polygonPath(ctx, cx, cy, polygonSides, Math.min(Math.abs(w),Math.abs(h))/2);
      _fillStroke(ctx);
      break;
    case 'arrow':
      _arrowPath(ctx, x1, y1, x2, y2, BRUSH_SIZE*2);
      _fillStroke(ctx);
      break;
    case 'heart':
      _heartPath(ctx, cx, cy, Math.min(Math.abs(w),Math.abs(h))/2);
      _fillStroke(ctx);
      break;
    case 'lightning':
      _lightningPath(ctx, x1, y1, x2, y2);
      _fillStroke(ctx);
      break;
    case 'callout':
      _calloutPath(ctx, x1, y1, w, h);
      _fillStroke(ctx);
      break;
    case 'curve':
      if (!curveControl) {
        curveControl = { x: cx, y: y1 };
      }
      ctx.moveTo(x1,y1);
      ctx.quadraticCurveTo(curveControl.x, curveControl.y, x2, y2);
      _stroke(ctx);
      if (commit) curveControl = null;
      break;
    case 'freehand':
    case 'lasso':
      if (strokePoints.length > 1) {
        ctx.moveTo(strokePoints[0][0], strokePoints[0][1]);
        strokePoints.forEach(p => ctx.lineTo(p[0], p[1]));
        ctx.closePath();
        _fillStroke(ctx);
      }
      break;
    case 'select-rect': {
      ctx.setLineDash([6,4]);
      ctx.strokeStyle = '#00aaff';
      ctx.fillStyle = 'rgba(0,170,255,0.1)';
      ctx.lineWidth = 2;
      ctx.rect(x1,y1,w,h);
      _fillStroke(ctx);
      ctx.setLineDash([]);
      break;
    }
    case 'crop': {
      ctx.setLineDash([6,4]);
      ctx.strokeStyle = '#ff6600';
      ctx.lineWidth = 2;
      ctx.rect(x1,y1,w,h);
      _stroke(ctx);
      ctx.setLineDash([]);
      if (commit) cropCanvas(x1, y1, x2, y2);
      break;
    }
  }
  ctx.restore();
}

function _stroke(ctx) {
  if (SHAPE_FILL === 'fill') {
    ctx.fill();
  } else {
    ctx.stroke();
  }
}

function _fillStroke(ctx) {
  if (SHAPE_FILL === 'fill' || SHAPE_FILL === 'both') ctx.fill();
  if (SHAPE_FILL === 'outline' || SHAPE_FILL === 'both') ctx.stroke();
}

function _starPath(ctx, cx, cy, points, outer, inner) {
  for (let i = 0; i < points*2; i++) {
    const r = i%2===0 ? outer : inner;
    const a = (i * Math.PI / points) - Math.PI/2;
    if (i===0) ctx.moveTo(cx+r*Math.cos(a), cy+r*Math.sin(a));
    else ctx.lineTo(cx+r*Math.cos(a), cy+r*Math.sin(a));
  }
  ctx.closePath();
}

function _polygonPath(ctx, cx, cy, sides, r) {
  for (let i = 0; i < sides; i++) {
    const a = (i * 2 * Math.PI / sides) - Math.PI/2;
    if (i===0) ctx.moveTo(cx+r*Math.cos(a), cy+r*Math.sin(a));
    else ctx.lineTo(cx+r*Math.cos(a), cy+r*Math.sin(a));
  }
  ctx.closePath();
}

function _arrowPath(ctx, x1, y1, x2, y2, hw) {
  const angle = Math.atan2(y2-y1, x2-x1);
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - hw*Math.cos(angle-Math.PI/6), y2 - hw*Math.sin(angle-Math.PI/6));
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - hw*Math.cos(angle+Math.PI/6), y2 - hw*Math.sin(angle+Math.PI/6));
}

function _heartPath(ctx, cx, cy, r) {
  ctx.moveTo(cx, cy + r * 0.3);
  ctx.bezierCurveTo(cx - r*2, cy - r*1.2, cx - r*2, cy + r*0.5, cx, cy + r*1.2);
  ctx.bezierCurveTo(cx + r*2, cy + r*0.5, cx + r*2, cy - r*1.2, cx, cy + r*0.3);
}

function _lightningPath(ctx, x1, y1, x2, y2) {
  const mx = (x1+x2)/2, my = (y1+y2)/2;
  const dx = (x2-x1)*0.3, dy = (y2-y1)*0.3;
  ctx.moveTo(x1, y1);
  ctx.lineTo(mx+dy, my-dx);
  ctx.lineTo(mx-dy*0.5, my+dx*0.5);
  ctx.lineTo(x2, y2);
}

function _calloutPath(ctx, x1, y1, w, h) {
  const tailX = x1, tailY = y1 + h + Math.abs(h)*0.3;
  const r2 = 10;
  ctx.roundRect ? ctx.roundRect(x1, y1, w, h, r2) : ctx.rect(x1, y1, w, h);
  ctx.moveTo(x1 + Math.abs(w)*0.2, y1+h);
  ctx.lineTo(tailX, tailY);
  ctx.lineTo(x1 + Math.abs(w)*0.4, y1+h);
}

// ═══════════════════════════════════════════════════════════
// SYMMETRY
// ═══════════════════════════════════════════════════════════
function applySymmetry(x1, y1, x2, y2) {
  if (SYMMETRY === 'none') return;
  const W = canvasW, H = canvasH;
  const cx = W/2, cy = H/2;

  function mirrorBrush(nx1, ny1, nx2, ny2) {
    applyBrushRaw(ctxDraw, nx1, ny1, nx2, ny2);
  }

  if (SYMMETRY === 'mirror_h' || SYMMETRY === 'quad') {
    mirrorBrush(W-x1, y1, W-x2, y2);
  }
  if (SYMMETRY === 'mirror_v' || SYMMETRY === 'quad') {
    mirrorBrush(x1, H-y1, x2, H-y2);
  }
  if (SYMMETRY === 'quad') {
    mirrorBrush(W-x1, H-y1, W-x2, H-y2);
  }
  if (SYMMETRY === 'radial4' || SYMMETRY === 'radial8') {
    const steps = SYMMETRY === 'radial4' ? 4 : 8;
    for (let i = 1; i < steps; i++) {
      const ang = (Math.PI*2/steps)*i;
      const cos = Math.cos(ang), sin = Math.sin(ang);
      const rx1 = cx + (x1-cx)*cos - (y1-cy)*sin;
      const ry1 = cy + (x1-cx)*sin + (y1-cy)*cos;
      const rx2 = cx + (x2-cx)*cos - (y2-cy)*sin;
      const ry2 = cy + (x2-cx)*sin + (y2-cy)*cos;
      mirrorBrush(rx1, ry1, rx2, ry2);
    }
  }
}

function applyBrushRaw(ctx, x1, y1, x2, y2) {
  const prevTool = CURRENT_TOOL;
  applyBrush(ctx, x1, y1, x2, y2);
}

// ═══════════════════════════════════════════════════════════
// PAINT TOOLS
// ═══════════════════════════════════════════════════════════
function floodFill(startX, startY) {
  pushUndo();
  const imgData = ctxDraw.getImageData(0, 0, canvasW, canvasH);
  const data = imgData.data;
  const idx = (Math.round(startY) * canvasW + Math.round(startX)) * 4;
  const tr = data[idx], tg = data[idx+1], tb = data[idx+2], ta = data[idx+3];

  const cr = parseInt(COLOR1.slice(1,3),16);
  const cg = parseInt(COLOR1.slice(3,5),16);
  const cb = parseInt(COLOR1.slice(5,7),16);
  const ca = Math.round(OPACITY * 255);

  if (tr===cr && tg===cg && tb===cb && ta===ca) return;

  const stack = [[Math.round(startX), Math.round(startY)]];
  const visited = new Uint8Array(canvasW * canvasH);
  const THRESHOLD = 30;

  function colorMatch(i) {
    return Math.abs(data[i]-tr) + Math.abs(data[i+1]-tg) + Math.abs(data[i+2]-tb) + Math.abs(data[i+3]-ta) < THRESHOLD;
  }

  while (stack.length) {
    const [x, y] = stack.pop();
    if (x<0||x>=canvasW||y<0||y>=canvasH) continue;
    const i4 = (y*canvasW+x)*4;
    if (visited[y*canvasW+x]) continue;
    if (!colorMatch(i4)) continue;
    visited[y*canvasW+x] = 1;
    data[i4]=cr; data[i4+1]=cg; data[i4+2]=cb; data[i4+3]=ca;
    stack.push([x+1,y],[x-1,y],[x,y+1],[x,y-1]);
  }
  ctxDraw.putImageData(imgData, 0, 0);
  showToast('🪣 Fill applied');
}

function pickColor(x, y, button) {
  const pixel = ctxDraw.getImageData(Math.round(x), Math.round(y), 1, 1).data;
  const hex = '#' + [pixel[0],pixel[1],pixel[2]].map(v=>v.toString(16).padStart(2,'0')).join('');
  if (button === 2) setColor2(hex);
  else setColor1(hex);
  showToast('Picked: ' + hex);
}

function placeText(x, y) {
  const wrap = document.getElementById('text-input-wrap');
  wrap.style.display = 'flex';
  const inp = document.getElementById('text-input');
  inp.focus();

  textPending = { x, y };
  inp.onkeydown = e => {
    if (e.key === 'Enter' && textPending) {
      commitText();
    }
  };
}

function commitText() {
  if (!textPending) return;
  pushUndo();
  const inp = document.getElementById('text-input');
  const font = document.getElementById('font-select').value;
  const txt = inp.value;
  if (!txt) return;

  ctxDraw.save();
  ctxDraw.font = `${BRUSH_SIZE * 3}px "${font}"`;
  ctxDraw.fillStyle = getColor(1);
  ctxDraw.globalAlpha = OPACITY;
  ctxDraw.fillText(txt, textPending.x, textPending.y);
  ctxDraw.restore();
  inp.value = '';
  textPending = null;
  showToast('Text placed');
}

function showMagnifier(x, y) {
  const size = 80;
  ctxOverlay.clearRect(0, 0, canvasW, canvasH);
  ctxOverlay.save();
  ctxOverlay.beginPath();
  ctxOverlay.arc(x, y - size - 10, size/2, 0, Math.PI*2);
  ctxOverlay.clip();
  ctxOverlay.drawImage(canvasDraw,
    x - size/(magnifierZoom*2), y - size/(magnifierZoom*2), size/magnifierZoom, size/magnifierZoom,
    x - size/2, y - size - 10 - size/2, size, size);
  ctxOverlay.restore();
  ctxOverlay.strokeStyle = '#00d4ff';
  ctxOverlay.lineWidth = 2;
  ctxOverlay.beginPath();
  ctxOverlay.arc(x, y - size - 10, size/2, 0, Math.PI*2);
  ctxOverlay.stroke();
}

function cropCanvas(x1, y1, x2, y2) {
  pushUndo();
  const cw = Math.abs(x2-x1), ch = Math.abs(y2-y1);
  const cx = Math.min(x1,x2), cy = Math.min(y1,y2);
  const img = ctxDraw.getImageData(cx, cy, cw, ch);
  ctxDraw.clearRect(0, 0, canvasW, canvasH);
  ctxDraw.putImageData(img, cx, cy);
  showToast('Cropped');
}

// ═══════════════════════════════════════════════════════════
// COLOR MANAGEMENT
// ═══════════════════════════════════════════════════════════
function setColor1(hex) {
  COLOR1 = hex;
  document.getElementById('color1-swatch').style.background = hex;
}
function setColor2(hex) {
  COLOR2 = hex;
  document.getElementById('color2-swatch').style.background = hex;
}

let pickerTarget = 'fg';
function openColorPicker(target) {
  pickerTarget = target;
  document.getElementById('color-picker-modal').style.display = 'flex';
  updatePickerPreview();
}
function closeColorPicker() {
  document.getElementById('color-picker-modal').style.display = 'none';
}
function applyPickerColor(target) {
  const h = document.getElementById('ph').value;
  const s = document.getElementById('ps').value;
  const l = document.getElementById('pl').value;
  const hex = hslToHex(h, s, l);
  if (target === 'fg') setColor1(hex);
  else setColor2(hex);
}
function updatePickerPreview() {
  const h = document.getElementById('ph').value;
  const s = document.getElementById('ps').value;
  const l = document.getElementById('pl').value;
  const hex = hslToHex(h, s, l);
  document.getElementById('picker-preview').style.background = hex;
  document.getElementById('phex').value = hex;
}

function drawColorWheel() {
  const c = document.getElementById('color-wheel-canvas');
  const ctx = c.getContext('2d');
  const cx = c.width/2, cy = c.height/2, r = cx - 5;
  for (let angle = 0; angle < 360; angle++) {
    const a1 = (angle-1) * Math.PI/180;
    const a2 = (angle+1) * Math.PI/180;
    const grad = ctx.createRadialGradient(cx,cy,0,cx,cy,r);
    grad.addColorStop(0, 'white');
    grad.addColorStop(1, `hsl(${angle},100%,50%)`);
    ctx.beginPath();
    ctx.moveTo(cx,cy);
    ctx.arc(cx,cy,r,a1,a2);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
  }
  document.getElementById('color-wheel-canvas').addEventListener('click', e => {
    const rect = c.getBoundingClientRect();
    const x = e.clientX - rect.left - cx;
    const y = e.clientY - rect.top - cy;
    const angle = ((Math.atan2(y,x)*180/Math.PI)+360)%360;
    const dist = Math.min(Math.sqrt(x*x+y*y)/r, 1);
    document.getElementById('ph').value = Math.round(angle);
    document.getElementById('ps').value = Math.round(dist * 100);
    updatePickerPreview();
  });
}

function hslToHex(h, s, l) {
  h=+h; s=+s/100; l=+l/100;
  const a = s * Math.min(l, 1-l);
  const f = n => {
    const k = (n+h/30)%12;
    const c = l - a*Math.max(Math.min(k-3,9-k,1),-1);
    return Math.round(255*c).toString(16).padStart(2,'0');
  };
  return '#'+f(0)+f(8)+f(4);
}

function hexToHsl(hex) {
  const r = parseInt(hex.slice(1,3),16)/255;
  const g = parseInt(hex.slice(3,5),16)/255;
  const b = parseInt(hex.slice(5,7),16)/255;
  const max = Math.max(r,g,b), min = Math.min(r,g,b);
  let h, s, l = (max+min)/2;
  if (max===min) { h=s=0; }
  else {
    const d = max-min;
    s = l>0.5 ? d/(2-max-min) : d/(max+min);
    switch(max) {
      case r: h=(g-b)/d+(g<b?6:0); break;
      case g: h=(b-r)/d+2; break;
      case b: h=(r-g)/d+4; break;
    }
    h*=60;
  }
  return { h: Math.round(h), s: Math.round(s*100), l: Math.round(l*100) };
}

// ═══════════════════════════════════════════════════════════
// BACKGROUND
// ═══════════════════════════════════════════════════════════
function renderBackground() {
  ctxBg.clearRect(0,0,canvasW,canvasH);
  switch(BACKGROUND) {
    case 'white':
      ctxBg.fillStyle = '#FFFFFF'; ctxBg.fillRect(0,0,canvasW,canvasH); break;
    case 'black':
      ctxBg.fillStyle = '#000000'; ctxBg.fillRect(0,0,canvasW,canvasH); break;
    case 'grid': {
      ctxBg.fillStyle = '#FFFFFF'; ctxBg.fillRect(0,0,canvasW,canvasH);
      ctxBg.strokeStyle = '#ddd'; ctxBg.lineWidth = 0.5;
      for (let x=0;x<canvasW;x+=20) { ctxBg.beginPath(); ctxBg.moveTo(x,0); ctxBg.lineTo(x,canvasH); ctxBg.stroke(); }
      for (let y=0;y<canvasH;y+=20) { ctxBg.beginPath(); ctxBg.moveTo(0,y); ctxBg.lineTo(canvasW,y); ctxBg.stroke(); }
      break;
    }
    case 'dotgrid': {
      ctxBg.fillStyle = '#FFFFFF'; ctxBg.fillRect(0,0,canvasW,canvasH);
      ctxBg.fillStyle = '#ccc';
      for (let x=0;x<canvasW;x+=20) for (let y=0;y<canvasH;y+=20) {
        ctxBg.fillRect(x-1,y-1,2,2);
      }
      break;
    }
    case 'stars': {
      ctxBg.fillStyle = '#0a0a1a'; ctxBg.fillRect(0,0,canvasW,canvasH);
      ctxBg.fillStyle = 'white';
      for (let i=0;i<300;i++) {
        const sx=Math.random()*canvasW, sy=Math.random()*canvasH, sr=Math.random()*1.5;
        ctxBg.beginPath(); ctxBg.arc(sx,sy,sr,0,Math.PI*2); ctxBg.fill();
      }
      break;
    }
    case 'blueprint': {
      ctxBg.fillStyle = '#0d2b4a'; ctxBg.fillRect(0,0,canvasW,canvasH);
      ctxBg.strokeStyle = 'rgba(100,180,255,0.3)'; ctxBg.lineWidth = 0.5;
      for (let x=0;x<canvasW;x+=30) { ctxBg.beginPath(); ctxBg.moveTo(x,0); ctxBg.lineTo(x,canvasH); ctxBg.stroke(); }
      for (let y=0;y<canvasH;y+=30) { ctxBg.beginPath(); ctxBg.moveTo(0,y); ctxBg.lineTo(canvasW,y); ctxBg.stroke(); }
      ctxBg.strokeStyle = 'rgba(100,180,255,0.6)'; ctxBg.lineWidth = 1;
      for (let x=0;x<canvasW;x+=150) { ctxBg.beginPath(); ctxBg.moveTo(x,0); ctxBg.lineTo(x,canvasH); ctxBg.stroke(); }
      for (let y=0;y<canvasH;y+=150) { ctxBg.beginPath(); ctxBg.moveTo(0,y); ctxBg.lineTo(canvasW,y); ctxBg.stroke(); }
      break;
    }
    case 'canvas': {
      ctxBg.fillStyle = '#f5e9d0'; ctxBg.fillRect(0,0,canvasW,canvasH);
      // Canvas texture lines
      ctxBg.strokeStyle = 'rgba(180,150,100,0.15)'; ctxBg.lineWidth = 1;
      for (let x=0;x<canvasW;x+=4) { ctxBg.beginPath(); ctxBg.moveTo(x,0); ctxBg.lineTo(x,canvasH); ctxBg.stroke(); }
      for (let y=0;y<canvasH;y+=4) { ctxBg.beginPath(); ctxBg.moveTo(0,y); ctxBg.lineTo(canvasW,y); ctxBg.stroke(); }
      break;
    }
    case 'gradient': {
      const grad = ctxBg.createLinearGradient(0,0,canvasW,canvasH);
      grad.addColorStop(0, '#1a0533');
      grad.addColorStop(0.5, '#0d2b4a');
      grad.addColorStop(1, '#0a2a0a');
      ctxBg.fillStyle = grad;
      ctxBg.fillRect(0,0,canvasW,canvasH);
      break;
    }
  }
}

// ═══════════════════════════════════════════════════════════
// EFFECTS / TRANSFORMS
// ═══════════════════════════════════════════════════════════
function applyFX(fx) {
  pushUndo();
  if (fx === 'fliph') {
    const tmp = document.createElement('canvas');
    tmp.width=canvasW; tmp.height=canvasH;
    const tc = tmp.getContext('2d');
    tc.drawImage(canvasDraw,0,0);
    ctxDraw.clearRect(0,0,canvasW,canvasH);
    ctxDraw.save();
    ctxDraw.translate(canvasW,0);
    ctxDraw.scale(-1,1);
    ctxDraw.drawImage(tmp,0,0);
    ctxDraw.restore();
    showToast('Flipped Horizontal'); return;
  }
  if (fx === 'flipv') {
    const tmp = document.createElement('canvas');
    tmp.width=canvasW; tmp.height=canvasH;
    const tc = tmp.getContext('2d');
    tc.drawImage(canvasDraw,0,0);
    ctxDraw.clearRect(0,0,canvasW,canvasH);
    ctxDraw.save();
    ctxDraw.translate(0,canvasH);
    ctxDraw.scale(1,-1);
    ctxDraw.drawImage(tmp,0,0);
    ctxDraw.restore();
    showToast('Flipped Vertical'); return;
  }
  if (fx === 'rot90') {
    const tmp = document.createElement('canvas');
    tmp.width=canvasH; tmp.height=canvasW;
    const tc = tmp.getContext('2d');
    tc.translate(canvasH,0);
    tc.rotate(Math.PI/2);
    tc.drawImage(canvasDraw,0,0);
    ctxDraw.clearRect(0,0,canvasW,canvasH);
    ctxDraw.drawImage(tmp,0,0,canvasW,canvasH);
    showToast('Rotated 90°'); return;
  }

  const imgData = ctxDraw.getImageData(0,0,canvasW,canvasH);
  const d = imgData.data;

  if (fx === 'invert') {
    for (let i=0;i<d.length;i+=4) {
      d[i]=255-d[i]; d[i+1]=255-d[i+1]; d[i+2]=255-d[i+2];
    }
  } else if (fx === 'grayscale') {
    for (let i=0;i<d.length;i+=4) {
      const g=0.299*d[i]+0.587*d[i+1]+0.114*d[i+2];
      d[i]=d[i+1]=d[i+2]=g;
    }
  } else if (fx === 'sepia') {
    for (let i=0;i<d.length;i+=4) {
      const r=d[i],g=d[i+1],b=d[i+2];
      d[i]  = Math.min(255, r*0.393+g*0.769+b*0.189);
      d[i+1]= Math.min(255, r*0.349+g*0.686+b*0.168);
      d[i+2]= Math.min(255, r*0.272+g*0.534+b*0.131);
    }
  } else if (fx === 'emboss') {
    const src = new Uint8ClampedArray(d);
    const kernel = [-2,-1,0,-1,1,1,0,1,2];
    const W = canvasW;
    for (let y=1;y<canvasH-1;y++) for (let x=1;x<W-1;x++) {
      let r=0,g=0,b=0;
      for (let ky=-1;ky<=1;ky++) for (let kx=-1;kx<=1;kx++) {
        const i4=((y+ky)*W+(x+kx))*4;
        const k=kernel[(ky+1)*3+(kx+1)];
        r+=src[i4]*k; g+=src[i4+1]*k; b+=src[i4+2]*k;
      }
      const i4=(y*W+x)*4;
      d[i4]=Math.min(255,Math.max(0,r+128));
      d[i4+1]=Math.min(255,Math.max(0,g+128));
      d[i4+2]=Math.min(255,Math.max(0,b+128));
    }
  } else if (fx === 'blur') {
    const src = new Uint8ClampedArray(d);
    const W = canvasW;
    const kernel = [1,2,1,2,4,2,1,2,1]; const ksum=16;
    for (let y=1;y<canvasH-1;y++) for (let x=1;x<W-1;x++) {
      let r=0,g=0,b=0;
      for (let ky=-1;ky<=1;ky++) for (let kx=-1;kx<=1;kx++) {
        const i4=((y+ky)*W+(x+kx))*4;
        const k=kernel[(ky+1)*3+(kx+1)];
        r+=src[i4]*k; g+=src[i4+1]*k; b+=src[i4+2]*k;
      }
      const i4=(y*W+x)*4;
      d[i4]=r/ksum; d[i4+1]=g/ksum; d[i4+2]=b/ksum;
    }
  } else if (fx === 'sharpen') {
    const src = new Uint8ClampedArray(d);
    const W = canvasW;
    const kernel = [0,-1,0,-1,5,-1,0,-1,0];
    for (let y=1;y<canvasH-1;y++) for (let x=1;x<W-1;x++) {
      let r=0,g=0,b=0;
      for (let ky=-1;ky<=1;ky++) for (let kx=-1;kx<=1;kx++) {
        const i4=((y+ky)*W+(x+kx))*4;
        const k=kernel[(ky+1)*3+(kx+1)];
        r+=src[i4]*k; g+=src[i4+1]*k; b+=src[i4+2]*k;
      }
      const i4=(y*W+x)*4;
      d[i4]=Math.min(255,Math.max(0,r));
      d[i4+1]=Math.min(255,Math.max(0,g));
      d[i4+2]=Math.min(255,Math.max(0,b));
    }
  }

  ctxDraw.putImageData(imgData, 0, 0);
  showToast('Effect: ' + fx);
}

// ═══════════════════════════════════════════════════════════
// AI FEATURES
// ═══════════════════════════════════════════════════════════

/** AI Auto-Shape Beautifier — detects drawn shape and redraws cleanly */
function runAISnap() {
  if (strokePoints.length < 3) { showToast('Draw something first!'); return; }
  const xs = strokePoints.map(p=>p[0]);
  const ys = strokePoints.map(p=>p[1]);
  const minX=Math.min(...xs), maxX=Math.max(...xs);
  const minY=Math.min(...ys), maxY=Math.max(...ys);
  const w=maxX-minX, h=maxY-minY;
  const cx=(minX+maxX)/2, cy=(minY+maxY)/2;

  // Calculate circularity
  const perimeter = strokePoints.reduce((acc,p,i,arr)=>{
    if (i===0) return 0;
    const dx=p[0]-arr[i-1][0], dy=p[1]-arr[i-1][1];
    return acc+Math.sqrt(dx*dx+dy*dy);
  }, 0);
  const area = w*h;
  const circularity = (4*Math.PI*area) / (perimeter*perimeter + 0.001);

  // Aspect ratio
  const ar = w / (h + 0.001);

  // Detect start/end closeness (closed shape?)
  const first=strokePoints[0], last=strokePoints[strokePoints.length-1];
  const closenessDist = Math.sqrt((first[0]-last[0])**2+(first[1]-last[1])**2);
  const isClosed = closenessDist < Math.max(w,h)*0.3;

  let detected = 'freehand';
  if (circularity > 0.5 && isClosed) detected = 'circle';
  else if (isClosed && ar > 0.6 && ar < 1.7) detected = 'rectangle';
  else if (isClosed && ar > 1.7) detected = 'rectangle';
  else if (isClosed && ar < 0.6) detected = 'rectangle';
  else if (!isClosed && strokePoints.length > 2) detected = 'line';

  // Check triangle (3-corner shape)
  if (isClosed && circularity < 0.3 && strokePoints.length > 5) {
    detected = 'triangle';
  }

  pushUndo();
  // Erase last stroke area
  ctxDraw.clearRect(minX-5, minY-5, w+10, h+10);

  const prevTool = CURRENT_TOOL;
  ctxDraw.save();
  ctxDraw.strokeStyle = getColor(1);
  ctxDraw.lineWidth = BRUSH_SIZE;
  ctxDraw.lineJoin = 'round';
  ctxDraw.beginPath();

  switch(detected) {
    case 'circle':
      ctxDraw.ellipse(cx, cy, w/2, h/2, 0, 0, Math.PI*2);
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
    default:
      ctxDraw.moveTo(strokePoints[0][0], strokePoints[0][1]);
      strokePoints.forEach(p => ctxDraw.lineTo(p[0], p[1]));
  }
  ctxDraw.stroke();
  ctxDraw.restore();
  showToast('🎯 AI Snap: ' + detected);
}

/** AI Doodle Classifier */
function runAIClassify() {
  if (strokePoints.length < 3) { showToast('Draw a doodle first!'); return; }
  const xs = strokePoints.map(p=>p[0]);
  const ys = strokePoints.map(p=>p[1]);
  const minX=Math.min(...xs), maxX=Math.max(...xs);
  const minY=Math.min(...ys), maxY=Math.max(...ys);
  const w=maxX-minX, h=maxY-minY;
  const ar = w/(h+0.001);

  const perimeter = strokePoints.reduce((acc,p,i,arr)=>{
    if(i===0) return 0;
    const dx=p[0]-arr[i-1][0], dy=p[1]-arr[i-1][1];
    return acc+Math.sqrt(dx*dx+dy*dy);
  }, 0);
  const area=w*h;
  const circ=(4*Math.PI*area)/(perimeter*perimeter+0.001);
  const first=strokePoints[0], last=strokePoints[strokePoints.length-1];
  const closed=Math.sqrt((first[0]-last[0])**2+(first[1]-last[1])**2)<Math.max(w,h)*0.35;

  let classes = [];
  if (circ > 0.6) classes.push({ label:'Circle / Moon 🌑', conf: circ });
  if (ar > 1.5 && !closed) classes.push({ label:'Horizontal Line ➖', conf: 0.8 });
  if (ar < 0.5 && !closed) classes.push({ label:'Vertical Line |', conf: 0.8 });
  if (closed && circ < 0.3) classes.push({ label:'Triangle △', conf: 0.7 });
  if (closed && circ > 0.3 && ar > 0.7 && ar < 1.4) classes.push({ label:'Rectangle / Square □', conf: 0.75 });
  if (strokePoints.length > 50 && !closed) classes.push({ label:'Zigzag / Lightning ⚡', conf: 0.6 });
  if (closed && strokePoints.length > 80) classes.push({ label:'Complex Shape / Doodle 🎨', conf: 0.5 });
  if (classes.length === 0) classes.push({ label:'Unknown Shape ❓', conf: 0.4 });

  classes.sort((a,b)=>b.conf-a.conf);
  const best = classes[0];
  const el = document.getElementById('ai-result');
  document.getElementById('ai-result-text').textContent = `🤖 AI thinks: ${best.label} (${Math.round(best.conf*100)}%)`;
  el.style.display = 'flex';
  showToast('🔍 Classified: ' + best.label);
}

/** AI Coloring Book — convert drawing to black outlines on white */
function runColoringBook() {
  pushUndo();
  const imgData = ctxDraw.getImageData(0,0,canvasW,canvasH);
  const d = imgData.data;
  const src = new Uint8ClampedArray(d);
  const W = canvasW;

  // Edge detection (Sobel approximation)
  for (let y=1;y<canvasH-1;y++) for (let x=1;x<W-1;x++) {
    const gx = (
      -src[((y-1)*W+(x-1))*4] - 2*src[(y*W+(x-1))*4] - src[((y+1)*W+(x-1))*4]
      +src[((y-1)*W+(x+1))*4] + 2*src[(y*W+(x+1))*4] + src[((y+1)*W+(x+1))*4]
    );
    const gy = (
      -src[((y-1)*W+(x-1))*4] - 2*src[((y-1)*W+x)*4] - src[((y-1)*W+(x+1))*4]
      +src[((y+1)*W+(x-1))*4] + 2*src[((y+1)*W+x)*4] + src[((y+1)*W+(x+1))*4]
    );
    const mag = Math.min(255, Math.sqrt(gx*gx+gy*gy));
    const i4=(y*W+x)*4;
    const edge = mag > 30 ? 0 : 255;
    d[i4]=d[i4+1]=d[i4+2]=edge;
    d[i4+3]=255;
  }
  ctxDraw.putImageData(imgData,0,0);
  BACKGROUND='white'; renderBackground();
  showToast('📖 Coloring Book mode applied!');
}

/** AI Inpainting — fill selected area with surrounding color average */
function runInpaint() {
  if (lassoPoints.length < 3) { showToast('Use Lasso tool to select area first'); return; }
  pushUndo();
  showToast('🪄 Inpainting... (smooth fill applied)');
  // Simple: gather edge pixels of lasso, average color, fill region
  const imgData = ctxDraw.getImageData(0,0,canvasW,canvasH);
  const d = imgData.data;
  let rSum=0,gSum=0,bSum=0,cnt=0;
  lassoPoints.forEach(p=>{
    const i4=(Math.round(p[1])*canvasW+Math.round(p[0]))*4;
    rSum+=d[i4]; gSum+=d[i4+1]; bSum+=d[i4+2]; cnt++;
  });
  const ar=Math.round(rSum/cnt), ag=Math.round(gSum/cnt), ab=Math.round(bSum/cnt);

  // Fill bounding box of lasso with average color
  const xs=lassoPoints.map(p=>p[0]), ys=lassoPoints.map(p=>p[1]);
  const minX=Math.max(0,Math.round(Math.min(...xs)));
  const minY=Math.max(0,Math.round(Math.min(...ys)));
  const maxX=Math.min(canvasW-1,Math.round(Math.max(...xs)));
  const maxY=Math.min(canvasH-1,Math.round(Math.max(...ys)));

  for (let y=minY;y<=maxY;y++) for (let x=minX;x<=maxX;x++) {
    const i4=(y*canvasW+x)*4;
    // noise blend
    d[i4]=Math.min(255,ar+Math.round((Math.random()-0.5)*20));
    d[i4+1]=Math.min(255,ag+Math.round((Math.random()-0.5)*20));
    d[i4+2]=Math.min(255,ab+Math.round((Math.random()-0.5)*20));
    d[i4+3]=255;
  }
  ctxDraw.putImageData(imgData,0,0);
}

/** AI Style Transfer — applies artistic convolution filters */
function runStyleTransfer() {
  pushUndo();
  showToast('🖼️ Applying style filter...');
  // Apply a stylized look: posterize + warm color shift
  const imgData = ctxDraw.getImageData(0,0,canvasW,canvasH);
  const d = imgData.data;
  const levels = 4;
  for (let i=0;i<d.length;i+=4) {
    d[i]  = Math.round(d[i]/(256/levels))*(256/levels);
    d[i+1]= Math.round(d[i+1]/(256/levels))*(256/levels);
    d[i+2]= Math.round(d[i+2]/(256/levels))*(256/levels);
    // Warm tint
    d[i] = Math.min(255, d[i]+15);
    d[i+2]= Math.max(0, d[i+2]-10);
  }
  ctxDraw.putImageData(imgData,0,0);
  showToast('🖼️ Style transfer complete!');
}

// ═══════════════════════════════════════════════════════════
// UNDO / REDO
// ═══════════════════════════════════════════════════════════
function pushUndo() {
  if (undoStack.length >= UNDO_MAX) undoStack.shift();
  undoStack.push(canvasDraw.toDataURL());
  redoStack = [];
}

function undo() {
  if (undoStack.length === 0) { showToast('Nothing to undo'); return; }
  redoStack.push(canvasDraw.toDataURL());
  const img = new Image();
  img.src = undoStack.pop();
  img.onload = () => {
    ctxDraw.clearRect(0,0,canvasW,canvasH);
    ctxDraw.drawImage(img,0,0);
  };
  showToast('↩️ Undo');
}

function redo() {
  if (redoStack.length === 0) { showToast('Nothing to redo'); return; }
  undoStack.push(canvasDraw.toDataURL());
  const img = new Image();
  img.src = redoStack.pop();
  img.onload = () => {
    ctxDraw.clearRect(0,0,canvasW,canvasH);
    ctxDraw.drawImage(img,0,0);
  };
  showToast('↪️ Redo');
}

function clearCanvas() {
  pushUndo();
  ctxDraw.clearRect(0,0,canvasW,canvasH);
  showToast('🗑️ Canvas cleared');
}

// ═══════════════════════════════════════════════════════════
// SAVE
// ═══════════════════════════════════════════════════════════
function saveImage() {
  const merged = document.createElement('canvas');
  merged.width = canvasW;
  merged.height = canvasH;
  const mc = merged.getContext('2d');
  mc.drawImage(canvasBg, 0, 0);
  mc.drawImage(canvasDraw, 0, 0);

  merged.toBlob(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ai-air-draw-${Date.now()}.png`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('💾 Saved!');
  }, 'image/png');
}

// ═══════════════════════════════════════════════════════════
// CAMERA & HAND TRACKING
// ═══════════════════════════════════════════════════════════
async function startCamera() {
  setTrackerStatus('Starting camera...', '📷');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
    });
    const video = document.getElementById('webcam');
    video.srcObject = stream;
    video.style.display = 'block';
    cameraActive = true;
    document.getElementById('btn-cam-toggle').textContent = '📷 Camera ON';
    setTrackerStatus('Camera ready, loading AI...', '🤖');
    await initHandLandmarker();
    requestAnimationFrame(trackLoop);
  } catch(err) {
    console.error('Camera error:', err);
    setTrackerStatus('Camera error: ' + err.message, '❌');
    showToast('⚠️ Camera failed — switching to mouse mode');
    handMode = false;
    document.getElementById('btn-mouse-mode').classList.add('active');
    document.getElementById('btn-hand-mode').classList.remove('active');
  }
}

async function initHandLandmarker() {
  try {
    const vision = await window.FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
    );
    handLandmarker = await window.HandLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
        delegate: 'GPU'
      },
      runningMode: 'VIDEO',
      numHands: 2
    });
    setTrackerStatus('Hand tracking ready ✋', '✅');
    showToast('✋ Hand tracking active! Pinch to draw.');
  } catch(err) {
    console.error('MediaPipe init error:', err);
    setTrackerStatus('AI init failed — mouse mode', '⚠️');
    handMode = false;
  }
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
    document.getElementById('btn-cam-toggle').textContent = '📷 Camera OFF';
    setTrackerStatus('Camera off', '📷');
  } else {
    handMode = true;
    startCamera();
  }
}

// ═══════════════════════════════════════════════════════════
// HAND TRACKING LOOP
// ═══════════════════════════════════════════════════════════
function trackLoop() {
  if (!cameraActive) return;
  requestAnimationFrame(trackLoop);

  const video = document.getElementById('webcam');
  if (!handLandmarker || video.readyState < 2) return;

  const now = performance.now();
  if (video.currentTime === lastVideoTime) return;
  lastVideoTime = video.currentTime;

  let results;
  try {
    results = handLandmarker.detectForVideo(video, now);
  } catch(e) { return; }

  ctxOverlay.clearRect(0,0,canvasW,canvasH);

  if (!results.landmarks || results.landmarks.length === 0) {
    pinchWasDown = false;
    setTrackerStatus('No hand detected', '👁️');
    return;
  }

  const lm = results.landmarks[0];
  processHandGesture(lm);

  // Draw skeleton
  drawHandSkeleton(ctxOverlay, lm);

  // Second hand = holographic palette
  if (results.landmarks.length > 1) {
    drawHoloPalette(ctxOverlay, results.landmarks[1]);
  }
}

function lmToCanvas(lm, idx) {
  // Mirror X (front camera mirroring)
  return {
    x: (1 - lm[idx].x) * canvasW,
    y: lm[idx].y * canvasH,
    z: lm[idx].z
  };
}

function processHandGesture(lm) {
  const tip4 = lmToCanvas(lm, 4);   // thumb tip
  const tip8 = lmToCanvas(lm, 8);   // index tip
  const tip12 = lmToCanvas(lm, 12); // middle tip
  const tip16 = lmToCanvas(lm, 16); // ring tip
  const tip20 = lmToCanvas(lm, 20); // pinky tip
  const pip8 = lmToCanvas(lm, 6);   // index pip
  const pip12 = lmToCanvas(lm, 10);
  const pip16 = lmToCanvas(lm, 14);
  const pip20 = lmToCanvas(lm, 18);
  const mcp4 = lmToCanvas(lm, 2);   // thumb mcp

  // Finger up states
  const idx_up = tip8.y < pip8.y;
  const mid_up = tip12.y < pip12.y;
  const ring_up = tip16.y < pip16.y;
  const pinky_up = tip20.y < pip20.y;
  const thumb_up = tip4.y < mcp4.y - 20;

  // Pinch distance (normalized)
  const pinchDist = Math.sqrt(
    (lm[4].x - lm[8].x)**2 + (lm[4].y - lm[8].y)**2
  );

  const cursorX = (tip8.x + tip4.x) / 2;
  const cursorY = (tip8.y + tip4.y) / 2;

  // Gesture detection
  let gesture = 'hover';
  if (idx_up && mid_up && !ring_up && !pinky_up) gesture = 'peace';    // ✌️ → eraser
  else if (!idx_up && !mid_up && !ring_up && !pinky_up && thumb_up) gesture = 'thumbsup'; // 👍 → save
  else if (ring_up && !idx_up && !mid_up) gesture = 'ring';           // ring up → fill
  else if (pinchDist < PINCH_THRESH) gesture = 'pinch';               // pinch → draw

  drawCursorDot(cursorX, cursorY);

  // Apply gesture action
  switch(gesture) {
    case 'pinch': {
      setTrackerStatus('Drawing ✏️', '🤏');
      // 3D pressure from Z
      const pressure = Math.max(0.3, Math.min(2.0, 1 + tip8.z * -5));
      const effectiveSize = Math.round(BRUSH_SIZE * pressure);
      if (!pinchWasDown) {
        onPointerDown(cursorX, cursorY, 0);
        pinchWasDown = true;
      } else {
        onPointerMove(cursorX, cursorY);
      }
      break;
    }
    case 'peace':
      if (pinchWasDown) { onPointerUp(); pinchWasDown = false; }
      const prevTool2 = CURRENT_TOOL;
      selectTool('eraser');
      setTrackerStatus('Eraser ✌️', '✌️');
      break;
    case 'thumbsup':
      if (pinchWasDown) { onPointerUp(); pinchWasDown = false; }
      saveImage();
      setTrackerStatus('Saved! 👍', '💾');
      break;
    case 'ring':
      if (pinchWasDown) { onPointerUp(); pinchWasDown = false; }
      floodFill(cursorX, cursorY);
      setTrackerStatus('Fill 🪣', '🪣');
      break;
    case 'hover': {
      if (pinchWasDown) { onPointerUp(); pinchWasDown = false; }
      setTrackerStatus('Hovering 🖐', '🖐');
      // Dwell on UI buttons
      checkDwell(cursorX, cursorY);
      break;
    }
  }
}

function drawHandSkeleton(ctx, lm) {
  const connections = [
    [0,1],[1,2],[2,3],[3,4],
    [0,5],[5,6],[6,7],[7,8],
    [0,9],[9,10],[10,11],[11,12],
    [0,13],[13,14],[14,15],[15,16],
    [0,17],[17,18],[18,19],[19,20],
    [5,9],[9,13],[13,17]
  ];

  ctx.strokeStyle = 'rgba(0,212,255,0.6)';
  ctx.lineWidth = 2;
  connections.forEach(([a,b]) => {
    const pa = lmToCanvas(lm,a), pb = lmToCanvas(lm,b);
    ctx.beginPath(); ctx.moveTo(pa.x,pa.y); ctx.lineTo(pb.x,pb.y); ctx.stroke();
  });

  // Joints
  ctx.fillStyle = 'rgba(0,212,255,0.9)';
  lm.forEach((_,i) => {
    const p = lmToCanvas(lm,i);
    ctx.beginPath(); ctx.arc(p.x,p.y,3,0,Math.PI*2); ctx.fill();
  });
}

function drawHoloPalette(ctx, lm) {
  const palm = lmToCanvas(lm, 0);
  const r = 70;
  PALETTE.slice(0,8).forEach((hex,i) => {
    const ang = (i/8)*Math.PI*2 - Math.PI/2;
    const px = palm.x + r*Math.cos(ang);
    const py = palm.y + r*Math.sin(ang);
    ctx.beginPath();
    ctx.arc(px, py, 14, 0, Math.PI*2);
    ctx.fillStyle = hex;
    ctx.fill();
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 2;
    ctx.stroke();
  });
}

// Dwell-click for hand tracking UI interaction
function checkDwell(cursorX, cursorY) {
  // Check if cursor is over the toolbar area
  const row1 = document.getElementById('toolbar-row1');
  const row2 = document.getElementById('toolbar-row2');
  const rect1 = row1.getBoundingClientRect();
  const rect2 = row2.getBoundingClientRect();

  if (cursorY < rect1.bottom + rect2.height) {
    // Over toolbar — find closest button
    const buttons = document.querySelectorAll('.tb-btn, .tab-btn');
    let best = null, bestDist = 60;
    buttons.forEach(btn => {
      const r = btn.getBoundingClientRect();
      const bx = r.left + r.width/2;
      const by = r.top + r.height/2;
      const dist = Math.sqrt((cursorX-bx)**2+(cursorY-by)**2);
      if (dist < bestDist) { bestDist=dist; best=btn; }
    });

    if (best) {
      if (dwellTarget !== best) {
        dwellTarget = best;
        dwellStart = performance.now();
        showDwellRing(cursorX, cursorY);
      } else {
        const elapsed = performance.now() - dwellStart;
        const progress = Math.min(elapsed / DWELL_MS, 1);
        updateDwellRing(cursorX, cursorY, progress);
        if (progress >= 1) {
          best.click();
          dwellTarget = null;
          hideDwellRing();
          showToast('👆 Dwell activated: ' + (best.title || best.textContent));
        }
      }
      return;
    }
  }
  dwellTarget = null;
  hideDwellRing();
}

function showDwellRing(x, y) {
  const svg = document.getElementById('dwell-svg');
  svg.style.display = 'block';
  svg.style.left = (x-30)+'px';
  svg.style.top = (y-30)+'px';
}

function updateDwellRing(x, y, progress) {
  const svg = document.getElementById('dwell-svg');
  svg.style.left = (x-30)+'px';
  svg.style.top = (y-30)+'px';
  const arc = document.getElementById('dwell-arc');
  const circumference = 163.4;
  arc.style.strokeDashoffset = circumference * (1-progress);
}

function hideDwellRing() {
  document.getElementById('dwell-svg').style.display = 'none';
}

function drawCursorDot(x, y) {
  const dot = document.getElementById('cursor-dot');
  dot.style.left = x+'px';
  dot.style.top = y+'px';
  dot.style.display = 'block';
}

// ═══════════════════════════════════════════════════════════
// KEYBOARD SHORTCUTS
// ═══════════════════════════════════════════════════════════
function bindKeyboard() {
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') return;
    if (e.ctrlKey || e.metaKey) {
      switch(e.key.toLowerCase()) {
        case 'z': e.preventDefault(); undo(); break;
        case 'y': e.preventDefault(); redo(); break;
        case 's': e.preventDefault(); saveImage(); break;
      }
      return;
    }
    switch(e.key.toLowerCase()) {
      case 'p': selectTool('pen'); break;
      case 'e': selectTool('eraser'); break;
      case 'f': selectTool('fill'); break;
      case 'i': selectTool('eyedropper'); break;
      case 't': selectTool('text'); break;
      case 's': selectTool('select-rect'); break;
      case 'l': selectTool('lasso'); break;
      case 'm': selectTool('magnifier'); break;
      case 'c': if (e.shiftKey) clearCanvas(); break;
      case '[': BRUSH_SIZE=Math.max(1,BRUSH_SIZE-2); document.getElementById('size-slider').value=BRUSH_SIZE; document.getElementById('size-val').textContent=BRUSH_SIZE; break;
      case ']': BRUSH_SIZE=Math.min(80,BRUSH_SIZE+2); document.getElementById('size-slider').value=BRUSH_SIZE; document.getElementById('size-val').textContent=BRUSH_SIZE; break;
    }
  });
}

// ═══════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════
let toastTimer = null;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('visible');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('visible'), 2500);
}

function setTrackerStatus(text, icon) {
  document.getElementById('tracker-text').textContent = text;
  document.getElementById('tracker-icon').textContent = icon;
}
