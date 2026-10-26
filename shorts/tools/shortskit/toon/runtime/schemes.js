/* TOON schemes (shorts 2.3): explainer diagrams in the channel style of reference/animation.md - blueprint / paper / dark
   backgrounds, thin colour lines, mono service text, cascade reveals (60-120 ms), ease-out.
   sc.scheme = {type, full (default true), bg: blue|paper|dark, title, sub, out, box:[x,y,w,h], ...type fields}.
   full:true replaces the set (frame = diagram); full:false draws a card over the scene (default upper part of the frame). */
'use strict';
(function () {
const T = window.TOON, {clamp, lerp, E, rgba, rr, ell, poly, glow, rng} = T.h, UI = T.UI;
const MONO = 'JetBrains Mono', SANS = 'Montserrat', BODY = 'Manrope', DISPLAY = 'Unbounded';
const THEMES = {
  blue:  {name: 'blue', bg: ['#0C1E33', '#11294A'], grid: 'rgba(59,142,234,0.13)', line: '#3B8EEA', ink: '#FFFFFF', sub: 'rgba(255,255,255,0.70)',
          stroke: 'rgba(235,244,255,0.88)', fill: '#163558', empty: 'rgba(255,255,255,0.12)', plate: 'rgba(8,16,30,0.86)', water: '#4FA8FF'},
  paper: {name: 'paper', light: true, bg: ['#F6F2E7', '#EEE6D2'], grid: 'rgba(20,24,33,0.06)', line: '#2F6DB5', ink: '#141821', sub: '#5A606C',
          stroke: '#1B2029', fill: '#E4DAC3', empty: 'rgba(20,24,33,0.10)', plate: 'rgba(255,253,247,0.96)', water: '#2F80D9'},
  dark:  {name: 'dark', bg: ['#0B0F1A', '#141D30'], grid: 'rgba(255,255,255,0.045)', line: '#3B8EEA', ink: '#FFFFFF', sub: 'rgba(255,255,255,0.66)',
          stroke: 'rgba(255,255,255,0.82)', fill: '#1B263C', empty: 'rgba(255,255,255,0.10)', plate: 'rgba(6,9,16,0.88)', water: '#4FA8FF'},
};
THEMES.sky = {name: 'sky', light: true, bg: ['#8ED6FA', '#E2F6FF'], grid: 'rgba(255,255,255,0.38)', line: '#2F6DB5', ink: '#13304D', sub: '#3D6788',
          stroke: '#1B3B5A', fill: '#FFFFFF', empty: 'rgba(20,50,80,0.12)', plate: 'rgba(255,255,255,0.96)', water: '#2F80D9'};
T.SCHEME_THEMES = THEMES;
const col = c => (T.col ? T.col(c) : (c || UI.warn));
const txt = (...a) => T.txt(...a), measure = (...a) => T.measure(...a);
const pk = (lt, t0, d = 0.32) => (lt < t0 ? 0 : E.outq((lt - t0) / d));        // pop-in 0..1 (ease-out)
const bk = (lt, t0, d = 0.42) => (lt < t0 ? 0 : E.back((lt - t0) / d));        // overshoot pop
const UP = s => String(s == null ? '' : s).toUpperCase();
function wrap(ctx, text, maxW, size, fam = SANS, weight = 800) {
  ctx.save(); ctx.font = T.font(weight, size, fam); const out = []; let line = '';
  String(text || '').split(/\s+/).filter(Boolean).forEach(w => { const tt = line ? line + ' ' + w : w;
    if (ctx.measureText(tt).width > maxW && line) { out.push(line); line = w; } else line = tt; });
  if (line) out.push(line); ctx.restore(); return out;
}
function fit(ctx, text, maxW, size, fam = SANS, weight = 800) { let s = size; while (s > 14 && measure(ctx, text, s, fam, weight) > maxW) s -= 2; return s; }
function plen(pts) { let L = 0; for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return L; }
function pointAt(pts, k) {                       // point + heading at fraction k of a polyline
  const L = plen(pts); let rem = L * clamp(k);
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    if (rem <= d || i === pts.length - 1) { const f = d ? Math.min(1, rem / d) : 0; return [lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f),
      Math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0])]; } rem -= d; }
  return [pts[0][0], pts[0][1], 0];
}
function partial(ctx, pts, k) {                  // stroke the first k (0..1) of a polyline, returns the head point
  if (k <= 0 || pts.length < 2) return pts[0]; const L = plen(pts); let rem = L * clamp(k); ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); let end = pts[0];
  for (let i = 1; i < pts.length && rem > 0; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]), f = d ? Math.min(1, rem / d) : 1;
    end = [lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)]; ctx.lineTo(end[0], end[1]); rem -= d; }
  ctx.stroke(); return end;
}
function head(ctx, x, y, ang, sz) { ctx.save(); ctx.translate(x, y); ctx.rotate(ang); poly(ctx, [[sz * 0.2, 0], [-sz, -sz * 0.62], [-sz * 0.7, 0], [-sz, sz * 0.62]]); ctx.fill(); ctx.restore(); }
function badge(ctx, x, y, r, kind) {             // filled circle with check (ok) or cross (no)
  ell(ctx, x, y, r, r); ctx.fillStyle = kind === 'ok' ? UI.ok : kind === 'warn' ? UI.warn : UI.danger; ctx.fill();
  ctx.strokeStyle = kind === 'warn' ? '#141821' : '#FFFFFF'; ctx.lineWidth = r * 0.24; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.beginPath();
  if (kind === 'ok') { ctx.moveTo(x - r * 0.45, y + r * 0.02); ctx.lineTo(x - r * 0.1, y + r * 0.36); ctx.lineTo(x + r * 0.48, y - r * 0.34); }
  else if (kind === 'warn') { ctx.moveTo(x, y - r * 0.45); ctx.lineTo(x, y + r * 0.1); ctx.moveTo(x, y + r * 0.38); ctx.lineTo(x, y + r * 0.4); }
  else { const q = r * 0.38; ctx.moveTo(x - q, y - q); ctx.lineTo(x + q, y + q); ctx.moveTo(x + q, y - q); ctx.lineTo(x - q, y + q); }
  ctx.stroke();
}
function pill(ctx, text, x, y, s, o = {}) {      // small plate with mono/sans text; align left|center|right; returns {w,h}
  const fs = (o.size || 28) * s, fam = o.fam || MONO, wt = o.weight || 700, pad = 18 * s, w = measure(ctx, text, fs, fam, wt) + pad * 2 + (o.icon ? fs * 1.3 : 0), h = fs * 1.9;
  const bx = o.align === 'left' ? x : o.align === 'right' ? x - w : x - w / 2;
  ctx.save(); if (o.alpha != null) ctx.globalAlpha *= o.alpha; rr(ctx, bx, y - h / 2, w, h, o.r == null ? h / 2 : o.r * s); ctx.fillStyle = o.bg || 'rgba(8,14,26,0.86)'; ctx.fill();
  if (o.border) { ctx.strokeStyle = o.border; ctx.lineWidth = 3 * s; ctx.stroke(); }
  let tx = bx + pad; if (o.icon) { T.icon(ctx, o.icon, tx + fs * 0.5, y, fs * 1.05, o.iconColor || o.border || o.color || '#FFF'); tx += fs * 1.3; }
  txt(ctx, text, tx, y + fs * 0.04, fs, {fam, weight: wt, color: o.color || '#FFFFFF'}); ctx.restore(); return {w, h, x: bx};
}
function plate(ctx, title, sub, x, y, s, th, o = {}) {   // HUD-like plate: icon + CAPS title + sub, thin coloured border
  const c = col(o.color || 'warn'), fsT = (o.size || 34) * s, fsS = fsT * 0.72, pad = 20 * s, ic = o.icon ? fsT * 1.5 : 0;
  const wT = measure(ctx, UP(title), fsT, SANS, 800), wS = sub ? measure(ctx, sub, fsS, BODY, 700) : 0, w = Math.max(wT, wS) + pad * 2 + (ic ? ic + pad * 0.6 : 0), h = sub ? fsT * 2.75 : fsT * 2.0;
  const bx = o.align === 'right' ? x - w : o.align === 'center' ? x - w / 2 : x;
  ctx.save(); ctx.shadowColor = 'rgba(0,0,0,0.30)'; ctx.shadowBlur = 16 * s; rr(ctx, bx, y - h / 2, w, h, 16 * s); ctx.fillStyle = o.bg || th.plate; ctx.fill(); ctx.shadowColor = 'transparent';
  ctx.strokeStyle = rgba(c, 0.95); ctx.lineWidth = 3 * s; ctx.stroke();
  let tx = bx + pad; if (ic) { rr(ctx, tx, y - ic / 2, ic, ic, 10 * s); ctx.fillStyle = rgba(c, 0.18); ctx.fill(); T.icon(ctx, o.icon, tx + ic / 2, y, ic * 0.62, c); tx += ic + pad * 0.6; }
  const ink = th.light ? '#141821' : '#FFFFFF', sb = th.light ? '#5A606C' : 'rgba(255,255,255,0.75)';
  if (sub) { txt(ctx, UP(title), tx, y - fsT * 0.42, fsT, {color: ink}); txt(ctx, sub, tx, y + fsT * 0.55, fsS, {fam: BODY, weight: 700, color: sb}); }
  else txt(ctx, UP(title), tx, y + fsT * 0.04, fsT, {color: ink});
  ctx.restore(); return {x: bx, y: y - h / 2, w, h};
}
function drawBg(ctx, x, y, w, h, th, s, card) {
  ctx.save(); const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, th.bg[0]); g.addColorStop(1, th.bg[1]);
  if (card) { ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 40 * s; ctx.shadowOffsetY = 14 * s; rr(ctx, x, y, w, h, 30 * s); ctx.fillStyle = g; ctx.fill(); ctx.shadowColor = 'transparent'; ctx.clip(); }
  else { ctx.fillStyle = g; ctx.fillRect(x, y, w, h); }
  const cell = 54 * s; ctx.strokeStyle = th.grid; ctx.lineWidth = Math.max(1, 1.4 * s); ctx.beginPath();
  for (let gx = x + ((w / 2) % cell); gx < x + w; gx += cell) { ctx.moveTo(gx, y); ctx.lineTo(gx, y + h); }
  for (let gy = y + ((h / 2) % cell); gy < y + h; gy += cell) { ctx.moveTo(x, gy); ctx.lineTo(x + w, gy); }
  ctx.stroke();
  const vg = ctx.createRadialGradient(x + w / 2, y + h * 0.42, Math.min(w, h) * 0.25, x + w / 2, y + h / 2, Math.hypot(w, h) * 0.62);
  vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, th.light ? 'rgba(90,70,30,0.12)' : 'rgba(0,0,0,0.38)'); ctx.fillStyle = vg; ctx.fillRect(x, y, w, h);
  ctx.restore();
  if (card) { ctx.save(); rr(ctx, x, y, w, h, 30 * s); ctx.strokeStyle = rgba(th.line, 0.6); ctx.lineWidth = 3 * s; ctx.stroke(); ctx.restore(); }
}
function titleBlock(ctx, sp, lt, x, y, s, th, maxW) {
  if (!sp.title) return 0; const k = pk(lt, 0.02, 0.35), t = UP(sp.title), fs = fit(ctx, t, maxW, 68 * s, SANS, 800);
  ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 18 * s);
  const ac = sp.title_color ? col(sp.title_color) : th.ink; txt(ctx, t, x, y, fs, {align: 'center', color: ac, shadow: !th.light});
  if (sp.sub) txt(ctx, UP(sp.sub), x, y + fs * 0.95, 28 * s, {fam: MONO, weight: 700, align: 'center', color: th.sub, ls: 2 * s});
  ctx.fillStyle = col(sp.accent || 'warn'); ctx.fillRect(x - 60 * s * k, y - fs * 0.95, 120 * s * k, 6 * s);
  ctx.restore(); return fs;
}
const FN = {}, TALL = {cutaway: 1, stairs: 1};
const cnt = sp => Math.max(1, (sp.items || sp.steps || sp.bars || sp.nodes || sp.options || []).length);
const PREF_H = {     // preferred content height of a partial card (px at scale s); the card never grows beyond its default box
  checklist: (sp, s) => cnt(sp) * 100 * s + 30 * s, timeline: (sp, s) => cnt(sp) * 118 * s, steps: (sp, s) => cnt(sp) * 118 * s,
  bars: (sp, s) => cnt(sp) * 112 * s, chain: (sp, s) => 330 * s, counter: (sp, s) => 420 * s, card: (sp, s) => 330 * s,
  quiz: (sp, s) => 170 * s + cnt(sp) * 122 * s,
  compare: (sp, s) => 120 * s + Math.max((sp.left && sp.left.items || []).length, (sp.right && sp.right.items || []).length, 1) * 112 * s};
function run(type, env, sp, lt, dur) {
  const {ctx, W, H, portrait} = env, full = sp.full !== false;
  const th = THEMES[sp.bg] || THEMES[(T.story.style || {}).scheme_bg] || (type === 'checklist' && !full ? THEMES.paper : THEMES.blue), s0 = Math.min(W, H) / 1080;
  const outA = sp.out != null && lt > sp.out ? 1 - clamp((lt - sp.out) / 0.25) : 1; if (outA <= 0) return;
  let box, s = s0;
  ctx.save();
  if (full) {
    drawBg(ctx, 0, 0, W, H, th, s, false);
    const z = env.cam ? env.cam.z : 1; ctx.translate(W / 2, H * 0.42); ctx.scale(z, z); ctx.translate(-W / 2, -H * 0.42);
    const tall = (TALL[type] || sp.tall) && portrait;
    titleBlock(ctx, sp, lt, W / 2, (portrait ? 0.125 : 0.1) * H, s, th, W * 0.86);
    box = portrait ? (tall ? {x: 0.07 * W, y: 0.17 * H, w: 0.86 * W, h: 0.405 * H} : {x: 0.07 * W, y: (sp.title ? 0.19 : 0.15) * H, w: 0.86 * W, h: (sp.title ? 0.37 : 0.41) * H})
                   : {x: 0.1 * W, y: (sp.title ? 0.2 : 0.12) * H, w: 0.8 * W, h: (sp.title ? 0.5 : 0.58) * H};    // ends above the landscape captions (0.78 H)
  } else {
    s = s0 * (sp.scale || 0.86);
    const bb = (sp.box || (portrait ? [0.06, 0.115, 0.88, 0.42] : [0.52, 0.1, 0.44, 0.66])).slice();
    if (!sp.box && PREF_H[type]) { const want = PREF_H[type](sp, s) + (sp.title ? (sp.sub ? 148 : 112) * s : 26 * s) + 26 * s; bb[3] = Math.min(bb[3], Math.max(0.16, want / H)); }
    const k = pk(lt, 0, 0.35), x = bb[0] * W, y = bb[1] * H, w = bb[2] * W, h = bb[3] * H, cx = x + w / 2, cy = y + h / 2;
    ctx.globalAlpha *= k * outA; ctx.translate(cx, cy); ctx.scale(0.94 + 0.06 * k, 0.94 + 0.06 * k); ctx.translate(-cx, -cy);
    drawBg(ctx, x, y, w, h, th, s, true);
    let top = y + 26 * s; if (sp.title) { titleBlock(ctx, sp, lt, cx, y + 60 * s, s * 0.82, th, w - 70 * s); top = y + (sp.sub ? 148 : 112) * s; }
    box = {x: x + 34 * s, y: top, w: w - 68 * s, h: y + h - 26 * s - top};
    rr(ctx, x, y, w, h, 30 * s); ctx.clip();
  }
  if (full && outA < 1) ctx.globalAlpha *= outA;
  box.s = s; box.partial = !full; FN[type](ctx, box, sp, lt, dur, th, s, env);
  ctx.restore();
}
// ------------------------------------------------------------------ cutaway: building section (floors, riser, pump, lift)
FN.cutaway = (ctx, b, sp, lt, dur, th, s) => {
  const n = Math.max(2, Math.min(40, sp.floors || 9)), hero = sp.hero_floor != null ? sp.hero_floor : sp.floor != null ? sp.floor : Math.ceil(n * 0.7);
  const power = sp.power !== false, fh = b.h / (n + 1.7), bw = Math.min(b.w * 0.5, Math.max(fh * 7, b.w * 0.36));
  const bx = b.x + b.w * 0.06, roofY = b.y + fh * 0.5, fy = i => roofY + (n - i) * fh, baseY = roofY + n * fh, baseH = fh * 1.15;
  const r = rng(hash2(sp.title || 'cut') + n), lit = []; for (let i = 0; i < n * 3; i++) lit.push(r() > 0.42);
  const lo = sp.lights_out != null ? sp.lights_out : null, sw = Math.max(2, 2.6 * s);
  ctx.lineJoin = 'round';
  // roof + antenna
  const kr = pk(lt, 0.05 + n * Math.min(0.035, 0.7 / n), 0.3);
  ctx.save(); ctx.globalAlpha *= kr; ctx.strokeStyle = th.stroke; ctx.lineWidth = sw; ctx.strokeRect(bx - 6 * s, roofY - fh * 0.22, bw + 12 * s, fh * 0.22);
  ctx.beginPath(); ctx.moveTo(bx + bw * 0.7, roofY - fh * 0.22); ctx.lineTo(bx + bw * 0.7, roofY - fh * 0.62); ctx.moveTo(bx + bw * 0.64, roofY - fh * 0.5); ctx.lineTo(bx + bw * 0.76, roofY - fh * 0.5); ctx.stroke(); ctx.restore();
  // floors cascade bottom -> top
  const pipeX = bx + bw * 0.1, liftX = bx + bw * 0.8, liftW = bw * 0.13;
  for (let i = 1; i <= n; i++) {
    const k = pk(lt, 0.05 + (i - 1) * Math.min(0.035, 0.7 / n), 0.3); if (k <= 0) continue; const y = fy(i);
    ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 12 * s);
    const isHero = i === hero; ctx.fillStyle = isHero ? rgba(UI.warn, 0.22) : th.fill; ctx.fillRect(bx, y, bw, fh);
    ctx.strokeStyle = isHero ? UI.warn : th.stroke; ctx.lineWidth = isHero ? sw * 1.6 : sw; ctx.strokeRect(bx, y, bw, fh);
    const nw = 3, ww = bw * 0.12, wh = fh * 0.48;                        // windows between riser and lift
    for (let j = 0; j < nw; j++) { const wx = bx + bw * (0.24 + j * 0.18), wy = y + fh * 0.24;
      let on = power && lit[(i * 3 + j) % lit.length]; if (lo != null && on) on = lt < lo + (n - i) * 0.05;
      ctx.fillStyle = on ? rgba('#FFB84D', 0.88) : (th.light ? '#C9BFA6' : '#0B1322'); ctx.fillRect(wx, wy, ww, wh);
      if (on) T.h.glow(ctx, wx + ww / 2, wy + wh / 2, ww * 1.1, '#FFB84D', 0.18); }
    if (isHero) { const hx = bx + bw * (0.24 + 0.18) + ww / 2, hy = y + fh * 0.62;   // tiny resident in the hero window
      ctx.fillStyle = UI.warn; ell(ctx, hx, hy - fh * 0.2, fh * 0.13, fh * 0.13); ctx.fill(); rr(ctx, hx - fh * 0.14, hy - fh * 0.06, fh * 0.28, fh * 0.2, fh * 0.08); ctx.fill(); }
    if (n <= 16 || i % 5 === 0 || i === 1 || isHero) txt(ctx, String(i), bx - 14 * s, y + fh / 2, Math.min(26 * s, fh * 0.55), {fam: MONO, weight: 700, align: 'right', color: isHero ? UI.warn : th.sub});
    ctx.restore();
  }
  // basement + pump
  const kb = pk(lt, 0.02, 0.3); ctx.save(); ctx.globalAlpha *= kb; ctx.fillStyle = th.light ? '#D6CCB4' : '#0E1A2C'; ctx.fillRect(bx - 6 * s, baseY, bw + 12 * s, baseH);
  ctx.strokeStyle = th.stroke; ctx.lineWidth = sw; ctx.strokeRect(bx - 6 * s, baseY, bw + 12 * s, baseH);
  ctx.setLineDash([10 * s, 8 * s]); ctx.beginPath(); ctx.moveTo(b.x, baseY); ctx.lineTo(b.x + b.w, baseY); ctx.stroke(); ctx.setLineDash([]);
  if (sp.pump !== false) { const px = bx + bw * 0.1, py = baseY + baseH * 0.5, pr = Math.min(baseH * 0.36, 34 * s), pc = power ? UI.ok : UI.danger;
    ell(ctx, px, py, pr, pr); ctx.fillStyle = rgba(pc, 0.2); ctx.fill(); ctx.strokeStyle = pc; ctx.lineWidth = sw; ctx.stroke(); T.icon(ctx, power ? 'tap' : 'bolt', px, py, pr * 1.2, pc);
    txt(ctx, sp.pump_label || 'НАСОС', px + pr * 1.5, py, Math.min(24 * s, baseH * 0.4), {fam: MONO, weight: 700, color: pc});
    if (!power) badge(ctx, px + pr * 0.85, py - pr * 0.8, pr * 0.42, 'no'); }
  ctx.restore();
  // riser pipe with water up to sp.water_to
  if (sp.water_to != null || sp.riser) {
    const yTop = roofY + fh * 0.2, yBot = baseY + baseH * 0.5; ctx.save(); ctx.lineCap = 'round';
    ctx.strokeStyle = th.empty; ctx.lineWidth = 12 * s; ctx.beginPath(); ctx.moveTo(pipeX, yBot); ctx.lineTo(pipeX, yTop); ctx.stroke();
    const wt = clamp(sp.water_to == null ? n : sp.water_to, 0, n), target = wt >= n ? yTop : fy(wt) + fh * 0.1, kw = E.io(clamp((lt - (sp.water_t == null ? 0.6 : sp.water_t)) / (sp.water_dur || 1.3)));
    const wf = sp.water_from != null ? clamp(sp.water_from, 0, n) : null, yStart = wf == null || wf <= 0 ? yBot : wf >= n ? yTop : fy(wf) + fh * 0.1;   // water_from: level drains from there
    const yW = lerp(yStart, target, kw); ctx.strokeStyle = th.water; ctx.lineWidth = 12 * s; ctx.beginPath(); ctx.moveTo(pipeX, yBot); ctx.lineTo(pipeX, yW); ctx.stroke();
    T.h.glow(ctx, pipeX, yW, 26 * s, th.water, 0.5);
    for (let q = 0; q < 4; q++) { const yy = lerp(yBot, yW, ((lt * 0.8 + q / 4) % 1)); ctx.fillStyle = 'rgba(255,255,255,0.75)'; ell(ctx, pipeX, yy, 3 * s, 5 * s); ctx.fill(); }
    if (wt < n && kw > 0.95) { const yy = fy(Math.min(n, wt + 1)) + fh * 0.5; badge(ctx, pipeX, yy, Math.min(16 * s, fh * 0.4), 'no'); }
    ctx.restore();
  }
  // lift shaft + cabin
  if (sp.lift_at != null) {
    ctx.save(); ctx.strokeStyle = th.sub; ctx.lineWidth = sw * 0.8; ctx.setLineDash([6 * s, 6 * s]); ctx.strokeRect(liftX, roofY, liftW, baseY - roofY); ctx.setLineDash([]);
    const la = clamp(sp.lift_at, 1, n), ly = power ? lerp(fy(1), fy(la), E.io(clamp(lt / Math.max(1, dur * 0.6)))) : fy(la);
    const lc = power ? UI.ok : UI.danger; rr(ctx, liftX + 3 * s, ly + fh * 0.1, liftW - 6 * s, fh * 0.8, 6 * s); ctx.fillStyle = rgba(lc, 0.3); ctx.fill(); ctx.strokeStyle = lc; ctx.lineWidth = sw; ctx.stroke();
    if (!power) txt(ctx, '!', liftX + liftW / 2, ly + fh * 0.52, fh * 0.55, {weight: 800, align: 'center', color: lc});
    ctx.restore();
  }
  // vent shaft: smell / smoke puffs spread from the hero floor to the whole riser
  if (sp.vent) {
    const vx = bx + bw * 0.92, yTop = roofY, yBot = baseY; ctx.save(); ctx.strokeStyle = th.sub; ctx.lineWidth = sw; ctx.setLineDash([8 * s, 6 * s]);
    ctx.strokeRect(vx - bw * 0.04, yTop, bw * 0.08, yBot - yTop); ctx.setLineDash([]);
    const y0 = fy(hero) + fh / 2, kv = clamp((lt - (sp.vent_t == null ? 0.5 : sp.vent_t)) / 1.6), vc = col(sp.vent_color || 'warn');
    for (let q = 0; q < 14; q++) { const ph = ((lt * 0.35 + q / 14) % 1), dirUp = q % 2, reach = kv * (dirUp ? y0 - yTop : yBot - y0);
      const yy = y0 + (dirUp ? -1 : 1) * ph * reach, r = (8 + 10 * ph) * s; ctx.fillStyle = rgba(vc, 0.55 * (1 - ph) * clamp(kv * 3)); ell(ctx, vx + Math.sin(q * 2 + lt * 3) * 6 * s, yy, r, r); ctx.fill();
      if (ph > 0.5 && kv > 0.3) { const fl = Math.round((n - (yy - roofY) / fh) + 0.5); if (fl >= 1 && fl <= n && fl !== hero) { ctx.fillStyle = rgba(vc, 0.10); ctx.fillRect(bx, fy(fl), bw, fh); } } }
    ctx.restore();
  }
  // labels: plates on the right with leader lines; pushed apart so they never overlap
  const L = (sp.labels || []).map((l, i) => Object.assign({i}, typeof l === 'string' ? {text: l, floor: hero} : l)).filter(l => l.text);
  if (!L.length && sp.hero_label !== false) L.push({text: sp.hero_label || `${hero} ЭТАЖ`, floor: hero, color: 'warn', sub: sp.hero_sub, i: 0});
  const lx = bx + bw + 46 * s, rowH = 96 * s; let lastY = -1e9;
  L.map(l => Object.assign(l, {y0: l.floor === 0 ? baseY + baseH / 2 : fy(clamp(l.floor || hero, 1, n)) + fh / 2})).sort((a, c) => a.y0 - c.y0).forEach(l => {
    l.y = Math.max(l.y0, lastY + rowH); lastY = l.y; });
  L.forEach((l, j) => { const k = pk(lt, l.t != null ? l.t : 0.9 + j * 0.25, 0.32); if (k <= 0) return; const c = col(l.color || 'warn');
    ctx.save(); ctx.globalAlpha *= k; ctx.strokeStyle = c; ctx.lineWidth = 3 * s; ctx.beginPath(); ctx.moveTo(bx + bw + 4 * s, l.y0); ctx.lineTo(lx - 14 * s, l.y); ctx.stroke();
    ell(ctx, bx + bw + 4 * s, l.y0, 7 * s, 7 * s); ctx.fillStyle = c; ctx.fill(); ctx.translate((1 - k) * 30 * s, 0);
    const maxW = b.x + b.w - lx; const pl = plate(ctx, l.text, l.sub, lx, l.y, s * Math.min(1, maxW / (measure(ctx, UP(l.text), 34 * s, SANS, 800) + 140 * s)), th, {color: l.color || 'warn', icon: l.icon});
    ctx.restore(); });
};
function hash2(str) { let h = 7; for (const ch of String(str)) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return h; }

// ------------------------------------------------------------------ stairs: zigzag flights, moving red dots, floor counter
FN.stairs = (ctx, b, sp, lt, dur, th, s) => {
  const m = Math.max(2, sp.flights || 6), from = sp.from == null ? 1 : sp.from, to = sp.to == null ? from + m : sp.to, down = sp.dir === 'down';
  const left = b.x + b.w * 0.06, right = b.x + b.w * 0.56, top = b.y + b.h * 0.04, bot = b.y + b.h * 0.96, fl = (bot - top) / m, land = b.w * 0.06;
  const path = [[left - land, bot]]; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  for (let i = 0; i < m; i++) { const y0 = bot - i * fl, y1 = y0 - fl, a = i % 2 ? right : left, c = i % 2 ? left : right;
    path.push([a, y0], [c, y1], [c + (i % 2 ? -land : land), y1]); }
  for (let i = 0; i < m; i++) {                          // flights with step teeth, cascade bottom -> top
    const k = pk(lt, 0.05 + i * 0.08, 0.3); if (k <= 0) continue; const y0 = bot - i * fl, y1 = y0 - fl, a = i % 2 ? right : left, c = i % 2 ? left : right, st = 8;
    ctx.save(); ctx.globalAlpha *= k; ctx.strokeStyle = th.stroke; ctx.lineWidth = 3 * s; ctx.beginPath(); ctx.moveTo(a, y0);
    for (let q = 1; q <= st; q++) { const xx = lerp(a, c, q / st), yy = lerp(y0, y1, q / st); ctx.lineTo(xx, lerp(y0, y1, (q - 1) / st)); ctx.lineTo(xx, yy); } ctx.stroke();
    ctx.lineWidth = 5 * s; ctx.beginPath(); ctx.moveTo(c, y1); ctx.lineTo(c + (i % 2 ? -land : land), y1); ctx.stroke();
    const fn = Math.round(lerp(from, to, (i + 1) / m)); txt(ctx, String(fn), c + (i % 2 ? -land - 12 * s : land + 12 * s), y1 - 18 * s, 26 * s, {fam: MONO, weight: 700, align: i % 2 ? 'right' : 'left', color: th.sub});
    ctx.restore();
  }
  const nd = sp.dots == null ? 3 : sp.dots, t0 = sp.t == null ? 0.6 : sp.t, d = Math.max(0.8, (sp.dur || dur - t0 - 0.3)), pg = clamp((lt - t0) / d);
  let lead = 0;
  for (let j = 0; j < nd; j++) { const kk = clamp(E.io(pg) * (1 - j * 0.12)), q = down ? 1 - kk : kk; lead = Math.max(lead, kk);
    if (lt < t0) continue; const [x, y] = pointAt(path, q); const bob = Math.abs(Math.sin(lt * 9 + j)) * 6 * s;
    T.h.glow(ctx, x, y - 18 * s - bob, 40 * s, UI.danger, 0.5); ell(ctx, x, y - 18 * s - bob, 13 * s, 13 * s); ctx.fillStyle = col(sp.color || 'danger'); ctx.fill();
    ctx.strokeStyle = '#FFF'; ctx.lineWidth = 3 * s; ctx.stroke(); }
  const cx = b.x + b.w * 0.81, cy = b.y + b.h * 0.24, k = pk(lt, 0.3, 0.4);
  if (sp.counter !== false && k > 0) { const cur = Math.round(lerp(from, to, down ? 1 - lead : lead)); ctx.save(); ctx.globalAlpha *= k;
    txt(ctx, 'ЭТАЖ', cx, cy - 80 * s, 30 * s, {fam: MONO, weight: 700, align: 'center', color: th.sub, ls: 4 * s});
    txt(ctx, String(down ? Math.round(lerp(to, from, lead)) : cur), cx, cy, 120 * s, {fam: DISPLAY, weight: 900, align: 'center', color: col(sp.color || 'danger')}); ctx.restore(); }
  if (sp.label) { const kl = pk(lt, 0.5, 0.35); ctx.save(); ctx.globalAlpha *= kl; plate(ctx, sp.label, sp.label_sub, cx, cy + 150 * s, s * 0.9, th, {align: 'center', color: sp.color || 'danger', icon: sp.icon || 'stairs'}); ctx.restore(); }
};

// ------------------------------------------------------------------ gauge: tank | battery | dial (+ optional countdown timer)
function timerBox(ctx, x, y, sec, s, th, c) {
  sec = Math.max(0, sec); const mm = String(Math.floor(sec / 60)).padStart(2, '0'), ss = String(Math.floor(sec % 60)).padStart(2, '0'), label = `${mm}:${ss} ОСТ.`;
  const fs = 64 * s, w = measure(ctx, label, fs, MONO, 700) + 60 * s, h = 104 * s, bl = sec < 30 ? 0.6 + 0.4 * Math.sin(sec * 12) : 1;
  rr(ctx, x - w / 2, y - h / 2, w, h, 14 * s); ctx.fillStyle = th.plate; ctx.fill(); ctx.strokeStyle = rgba(c, bl); ctx.lineWidth = 5 * s; ctx.stroke();
  txt(ctx, label, x, y + 3 * s, fs, {fam: MONO, weight: 700, align: 'center', color: rgba(c, bl)});
}
FN.gauge = (ctx, b, sp, lt, dur, th, s) => {
  const kind = sp.kind || 'tank', from = sp.from == null ? 1 : sp.from, to = sp.to == null ? 0.25 : sp.to, t0 = sp.t == null ? 0.45 : sp.t;
  const d = sp.dur || Math.max(0.8, dur - t0 - 0.5), v = lerp(from, to, E.io(clamp((lt - t0) / d)));
  const auto = v < 0.25 ? UI.danger : v < 0.5 ? UI.warn : (kind === 'tank' ? th.water : UI.ok), c = sp.color ? col(sp.color) : auto, k = pk(lt, 0.05, 0.4);
  const hasT = sp.timer != null, ch = hasT ? b.h - 130 * s : b.h, cx = b.x + b.w / 2;
  ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 20 * s);
  const pct = sp.value_text || (Math.round(v * 100) + '%');
  if (kind === 'tank') {
    const tw = Math.min(b.w * 0.38, ch * 0.62), tht = ch * 0.86, tx = cx - tw / 2, ty = b.y + ch * 0.07;
    ctx.save(); rr(ctx, tx, ty, tw, tht, 34 * s); ctx.fillStyle = th.fill; ctx.fill(); ctx.clip();
    const wy = ty + tht * (1 - v); ctx.fillStyle = rgba(c, 0.85); ctx.beginPath(); ctx.moveTo(tx, wy);
    for (let q = 0; q <= 24; q++) { const xx = tx + tw * q / 24; ctx.lineTo(xx, wy + Math.sin(q * 0.8 + lt * 4) * 6 * s); } ctx.lineTo(tx + tw, ty + tht); ctx.lineTo(tx, ty + tht); ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.16)'; ctx.fillRect(tx + tw * 0.12, ty, tw * 0.08, tht);
    for (let q = 0; q < 6; q++) { const bx2 = tx + tw * (0.2 + 0.6 * ((q * 0.37) % 1)), by2 = ty + tht - ((lt * 60 * s + q * 70 * s) % Math.max(1, tht * v)); if (by2 > wy) { ell(ctx, bx2, by2, 5 * s, 5 * s); ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.fill(); } }
    ctx.restore(); rr(ctx, tx, ty, tw, tht, 34 * s); ctx.strokeStyle = th.stroke; ctx.lineWidth = 4 * s; ctx.stroke();
    for (let q = 0; q <= 4; q++) { const yy = ty + tht * (1 - q / 4); ctx.strokeStyle = th.sub; ctx.lineWidth = 3 * s; ctx.beginPath(); ctx.moveTo(tx + tw + 10 * s, yy); ctx.lineTo(tx + tw + 34 * s, yy); ctx.stroke();
      txt(ctx, q * 25 + '%', tx + tw + 44 * s, yy, 24 * s, {fam: MONO, weight: 700, color: th.sub}); }
    txt(ctx, pct, cx, ty + tht * 0.5, 84 * s, {fam: DISPLAY, weight: 900, align: 'center', color: '#FFFFFF', stroke: 10 * s, strokeColor: 'rgba(8,12,20,0.9)'});
    if (sp.label) pill(ctx, UP(sp.label), tx - 20 * s, ty + 40 * s, s, {align: 'right', icon: sp.icon || 'drop', border: c, color: '#FFF', size: 26});
  } else if (kind === 'battery') {
    const bw2 = Math.min(b.w * 0.72, ch * 1.5), bh2 = bw2 * 0.42, bx2 = cx - bw2 / 2, by2 = b.y + ch * 0.5 - bh2 / 2, seg = sp.segments || 5, on = Math.ceil(v * seg - 0.001);
    rr(ctx, bx2, by2, bw2, bh2, 26 * s); ctx.fillStyle = th.fill; ctx.fill(); ctx.strokeStyle = th.stroke; ctx.lineWidth = 6 * s; ctx.stroke();
    rr(ctx, bx2 + bw2, by2 + bh2 * 0.3, 22 * s, bh2 * 0.4, 8 * s); ctx.fillStyle = th.stroke; ctx.fill();
    const g = 12 * s, sw2 = (bw2 - g * (seg + 1)) / seg; for (let q = 0; q < seg; q++) { const lastBlink = q === on - 1 && v < 0.25 ? 0.5 + 0.5 * Math.sin(lt * 10) : 1;
      rr(ctx, bx2 + g + q * (sw2 + g), by2 + g, sw2, bh2 - g * 2, 10 * s); ctx.fillStyle = q < on ? rgba(c, lastBlink) : th.empty; ctx.fill(); }
    txt(ctx, pct, cx, by2 + bh2 + 80 * s, 80 * s, {fam: DISPLAY, weight: 900, align: 'center', color: c});
    if (to > from) T.icon(ctx, 'bolt', cx, by2 - 60 * s, 70 * s, UI.warn);
    if (sp.label) txt(ctx, UP(sp.label), cx, by2 - (to > from ? 130 : 50) * s, 36 * s, {align: 'center', color: th.ink});
  } else {                                                   // dial
    const R = Math.min(b.w * 0.42, ch * 0.75), ox = cx, oy = b.y + ch * 0.82, zones = sp.zones || [[0, 0.5, UI.ok], [0.5, 0.8, UI.warn], [0.8, 1, UI.danger]];
    zones.forEach(([a0, a1, zc]) => { ctx.strokeStyle = col(zc); ctx.lineWidth = 30 * s; ctx.beginPath(); ctx.arc(ox, oy, R, Math.PI + a0 * Math.PI + 0.01, Math.PI + a1 * Math.PI - 0.01); ctx.stroke(); });
    for (let q = 0; q <= 10; q++) { const a = Math.PI + q / 10 * Math.PI; ctx.strokeStyle = th.sub; ctx.lineWidth = 3 * s; ctx.beginPath(); ctx.moveTo(ox + Math.cos(a) * (R - 40 * s), oy + Math.sin(a) * (R - 40 * s)); ctx.lineTo(ox + Math.cos(a) * (R - (q % 5 ? 56 : 70) * s), oy + Math.sin(a) * (R - (q % 5 ? 56 : 70) * s)); ctx.stroke(); }
    const a = Math.PI + clamp(v) * Math.PI + Math.sin(lt * 20) * 0.01; ctx.strokeStyle = th.ink; ctx.lineWidth = 8 * s; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox + Math.cos(a) * (R - 60 * s), oy + Math.sin(a) * (R - 60 * s)); ctx.stroke();
    ell(ctx, ox, oy, 18 * s, 18 * s); ctx.fillStyle = th.ink; ctx.fill();
    const val = sp.min != null && sp.max != null ? (Math.round(lerp(sp.min, sp.max, v) * 10) / 10 + (sp.unit || '')) : pct;
    txt(ctx, String(val), ox, oy - R * 0.38, 70 * s, {fam: DISPLAY, weight: 900, align: 'center', color: zones.reduce((acc, z) => (v >= z[0] ? col(z[2]) : acc), UI.ok)});
    if (sp.label) txt(ctx, UP(sp.label), ox, oy + 50 * s, 32 * s, {fam: MONO, weight: 700, align: 'center', color: th.sub});
  }
  if (hasT) timerBox(ctx, cx, b.y + b.h - 56 * s, sp.timer - Math.max(0, lt - t0) * (sp.rate || 1), s, th, col(sp.timer_color || 'danger'));
  ctx.restore();
};
// ------------------------------------------------------------------ map / radius: top view, rings 1/2/4 KM, points, route
function mapBase(ctx, b, s, th, seed, lt) {
  const r = rng(seed), cell = Math.max(60 * s, Math.min(b.w, b.h) / 7), k = pk(lt, 0, 0.5);
  ctx.save(); ctx.globalAlpha *= 0.9 * k; rr(ctx, b.x, b.y, b.w, b.h, 22 * s); ctx.clip();
  ctx.fillStyle = th.light ? '#ECE3CE' : '#0F223A'; ctx.fillRect(b.x, b.y, b.w, b.h);
  for (let gx = b.x; gx < b.x + b.w; gx += cell) for (let gy = b.y; gy < b.y + b.h; gy += cell) {
    const v = r(); if (v < 0.1) continue; const pad = cell * 0.14;
    ctx.fillStyle = v < 0.2 ? rgba(UI.ok, th.light ? 0.25 : 0.13) : (th.light ? '#DCD1B8' : '#16304F');
    rr(ctx, gx + pad, gy + pad, cell - pad * 2, cell - pad * 2, 8 * s); ctx.fill(); }
  ctx.strokeStyle = th.light ? 'rgba(255,255,255,0.9)' : 'rgba(150,190,240,0.20)'; ctx.lineWidth = 12 * s;    // two main roads
  ctx.beginPath(); ctx.moveTo(b.x, b.y + b.h * 0.62); ctx.lineTo(b.x + b.w, b.y + b.h * 0.48); ctx.moveTo(b.x + b.w * 0.36, b.y); ctx.lineTo(b.x + b.w * 0.44, b.y + b.h); ctx.stroke();
  ctx.strokeStyle = rgba(th.water, 0.55); ctx.lineWidth = 18 * s; ctx.beginPath(); ctx.moveTo(b.x + b.w, b.y + b.h * 0.1);   // river
  ctx.bezierCurveTo(b.x + b.w * 0.75, b.y + b.h * 0.3, b.x + b.w * 0.95, b.y + b.h * 0.7, b.x + b.w * 0.7, b.y + b.h); ctx.stroke();
  ctx.restore();
}
FN.map = (ctx, b, sp, lt, dur, th, s) => {
  mapBase(ctx, b, s, th, hash2(sp.title || 'map'), lt);
  const P = f => [b.x + f[0] * b.w, b.y + f[1] * b.h], c = P(sp.center || [0.5, 0.5]), Rmax = Math.min(b.w, b.h) * 0.47;
  const rings = (sp.rings || []).map((r, i) => (typeof r === 'number' ? {r, label: r + ' ' + (sp.unit || 'КМ')} : r));
  const maxR = Math.max(1, ...rings.map(r => r.r)), RC = [UI.danger, '#FF8A3D', UI.warn, UI.blue];
  ctx.save(); ctx.beginPath(); ctx.rect(b.x, b.y, b.w, b.h); ctx.clip();
  rings.slice().reverse().forEach((rg, jj) => { const j = rings.length - 1 - jj, k = pk(lt, (rg.t != null ? rg.t : 0.35 + j * 0.35), 0.55); if (k <= 0) return;
    const R = Rmax * rg.r / maxR * k, cc = col(rg.color || RC[j % RC.length]);
    ell(ctx, c[0], c[1], R, R); ctx.fillStyle = rgba(cc, 0.09); ctx.fill(); ctx.strokeStyle = cc; ctx.lineWidth = 4 * s; ctx.setLineDash(j ? [16 * s, 10 * s] : []); ctx.stroke(); ctx.setLineDash([]); });
  ctx.restore();
  rings.forEach((rg, j) => { const k = pk(lt, (rg.t != null ? rg.t : 0.35 + j * 0.35) + 0.35, 0.3); if (k <= 0) return; const R = Rmax * rg.r / maxR, a = -Math.PI / 4 - j * 0.18;
    ctx.save(); ctx.globalAlpha *= k; pill(ctx, UP(rg.label), c[0] + Math.cos(a) * R, c[1] + Math.sin(a) * R, s, {border: col(rg.color || RC[j % RC.length]), size: 26}); ctx.restore(); });
  if (sp.route && sp.route.length > 1) {
    const pts = sp.route.map(P), t0 = sp.route_t == null ? 0.5 : sp.route_t, kd = E.io(clamp((lt - t0) / (sp.route_dur || Math.max(0.8, dur - t0 - 0.5))));
    ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = rgba('#000000', 0.35); ctx.lineWidth = 14 * s; partial(ctx, pts, kd);
    ctx.strokeStyle = col(sp.route_color || 'warn'); ctx.lineWidth = 8 * s; ctx.setLineDash([18 * s, 12 * s]); ctx.lineDashOffset = -lt * 50 * s; partial(ctx, pts, kd); ctx.setLineDash([]);
    if (lt >= t0) { const [hx, hy] = pointAt(pts, kd); T.h.glow(ctx, hx, hy, 50 * s, UI.warn, 0.5); ell(ctx, hx, hy, 16 * s, 16 * s); ctx.fillStyle = col(sp.route_color || 'warn'); ctx.fill();
      ctx.strokeStyle = '#FFF'; ctx.lineWidth = 4 * s; ctx.stroke(); }
    ctx.restore();
  }
  const kc = bk(lt, 0.15); if (kc > 0 && sp.center !== false) { const pr = 34 * s * kc, pulse = (lt * 0.8) % 1;
    ell(ctx, c[0], c[1], pr * (1 + pulse * 1.6), pr * (1 + pulse * 1.6)); ctx.strokeStyle = rgba(UI.warn, 0.6 * (1 - pulse)); ctx.lineWidth = 3 * s; ctx.stroke();
    ell(ctx, c[0], c[1], pr, pr); ctx.fillStyle = col(sp.center_color || 'warn'); ctx.fill(); T.icon(ctx, sp.center_icon || 'house', c[0], c[1], pr * 1.1, '#141821');
    if (sp.center_label) pill(ctx, UP(sp.center_label), c[0], c[1] + pr + 34 * s, s, {size: 24}); }
  (sp.points || []).forEach((p, j) => { const k = bk(lt, p.t != null ? p.t : 0.8 + j * 0.2); if (k <= 0) return; const [x, y] = P(p.at || [0.5, 0.5]), cc = col(p.color || 'danger'), pr = 26 * s * k;
    ctx.save(); ell(ctx, x, y, pr, pr); ctx.fillStyle = cc; ctx.fill(); ctx.strokeStyle = '#FFF'; ctx.lineWidth = 3 * s; ctx.stroke(); T.icon(ctx, p.icon || 'warning', x, y, pr * 1.1, '#FFF');
    if (p.label) pill(ctx, UP(p.label), x + (x > b.x + b.w * 0.6 ? -pr - 10 * s : pr + 10 * s), y, s, {align: x > b.x + b.w * 0.6 ? 'right' : 'left', border: cc, size: 24, alpha: clamp(k)});
    ctx.restore(); });
};
FN.radius = (ctx, b, sp, lt, dur, th, s) => FN.map(ctx, b, Object.assign({rings: [1, 2, 4]}, sp), lt, dur, th, s);

// ------------------------------------------------------------------ chain: cause -> effect nodes, flow dots, optional broken link
FN.chain = (ctx, b, sp, lt, dur, th, s) => {
  const nodes = (sp.nodes || [{icon: 'bolt', text: 'Сеть'}, {icon: 'house', text: 'Дом'}, {icon: 'tap', text: 'Насос'}, {icon: 'drop', text: 'Вода'}]).map(n => (typeof n === 'string' ? {text: n} : n));
  const n = nodes.length, vert = sp.dir === 'down' || (n > 5 && b.h > b.w * 0.8);
  const step = Math.min(0.5, (dur * 0.55) / n), bi = sp.broken, tb = sp.break_t != null ? sp.break_t : Math.min(dur - 0.9, 0.25 + n * step + 0.3);
  const gap = (vert ? b.h : b.w) / n, R = Math.min(gap * (vert ? 0.3 : 0.34), (vert ? b.w * 0.16 : b.h * 0.2)), P = [];
  for (let i = 0; i < n; i++) P.push(vert ? [b.x + b.w * 0.3, b.y + gap * (i + 0.5)] : [b.x + gap * (i + 0.5), b.y + b.h * 0.42]);
  const broken = bi != null && lt >= tb, kb = bi != null ? bk(lt, tb, 0.45) : 0;
  for (let i = 0; i < n - 1; i++) {                            // arrows + flow
    const t0 = 0.2 + i * step + step * 0.45, k = E.out(clamp((lt - t0) / (step * 0.6))); if (k <= 0) continue;
    const a = P[i], c2 = P[i + 1], ang = Math.atan2(c2[1] - a[1], c2[0] - a[0]), sx = a[0] + Math.cos(ang) * (R + 12 * s), sy = a[1] + Math.sin(ang) * (R + 12 * s);
    const ex = c2[0] - Math.cos(ang) * (R + 18 * s), ey = c2[1] - Math.sin(ang) * (R + 18 * s), isB = broken && i === bi, dead = broken && i > bi;
    const cc = isB ? UI.danger : dead ? th.empty : col(sp.color || th.line);
    ctx.save(); ctx.strokeStyle = cc; ctx.fillStyle = cc; ctx.lineWidth = 6 * s; ctx.lineCap = 'round'; if (isB) ctx.setLineDash([12 * s, 12 * s]);
    const hx = lerp(sx, ex, k), hy = lerp(sy, ey, k); ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(hx, hy); ctx.stroke(); ctx.setLineDash([]); head(ctx, hx, hy, ang, 22 * s);
    if (!broken || i < bi) for (let q = 0; q < 3; q++) { const f = (lt * 0.9 + q / 3) % 1; if (k < 1) break; ell(ctx, lerp(sx, ex, f), lerp(sy, ey, f), 6 * s, 6 * s); ctx.fillStyle = '#FFFFFF'; ctx.fill(); }
    if (isB && kb > 0) { const mx = (sx + ex) / 2, my = (sy + ey) / 2; T.h.glow(ctx, mx, my, 70 * s, UI.danger, 0.6 * clamp(kb)); badge(ctx, mx, my, 26 * s * kb, 'no'); }
    ctx.restore();
  }
  nodes.forEach((nd, i) => { const k = bk(lt, 0.2 + i * step); if (k <= 0) return; const [x, y] = P[i], dead = broken && i > bi, cc = dead ? UI.danger : col(nd.color || sp.color || th.line);
    ctx.save(); ctx.globalAlpha *= dead ? 0.55 + 0.45 * (1 - clamp(kb)) : 1; ell(ctx, x, y, R * k, R * k); ctx.fillStyle = th.fill; ctx.fill(); ctx.strokeStyle = cc; ctx.lineWidth = 5 * s; ctx.stroke();
    T.icon(ctx, nd.icon || 'question', x, y, R * 1.0 * k, dead ? th.sub : th.ink);
    const fs = Math.min(30 * s, (vert ? b.w * 0.5 : gap * 0.9) / Math.max(4, UP(nd.text).length) * 1.6);
    if (vert) { txt(ctx, UP(nd.text), x + R + 28 * s, y - (nd.sub ? 16 * s : 0), Math.max(fs, 26 * s), {color: th.ink}); if (nd.sub) txt(ctx, nd.sub, x + R + 28 * s, y + 24 * s, 24 * s, {fam: BODY, weight: 700, color: th.sub}); }
    else { txt(ctx, UP(nd.text), x, y + R + 36 * s, fs, {align: 'center', color: th.ink}); if (nd.sub) txt(ctx, nd.sub, x, y + R + 74 * s, Math.min(24 * s, fs * 0.85), {fam: BODY, weight: 700, align: 'center', color: th.sub}); }
    if (dead && kb > 0) badge(ctx, x + R * 0.72, y - R * 0.72, 16 * s * clamp(kb), 'no');
    ctx.restore(); });
};

// ------------------------------------------------------------------ topview: floor plan, windows, zones, marks, walking path
FN.topview = (ctx, b, sp, lt, dur, th, s) => {
  const rooms = sp.rooms || [{x: 0, y: 0, w: 0.58, h: 0.62, label: 'Комната'}, {x: 0.58, y: 0, w: 0.42, h: 0.38, label: 'Кухня'}, {x: 0.58, y: 0.38, w: 0.42, h: 0.24, label: 'Ванная'},
    {x: 0, y: 0.62, w: 1, h: 0.38, label: 'Прихожая'}];
  const asp = sp.aspect || 1.25; let pw = b.w, ph = pw / asp; if (ph > b.h) { ph = b.h; pw = ph * asp; }
  const px = b.x + (b.w - pw) / 2, py = b.y + (b.h - ph) / 2, P = f => [px + f[0] * pw, py + f[1] * ph], kd = E.out(clamp((lt - 0.05) / 0.7));
  ctx.save(); ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  ctx.fillStyle = th.fill; ctx.globalAlpha *= clamp(kd * 2); ctx.fillRect(px, py, pw, ph); ctx.globalAlpha = 1 * (ctx.globalAlpha > 0 ? 1 : 0);
  (sp.zones || []).forEach((z, j) => { const k = pk(lt, z.t != null ? z.t : 0.6 + j * 0.2, 0.4); if (k <= 0) return; const cc = col(z.color || 'danger');
    ctx.save(); ctx.globalAlpha *= k * (0.75 + 0.25 * Math.sin(lt * 4)); ctx.fillStyle = rgba(cc, 0.22); ctx.fillRect(px + z.x * pw, py + z.y * ph, z.w * pw, z.h * ph);
    ctx.strokeStyle = cc; ctx.lineWidth = 3 * s; ctx.setLineDash([10 * s, 8 * s]); ctx.strokeRect(px + z.x * pw, py + z.y * ph, z.w * pw, z.h * ph); ctx.setLineDash([]);
    if (z.label) pill(ctx, UP(z.label), px + (z.x + z.w / 2) * pw, py + (z.y + z.h / 2) * ph, s, {border: cc, size: 22}); ctx.restore(); });
  ctx.strokeStyle = th.stroke; ctx.lineWidth = 5 * s;
  rooms.forEach((rm, j) => { const pts = [P([rm.x, rm.y]), P([rm.x + rm.w, rm.y]), P([rm.x + rm.w, rm.y + rm.h]), P([rm.x, rm.y + rm.h]), P([rm.x, rm.y])]; partial(ctx, pts, clamp(kd * 1.2 - j * 0.05));
    if (rm.label) { const k = pk(lt, 0.5 + j * 0.08, 0.3); ctx.save(); ctx.globalAlpha *= k; txt(ctx, UP(rm.label), px + (rm.x + rm.w / 2) * pw, py + (rm.y + rm.h / 2) * ph, 24 * s, {fam: MONO, weight: 700, align: 'center', color: th.sub, ls: 2 * s}); ctx.restore(); } });
  ctx.lineWidth = 12 * s; ctx.strokeRect(px, py, pw * Math.min(1, kd * 1.1), ph * Math.min(1, kd * 1.1));
  (sp.windows || [[0.12, 0, 0.42, 0], [0.66, 0, 0.9, 0]]).forEach(w => { const a = P([w[0], w[1]]), c2 = P([w[2], w[3]]); ctx.strokeStyle = '#8FD0FF'; ctx.lineWidth = 12 * s; ctx.globalAlpha = clamp(kd * 1.5 - 0.3);
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(c2[0], c2[1]); ctx.stroke(); ctx.globalAlpha = 1; });
  (sp.doors || [[0.2, 1]]).forEach(dd => { const [x, y] = P(dd); ctx.fillStyle = th.bg[0]; ctx.fillRect(x - 34 * s, y - 8 * s, 68 * s, 16 * s);
    ctx.strokeStyle = th.sub; ctx.lineWidth = 3 * s; ctx.beginPath(); ctx.arc(x - 34 * s, y, 68 * s, -Math.PI / 2, 0); ctx.stroke(); });
  (sp.marks || []).forEach((m, j) => { const k = bk(lt, m.t != null ? m.t : 0.8 + j * 0.18); if (k <= 0) return; const [x, y] = P(m.at || [0.5, 0.5]), cc = col(m.color || 'warn'), r = 24 * s * k;
    ell(ctx, x, y, r, r); ctx.fillStyle = cc; ctx.fill(); ctx.strokeStyle = '#FFF'; ctx.lineWidth = 3 * s; ctx.stroke(); T.icon(ctx, m.icon || 'warning', x, y, r * 1.1, '#141821');
    if (m.label) pill(ctx, UP(m.label), x, y - r - 28 * s, s, {border: cc, size: 22, alpha: clamp(k)}); });
  if (sp.path && sp.path.length > 1) { const pts = sp.path.map(P), t0 = sp.path_t == null ? 0.9 : sp.path_t, kp = E.io(clamp((lt - t0) / (sp.path_dur || Math.max(0.8, dur - t0 - 0.4))));
    ctx.strokeStyle = col(sp.path_color || 'warn'); ctx.lineWidth = 5 * s; ctx.setLineDash([12 * s, 10 * s]); partial(ctx, pts, kp); ctx.setLineDash([]);
    if (lt >= t0) { const [x, y] = pointAt(pts, kp); T.h.glow(ctx, x, y, 46 * s, UI.warn, 0.55); ell(ctx, x, y, 17 * s, 17 * s); ctx.fillStyle = col(sp.path_color || 'warn'); ctx.fill(); ctx.strokeStyle = '#141821'; ctx.lineWidth = 4 * s; ctx.stroke(); } }
  ctx.restore();
};
// ------------------------------------------------------------------ checklist: paper card, items checked one by one
FN.checklist = (ctx, b, sp, lt, dur, th, s) => {
  const items = (sp.items || []).map(it => (typeof it === 'string' ? {text: it} : it)), n = Math.max(1, items.length);
  const gap = sp.gap || Math.min(0.6, Math.max(0.25, (dur - 0.9) / n)), rowH = Math.min(96 * s, (b.h - 40 * s) / n), cw = b.w * 0.94, chH = rowH * n + 40 * s;
  const plain = b.partial && sp.paper !== true, cx = b.x + (b.w - cw) / 2, cy = plain ? b.y : b.y + (b.h - chH) / 2, onPaper = th.light, k0 = pk(lt, 0.05, 0.35);
  const ink = plain && !th.light ? '#FFFFFF' : '#141821';
  ctx.save(); ctx.globalAlpha *= k0; ctx.translate(b.x + b.w / 2, b.y + b.h / 2); ctx.rotate((plain ? 0 : sp.rot == null ? -1.2 : sp.rot) * Math.PI / 180); ctx.translate(-b.x - b.w / 2, -b.y - b.h / 2 + (1 - k0) * 30 * s);
  if (!plain) { ctx.shadowColor = 'rgba(0,0,0,0.35)'; ctx.shadowBlur = 30 * s; ctx.shadowOffsetY = 10 * s; ctx.fillStyle = onPaper ? '#FFFDF7' : UI.paper; ctx.fillRect(cx, cy, cw, chH); ctx.shadowColor = 'transparent';
    ctx.strokeStyle = 'rgba(229,57,53,0.35)'; ctx.lineWidth = 2 * s; ctx.beginPath(); ctx.moveTo(cx + 92 * s, cy); ctx.lineTo(cx + 92 * s, cy + chH); ctx.stroke();     // margin line
    ctx.fillStyle = 'rgba(255,255,255,0.55)'; ctx.save(); ctx.translate(cx + cw / 2, cy - 4 * s); ctx.rotate(0.03); ctx.fillRect(-70 * s, -16 * s, 140 * s, 34 * s); ctx.restore(); }   // tape
  ctx.strokeStyle = plain ? th.empty : 'rgba(47,109,181,0.18)'; ctx.lineWidth = 2 * s; for (let i = 1; i < n; i++) { ctx.beginPath(); ctx.moveTo(cx + 24 * s, cy + 20 * s + i * rowH); ctx.lineTo(cx + cw - 24 * s, cy + 20 * s + i * rowH); ctx.stroke(); }
  items.forEach((it, i) => { const ti = (it.t != null ? it.t : 0.3 + i * gap), k = pk(lt, ti, 0.3); if (k <= 0) return; const y = cy + 20 * s + rowH * (i + 0.5), bxx = cx + 30 * s, bs = Math.min(44 * s, rowH * 0.56);
    ctx.save(); ctx.globalAlpha *= k; ctx.translate((1 - k) * 40 * s, 0);
    const kc = clamp((lt - ti - 0.25) / 0.25), bad = it.ok === false;
    if (it.swatch) { const kq = E.back(clamp((lt - ti) / 0.4)); ell(ctx, bxx + bs / 2, y, bs * 0.62 * kq, bs * 0.62 * kq); ctx.fillStyle = col(it.swatch); ctx.fill();
      ctx.strokeStyle = '#FFFFFF'; ctx.lineWidth = 4 * s; ctx.stroke(); }
    else { ctx.strokeStyle = ink; ctx.lineWidth = 4 * s; rr(ctx, bxx, y - bs / 2, bs, bs, 6 * s); ctx.stroke(); }
    if (kc > 0 && !it.swatch) { ctx.strokeStyle = bad ? UI.danger : '#1E9E5A'; ctx.lineWidth = 7 * s; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      if (bad) { partial(ctx, [[bxx + bs * 0.2, y - bs * 0.3], [bxx + bs * 0.8, y + bs * 0.3]], kc * 2); if (kc > 0.5) partial(ctx, [[bxx + bs * 0.8, y - bs * 0.3], [bxx + bs * 0.2, y + bs * 0.3]], (kc - 0.5) * 2); }
      else partial(ctx, [[bxx + bs * 0.12, y], [bxx + bs * 0.42, y + bs * 0.32], [bxx + bs * 1.0, y - bs * 0.5]], kc); }
    const tx = cx + 116 * s, maxW = cw - 140 * s - (it.note ? 150 * s : 0), label = sp.caps === false ? it.text : UP(it.text), fs = fit(ctx, label, maxW, Math.min(40 * s, rowH * 0.42), SANS, 800);
    txt(ctx, label, tx, y + 2 * s, fs, {color: bad ? '#7A7F8A' : ink});
    if (bad && kc >= 1) { ctx.strokeStyle = rgba(UI.danger, 0.85); ctx.lineWidth = 4 * s; ctx.beginPath(); ctx.moveTo(tx - 6 * s, y + 2 * s); ctx.lineTo(tx + measure(ctx, label, fs) + 6 * s, y + 2 * s); ctx.stroke(); }
    if (it.note) txt(ctx, UP(it.note), cx + cw - 30 * s, y + 2 * s, 28 * s, {fam: MONO, weight: 700, align: 'right', color: col(it.color || (bad ? 'danger' : 'blue'))});
    ctx.restore(); });
  ctx.restore();
};

// ------------------------------------------------------------------ compare: two columns (НЕЛЬЗЯ / МОЖНО, ДО / ПОСЛЕ)
FN.compare = (ctx, b, sp, lt, dur, th, s) => {
  const L = Object.assign({title: 'Нельзя', color: 'danger', icon: 'cross'}, sp.left || {}), R = Object.assign({title: 'Можно', color: 'ok', icon: 'check'}, sp.right || {});
  const nmax = Math.max(1, (L.items || []).length, (R.items || []).length); s *= clamp((b.h - 112 * s) / nmax / (120 * s), 1, 1.35);
  const cw = b.w * 0.48, gapT = Math.min(0.5, (dur - 1) / Math.max(2, (L.items || []).length + (R.items || []).length));
  [[L, b.x, 0], [R, b.x + b.w - cw, 1]].forEach(([C, x, side]) => {
    const cc = col(C.color), kh = bk(lt, 0.1 + side * 0.12), hh = 92 * s; if (kh <= 0) return;
    ctx.save(); ctx.globalAlpha *= clamp(kh); rr(ctx, x, b.y, cw, hh, 18 * s); ctx.fillStyle = cc; ctx.fill();
    T.icon(ctx, C.icon, x + 50 * s, b.y + hh / 2, 46 * s, '#FFFFFF'); txt(ctx, UP(C.title), x + 88 * s, b.y + hh / 2 + 2 * s, fit(ctx, UP(C.title), cw - 110 * s, 40 * s), {color: '#FFFFFF'});
    ctx.restore();
    const items = (C.items || []).map(it => (typeof it === 'string' ? {text: it} : it)), rowH = Math.min(120 * s, (b.h - hh - 20 * s) / Math.max(1, items.length));
    items.forEach((it, i) => { const k = pk(lt, it.t != null ? it.t : 0.45 + (i * 2 + side) * gapT, 0.32); if (k <= 0) return; const y = b.y + hh + 20 * s + rowH * (i + 0.5);
      ctx.save(); ctx.globalAlpha *= k; ctx.translate((1 - k) * (side ? 30 : -30) * s, 0); rr(ctx, x, y - rowH * 0.44, cw, rowH * 0.88, 14 * s); ctx.fillStyle = th.light ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.07)'; ctx.fill();
      ctx.strokeStyle = rgba(cc, 0.55); ctx.lineWidth = 2.5 * s; ctx.stroke(); T.icon(ctx, it.icon || C.icon, x + 40 * s, y, 34 * s, cc);
      const lines = wrap(ctx, it.text, cw - 90 * s, 30 * s, BODY, 700).slice(0, 2); lines.forEach((ln, j) => txt(ctx, ln, x + 72 * s, y + (j - (lines.length - 1) / 2) * 36 * s, 30 * s, {fam: BODY, weight: 700, color: th.ink}));
      ctx.restore(); });
  });
  if (sp.vs !== false) { const k = bk(lt, 0.3); if (k > 0) { const x = b.x + b.w / 2, y = b.y + 46 * s; ell(ctx, x, y, 34 * s * k, 34 * s * k); ctx.fillStyle = th.ink; ctx.fill();
    txt(ctx, 'VS', x, y + 2 * s, 26 * s * k, {fam: DISPLAY, weight: 900, align: 'center', color: th.bg[0]}); } }
};

// ------------------------------------------------------------------ bars: horizontal bars growing in cascade, values counting
FN.bars = (ctx, b, sp, lt, dur, th, s) => {
  const bars = sp.bars || [], n = Math.max(1, bars.length), max = sp.max || Math.max(1, ...bars.map(x => x.value || 0)); s *= clamp(b.h / n / (130 * s), 1, 1.4);
  const rowH = Math.min(130 * s, b.h / n), bw = b.w * 0.78;
  bars.forEach((br, i) => { const t0 = br.t != null ? br.t : 0.3 + i * Math.min(0.35, (dur - 1) / n), k = E.outq(clamp((lt - t0) / 0.8)), ka = pk(lt, t0 - 0.1, 0.25); if (ka <= 0) return;
    const y = b.y + rowH * i + rowH * 0.3, hi = sp.hi === i || br.hi, cc = col(br.color || (hi ? 'warn' : th.line)), v = (br.value || 0) * k;
    ctx.save(); ctx.globalAlpha *= ka; txt(ctx, UP(br.label), b.x, y, 30 * s, {color: th.ink});
    rr(ctx, b.x, y + 24 * s, bw, 42 * s, 21 * s); ctx.fillStyle = th.empty; ctx.fill(); rr(ctx, b.x, y + 24 * s, Math.max(42 * s, bw * v / max), 42 * s, 21 * s); ctx.fillStyle = cc; ctx.fill();
    if (hi) T.h.glow(ctx, b.x + bw * v / max, y + 45 * s, 60 * s, cc, 0.4);
    const vt = (sp.prefix || '') + (sp.decimals ? v.toFixed(sp.decimals).replace('.', ',') : Math.round(v)) + (br.unit || sp.unit || ''); txt(ctx, vt, b.x + Math.max(42 * s, bw * v / max) + 18 * s, y + 46 * s, 36 * s, {fam: MONO, weight: 700, color: cc});
    ctx.restore(); });
};

// ------------------------------------------------------------------ counter: one big number counting up/down
FN.counter = (ctx, b, sp, lt, dur, th, s) => {
  const t0 = sp.t == null ? 0.25 : sp.t, d = sp.dur || Math.max(0.6, Math.min(2.2, dur - t0 - 0.6)), p = E.out(clamp((lt - t0) / d)), v = lerp(sp.from || 0, sp.to == null ? 100 : sp.to, p);
  const cx = b.x + b.w / 2, cy = b.y + b.h * 0.5, cc = col(sp.color || 'warn'), k = bk(lt, 0.05);
  const num = (sp.prefix || '') + (sp.decimals ? v.toFixed(sp.decimals).replace('.', ',') : String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')) + (sp.suffix || '');
  ctx.save(); ctx.globalAlpha *= clamp(k); ctx.translate(cx, cy); ctx.scale(0.85 + 0.15 * k, 0.85 + 0.15 * k); ctx.translate(-cx, -cy);
  if (sp.ring !== false) { const R = Math.min(b.w, b.h) * 0.44; ctx.strokeStyle = th.empty; ctx.lineWidth = 16 * s; ell(ctx, cx, cy, R, R); ctx.stroke();
    ctx.strokeStyle = cc; ctx.lineCap = 'round'; ctx.beginPath(); ctx.arc(cx, cy, R, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * p * (sp.ring_k || 1)); ctx.stroke(); }
  const fs = fit(ctx, num, Math.min(b.w, b.h) * 0.8, 170 * s, DISPLAY, 900); txt(ctx, num, cx, cy + 6 * s, fs, {fam: DISPLAY, weight: 900, align: 'center', color: cc});
  if (sp.label) txt(ctx, UP(sp.label), cx, cy - fs * 0.85, 34 * s, {align: 'center', color: th.ink, ls: 3 * s});
  if (sp.unit_label) txt(ctx, UP(sp.unit_label), cx, cy + fs * 0.85, 30 * s, {fam: MONO, weight: 700, align: 'center', color: th.sub, ls: 2 * s});
  if (sp.icon) T.icon(ctx, sp.icon, cx, cy - fs * 0.85 - 70 * s, 64 * s, cc);
  ctx.restore();
};

// ------------------------------------------------------------------ quiz: question + 2-4 options, countdown bar, reveal
FN.quiz = (ctx, b, sp, lt, dur, th, s) => {
  const opts = sp.options || ['Да', 'Нет'], n = opts.length, ans = sp.answer || 0, rv = sp.reveal != null ? sp.reveal : Math.max(1.2, dur * 0.62), L = 'ABCD';
  const ql = wrap(ctx, UP(sp.question || ''), b.w, 48 * s).slice(0, 3), qh = ql.length * 58 * s; const kq = pk(lt, 0.05, 0.3);
  ctx.save(); ctx.globalAlpha *= kq; ql.forEach((ln, i) => txt(ctx, ln, b.x + b.w / 2, b.y + 30 * s + i * 58 * s, 48 * s, {align: 'center', color: th.ink})); ctx.restore();
  const top = b.y + qh + 40 * s, oh = Math.min(104 * s, (b.y + b.h - top - 40 * s) / n - 18 * s);
  if (lt < rv) { const kk = clamp((lt - 0.4) / Math.max(0.3, rv - 0.4)); rr(ctx, b.x, top - 6 * s, b.w, 10 * s, 5 * s); ctx.fillStyle = th.empty; ctx.fill();
    rr(ctx, b.x, top - 6 * s, b.w * (1 - kk), 10 * s, 5 * s); ctx.fillStyle = col('warn'); ctx.fill(); }
  opts.forEach((o, i) => { const k = bk(lt, 0.3 + i * 0.12); if (k <= 0) return; const y = top + 26 * s + i * (oh + 18 * s), rev = lt >= rv, good = i === ans, kr = rev ? bk(lt, rv, 0.4) : 0;
    ctx.save(); ctx.globalAlpha *= clamp(k) * (rev && !good ? 0.45 : 1); const cx = b.x + b.w / 2, cy = y + oh / 2, sc2 = (0.9 + 0.1 * clamp(k)) * (good ? 1 + 0.05 * Math.sin(clamp(kr) * Math.PI) : 1);
    ctx.translate(cx, cy); ctx.scale(sc2, sc2); ctx.translate(-cx, -cy);
    rr(ctx, b.x, y, b.w, oh, 18 * s); ctx.fillStyle = rev && good ? UI.ok : (th.light ? '#FFFFFF' : 'rgba(255,255,255,0.08)'); ctx.fill();
    ctx.strokeStyle = rev ? (good ? UI.ok : rgba(UI.danger, 0.7)) : rgba(th.line, 0.8); ctx.lineWidth = 3 * s; ctx.stroke();
    ell(ctx, b.x + oh / 2 + 6 * s, cy, oh * 0.32, oh * 0.32); ctx.fillStyle = rev && good ? '#FFFFFF' : col('warn'); ctx.fill();
    txt(ctx, L[i] || String(i + 1), b.x + oh / 2 + 6 * s, cy + 2 * s, oh * 0.34, {fam: DISPLAY, weight: 900, align: 'center', color: '#141821'});
    const label = typeof o === 'string' ? o : o.text; txt(ctx, UP(label), b.x + oh + 20 * s, cy + 2 * s, fit(ctx, UP(label), b.w - oh - 110 * s, 38 * s), {color: rev && good ? '#0B2416' : th.ink});
    if (rev) badge(ctx, b.x + b.w - oh * 0.5, cy, oh * 0.28 * clamp(kr), good ? 'ok' : 'no');
    ctx.restore(); });
};

// ------------------------------------------------------------------ timeline / steps: vertical list with progress line
FN.timeline = (ctx, b, sp, lt, dur, th, s) => {
  const st = (sp.steps || sp.items || []).map(x => (typeof x === 'string' ? {text: x} : x)), n = Math.max(1, st.length), numbered = sp.numbered || sp.type === 'steps';
  s *= clamp(b.h / n / (150 * s), 1, 1.4);                                     // few steps in a big box: everything grows
  const rowH = Math.min(150 * s, b.h / n), lx = b.x + 50 * s, gap = Math.min(0.55, Math.max(0.25, (dur - 1) / n)), cur = sp.current == null ? n - 1 : sp.current;
  const yAt = i => b.y + rowH * (i + 0.5), kLine = E.io(clamp((lt - 0.3) / (gap * (cur + 1))));
  ctx.save(); ctx.strokeStyle = th.empty; ctx.lineWidth = 8 * s; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(lx, yAt(0)); ctx.lineTo(lx, yAt(n - 1)); ctx.stroke();
  ctx.strokeStyle = col(sp.color || 'warn'); ctx.beginPath(); ctx.moveTo(lx, yAt(0)); ctx.lineTo(lx, lerp(yAt(0), yAt(cur), kLine)); ctx.stroke(); ctx.restore();
  st.forEach((it, i) => { const k = bk(lt, it.t != null ? it.t : 0.3 + i * gap); if (k <= 0) return; const y = yAt(i), done = i <= cur && lt > 0.3 + i * gap, cc = col(it.color || (done ? sp.color || 'warn' : th.line)), r = (numbered ? 34 : 18) * s;
    ctx.save(); ell(ctx, lx, y, r * clamp(k, 0, 1.2), r * clamp(k, 0, 1.2)); ctx.fillStyle = done ? cc : th.bg[0]; ctx.fill(); ctx.strokeStyle = cc; ctx.lineWidth = 4 * s; ctx.stroke();
    if (numbered) txt(ctx, String(i + 1), lx, y + 2 * s, 34 * s, {fam: DISPLAY, weight: 900, align: 'center', color: done ? '#141821' : cc});
    ctx.globalAlpha *= clamp(k); ctx.translate((1 - clamp(k)) * 30 * s, 0); const tx = lx + r + 30 * s, maxW = b.x + b.w - tx;
    if (it.time) { txt(ctx, UP(it.time), tx, y - 24 * s, 28 * s, {fam: MONO, weight: 700, color: cc, ls: 2 * s}); }
    const lines = wrap(ctx, UP(it.text), maxW, 38 * s).slice(0, 2), dy = (it.time ? 18 * s : 0) - (it.sub ? 16 * s : 0);
    lines.forEach((ln, j) => txt(ctx, ln, tx, y + dy + (j - (lines.length - 1) / 2) * 44 * s, 38 * s, {color: th.ink}));
    if (it.sub) txt(ctx, it.sub, tx, y + dy + (lines.length - 1) * 22 * s + 40 * s, 28 * s, {fam: BODY, weight: 700, color: th.sub});
    ctx.restore(); });
};
FN.steps = (ctx, b, sp, lt, dur, th, s) => FN.timeline(ctx, b, Object.assign({numbered: true}, sp), lt, dur, th, s);

// ------------------------------------------------------------------ closeup: one item big on a spotlight + note callouts
FN.closeup = (ctx, b, sp, lt, dur, th, s, env) => {
  const cx = b.x + b.w / 2, cy = b.y + b.h * 0.46, R = Math.min(b.w, b.h) * 0.42, k = bk(lt, 0.05, 0.5);
  ctx.save(); ctx.fillStyle = T.h.rgrad(ctx, cx, cy, R * 0.1, R * 1.25, [[0, rgba('#FFE7A8', th.light ? 0.55 : 0.28)], [1, rgba('#FFE7A8', 0)]]); ctx.fillRect(b.x - 40 * s, b.y - 40 * s, b.w + 80 * s, b.h + 80 * s);
  ell(ctx, cx, cy, R * clamp(k), R * clamp(k)); ctx.strokeStyle = rgba(th.line, 0.6); ctx.lineWidth = 3 * s; ctx.setLineDash([10 * s, 10 * s]); ctx.lineDashOffset = -lt * 20 * s; ctx.stroke(); ctx.setLineDash([]); ctx.restore();
  if (sp.item && T.drawProp) { const e2 = Object.assign({}, env, {lt}), unitPx = (env.portrait ? 0.30 : 0.50) * env.H / 1000, bb = itemBox(sp.item, env), D = R * (sp.fill || 1.3);
    const sc = sp.scale || D / (Math.max(bb.w, bb.h) * unitPx), base = cy + (bb.h / 2 - bb.bottom) * unitPx * sc;
    ctx.save(); T.drawProp(e2, {id: sp.item, at: [cx / env.W, base / env.H], scale: sc * clamp(k, 0, 1.15), shadow: 0.8, rot: Math.sin(lt * 1.3) * 0.04,
      on: sp.on, level: sp.level, color: sp.color, glow: sp.glow}, 0); ctx.restore(); }
  else if (sp.icon) T.icon(ctx, sp.icon, cx, cy, R * 1.1 * clamp(k), col(sp.color || 'warn'));
  (sp.notes || []).forEach((nt, i) => { const kn = pk(lt, nt.t != null ? nt.t : 0.6 + i * 0.3, 0.32); if (kn <= 0) return; const n2 = typeof nt === 'string' ? {text: nt} : nt;
    const side = n2.side || (i % 2 ? 'left' : 'right'), y = b.y + b.h * (n2.y != null ? n2.y : 0.18 + 0.22 * Math.floor(i / 2) + (i % 2) * 0.1), ax = cx + (side === 'left' ? -R * 0.45 : R * 0.45), ay = cy - R * 0.2 + i * R * 0.12;
    const px2 = side === 'left' ? b.x : b.x + b.w; ctx.save(); ctx.globalAlpha *= kn; ctx.strokeStyle = col(n2.color || 'warn'); ctx.lineWidth = 3 * s; ctx.beginPath(); ctx.moveTo(ax, ay);
    ctx.lineTo(lerp(ax, px2 + (side === 'left' ? 200 * s : -200 * s), E.out(kn)), y); ctx.stroke(); ell(ctx, ax, ay, 8 * s, 8 * s); ctx.fillStyle = col(n2.color || 'warn'); ctx.fill();
    plate(ctx, n2.text, n2.sub, side === 'left' ? b.x : b.x + b.w, y, s * 0.8, th, {align: side === 'left' ? 'left' : 'right', color: n2.color || 'warn', icon: n2.icon}); ctx.restore(); });
  if (sp.label) { const kl = pk(lt, 0.35, 0.35); ctx.save(); ctx.globalAlpha *= kl; txt(ctx, UP(sp.label), cx, b.y + b.h - 40 * s, fit(ctx, UP(sp.label), b.w, 56 * s), {align: 'center', color: th.ink, shadow: !th.light});
    if (sp.label_sub) txt(ctx, UP(sp.label_sub), cx, b.y + b.h + 6 * s, 28 * s, {fam: MONO, weight: 700, align: 'center', color: th.sub}); ctx.restore(); }
};

const IBOX = {};
function itemBox(id, env) {            // bounding box of an item in prop units (1000 = human height), measured once offscreen
  if (IBOX[id]) return IBOX[id]; const N = 1400, c = document.createElement('canvas'); c.width = N; c.height = N; const x = c.getContext('2d', {willReadFrequently: true});
  const port = T.story.H >= T.story.W, u = (port ? 0.30 : 0.50) * N / 1000, saved = T.LIGHTS; T.LIGHTS = [];
  try { T.drawProp({ctx: x, W: N, H: N, lt: 3, t: 3, style: {}, P: env.P, portrait: port, sc: env.sc}, {id, at: [0.5, 0.8], scale: 1, shadow: false}, 0); } catch (e) {}
  T.LIGHTS = saved; const d = x.getImageData(0, 0, N, N).data; let x0 = N, y0 = N, x1 = 0, y1 = 0;
  for (let yy = 0; yy < N; yy += 2) for (let xx = 0; xx < N; xx += 2) if (d[(yy * N + xx) * 4 + 3] > 24) { if (xx < x0) x0 = xx; if (xx > x1) x1 = xx; if (yy < y0) y0 = yy; if (yy > y1) y1 = yy; }
  const r = x1 > x0 ? {w: (x1 - x0) / u, h: (y1 - y0) / u, bottom: (y1 - 0.8 * N) / u} : {w: 300, h: 300, bottom: 0}; IBOX[id] = r; return r;
}
// ------------------------------------------------------------------ card: big statement (chapter / day / rule) on the scheme background
FN.card = (ctx, b, sp, lt, dur, th, s) => {
  const k = bk(lt, 0.08, 0.5), cx = b.x + b.w / 2, cy = b.y + b.h * 0.48, t = UP(sp.text || ''), fs = fit(ctx, t, b.w * 0.95, 150 * s, DISPLAY, 900), cc = col(sp.color || 'warn');
  ctx.save(); ctx.globalAlpha *= clamp(k); ctx.translate(cx, cy); ctx.scale(0.8 + 0.2 * k, 0.8 + 0.2 * k); ctx.translate(-cx, -cy);
  if (sp.icon) T.icon(ctx, sp.icon, cx, cy - fs * 1.1, 110 * s, cc);
  txt(ctx, t, cx, cy, fs, {fam: DISPLAY, weight: 900, align: 'center', color: cc, shadow: !th.light});
  if (sp.text2) txt(ctx, UP(sp.text2), cx, cy + fs * 0.9, 44 * s, {align: 'center', color: th.ink, ls: 3 * s});
  ctx.restore();
};

// ------------------------------------------------------------------ prism: white ray -> drop / prism -> fan of colour rays (light, rainbow, any "one thing splits into many")
const SPECTRUM = ['#FF4B4B', '#FF9A3C', '#FFE04D', '#5ED36A', '#5BC8F5', '#3B6FE0', '#9B5BE0'];
FN.prism = (ctx, b, sp, lt, dur, th, s) => {
  const cols = (sp.colors || SPECTRUM).map(col), n = cols.length, cx = b.x + b.w * 0.44, cy = b.y + b.h * 0.42, R = Math.min(b.w, b.h) * 0.16;
  const tSplit = sp.split_t != null ? sp.split_t : Math.min(1.3, dur * 0.4), kIn = E.out(clamp((lt - 0.15) / 0.55)), kOut = E.out(clamp((lt - tSplit) / 0.7));
  const sx = b.x + 50 * s, sy = b.y + b.h * 0.12, ex = cx - R * 0.55, ey = cy - R * 0.1, hx = lerp(sx, ex, kIn), hy = lerp(sy, ey, kIn);
  ctx.save(); ctx.lineCap = 'round';
  if (sp.source !== false) T.icon(ctx, sp.source || 'sun', sx, sy, 96 * s * clamp(kIn * 3), col('warn'));
  ctx.globalCompositeOperation = th.light ? 'source-over' : 'lighter';
  ctx.strokeStyle = rgba(th.light ? '#FFFFFF' : '#FFFFFF', 0.35); ctx.lineWidth = 34 * s; ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(hx, hy); ctx.stroke();
  ctx.strokeStyle = '#FFFFFF'; ctx.lineWidth = 12 * s; ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(hx, hy); ctx.stroke();
  ctx.globalCompositeOperation = 'source-over';
  if (kOut > 0) { const ox = cx + R * 0.45, oy = cy + R * 0.12, x1 = b.x + b.w + 20 * s, y0 = cy - b.h * 0.06, y1 = cy + b.h * 0.5, xr = lerp(ox, x1, kOut);
    for (let i = 0; i < n; i++) { const ya = lerp(y0, y1, i / n), yb = lerp(y0, y1, (i + 1) / n), f = (xr - ox) / (x1 - ox);
      ctx.fillStyle = rgba(cols[i], 0.88); poly(ctx, [[ox, oy], [xr, lerp(oy, ya, f)], [xr, lerp(oy, yb, f)]]); ctx.fill(); }
    if (sp.labels && kOut > 0.6) { const kl = clamp((kOut - 0.6) / 0.4); (sp.labels || []).slice(0, n).forEach((lb, i) => {
      const yy = lerp(y0, y1, (i + 0.5) / n); ctx.save(); ctx.globalAlpha *= kl; txt(ctx, UP(lb), b.x + b.w - 14 * s, yy, Math.min(26 * s, (y1 - y0) / n * 0.6), {align: 'right', color: '#FFFFFF', stroke: 5 * s, strokeColor: rgba('#13304D', 0.7)}); ctx.restore(); }); } }
  // the splitter: a water drop (default) or a glass prism
  const kb = bk(lt, 0.05, 0.5); ctx.save(); ctx.translate(cx, cy); ctx.scale(kb, kb); ctx.beginPath();
  if (sp.shape === 'prism') { ctx.moveTo(0, -R * 1.1); ctx.lineTo(R * 1.0, R * 0.75); ctx.lineTo(-R * 1.0, R * 0.75); ctx.closePath(); }
  else { ctx.moveTo(0, -R * 1.25); ctx.bezierCurveTo(R * 0.55, -R * 0.55, R * 0.95, -R * 0.05, R * 0.95, R * 0.3); ctx.arc(0, R * 0.3, R * 0.95, 0, Math.PI); ctx.bezierCurveTo(-R * 0.95, -R * 0.05, -R * 0.55, -R * 0.55, 0, -R * 1.25); }
  ctx.fillStyle = rgba('#7CC8F2', 0.55); ctx.fill(); ctx.strokeStyle = '#FFFFFF'; ctx.lineWidth = 6 * s; ctx.stroke();
  ctx.fillStyle = rgba('#FFFFFF', 0.7); ell(ctx, -R * 0.38, R * 0.05, R * 0.12, R * 0.22, 0.4); ctx.fill(); ctx.restore();
  if (sp.label) { const k = pk(lt, 0.4); ctx.globalAlpha *= k; txt(ctx, UP(sp.label), cx, cy + R * 1.65, 34 * s, {align: 'center', color: th.ink}); }
  ctx.restore();
};

Object.keys(FN).forEach(type => { T.SCHEMES[type] = (env, sp, lt, dur) => run(type, env, sp, lt, dur); });
T.SCHEME_NAMES = Object.keys(FN);
})();
