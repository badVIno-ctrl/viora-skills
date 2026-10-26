/* TOON ui: icons, HUD overlays (clock pill, counters, paper tape, ribbon, stamp, plates, callouts, titles, bars, timer)
   and karaoke captions. All text is drawn by code with embedded fonts (never inside generated pictures). */
'use strict';
(function () {
const T = window.TOON, {clamp, lerp, E, hash, rng, vnoise, mix, shade, rgba, rr, ell, poly, rgrad} = T.h;
const UI = T.UI, COL = {danger: UI.danger, ok: UI.ok, warn: UI.warn, info: UI.blue, blue: UI.blue, white: '#FFFFFF', red: UI.danger, green: UI.ok, yellow: UI.warn};
const col = c => COL[c] || c || UI.warn;
const MONO = 'JetBrains Mono', SANS = 'Montserrat', BODY = 'Manrope', DISPLAY = 'Unbounded';
T.col = col;

// ------------------------------------------------------------------ icons (line icons, size = box side)
const IC = {
  drop: (c, s) => { c.beginPath(); c.moveTo(0, -s * 0.45); c.bezierCurveTo(s * 0.35, -s * 0.05, s * 0.32, s * 0.42, 0, s * 0.42); c.bezierCurveTo(-s * 0.32, s * 0.42, -s * 0.35, -s * 0.05, 0, -s * 0.45); c.fill(); },
  bolt: (c, s) => { poly(c, [[s * 0.08, -s * 0.48], [-s * 0.3, s * 0.06], [-s * 0.02, s * 0.06], [-s * 0.1, s * 0.48], [s * 0.3, -s * 0.08], [s * 0.02, -s * 0.08]]); c.fill(); },
  fire: (c, s) => { c.beginPath(); c.moveTo(0, -s * 0.48); c.bezierCurveTo(s * 0.45, -s * 0.1, s * 0.35, s * 0.45, 0, s * 0.45); c.bezierCurveTo(-s * 0.35, s * 0.45, -s * 0.4, 0, -s * 0.1, -s * 0.2); c.bezierCurveTo(-s * 0.05, -s * 0.05, s * 0.05, -s * 0.2, 0, -s * 0.48); c.fill(); },
  food: (c, s) => { rr(c, -s * 0.3, -s * 0.32, s * 0.6, s * 0.7, s * 0.08); c.fill(); c.save(); c.globalCompositeOperation = 'destination-out'; c.fillRect(-s * 0.3, -s * 0.12, s * 0.6, s * 0.08); c.restore(); },
  clock: (c, s) => { c.lineWidth = s * 0.1; ell(c, 0, 0, s * 0.4, s * 0.4); c.stroke(); c.beginPath(); c.moveTo(0, -s * 0.24); c.lineTo(0, 0); c.lineTo(s * 0.18, s * 0.1); c.stroke(); },
  warning: (c, s) => { poly(c, [[0, -s * 0.45], [s * 0.48, s * 0.4], [-s * 0.48, s * 0.4]]); c.fill(); c.save(); c.globalCompositeOperation = 'destination-out'; c.fillRect(-s * 0.04, -s * 0.15, s * 0.08, s * 0.3); c.fillRect(-s * 0.04, s * 0.22, s * 0.08, s * 0.08); c.restore(); },
  check: (c, s) => { c.lineWidth = s * 0.14; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(-s * 0.32, 0); c.lineTo(-s * 0.08, s * 0.25); c.lineTo(s * 0.35, -s * 0.28); c.stroke(); },
  cross: (c, s) => { c.lineWidth = s * 0.14; c.lineCap = 'round'; c.beginPath(); c.moveTo(-s * 0.28, -s * 0.28); c.lineTo(s * 0.28, s * 0.28); c.moveTo(s * 0.28, -s * 0.28); c.lineTo(-s * 0.28, s * 0.28); c.stroke(); },
  house: (c, s) => { poly(c, [[0, -s * 0.42], [s * 0.42, -s * 0.05], [s * 0.3, -s * 0.05], [s * 0.3, s * 0.4], [-s * 0.3, s * 0.4], [-s * 0.3, -s * 0.05], [-s * 0.42, -s * 0.05]]); c.fill(); },
  phone: (c, s) => { rr(c, -s * 0.2, -s * 0.42, s * 0.4, s * 0.84, s * 0.08); c.fill(); c.save(); c.globalCompositeOperation = 'destination-out'; rr(c, -s * 0.14, -s * 0.32, s * 0.28, s * 0.56, s * 0.03); c.fill(); c.restore(); },
  battery: (c, s) => { c.lineWidth = s * 0.08; rr(c, -s * 0.4, -s * 0.2, s * 0.72, s * 0.4, s * 0.06); c.stroke(); c.fillRect(s * 0.34, -s * 0.08, s * 0.08, s * 0.16); c.fillRect(-s * 0.32, -s * 0.12, s * 0.22, s * 0.24); },
  heart: (c, s) => { c.beginPath(); c.moveTo(0, s * 0.4); c.bezierCurveTo(-s * 0.6, 0, -s * 0.3, -s * 0.55, 0, -s * 0.18); c.bezierCurveTo(s * 0.3, -s * 0.55, s * 0.6, 0, 0, s * 0.4); c.fill(); },
  snow: (c, s) => { c.lineWidth = s * 0.08; c.lineCap = 'round'; for (let i = 0; i < 3; i++) { c.save(); c.rotate(i * Math.PI / 3); c.beginPath(); c.moveTo(0, -s * 0.42); c.lineTo(0, s * 0.42); c.moveTo(-s * 0.1, -s * 0.32); c.lineTo(0, -s * 0.22); c.lineTo(s * 0.1, -s * 0.32); c.stroke(); c.restore(); } },
  temp: (c, s) => { c.lineWidth = s * 0.08; rr(c, -s * 0.08, -s * 0.42, s * 0.16, s * 0.6, s * 0.08); c.stroke(); ell(c, 0, s * 0.28, s * 0.15, s * 0.15); c.fill(); },
  people: (c, s) => { [[-s * 0.18, 0.9], [s * 0.18, 1]].forEach(([x, k]) => { ell(c, x, -s * 0.18, s * 0.12 * k, s * 0.12 * k); c.fill(); c.beginPath(); c.arc(x, s * 0.3, s * 0.22 * k, Math.PI, 0); c.fill(); }); },
  key: (c, s) => { c.lineWidth = s * 0.1; ell(c, -s * 0.18, 0, s * 0.16, s * 0.16); c.stroke(); c.beginPath(); c.moveTo(-s * 0.02, 0); c.lineTo(s * 0.42, 0); c.moveTo(s * 0.3, 0); c.lineTo(s * 0.3, s * 0.14); c.moveTo(s * 0.4, 0); c.lineTo(s * 0.4, s * 0.12); c.stroke(); },
  door: (c, s) => { c.lineWidth = s * 0.08; c.strokeRect(-s * 0.26, -s * 0.42, s * 0.52, s * 0.84); ell(c, s * 0.12, 0, s * 0.05, s * 0.05); c.fill(); },
  signal: (c, s) => { for (let i = 0; i < 4; i++) c.fillRect(-s * 0.38 + i * s * 0.2, s * 0.35 - (i + 1) * s * 0.18, s * 0.13, (i + 1) * s * 0.18); },
  sun: (c, s) => { ell(c, 0, 0, s * 0.2, s * 0.2); c.fill(); c.lineWidth = s * 0.07; c.lineCap = 'round'; for (let i = 0; i < 8; i++) { c.save(); c.rotate(i * Math.PI / 4); c.beginPath(); c.moveTo(0, -s * 0.3); c.lineTo(0, -s * 0.44); c.stroke(); c.restore(); } },
  moon: (c, s) => { c.beginPath(); c.arc(0, 0, s * 0.38, Math.PI * 0.35, Math.PI * 1.65); c.arc(s * 0.16, -s * 0.05, s * 0.3, Math.PI * 1.5, Math.PI * 0.5, true); c.fill(); },
  flashlight: (c, s) => { c.save(); c.rotate(-0.8); rr(c, -s * 0.1, -s * 0.05, s * 0.2, s * 0.45, s * 0.04); c.fill(); poly(c, [[-s * 0.1, -s * 0.05], [-s * 0.18, -s * 0.25], [s * 0.18, -s * 0.25], [s * 0.1, -s * 0.05]]); c.fill(); c.restore(); },
  med: (c, s) => { c.fillRect(-s * 0.12, -s * 0.38, s * 0.24, s * 0.76); c.fillRect(-s * 0.38, -s * 0.12, s * 0.76, s * 0.24); },
  car: (c, s) => { rr(c, -s * 0.45, -s * 0.05, s * 0.9, s * 0.28, s * 0.08); c.fill(); poly(c, [[-s * 0.28, -s * 0.05], [-s * 0.16, -s * 0.3], [s * 0.18, -s * 0.3], [s * 0.3, -s * 0.05]]); c.fill(); ell(c, -s * 0.25, s * 0.25, s * 0.1, s * 0.1); c.fill(); ell(c, s * 0.25, s * 0.25, s * 0.1, s * 0.1); c.fill(); },
  tap: (c, s) => { c.fillRect(-s * 0.4, -s * 0.2, s * 0.5, s * 0.16); c.fillRect(s * 0.02, -s * 0.2, s * 0.16, s * 0.36); c.fillRect(-s * 0.25, -s * 0.36, s * 0.2, s * 0.16); ell(c, s * 0.1, s * 0.32, s * 0.06, s * 0.09); c.fill(); },
  stairs: (c, s) => { poly(c, [[-s * 0.45, s * 0.4], [-s * 0.45, s * 0.15], [-s * 0.15, s * 0.15], [-s * 0.15, -s * 0.1], [s * 0.15, -s * 0.1], [s * 0.15, -s * 0.35], [s * 0.45, -s * 0.35], [s * 0.45, s * 0.4]]); c.fill(); },
  gas: (c, s) => { IC.fire(c, s * 0.8); },
  shield: (c, s) => { c.beginPath(); c.moveTo(0, -s * 0.45); c.lineTo(s * 0.38, -s * 0.3); c.quadraticCurveTo(s * 0.35, s * 0.25, 0, s * 0.45); c.quadraticCurveTo(-s * 0.35, s * 0.25, -s * 0.38, -s * 0.3); c.closePath(); c.fill(); },
  eye: (c, s) => { c.beginPath(); c.moveTo(-s * 0.45, 0); c.quadraticCurveTo(0, -s * 0.42, s * 0.45, 0); c.quadraticCurveTo(0, s * 0.42, -s * 0.45, 0); c.fill(); c.save(); c.globalCompositeOperation = 'destination-out'; ell(c, 0, 0, s * 0.14, s * 0.14); c.fill(); c.restore(); },
  radio: (c, s) => { rr(c, -s * 0.42, -s * 0.18, s * 0.84, s * 0.55, s * 0.08); c.fill(); c.lineWidth = s * 0.06; c.beginPath(); c.moveTo(s * 0.2, -s * 0.18); c.lineTo(s * 0.4, -s * 0.45); c.stroke(); },
  plant: (c, s) => { c.fillRect(-s * 0.03, -s * 0.1, s * 0.06, s * 0.5); c.beginPath(); c.ellipse(-s * 0.18, -s * 0.12, s * 0.2, s * 0.1, -0.6, 0, Math.PI * 2); c.fill(); c.beginPath(); c.ellipse(s * 0.18, -s * 0.25, s * 0.2, s * 0.1, 0.6, 0, Math.PI * 2); c.fill(); },
  star: (c, s) => { c.beginPath(); for (let i = 0; i < 10; i++) { const r = i % 2 ? s * 0.2 : s * 0.46, a = -Math.PI / 2 + i * Math.PI / 5; c.lineTo(Math.cos(a) * r, Math.sin(a) * r); } c.closePath(); c.fill(); },
  question: (c, s) => { c.font = T.font(800, s * 0.9, SANS); c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('?', 0, s * 0.04); },
  zombie: (c, s) => { c.beginPath(); c.moveTo(-s * 0.18, s * 0.45); c.lineTo(-s * 0.2, -s * 0.05); c.lineTo(-s * 0.3, -s * 0.35); c.lineTo(-s * 0.18, -s * 0.38); c.lineTo(-s * 0.1, -s * 0.15); c.lineTo(-s * 0.05, -s * 0.45); c.lineTo(s * 0.06, -s * 0.45); c.lineTo(s * 0.08, -s * 0.15);
    c.lineTo(s * 0.16, -s * 0.4); c.lineTo(s * 0.27, -s * 0.36); c.lineTo(s * 0.2, -s * 0.05); c.lineTo(s * 0.18, s * 0.45); c.closePath(); c.fill(); },
  money: (c, s) => { c.lineWidth = s * 0.08; rr(c, -s * 0.42, -s * 0.24, s * 0.84, s * 0.48, s * 0.06); c.stroke(); ell(c, 0, 0, s * 0.12, s * 0.12); c.fill(); },
  wifi: (c, s) => { c.lineWidth = s * 0.08; c.lineCap = 'round'; [0.42, 0.28, 0.14].forEach(r => { c.beginPath(); c.arc(0, s * 0.3, s * r, Math.PI * 1.25, Math.PI * 1.75); c.stroke(); }); ell(c, 0, s * 0.3, s * 0.05, s * 0.05); c.fill(); },
};
T.ICON_NAMES = Object.keys(IC);
T.icon = function (ctx, name, x, y, s, color) { const f = IC[name]; if (!f) return false; ctx.save(); ctx.translate(x, y); ctx.fillStyle = ctx.strokeStyle = color || '#FFF'; f(ctx, s); ctx.restore(); return true; };

// ------------------------------------------------------------------ helpers
function pop(lt, t0, d = 0.28) { return lt < t0 ? 0 : E.outq((lt - t0) / d); }
function springIn(lt, t0) { return lt < t0 ? 0 : E.spring((lt - t0) / 0.5); }
function outK(lt, el, dur) { const t1 = el.out != null ? el.out : null; if (t1 == null || lt < t1) return 1; return 1 - clamp((lt - t1) / 0.2); }
function txt(ctx, s, x, y, size, o = {}) { ctx.save(); ctx.font = T.font(o.weight || 800, size, o.fam || SANS); ctx.textAlign = o.align || 'left'; ctx.textBaseline = 'middle';
  if (o.ls) { try { ctx.letterSpacing = o.ls + 'px'; } catch (e) {} }
  if (o.shadow) { ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = size * 0.25; ctx.shadowOffsetY = size * 0.05; }
  if (o.stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = o.stroke; ctx.strokeStyle = o.strokeColor || '#0B0D12'; ctx.strokeText(s, x, y); }
  ctx.fillStyle = o.color || '#FFF'; ctx.fillText(s, x, y); const w = ctx.measureText(s).width; ctx.restore(); return w; }
function measure(ctx, s, size, fam = SANS, weight = 800, ls = 0) { ctx.save(); ctx.font = T.font(weight, size, fam); if (ls) { try { ctx.letterSpacing = ls + 'px'; } catch (e) {} } const w = ctx.measureText(s).width; ctx.restore(); return w; }
T.txt = txt; T.measure = measure;
const SAFE = () => { const st = T.story, p = st.H >= st.W; return p ? {top: 0.085, bottom: 0.76, left: 0.06, right: 0.86} : {top: 0.07, bottom: 0.9, left: 0.05, right: 0.95}; };
T.SAFE = SAFE;
function anchor(el, W, H, def) { const a = el.at || def; if (Array.isArray(a)) return [a[0] * W, a[1] * H]; const sf = SAFE();
  return {tl: [sf.left * W, sf.top * H], tl2: [sf.left * W, (sf.top + 0.062) * H], tr: [sf.right * W, sf.top * H], top: [W / 2, (sf.top + 0.08) * H], center: [W / 2, H * 0.42], upper: [W / 2, H * 0.2], lower: [W / 2, H * 0.8]}[a] || [W / 2, H * 0.2]; }   // upper = above the faces of medium / close shots

// ------------------------------------------------------------------ HUD elements
const HUD = T.HUD = {};
HUD.clock = (ctx, el, lt, W, H, sc) => {     // pill: red dot + "ДЕНЬ 1 — 06:15" (mono)
  const k = el.t != null && el.t > 0 ? pop(lt, el.t) : 1, s = (el.size || 1) * Math.min(W, H) / 1080, [x, y] = anchor(el, W, H, 'tl');
  const label = el.text || '', fs = 40 * s, padX = 30 * s, dot = 13 * s, w = measure(ctx, label, fs, MONO, 700) + padX * 2 + dot * 2.6, h = 74 * s;
  ctx.save(); ctx.globalAlpha = k; ctx.translate(x - (1 - k) * 40 * s, y);
  rr(ctx, 0, -h / 2, w, h, h / 2); ctx.fillStyle = 'rgba(10,14,22,0.72)'; ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.lineWidth = 2 * s; ctx.stroke();
  const blink = 0.55 + 0.45 * Math.sin((sc.t0 + lt) * Math.PI * 2 / 1.2); ell(ctx, padX + dot, 0, dot, dot); ctx.fillStyle = rgba(UI.danger, blink); ctx.fill();
  T.h.glow(ctx, padX + dot, 0, dot * 3, UI.danger, 0.35 * blink);
  if (el.flip != null && lt < el.flip + 0.3 && el.prev) { const f = clamp((lt - el.flip) / 0.3); ctx.save(); ctx.beginPath(); ctx.rect(padX + dot * 2.6, -h / 2, w, h); ctx.clip();
    txt(ctx, el.prev, padX + dot * 2.6, -f * h, fs, {fam: MONO, weight: 700}); txt(ctx, label, padX + dot * 2.6, (1 - f) * h, fs, {fam: MONO, weight: 700}); ctx.restore(); }
  else txt(ctx, label, padX + dot * 2.6, 2 * s, fs, {fam: MONO, weight: 700});
  ctx.restore(); return h;
};
HUD.counter = (ctx, el, lt, W, H, sc) => {   // panel: LABEL small caps + big mono number
  const k = pop(lt, el.t == null ? 0.15 : el.t), s = (el.size || 1) * Math.min(W, H) / 1080; if (k <= 0) return;
  let [x, y] = anchor(el, W, H, 'tr'); const c = col(el.color || 'ok');
  const dur = el.dur || Math.max(0.6, (sc.t1 - sc.t0) - (el.t || 0.15) - 0.4), p = E.out(clamp((lt - (el.t || 0.15)) / dur));
  const v = el.to == null ? el.from : lerp(el.from || 0, el.to, p); const num = (el.prefix || '') + fmtNum(v, el.decimals) + (el.suffix || '');
  const lab = (el.label || '').toUpperCase(), fsL = 26 * s, fsN = 64 * s, w = Math.max(measure(ctx, lab, fsL, SANS, 800, 3 * s), measure(ctx, num, fsN, MONO, 700)) + 56 * s, h = 150 * s;
  if (el.at === 'tr' || !el.at) x -= w; else if (Array.isArray(el.at)) x -= w / 2;
  ctx.save(); ctx.globalAlpha = k * outK(lt, el); ctx.translate(x, y + (1 - k) * 20 * s);
  rr(ctx, 0, 0, w, h, 18 * s); ctx.fillStyle = 'rgba(10,14,22,0.74)'; ctx.fill(); ctx.strokeStyle = rgba(c, 0.85); ctx.lineWidth = 3 * s; ctx.stroke();
  txt(ctx, lab, 28 * s, 40 * s, fsL, {color: 'rgba(255,255,255,0.75)', ls: 3 * s}); txt(ctx, num, 28 * s, 100 * s, fsN, {fam: MONO, weight: 700, color: c});
  ctx.restore();
};
function fmtNum(v, d) { if (d) return v.toFixed(d).replace('.', ','); const n = Math.round(v); return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
HUD.tape = (ctx, el, lt, W, H) => {          // paper tape label "МИНУС 1 · СТЕКЛО"
  const t0 = el.t == null ? 0.2 : el.t; if (lt < t0) return; const s = (el.size || 1) * Math.min(W, H) / 1080, k = E.outq((lt - t0) / 0.22), [x, y] = anchor(el, W, H, 'upper');
  const label = (el.text || '').toUpperCase(), fs = 46 * s, w = measure(ctx, label, fs, MONO, 700) + 70 * s, h = 92 * s;
  ctx.save(); ctx.globalAlpha = Math.min(1, k * 1.5) * outK(lt, el); ctx.translate(x, y); ctx.rotate((el.rot == null ? -3 : el.rot) * Math.PI / 180); ctx.scale(1.25 - 0.25 * k, 1.25 - 0.25 * k);
  ctx.shadowColor = 'rgba(0,0,0,0.35)'; ctx.shadowBlur = 14 * s; ctx.shadowOffsetY = 6 * s;
  ctx.beginPath(); const z = 10 * s; ctx.moveTo(-w / 2, -h / 2); for (let i = 0; i <= 6; i++) ctx.lineTo(-w / 2 + (i % 2 ? z : 0), -h / 2 + i * h / 6); ctx.lineTo(w / 2, h / 2);
  for (let i = 6; i >= 0; i--) ctx.lineTo(w / 2 - (i % 2 ? z : 0), -h / 2 + i * h / 6); ctx.closePath(); ctx.fillStyle = el.paper || UI.paper; ctx.fill(); ctx.shadowColor = 'transparent';
  ctx.fillStyle = 'rgba(0,0,0,0.05)'; ctx.fillRect(-w / 2, -h / 2, w, h * 0.3);
  txt(ctx, label, 0, 3 * s, fs, {fam: MONO, weight: 700, color: el.color ? col(el.color) : UI.ink, align: 'center'}); ctx.restore();
};
HUD.ribbon = (ctx, el, lt, W, H) => {        // red diagonal ribbon across the frame
  const t0 = el.t == null ? 0.25 : el.t; if (lt < t0) return; const s = Math.min(W, H) / 1080, k = E.outq((lt - t0) / 0.35), y = (el.y || 0.2) * H, c = col(el.color || 'danger');
  const label = (el.text || '').toUpperCase(), fs = 64 * s * (el.size || 1), h = 128 * s * (el.size || 1);
  ctx.save(); ctx.globalAlpha = outK(lt, el); ctx.translate(W / 2, y); ctx.rotate((el.rot == null ? -8 : el.rot) * Math.PI / 180); ctx.translate((1 - k) * -W * 1.4, 0);
  ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 24 * s; ctx.fillStyle = c; ctx.fillRect(-W * 1.2, -h / 2, W * 2.4, h); ctx.shadowColor = 'transparent';
  ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(-W * 1.2, -h / 2, W * 2.4, 6 * s); ctx.fillStyle = 'rgba(0,0,0,0.18)'; ctx.fillRect(-W * 1.2, h / 2 - 6 * s, W * 2.4, 6 * s);
  T.fitText(ctx, label, W * 0.9, fs, '800'); const f2 = Math.min(fs, T.fitText(ctx, label, W * 0.88, fs, '800')); txt(ctx, label, 0, 4 * s, f2, {align: 'center', ls: 2 * s}); ctx.restore();
};
HUD.stamp = (ctx, el, lt, W, H) => {         // big stamp "ОШИБКА" / "ВЕРНО" with impact
  const t0 = el.t == null ? 0.3 : el.t; if (lt < t0) return; const s = (el.size || 1) * Math.min(W, H) / 1080, k = clamp((lt - t0) / 0.18), [x, y] = anchor(el, W, H, 'upper');
  const c = col(el.color || 'danger'), label = (el.text || '').toUpperCase(), fs = 110 * s, w = measure(ctx, label, fs, DISPLAY, 900) + 90 * s, h = 190 * s;
  const sc = k < 1 ? 2.2 - 1.2 * E.out(k) : 1 + Math.exp(-(lt - t0 - 0.18) * 12) * 0.05 * Math.sin((lt - t0) * 50);
  ctx.save(); ctx.globalAlpha = Math.min(1, k * 1.4) * outK(lt, el) * 0.95; ctx.translate(x, y); ctx.rotate((el.rot == null ? -12 : el.rot) * Math.PI / 180); ctx.scale(sc, sc);
  ctx.strokeStyle = c; ctx.lineWidth = 12 * s; rr(ctx, -w / 2, -h / 2, w, h, 22 * s); ctx.stroke(); ctx.lineWidth = 4 * s; rr(ctx, -w / 2 + 16 * s, -h / 2 + 16 * s, w - 32 * s, h - 32 * s, 12 * s); ctx.stroke();
  txt(ctx, label, 0, 8 * s, fs, {fam: DISPLAY, weight: 900, color: c, align: 'center'}); ctx.restore();
};
function plateSize(ctx, el, s) {
  const title = (el.text || '').toUpperCase(), sub = el.sub || '', fsT = 44 * s * (el.size || 1), fsS = 32 * s * (el.size || 1), pad = 26 * s, ic = el.icon ? 64 * s * (el.size || 1) : 0;
  const wT = measure(ctx, title, fsT, SANS, 800), wS = sub ? measure(ctx, sub, fsS, BODY, 700) : 0;
  return {w: Math.max(wT, wS) + pad * 2 + (ic ? ic + pad * 0.7 : 0), h: (sub ? 128 : 96) * s * (el.size || 1)};
}
function plateBox(ctx, el, x, y, s, lt, k, align, W) {
  const c = col(el.color || 'warn'), title = (el.text || '').toUpperCase(), sub = el.sub || '', icon = el.icon;
  const fsT = 44 * s * (el.size || 1), fsS = 32 * s * (el.size || 1), pad = 26 * s, ic = icon ? 64 * s * (el.size || 1) : 0;
  const {w, h} = plateSize(ctx, el, s);
  let bx = align === 'center' ? x - w / 2 : align === 'right' ? x - w : x; const by = y - h / 2;
  if (W) bx = clamp(bx, 0.04 * W, Math.max(0.04 * W, 0.96 * W - w));          // never off-frame
  ctx.save(); ctx.globalAlpha = k; ctx.translate(0, (1 - k) * 24 * s);
  ctx.shadowColor = 'rgba(0,0,0,0.4)'; ctx.shadowBlur = 20 * s; rr(ctx, bx, by, w, h, 20 * s); ctx.fillStyle = el.bg || 'rgba(10,14,22,0.80)'; ctx.fill(); ctx.shadowColor = 'transparent';
  ctx.strokeStyle = rgba(c, 0.9); ctx.lineWidth = 3 * s; ctx.stroke();
  let tx = bx + pad; if (ic) { rr(ctx, tx, y - ic / 2, ic, ic, 14 * s); ctx.fillStyle = rgba(c, 0.18); ctx.fill(); T.icon(ctx, icon, tx + ic / 2, y, ic * 0.62, c); tx += ic + pad * 0.7; }
  if (sub) { txt(ctx, title, tx, y - 20 * s * (el.size || 1), fsT, {color: '#FFF'}); txt(ctx, sub, tx, y + 28 * s * (el.size || 1), fsS, {fam: BODY, weight: 700, color: 'rgba(255,255,255,0.78)'}); }
  else txt(ctx, title, tx, y + 2 * s, fsT, {color: '#FFF'});
  ctx.restore(); return {x: bx, y: by, w, h};
}
HUD.plate = (ctx, el, lt, W, H) => { const k = pop(lt, el.t == null ? 0.2 : el.t) * outK(lt, el); if (k <= 0) return; const s = Math.min(W, H) / 1080, [x, y] = anchor(el, W, H, 'upper');
  plateBox(ctx, el, x, y, s, lt, k, el.align || 'center', W); };
HUD.callout = (ctx, el, lt, W, H) => {       // plate + dashed leader line + target dot
  const t0 = el.t == null ? 0.2 : el.t, k = pop(lt, t0) * outK(lt, el); if (k <= 0) return; const s = Math.min(W, H) / 1080, [x, y] = anchor(el, W, H, 'upper'), to = el.to || [0.5, 0.55];
  const tx = to[0] * W, ty = to[1] * H, c = col(el.color || 'warn'), lk = clamp((lt - t0) / 0.4);
  const {w} = plateSize(ctx, el, s), right = x > tx;                 // plate sits on the far side of the anchor, clamped into frame
  const px = clamp(right ? x : x - w, 0.04 * W, Math.max(0.04 * W, 0.96 * W - w)), ex = right ? px : px + w;
  ctx.save(); ctx.globalAlpha = k; ctx.strokeStyle = c; ctx.lineWidth = 4 * s; ctx.setLineDash([14 * s, 10 * s]); ctx.lineDashOffset = -lt * 40 * s;
  ctx.beginPath(); ctx.moveTo(ex, y); ctx.lineTo(lerp(ex, tx, E.out(lk)), lerp(y, ty, E.out(lk))); ctx.stroke(); ctx.setLineDash([]);
  if (lk >= 1) { const r = 12 * s + 4 * s * Math.sin(lt * 6); ell(ctx, tx, ty, r, r); ctx.fillStyle = c; ctx.fill(); ell(ctx, tx, ty, r * 2.2, r * 2.2); ctx.strokeStyle = rgba(c, 0.5); ctx.lineWidth = 3 * s; ctx.stroke(); }
  ctx.restore(); plateBox(ctx, el, px, y, s, lt, k, 'left');
};
HUD.title = (ctx, el, lt, W, H) => {         // big title "ДЕНЬ 30"
  const t0 = el.t == null ? 0.1 : el.t; if (lt < t0) return; const s = (el.size || 1) * Math.min(W, H) / 1080, k = springIn(lt, t0), [x, y] = anchor(el, W, H, 'upper'), c = col(el.color || 'danger');
  const label = (el.text || '').toUpperCase(), fs0 = 150 * s, room = Math.min(W * 0.86, 2 * Math.min(x, W - x) - 0.06 * W);   // never past the frame edge
  const fs = Math.min(fs0, T.fitText(ctx, label, Math.max(W * 0.3, room), fs0, '900', DISPLAY));
  ctx.save(); ctx.globalAlpha = clamp(k * 1.5) * outK(lt, el); ctx.translate(x, y); ctx.scale(0.8 + 0.2 * k, 0.8 + 0.2 * k);
  txt(ctx, label, 0, 0, fs, {fam: DISPLAY, weight: 900, color: c, align: 'center', stroke: 14 * s, strokeColor: '#0B0D12', shadow: true});
  if (el.sub) txt(ctx, el.sub.toUpperCase(), 0, fs * 0.78, fs * 0.32, {align: 'center', color: '#FFF', stroke: 6 * s, ls: 3 * s});
  ctx.restore();
};
HUD.chapter = (ctx, el, lt, W, H) => {       // long-form chapter card: number + title on a band (full: dims the whole frame first)
  const t0 = el.t == null ? 0.1 : el.t; if (lt < t0) return; const s = Math.min(W, H) / 1080, k = pop(lt, t0, 0.5) * outK(lt, el), y = (el.y || (el.full ? 0.45 : 0.5)) * H;
  ctx.save(); ctx.globalAlpha = el.full ? Math.min(1, outK(lt, el) * 1.0) : k;
  if (el.full) { ctx.fillStyle = 'rgba(6,8,14,0.86)'; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = k; }
  else { ctx.fillStyle = 'rgba(8,10,16,0.72)'; ctx.fillRect(0, y - 120 * s, W, 240 * s); } ctx.fillStyle = col(el.color || 'warn'); ctx.fillRect(W / 2 - 80 * s * k, y - 80 * s, 160 * s * k, 6 * s);
  txt(ctx, (el.num != null ? 'ГЛАВА ' + el.num : '').toUpperCase(), W / 2, y - 40 * s, 34 * s, {fam: MONO, weight: 700, align: 'center', color: col(el.color || 'warn'), ls: 6 * s});
  txt(ctx, (el.text || '').toUpperCase(), W / 2, y + 30 * s, 72 * s, {align: 'center'}); ctx.restore();
};
HUD.question = (ctx, el, lt, W, H) => {      // yellow plate, black text, tilted 2-3 degrees (comment prompt)
  const t0 = el.t == null ? 0.3 : el.t, k = springIn(lt, t0); if (k <= 0) return; const s = Math.min(W, H) / 1080, [x, y] = anchor(el, W, H, 'upper');
  const label = (el.text || '').toUpperCase(), fs0 = 60 * s, fs = Math.min(fs0, T.fitText(ctx, label, W * 0.8, fs0, '800')), w = measure(ctx, label, fs) + 80 * s, h = fs * 1.9;
  ctx.save(); ctx.globalAlpha = clamp(k * 1.4) * outK(lt, el); ctx.translate(x, y); ctx.rotate((el.rot == null ? -2.5 : el.rot) * Math.PI / 180); ctx.scale(0.85 + 0.15 * k, 0.85 + 0.15 * k);
  ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 24 * s; ctx.fillStyle = el.bg || '#FFD43B'; ctx.fillRect(-w / 2, -h / 2, w, h); ctx.shadowColor = 'transparent';
  txt(ctx, label, 0, 4 * s, fs, {align: 'center', color: '#111'}); ctx.restore();
};
HUD.bar = (ctx, el, lt, W, H, sc) => {       // resource bar: label + track + fill animating from -> to
  const t0 = el.t == null ? 0.2 : el.t, k = pop(lt, t0) * outK(lt, el); if (k <= 0) return; const s = Math.min(W, H) / 1080, [x, y] = anchor(el, W, H, sc.clock ? 'tl2' : 'tl');
  const dur = el.dur || Math.max(0.6, sc.t1 - sc.t0 - t0 - 0.3), p = E.io(clamp((lt - t0) / dur)), v = lerp(el.from == null ? 1 : el.from, el.to == null ? 0.2 : el.to, p);
  const c = col(el.color || (v < 0.3 ? 'danger' : v < 0.6 ? 'warn' : 'ok')), w = (el.w || 0.42) * W, h = 26 * s;
  ctx.save(); ctx.globalAlpha = k; const lab = (el.text || el.label || '').toUpperCase(); if (el.icon) T.icon(ctx, el.icon, x + 22 * s, y, 40 * s, c);
  const lx = x + (el.icon ? 54 * s : 0); txt(ctx, lab, lx, y, 34 * s, {shadow: true}); const pct = Math.round(v * 100) + '%'; txt(ctx, pct, lx + w, y, 34 * s, {fam: MONO, weight: 700, align: 'right', color: c, shadow: true});
  rr(ctx, lx, y + 32 * s, w, h, h / 2); ctx.fillStyle = 'rgba(10,14,22,0.7)'; ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = 2 * s; ctx.stroke();
  rr(ctx, lx + 4 * s, y + 36 * s, Math.max(h - 8 * s, (w - 8 * s) * v), h - 8 * s, (h - 8 * s) / 2); ctx.fillStyle = c; ctx.fill(); ctx.restore();
};
HUD.timer = (ctx, el, lt, W, H) => {         // countdown "04:29 ОСТ." in a red frame
  const t0 = el.t == null ? 0.2 : el.t, k = pop(lt, t0) * outK(lt, el); if (k <= 0) return; const s = (el.size || 1) * Math.min(W, H) / 1080, [x, y] = anchor(el, W, H, 'top'), c = col(el.color || 'danger');
  const sec0 = el.from == null ? 269 : el.from, rate = el.rate || 1, sec = Math.max(0, sec0 - Math.max(0, lt - t0) * rate * (el.speed || 1));
  const mm = String(Math.floor(sec / 60)).padStart(2, '0'), ss = String(Math.floor(sec % 60)).padStart(2, '0'), label = `${mm}:${ss}`, suf = el.suffix == null ? ' ОСТ.' : el.suffix;
  const fs = 76 * s, w = measure(ctx, label + suf, fs, MONO, 700) + 70 * s, h = 120 * s, blink = sec < 30 ? 0.6 + 0.4 * Math.sin(lt * 12) : 1;
  ctx.save(); ctx.globalAlpha = k; ctx.translate(x, y); rr(ctx, -w / 2, -h / 2, w, h, 14 * s); ctx.fillStyle = 'rgba(10,14,22,0.82)'; ctx.fill(); ctx.strokeStyle = rgba(c, blink); ctx.lineWidth = 6 * s; ctx.stroke();
  txt(ctx, label + suf, 0, 4 * s, fs, {fam: MONO, weight: 700, align: 'center', color: rgba(c, blink)}); ctx.restore();
};
HUD.arrow = (ctx, el, lt, W, H) => {         // animated arrow pointing to a target
  const t0 = el.t == null ? 0.2 : el.t, k = pop(lt, t0) * outK(lt, el); if (k <= 0) return; const s = Math.min(W, H) / 1080, to = el.to || [0.5, 0.5], from = el.from || [to[0] + 0.18, to[1] - 0.12];
  const c = col(el.color || 'warn'), bob = Math.sin(lt * 6) * 10 * s, ang = Math.atan2(to[1] * H - from[1] * H, to[0] * W - from[0] * W);
  ctx.save(); ctx.globalAlpha = k; ctx.translate(to[0] * W - Math.cos(ang) * (40 * s + bob), to[1] * H - Math.sin(ang) * (40 * s + bob)); ctx.rotate(ang);
  ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 12 * s; ctx.fillStyle = c; const L = Math.hypot((to[0] - from[0]) * W, (to[1] - from[1]) * H) * E.out(k);
  ctx.fillRect(-L, -10 * s, L - 30 * s, 20 * s); poly(ctx, [[0, 0], [-48 * s, -34 * s], [-48 * s, 34 * s]]); ctx.fill(); ctx.restore();
};
HUD.circle = (ctx, el, lt, W, H) => {        // hand-drawn highlight circle around a target
  const t0 = el.t == null ? 0.2 : el.t; if (lt < t0) return; const s = Math.min(W, H) / 1080, k = E.out((lt - t0) / 0.5), to = el.to || [0.5, 0.5], r = (el.r || 0.1) * W;
  ctx.save(); ctx.globalAlpha = outK(lt, el); ctx.strokeStyle = col(el.color || 'danger'); ctx.lineWidth = 10 * s; ctx.lineCap = 'round'; ctx.beginPath();
  for (let i = 0; i <= 60 * k; i++) { const a = -1.2 + i / 60 * Math.PI * 2.15, rr2 = r * (1 + 0.06 * Math.sin(i * 0.4)); ctx.lineTo(to[0] * W + Math.cos(a) * rr2, to[1] * H + Math.sin(a) * rr2 * 0.85); } ctx.stroke(); ctx.restore();
};
HUD.label = (ctx, el, lt, W, H) => {         // small mono label (service text)
  const k = pop(lt, el.t == null ? 0.2 : el.t) * outK(lt, el); if (k <= 0) return; const s = Math.min(W, H) / 1080, [x, y] = anchor(el, W, H, 'upper');
  ctx.save(); ctx.globalAlpha = k; txt(ctx, (el.text || '').toUpperCase(), x, y, (el.size || 1) * 34 * s, {fam: MONO, weight: 700, align: el.align || 'center', color: col(el.color || 'white'), shadow: true, ls: 2 * s}); ctx.restore();
};
HUD.brand = (ctx, el, lt, W, H) => { const s = Math.min(W, H) / 1080; ctx.save(); ctx.globalAlpha = 0.55; txt(ctx, el.text || '', W - 40 * s, Math.max(36 * s, H * SAFE().top - 40 * s), 28 * s, {fam: MONO, weight: 700, align: 'right', shadow: true}); ctx.restore(); };
T.HUD_NAMES = Object.keys(HUD);

T.overlays = function (ctx, sc, lt, t, W, H) {
  if (T.story.brand) HUD.brand(ctx, {text: T.story.brand}, lt, W, H);
  if (sc.clock) HUD.clock(ctx, Object.assign({t: sc.clock_new ? 0.05 : -1}, typeof sc.clock === 'string' ? {text: sc.clock} : sc.clock, sc.clock_prev ? {prev: sc.clock_prev, flip: 0.05} : {}), lt, W, H, sc);
  (sc.hud || []).forEach((el, i) => { const f = HUD[el.type]; if (!f) return; const e = Object.assign({}, el); if (e.t == null && ['clock', 'brand'].indexOf(e.type) < 0) e.t = 0.15 + i * 0.09; f(ctx, e, lt, W, H, sc); });
};

// ------------------------------------------------------------------ karaoke captions
// story.captions = [{t0, t1, lines: [[{w, s, e, a}]], color}] prepared by Python (line breaks measured with the same font)
T.captions = function (ctx, t, W, H) {
  const C = T.story.captions, st = T.story.style || {}; if (!C || !C.length || st.captions === 'off') return;
  let lo = 0, hi = C.length - 1, cur = null; while (lo <= hi) { const m = (lo + hi) >> 1; if (C[m].t1 <= t) lo = m + 1; else if (C[m].t0 > t) hi = m - 1; else { cur = C[m]; break; } }
  if (!cur) return;
  const portrait = H >= W, s = Math.min(W, H) / 1080, caps = st.captions !== 'sentence', fs = (st.caption_size || (portrait ? 84 : 72)) * s, lh = fs * 1.12;
  const cy = (st.caption_y || (portrait ? 0.655 : 0.84)) * H, k = E.outq((t - cur.t0) / 0.14), scl = (0.94 + 0.06 * k) * (cur.fit || 1);
  const acc = col(cur.color || 'yellow'), dim = st.caption_dim == null ? 0.5 : st.caption_dim;
  ctx.save(); ctx.font = T.font(800, fs, SANS); ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  const n = cur.lines.length, y0 = cy - (n - 1) * lh / 2;
  ctx.translate(W / 2, cy); ctx.scale(scl, scl); ctx.translate(-W / 2, -cy);
  cur.lines.forEach((line, li) => {
    const words = line.map(w => caps ? w.w.toUpperCase() : w.w), sp = ctx.measureText(' ').width, ws = words.map(w => ctx.measureText(w).width);
    const tot = ws.reduce((a, b) => a + b, 0) + sp * (words.length - 1); let x = W / 2 - tot / 2; const y = y0 + li * lh;
    words.forEach((w, i) => { const wd = line[i], said = t >= wd.s - 0.02, c = wd.a ? acc : '#FFFFFF';
      ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 14 * s; ctx.shadowOffsetY = 3 * s; ctx.lineWidth = 7 * s; ctx.strokeStyle = 'rgba(8,10,14,0.92)'; ctx.strokeText(w, x, y);
      ctx.shadowColor = 'transparent'; ctx.fillStyle = said ? c : rgba(c, dim); ctx.fillText(w, x, y); x += ws[i] + sp; });
  });
  ctx.restore();
};
})();
