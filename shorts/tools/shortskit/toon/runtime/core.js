/* TOON core (shorts 2.3): deterministic 2D cartoon renderer. window.__seek(t) draws frame t. No clocks, no randomness
   without a seed: the same story always gives the same pixels. Units: px of the output canvas (W x H). */
'use strict';
const TOON = (window.TOON = window.TOON || {});
TOON.SETS = {}; TOON.PROPS = {}; TOON.SCHEMES = {}; TOON.CHARS = {};

// ---------------------------------------------------------------- math
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, k) => a + (b - a) * k;
const E = {
  lin: x => x,
  io: x => 0.5 - 0.5 * Math.cos(Math.PI * clamp(x)),              // ease in-out sine (camera)
  out: x => 1 - Math.pow(1 - clamp(x), 3),                         // ease-out cubic
  outq: x => { x = clamp(x); return 1 - Math.pow(1 - x, 5); },     // ~ cubic-bezier(.16,1,.3,1)
  back: x => { x = clamp(x); const c = 1.70158; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); },
  spring: (x, d = 16) => { x = clamp(x); return 1 - Math.exp(-d * x * 0.42) * Math.cos(x * 9.5); },
};
function rng(seed) { let s = (seed | 0) || 1; return () => { s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hash(str) { let h = 2166136261; for (const c of String(str)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
function vnoise(seed, x) { const i = Math.floor(x), f = x - i, a = rng(seed + i * 7919)(), b = rng(seed + (i + 1) * 7919)();
  const u = f * f * (3 - 2 * f); return a + (b - a) * u; }      // smooth 0..1 value noise
const wave = (t, period, ph = 0) => Math.sin((t / period + ph) * Math.PI * 2);

// ---------------------------------------------------------------- colour
function hex2rgb(h) { h = String(h).replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join('');
  const n = parseInt(h.slice(0, 6), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function rgb2hex(r) { return '#' + r.map(v => Math.round(clamp(v, 0, 255)).toString(16).padStart(2, '0')).join(''); }
function mix(a, b, k) { const A = hex2rgb(a), B = hex2rgb(b); return rgb2hex(A.map((v, i) => lerp(v, B[i], k))); }
function shade(c, k) { return k < 0 ? mix(c, '#0b0d14', -k) : mix(c, '#ffffff', k); }   // k -1..1
function rgba(c, a) { const [r, g, b] = hex2rgb(c); return `rgba(${r},${g},${b},${a})`; }

// ---------------------------------------------------------------- palettes (time of day / mood)
TOON.PAL = {   // day/farm and night/blackout follow the channel palette of reference/animation.md
  day:      {sky: ['#ADC0C2', '#DFDEC6'], far: '#9DB0A6', mid: '#6F8458', ground: '#788856', grass: '#505D36', olive: '#3B3D24', tint: null, light: '#FFF1D2', amb: 0, haze: '#DFDEC6'},
  dusk:     {sky: ['#2C3A5A', '#E08A5A'], far: '#4B4A63', mid: '#3F4A4F', ground: '#4A4A3A', grass: '#3B4030', olive: '#2E2E22', tint: ['#FF9B5A', 0.10], light: '#FFB070', amb: 0.16, haze: '#C9826A'},
  night:    {sky: ['#0B0F1A', '#1C2942'], far: '#16203A', mid: '#121A2D', ground: '#1A2230', grass: '#162030', olive: '#10161F', tint: ['#1B2A55', 0.26], light: '#FFB84D', amb: 0.46, haze: '#1C2942'},
  blackout: {sky: ['#05070D', '#121A2B'], far: '#0C121F', mid: '#0A0F1A', ground: '#0F1520', grass: '#0D131C', olive: '#0A0E15', tint: ['#0B1430', 0.40], light: '#FFB84D', amb: 0.64, haze: '#121A2B'},
  winter:   {sky: ['#9AA9B8', '#DDE3E8'], far: '#A3ADB5', mid: '#7F8A90', ground: '#E9EEF2', grass: '#C9D3DA', olive: '#5E6A70', tint: ['#BCD0E0', 0.08], light: '#F4F8FF', amb: 0.04, haze: '#DDE3E8'},
  toxic:    {sky: ['#1F2A22', '#5F7A52'], far: '#2C3A2E', mid: '#253228', ground: '#3A4632', grass: '#2C3826', olive: '#1E261A', tint: ['#7FA05A', 0.14], light: '#D9F27A', amb: 0.26, haze: '#5F7A52'},
  paper:    {sky: ['#F6F2E7', '#EFE7D4'], far: '#D9CFB8', mid: '#C9BFA6', ground: '#E8DFC8', grass: '#B9AE90', olive: '#8C8166', tint: null, light: '#FFFFFF', amb: 0, haze: '#F6F2E7'},
  kids:     {sky: ['#7FD3F7', '#D8F3FF'], far: '#9EDB8B', mid: '#6CC36A', ground: '#7CCB5B', grass: '#4FA845', olive: '#3D7F37', tint: null, light: '#FFFFFF', amb: 0, haze: '#D8F3FF'},
};
TOON.UI = {danger: '#E53935', ok: '#3DDC84', warn: '#F5C518', blue: '#3B8EEA', ink: '#141821', paper: '#F3EAD7', white: '#FFFFFF'};
function pal(sc) { const p = TOON.PAL[(sc.set && sc.set.time) || 'day'] || TOON.PAL.day; return p; }

// ---------------------------------------------------------------- drawing helpers
function rr(ctx, x, y, w, h, r) { r = Math.min(r, w / 2, h / 2); ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function poly(ctx, pts, close = true) { ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); if (close) ctx.closePath(); }
function ell(ctx, x, y, rx, ry, rot = 0) { ctx.beginPath(); ctx.ellipse(x, y, Math.max(0.1, rx), Math.max(0.1, ry), rot, 0, Math.PI * 2); }
function fillWith(ctx, color, outline) { ctx.fillStyle = color; ctx.fill(); if (outline) { ctx.lineWidth = outline.w; ctx.strokeStyle = outline.c; ctx.lineJoin = 'round'; ctx.stroke(); } }
function vgrad(ctx, y0, y1, stops) { const g = ctx.createLinearGradient(0, y0, 0, y1); stops.forEach(([o, c]) => g.addColorStop(o, c)); return g; }
function rgrad(ctx, x, y, r0, r1, stops) { const g = ctx.createRadialGradient(x, y, r0, x, y, r1); stops.forEach(([o, c]) => g.addColorStop(o, c)); return g; }
function glow(ctx, x, y, r, color, a = 0.5) { ctx.save(); ctx.globalCompositeOperation = 'lighter';
  ctx.fillStyle = rgrad(ctx, x, y, 0, r, [[0, rgba(color, a)], [0.4, rgba(color, a * 0.35)], [1, rgba(color, 0)]]); ctx.fillRect(x - r, y - r, 2 * r, 2 * r); ctx.restore(); }
function shadowBlob(ctx, x, y, w, a = 0.28) { ctx.save(); ctx.fillStyle = rgrad(ctx, 0, 0, 0, 1, [[0, `rgba(0,0,0,${a})`], [1, 'rgba(0,0,0,0)']]);
  ctx.translate(x, y); ctx.scale(w, w * 0.16); ctx.beginPath(); ctx.arc(0, 0, 1, 0, Math.PI * 2); ctx.fill(); ctx.restore(); }
function limb(ctx, x0, y0, x1, y1, w, color, outline) { ctx.lineCap = 'round'; if (outline) { ctx.strokeStyle = outline.c; ctx.lineWidth = w + outline.w * 2;
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); } ctx.strokeStyle = color; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); }
TOON.h = {clamp, lerp, E, rng, hash, vnoise, wave, mix, shade, rgba, hex2rgb, rr, poly, ell, fillWith, vgrad, rgrad, glow, shadowBlob, limb, pal};

// ---------------------------------------------------------------- text
TOON.font = (w, size, fam = 'Montserrat') => `${w} ${Math.round(size)}px "${fam}"`;
function fitText(ctx, text, maxW, size, weight = '800', fam = 'Montserrat') { let s = size; ctx.font = TOON.font(weight, s, fam);
  while (s > 18 && ctx.measureText(text).width > maxW) { s -= 2; ctx.font = TOON.font(weight, s, fam); } return s; }
function textBox(ctx, text, x, y, o = {}) {           // centred text with outline + soft shadow; returns width
  const size = o.size || 64, fam = o.fam || 'Montserrat', weight = o.weight || '800';
  ctx.save(); ctx.font = TOON.font(weight, size, fam); ctx.textAlign = o.align || 'center'; ctx.textBaseline = 'middle';
  if (o.shadow !== false) { ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = size * 0.22; ctx.shadowOffsetY = size * 0.05; }
  if (o.stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = o.stroke; ctx.strokeStyle = o.strokeColor || '#0b0d12'; ctx.strokeText(text, x, y); ctx.shadowColor = 'transparent'; }
  ctx.fillStyle = o.color || '#fff'; ctx.fillText(text, x, y); const w = ctx.measureText(text).width; ctx.restore(); return w; }
TOON.fitText = fitText; TOON.textBox = textBox;

// ---------------------------------------------------------------- camera
// world = screen at zoom 1. A layer at depth d (0 sky, 1 actors, >1 foreground) moves d times the camera offset.
function camAt(sc, lt, W, H) {
  const dur = Math.max(0.01, sc.t1 - sc.t0), k = E.io(lt / dur);
  const sh = sc._shot ? {x: sc._shot.x * W, y: sc._shot.y * H, z: sc._shot.z} : {};
  const c = Object.assign({x: W / 2, y: H / 2, z: 1, rot: 0}, sh, sc.cam0 || {});
  const mv = sc.camera || 'drift', amt = sc.cam_amount == null ? 1 : sc.cam_amount;
  const z0 = c.z;
  if (mv === 'push') c.z = z0 * (1 + 0.06 * amt * k);
  else if (mv === 'pull') c.z = z0 * (1 + 0.06 * amt * (1 - k));
  else if (mv === 'pan_left') c.x += W * 0.05 * amt * (0.5 - k) / z0;
  else if (mv === 'pan_right') c.x -= W * 0.05 * amt * (0.5 - k) / z0;
  else if (mv === 'tilt_up') c.y += H * 0.04 * amt * (0.5 - k) / z0;
  else if (mv === 'tilt_down') c.y -= H * 0.04 * amt * (0.5 - k) / z0;
  else if (mv === 'crash') c.z = z0 * (1 + 0.16 * amt * E.outq(lt / 0.45));
  if (mv !== 'static') {                               // the camera is never dead: slow breathing drift
    const s = hash(sc.id || 'sc');
    c.x += (vnoise(s, lt * 0.35) - 0.5) * W * 0.006; c.y += (vnoise(s + 9, lt * 0.3) - 0.5) * H * 0.004;
    if (mv === 'drift') c.z = z0 * (1 + 0.025 * amt * k);
  }
  if (sc.shake) { const a = sc.shake * Math.exp(-lt * 3); c.x += Math.sin(lt * 61) * W * 0.012 * a; c.y += Math.cos(lt * 53) * H * 0.008 * a; }
  return c;
}
function withDepth(ctx, cam, d, W, H, fn) {
  ctx.save(); const z = 1 + (cam.z - 1) * d;
  ctx.translate(W / 2, H / 2); if (cam.rot) ctx.rotate(cam.rot); ctx.scale(z, z);
  ctx.translate(-(W / 2 + (cam.x - W / 2) * d), -(H / 2 + (cam.y - H / 2) * d)); fn(); ctx.restore();
}
TOON.camAt = camAt; TOON.withDepth = withDepth;
function toScreen(cam, d, W, H, x, y) { const z = 1 + (cam.z - 1) * d; return [W / 2 + (x - (W / 2 + (cam.x - W / 2) * d)) * z, H / 2 + (y - (H / 2 + (cam.y - H / 2) * d)) * z]; }
TOON.toScreen = toScreen;

// ---------------------------------------------------------------- scene
function sceneAt(t) { const S = TOON.story.scenes; let i = 0; while (i < S.length - 1 && t >= S[i + 1].t0) i++; return i; }

function drawScene(ctx, sc, lt, W, H) {
  const P = Object.assign({}, pal(sc)), set = TOON.SETS[(sc.set && sc.set.id) || 'plain'] || TOON.SETS.plain;
  const portrait = H >= W, U = (portrait ? 0.30 : 0.50) * H;
  const ground = ((sc.set && sc.set.ground) || (portrait ? (set.ground || 0.8) : (set.ground_l || 0.86))) * H;
  if (sc._shot === undefined) sc._shot = sc.shot && TOON.shotCam && !(sc.scheme && sc.scheme.full !== false) ? TOON.shotCam(sc, W, H, ground) : null;
  const cam = camAt(sc, lt, W, H); sc._cam = cam; TOON.LIGHTS = [];
  const env = {ctx, W, H, P, sc, lt, cam, t: sc.t0 + lt, style: TOON.story.style || {}, U, portrait,
    L: (d, fn) => withDepth(ctx, cam, d, W, H, fn), ground};
  ctx.save(); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  if (sc.scheme && sc.scheme.full !== false && TOON.SCHEMES[sc.scheme.type]) { TOON.SCHEMES[sc.scheme.type](env, sc.scheme, lt, sc.t1 - sc.t0); ctx.restore(); return cam; }
  set.draw(env, sc.set || {});
  const items = [];
  const gz = env.ground / H, zOf = o => (o.at && o.at[1] != null ? o.at[1] : gz);
  (sc.props || []).forEach((p, i) => items.push({z: p.z == null ? zOf(p) : p.z, d: p.depth || 1, fn: () => TOON.drawProp(env, p, i)}));
  (sc.actors || []).forEach((a, i) => items.push({z: a.z == null ? zOf(a) + 0.001 : a.z, d: a.depth || 1, fn: () => TOON.drawActor(env, a, i)}));
  items.sort((a, b) => a.z - b.z).forEach(it => env.L(it.d, it.fn));
  if (set.front) set.front(env, sc.set || {});
  TOON.fxWorld && TOON.fxWorld(env, sc.fx || []);
  if (P.tint && !(sc.set && sc.set.no_tint)) { ctx.save(); ctx.globalCompositeOperation = 'multiply'; ctx.fillStyle = rgba(P.tint[0], 1);
    ctx.globalAlpha = P.tint[1]; ctx.fillRect(0, 0, W, H); ctx.restore(); }
  TOON.lights && TOON.lights(env);
  if (sc.scheme && sc.scheme.full === false && TOON.SCHEMES[sc.scheme.type]) TOON.SCHEMES[sc.scheme.type](env, sc.scheme, lt, sc.t1 - sc.t0);
  ctx.restore(); return cam;
}
TOON.drawScene = drawScene;

// ---------------------------------------------------------------- transitions
const BUF = {};
function buf(name, W, H) { if (!BUF[name]) { const c = document.createElement('canvas'); c.width = W; c.height = H; BUF[name] = c; } return BUF[name]; }
function composite(ctx, t, W, H) {
  const S = TOON.story.scenes, i = sceneAt(t), sc = S[i];
  const nx = S[i + 1], tr = nx && nx.transition && nx.transition !== 'cut' ? nx.transition : null;
  const td = nx ? (nx.tr_dur || ({fade: 0.5, iris: 0.45, slide: 0.35, whip: 0.3, flash: 0.3, zoom: 0.35}[tr] || 0.35)) : 0;
  const prevTr = sc.transition && sc.transition !== 'cut' && i > 0 ? sc.transition : null;
  const ptd = sc.tr_dur || ({fade: 0.5, iris: 0.45, slide: 0.35, whip: 0.3, flash: 0.3, zoom: 0.35}[prevTr] || 0.35);
  // incoming half of a transition: the previous scene keeps playing for td/2 into this one
  if (prevTr && t < sc.t0 + ptd / 2) { blend(ctx, S[i - 1], sc, prevTr, 0.5 + (t - sc.t0) / ptd, t, W, H); return; }
  if (tr && t > nx.t0 - td / 2) { blend(ctx, sc, nx, tr, 0.5 - (nx.t0 - t) / td, t, W, H); return; }
  drawScene(ctx, sc, t - sc.t0, W, H);
}
function blend(ctx, a, b, kind, k, t, W, H) {
  k = clamp(k); const A = buf('A', W, H), B = buf('B', W, H), ca = A.getContext('2d', {willReadFrequently: true}), cb = B.getContext('2d', {willReadFrequently: true});
  drawScene(ca, a, t - a.t0, W, H); drawScene(cb, b, Math.max(0, t - b.t0), W, H);
  ctx.save();
  if (kind === 'fade') { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = k < 0.5 ? 1 - k * 2 : (k - 0.5) * 2; ctx.drawImage(k < 0.5 ? A : B, 0, 0); }
  else if (kind === 'flash') { ctx.drawImage(k < 0.5 ? A : B, 0, 0); ctx.fillStyle = '#fff'; ctx.globalAlpha = 1 - Math.abs(k - 0.5) * 2; ctx.fillRect(0, 0, W, H); }
  else if (kind === 'iris') { ctx.drawImage(A, 0, 0); const r = E.io(k) * Math.hypot(W, H) * 0.6; const f = b.focus_xy || [W / 2, H * 0.45];
    ctx.beginPath(); ctx.arc(f[0], f[1], Math.max(1, r), 0, Math.PI * 2); ctx.clip(); ctx.drawImage(B, 0, 0); }
  else if (kind === 'slide' || kind === 'whip') { const e = kind === 'whip' ? E.io(k) : E.out(k); const dx = -e * W;
    if (kind === 'whip') { for (let j = 0; j < 5; j++) { ctx.globalAlpha = 0.32; ctx.drawImage(A, dx - j * 22, 0); ctx.drawImage(B, dx + W - j * 22, 0); } ctx.globalAlpha = 1; }
    ctx.drawImage(A, dx, 0); ctx.drawImage(B, dx + W, 0); }
  else if (kind === 'zoom') { ctx.drawImage(A, 0, 0); ctx.globalAlpha = E.out(k); const s = 1.12 - 0.12 * E.out(k); ctx.translate(W / 2, H / 2); ctx.scale(s, s); ctx.drawImage(B, -W / 2, -H / 2); }
  else ctx.drawImage(k < 0.5 ? A : B, 0, 0);
  ctx.restore();
  (k < 0.5 ? a : b)._cam = (k < 0.5 ? a : b)._cam;
}

// ---------------------------------------------------------------- soft focus layer
// fn(ctx, env) draws foreground into a half-res buffer; it is blurred there once and scaled onto the frame.
// (ctx.filter = 'blur()' on every shape of a layer costs ~100x more on a CPU canvas.)
const SOFT = {};
function softBuf(k, w, h) { let c = SOFT[k]; if (!c) c = SOFT[k] = document.createElement('canvas'); if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  const x = c.getContext('2d', {willReadFrequently: true}); x.setTransform(1, 0, 0, 1, 0, 0); x.filter = 'none'; x.clearRect(0, 0, w, h); return [c, x]; }
function soft(env, px, fn) {
  const {ctx, W, H} = env, w = Math.ceil(W / 2), h = Math.ceil(H / 2), m = ctx.getTransform();
  const [c, x] = softBuf('a', w, h); x.setTransform(m.a / 2, m.b / 2, m.c / 2, m.d / 2, m.e / 2, m.f / 2);
  const keep = TOON.addLight; TOON.addLight = () => {};
  try { fn(x, Object.assign({}, env, {ctx: x})); } finally { TOON.addLight = keep; }
  const [c2, x2] = softBuf('b', w, h); x2.filter = `blur(${Math.max(0.5, px / 2)}px)`; x2.drawImage(c, 0, 0); x2.filter = 'none';
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(c2, 0, 0, W, H); ctx.restore();
}
TOON.soft = soft;

// ---------------------------------------------------------------- post: grain + vignette
let GRAIN = null;
function grain(ctx, t, W, H, amt) {
  if (!amt) return;
  if (!GRAIN) { GRAIN = []; for (let g = 0; g < 4; g++) { const c = document.createElement('canvas'); c.width = 256; c.height = 256; const x = c.getContext('2d', {willReadFrequently: true});
    const im = x.createImageData(256, 256), r = rng(77 + g); for (let p = 0; p < im.data.length; p += 4) { const v = 128 + (r() - 0.5) * 255; im.data[p] = im.data[p + 1] = im.data[p + 2] = v; im.data[p + 3] = 255; }
    x.putImageData(im, 0, 0); GRAIN.push(c); } }
  const fr = Math.floor(t * 12) % 4, pat = ctx.createPattern(GRAIN[fr], 'repeat');
  ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.globalAlpha = amt; ctx.fillStyle = pat; ctx.fillRect(0, 0, W, H); ctx.restore();
}
function vignette(ctx, W, H, a) { if (!a) return; ctx.save(); ctx.fillStyle = rgrad(ctx, W / 2, H * 0.47, Math.min(W, H) * 0.35, Math.hypot(W, H) * 0.62,
  [[0, 'rgba(0,0,0,0)'], [1, `rgba(0,0,0,${a})`]]); ctx.fillRect(0, 0, W, H); ctx.restore(); }

// ---------------------------------------------------------------- frame
let CANVAS = null, CTX = null;
TOON.init = function (story) {
  TOON.story = story; CANVAS = document.getElementById('c'); CANVAS.width = story.W; CANVAS.height = story.H; CTX = CANVAS.getContext('2d', {willReadFrequently: true});
  story.scenes.forEach((s, i) => { s.id = s.id || 'sc' + i; });
};
window.__seek = function (t) {
  const S = TOON.story, W = S.W, H = S.H, ctx = CTX;
  composite(ctx, t, W, H);
  const i = sceneAt(t), sc = S.scenes[i], lt = t - sc.t0;
  const st = S.style || {};
  vignette(ctx, W, H, st.vignette == null ? 0.38 : st.vignette);
  TOON.fxScreen && TOON.fxScreen(ctx, sc, lt, t, W, H);
  TOON.overlays && TOON.overlays(ctx, sc, lt, t, W, H);
  TOON.captions && TOON.captions(ctx, t, W, H);
  grain(ctx, t, W, H, st.grain == null ? 0.05 : st.grain);
  return true;
};
TOON.frameJPEG = q => CANVAS.toDataURL('image/jpeg', q || 0.93).slice(23);
