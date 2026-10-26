/* TOON sets: parametric backgrounds with parallax layers. Every set reads the palette (time of day) so one set works
   for day / dusk / night / blackout / winter. Sizes use env.U (default human height in px), positions use W/H. */
'use strict';
(function () {
const T = window.TOON, {clamp, lerp, E, hash, rng, vnoise, mix, shade, rgba, rr, ell, poly, vgrad, rgrad} = T.h;
const S = T.SETS;
const OUTW = {none: 0, thin: 7, thick: 14};
function oc(env, c) { const w = OUTW[env.style.outline] == null ? OUTW.thin : OUTW[env.style.outline]; return w ? {w, c: env.style.outline === 'thick' ? '#15171C' : shade(c, -0.5)} : null; }
function fill(ctx, c, o) { ctx.fillStyle = c; ctx.fill(); if (o) { ctx.lineWidth = o.w; ctx.strokeStyle = o.c; ctx.lineJoin = 'round'; ctx.stroke(); } }
function rect(ctx, x, y, w, h, c, o, r = 0) { rr(ctx, x, y, w, h, r); fill(ctx, c, o); }
const night = env => ['night', 'blackout'].includes((env.sc.set && env.sc.set.time) || 'day');
const timeOf = env => (env.sc.set && env.sc.set.time) || 'day';
// power: 1 = lights on. set.power (bool), set.power_off (scene time when it goes out, with a flicker)
function power(env, o) { const t = timeOf(env); let p = o.power != null ? (o.power ? 1 : 0) : (t === 'blackout' ? 0 : 1);
  if (o.power_off != null) { const lt = env.lt, po = o.power_off; if (lt >= po) p = 0; else if (lt > po - 0.45) p = vnoise(31, lt * 30) > 0.45 ? 1 : 0.15; }
  return p; }
T.power = power;
// ---------------------------------------------------------------- shared painters
function sky(env, o) { const {ctx, W, H, P} = env; ctx.fillStyle = vgrad(ctx, 0, H * (o.sky_h || 0.75), [[0, P.sky[0]], [1, P.sky[1]]]); ctx.fillRect(-W, -H, W * 3, H * 3); if (T.skyFx) T.skyFx(env); }
function sun(env, x, y, r) { const {ctx, P} = env; const n = night(env), c = n ? '#F2EBD3' : timeOf(env) === 'dusk' ? '#FFB36B' : '#FFF4D6';
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = rgrad(ctx, x, y, r * 0.5, r * 4, [[0, rgba(c, n ? 0.25 : 0.45)], [1, rgba(c, 0)]]); ctx.fillRect(x - r * 4, y - r * 4, r * 8, r * 8); ctx.restore();
  ell(ctx, x, y, r, r); ctx.fillStyle = c; ctx.fill(); if (n) { ctx.fillStyle = rgba('#000', 0.08); ell(ctx, x - r * 0.3, y - r * 0.2, r * 0.25, r * 0.25); ctx.fill(); ell(ctx, x + r * 0.35, y + r * 0.3, r * 0.15, r * 0.15); ctx.fill(); } }
function stars(env, n = 80) { const {ctx, W, H, t} = env, R = rng(83); for (let i = 0; i < n; i++) { const x = R() * W * 1.4 - W * 0.2, y = R() * H * 0.45, r = 1 + R() * 2.2;
  ctx.fillStyle = rgba('#FFFFFF', 0.25 + 0.55 * vnoise(i, t * 0.6)); ell(ctx, x, y, r, r); ctx.fill(); } }
function clouds(env, y0, y1, n, seed, c) { const {ctx, W, H, t} = env, R = rng(seed); ctx.fillStyle = c;
  for (let i = 0; i < n; i++) { const w = W * (0.18 + R() * 0.2), x = ((R() * W * 1.6 + t * (8 + R() * 10)) % (W * 1.8)) - W * 0.4, y = lerp(y0, y1, R()) * H;
    ell(ctx, x, y, w * 0.5, w * 0.16); ctx.fill(); ell(ctx, x - w * 0.18, y - w * 0.08, w * 0.22, w * 0.14); ctx.fill(); ell(ctx, x + w * 0.12, y - w * 0.11, w * 0.26, w * 0.17); ctx.fill(); } }
function hills(env, base, amp, c, seed, k = 1) { const {ctx, W, H} = env; ctx.beginPath(); ctx.moveTo(-W, H * 2); for (let x = -W; x <= W * 2; x += W / 24) ctx.lineTo(x, base - amp * vnoise(seed, x / W * 3 * k));
  ctx.lineTo(W * 2, H * 2); ctx.closePath(); ctx.fillStyle = c; ctx.fill(); }
function treeLine(env, base, h, c, seed, snow) { const {ctx, W} = env, R = rng(seed); ctx.fillStyle = c;
  for (let x = -W * 0.6; x < W * 1.6; x += h * (0.22 + R() * 0.16)) { const hh = h * (0.6 + R() * 0.5), w = hh * 0.34; ctx.beginPath(); ctx.moveTo(x - w, base); ctx.lineTo(x, base - hh); ctx.lineTo(x + w, base); ctx.closePath(); ctx.fill();
    if (snow) { ctx.save(); ctx.fillStyle = rgba('#F4F7FA', 0.85); ctx.beginPath(); ctx.moveTo(x - w * 0.3, base - hh * 0.7); ctx.lineTo(x, base - hh); ctx.lineTo(x + w * 0.3, base - hh * 0.7); ctx.closePath(); ctx.fill(); ctx.restore(); } }
  ctx.fillRect(-W, base - 2, W * 3, h * 0.5); }
function haze(env, y0, y1, a) { const {ctx, W, P} = env; ctx.fillStyle = vgrad(ctx, y0, y1, [[0, rgba(P.haze || P.sky[1], 0)], [1, rgba(P.haze || P.sky[1], a)]]); ctx.fillRect(-W, y0, W * 3, y1 - y0); }
function skyline(env, base, hmin, hmax, c, seed, lit, pw) { const {ctx, W, H, t} = env, R = rng(seed); let x = -W * 0.5;
  while (x < W * 1.5) { const w = W * (0.07 + R() * 0.09), h = lerp(hmin, hmax, R()) * H; ctx.fillStyle = c; ctx.fillRect(x, base - h, w + 1, h + 4);
    if (R() < 0.3) ctx.fillRect(x + w * 0.4, base - h - H * 0.03, 3, H * 0.03);
    if (lit > 0) { const cols = Math.max(2, Math.floor(w / 16)), rows = Math.floor(h / 22); for (let r = 1; r < rows; r++) for (let q = 0; q < cols; q++) { const v = R();
      if (v < lit * pw) { ctx.fillStyle = rgba('#FFC870', 0.55 + 0.3 * vnoise(q * 7 + r, t * 0.2)); ctx.fillRect(x + 6 + q * (w - 8) / cols, base - h + r * 22, 6, 9); } } }
    x += w + R() * W * 0.015; } }
function grassTufts(env, y, n, c, seed, blur) { if (blur) return T.soft(env, blur, (cx, e) => grassTufts(e, y, n, c, seed, 0));
  const {ctx, W, U, t} = env, R = rng(seed); ctx.save(); ctx.fillStyle = c;
  for (let i = 0; i < n; i++) { const x = R() * W * 1.3 - W * 0.15, h = U * (0.08 + R() * 0.14), sw = Math.sin(t * 1.2 + i) * h * 0.08; ctx.beginPath(); ctx.moveTo(x - h * 0.25, y + 4);
    ctx.quadraticCurveTo(x - h * 0.1 + sw, y - h * 0.6, x - h * 0.2 + sw, y - h); ctx.quadraticCurveTo(x + sw * 0.5, y - h * 0.5, x + h * 0.05, y - h * 0.8 + 6); ctx.quadraticCurveTo(x + h * 0.1 + sw, y - h * 0.4, x + h * 0.3 + sw, y - h * 0.9);
    ctx.quadraticCurveTo(x + h * 0.15, y - h * 0.3, x + h * 0.25, y + 4); ctx.closePath(); ctx.fill(); } ctx.restore(); }
function winLight(env, x, y, w, h, on, warm) { const {ctx} = env; if (!on) return; T.addLight(ctx, x + w / 2, y + h / 2, {kind: 'point', r: Math.max(w, h) * 1.6, color: warm || '#FFB84D', a: 0.55 * on, glow: 0.5}); }
// window with an outside view (outside drawn by fn inside a clip)
function windowView(env, x, y, w, h, o, outside) { const {ctx} = env; const frame = o.frame || '#F1EDE4';
  ctx.save(); rr(ctx, x, y, w, h, 6); ctx.clip(); outside(); ctx.restore();
  ctx.strokeStyle = frame; ctx.lineWidth = Math.max(10, w * 0.045); rr(ctx, x, y, w, h, 6); ctx.stroke(); ctx.beginPath(); ctx.moveTo(x + w / 2, y); ctx.lineTo(x + w / 2, y + h); ctx.moveTo(x, y + h * 0.38); ctx.lineTo(x + w, y + h * 0.38); ctx.stroke();
  rect(ctx, x - w * 0.06, y + h - 4, w * 1.12, Math.max(14, h * 0.05), shade(frame, -0.08), oc(env, frame), 4); }
function outsideView(env, x, y, w, h, o) { const {ctx, W, H, P} = env, n = night(env), pw = power(env, o);
  ctx.fillStyle = vgrad(ctx, y, y + h, [[0, P.sky[0]], [1, P.sky[1]]]); ctx.fillRect(x, y, w, h);
  if (n) { const R = rng(9); for (let i = 0; i < 30; i++) { ctx.fillStyle = rgba('#FFF', 0.6 * R()); ctx.fillRect(x + R() * w, y + R() * h * 0.5, 2, 2); } }
  if ((o.outside || 'city') === 'city') { ctx.save(); ctx.translate(0, 0); const env2 = Object.assign({}, env, {W: W, H: H});
    skyline(env2, y + h, 0.05, 0.16, shade(P.far, -0.1), 17, n ? 0.35 : 0, (o.city_power != null ? o.city_power : (timeOf(env) === 'blackout' ? 0 : 1)));
    ctx.restore(); }
  else { hills(env, y + h * 0.8, h * 0.25, P.far, 5); treeLine(env, y + h * 0.95, h * 0.3, shade(P.mid, -0.1), 6, timeOf(env) === 'winter'); }
  if (n) sun(env, x + w * 0.75, y + h * 0.22, Math.min(w, h) * 0.07); }
function planks(env, y0, y1, c) { const {ctx, W} = env; ctx.fillStyle = vgrad(ctx, y0, y1, [[0, shade(c, 0.06)], [1, shade(c, -0.18)]]); ctx.fillRect(-W, y0, W * 3, y1 - y0);
  ctx.strokeStyle = rgba(shade(c, -0.5), 0.35); ctx.lineWidth = 3; for (let i = 1; i < 9; i++) { const y = y0 + (y1 - y0) * Math.pow(i / 9, 1.35); ctx.beginPath(); ctx.moveTo(-W, y); ctx.lineTo(W * 2, y); ctx.stroke(); }
  const R = rng(3); for (let i = 0; i < 26; i++) { const r = Math.floor(R() * 9), y = y0 + (y1 - y0) * Math.pow(r / 9, 1.35), y2 = y0 + (y1 - y0) * Math.pow((r + 1) / 9, 1.35), x = R() * W;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y2); ctx.stroke(); } }
function lampCeiling(env, x, y, o, pw) { const {ctx, U} = env; ctx.strokeStyle = '#2A2E36'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x, -10); ctx.lineTo(x, y); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x - U * 0.16, y + U * 0.12); ctx.lineTo(x - U * 0.06, y); ctx.lineTo(x + U * 0.06, y); ctx.lineTo(x + U * 0.16, y + U * 0.12); ctx.closePath(); fill(ctx, o.lamp || '#3F6A6A', oc(env, '#3F6A6A'));
  ell(ctx, x, y + U * 0.12, U * 0.05, U * 0.025); ctx.fillStyle = pw > 0.5 ? '#FFF2C8' : '#6B6F75'; ctx.fill();
  if (pw > 0) T.addLight(ctx, x, y + U * 0.14, {kind: 'point', r: U * 2.6, color: '#FFE2A8', a: 0.85 * pw, glow: 0.35}); }
function frameArt(env, x, y, w, h, seed) { const {ctx, P} = env; rect(ctx, x, y, w, h, '#6A4B30', oc(env, '#6A4B30'), 4); ctx.save(); rr(ctx, x + w * 0.1, y + h * 0.1, w * 0.8, h * 0.8, 2); ctx.clip();
  ctx.fillStyle = '#BFD3D6'; ctx.fillRect(x, y, w, h); ctx.fillStyle = '#7F9B6A'; ell(ctx, x + w * 0.3, y + h * 0.95, w * 0.6, h * 0.45); ctx.fill(); ctx.fillStyle = '#5E7F55'; ell(ctx, x + w * 0.85, y + h * 1.0, w * 0.5, h * 0.5); ctx.fill();
  ctx.fillStyle = '#F6E7B8'; ell(ctx, x + w * 0.7, y + h * 0.3, w * 0.09, w * 0.09); ctx.fill(); ctx.restore(); }

// ---------------------------------------------------------------- plain / paper
S.plain = {ground: 0.8, draw(env, o) { const {ctx, W, H, P} = env; ctx.fillStyle = vgrad(ctx, 0, H, [[0, P.sky[0]], [1, P.sky[1]]]); ctx.fillRect(-W, -H, W * 3, H * 3);
  ctx.fillStyle = rgrad(ctx, W / 2, H * 0.45, 0, H * 0.7, [[0, rgba('#FFFFFF', 0.10)], [1, rgba('#FFFFFF', 0)]]); ctx.fillRect(0, 0, W, H);
  env.L(1, () => { ctx.fillStyle = o.floor || P.ground; ctx.fillRect(-W, env.ground, W * 3, H); }); }};

// ---------------------------------------------------------------- room (living / bedroom / kitchen / empty)
S.room = {ground: 0.84, ground_l: 0.88, draw(env, o) {
  const {ctx, W, H, U, P} = env, g = env.ground, wb = g - (env.portrait ? 0.09 : 0.12) * H, pw = power(env, o), n = night(env);
  const wall = o.wall || (o.variant === 'kitchen' ? '#CFD8CF' : '#D8CBB0'), floorC = o.floor || '#8A6A4A';
  const winX = (o.window_x != null ? o.window_x : (o.window === 'left' ? 0.08 : (o.variant === 'kitchen' ? 0.6 : 0.58))) * W, winW = Math.max(U * 0.62, W * (env.portrait ? 0.34 : 0.2)), winH = U * 0.78, winY = wb - U * 1.3;
  env.L(1, () => {
    ctx.fillStyle = vgrad(ctx, -H * 0.1, wb, [[0, shade(wall, -0.12)], [0.6, wall], [1, shade(wall, -0.05)]]); ctx.fillRect(-W, -H, W * 3, wb + H);
    ctx.fillStyle = rgba(shade(wall, -0.3), 0.07); for (let x = -W; x < W * 2; x += U * 0.12) ctx.fillRect(x, -H, U * 0.05, wb + H);
    if (o.window !== false) windowView(env, winX, winY, winW, winH, o, () => outsideView(env, winX, winY, winW, winH, o));
    if (o.window !== false) { const cc = o.curtain || '#9C4F3F', sw = Math.sin(env.t * 0.9) * U * 0.01;
      [[winX - U * 0.16, 1], [winX + winW + U * 0.02, -1]].forEach(([cx, d]) => { ctx.beginPath(); ctx.moveTo(cx, winY - U * 0.12); ctx.lineTo(cx + U * 0.14, winY - U * 0.12);
        ctx.quadraticCurveTo(cx + U * 0.1 + sw, winY + winH * 0.6, cx + U * 0.16 + sw, winY + winH + U * 0.1); ctx.lineTo(cx - U * 0.02 + sw, winY + winH + U * 0.1); ctx.closePath(); fill(ctx, cc, oc(env, cc)); });
      rect(ctx, winX - U * 0.22, winY - U * 0.15, winW + U * 0.44, U * 0.04, '#5A4636', oc(env, '#5A4636'), 4);
      if (!n && timeOf(env) !== 'blackout') { ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = rgba('#FFF1D2', 0.10); ctx.beginPath(); ctx.moveTo(winX, winY + winH); ctx.lineTo(winX + winW, winY + winH);
        ctx.lineTo(winX + winW + U * 0.7, g + H * 0.08); ctx.lineTo(winX + U * 0.4, g + H * 0.08); ctx.closePath(); ctx.fill(); ctx.restore(); } }
    if (o.door) { const dx = (o.door_x != null ? o.door_x : 0.12) * W; rect(ctx, dx, wb - U * 1.25, U * 0.5, U * 1.25, shade('#7A5A3C', -0.3), oc(env, '#7A5A3C'), 4); rect(ctx, dx + U * 0.03, wb - U * 1.22, U * 0.44, U * 1.22, '#7A5A3C', oc(env, '#7A5A3C'), 3);
      ell(ctx, dx + U * 0.4, wb - U * 0.6, U * 0.025, U * 0.025); ctx.fillStyle = '#E2B544'; ctx.fill(); }
    // baseboard + floor
    ctx.fillStyle = shade(wall, -0.35); ctx.fillRect(-W, wb - U * 0.05, W * 3, U * 0.05);
    planks(env, wb, H * 1.2, floorC);
    const v = o.variant || 'living', unit = U / 1000;
    const prop = (id, x, y, sc, k) => { const it = T.ITEMS[id]; if (!it) return; ctx.save(); ctx.translate(x, y); ctx.scale(unit * sc, unit * sc); T.h.shadowBlob(ctx, 0, 0, 300, 0.2);
      it.draw(ctx, c => { const w = OUTW[env.style.outline] == null ? 9 : OUTW[env.style.outline] * 1.3; return w ? {w, c: shade(c, -0.55)} : null; }, Object.assign({seed: 'room'}, k || {}), env); ctx.restore(); };
    if (v === 'living') { frameArt(env, W * 0.12, wb - U * 1.2, U * 0.36, U * 0.28); prop('sofa', W * 0.24, wb + U * 0.05, 0.9, {color: o.sofa}); prop('pot', W * 0.92, wb + U * 0.04, 0.9); }
    else if (v === 'bedroom') { frameArt(env, W * 0.16, wb - U * 1.25, U * 0.3, U * 0.4); prop('bed', W * 0.26, wb + U * 0.08, 0.85, {color: o.blanket}); prop('table', W * 0.9, wb + U * 0.04, 0.5); }
    else if (v === 'kitchen') { const cw = Math.min(W * 0.5, winX - U * 0.3), cy = wb - U * 0.5;
      ctx.fillStyle = rgba('#FFFFFF', 0.35); for (let x = 0; x < cw; x += U * 0.1) for (let y = cy - U * 0.45; y < cy; y += U * 0.1) { ctx.fillRect(x + 2, y + 2, U * 0.1 - 4, U * 0.1 - 4); }
      rect(ctx, -U * 0.1, wb - U * 1.4, cw + U * 0.1, U * 0.42, '#E7E1D6', oc(env, '#E7E1D6'), 6); for (let x = U * 0.05; x < cw; x += U * 0.4) { ctx.strokeStyle = shade('#E7E1D6', -0.2); ctx.lineWidth = 4; ctx.strokeRect(x, wb - U * 1.36, U * 0.34, U * 0.34); }
      rect(ctx, -U * 0.1, cy, cw + U * 0.1, U * 0.5, '#7F9C8C', oc(env, '#7F9C8C'), 6); rect(ctx, -U * 0.14, cy - U * 0.05, cw + U * 0.2, U * 0.06, '#EDE7DA', oc(env, '#EDE7DA'), 4);
      rect(ctx, cw * 0.55, cy - U * 0.05, U * 0.3, U * 0.04, '#9AA3AA', null, 3); ctx.strokeStyle = '#9AA3AA'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(cw * 0.55 + U * 0.15, cy - U * 0.05); ctx.lineTo(cw * 0.55 + U * 0.15, cy - U * 0.2); ctx.lineTo(cw * 0.55 + U * 0.24, cy - U * 0.2); ctx.stroke();
      prop('fridge', Math.min(W - U * 0.2, winX + winW + U * 0.3), wb + U * 0.02, 1.0); prop('cup', cw * 0.25, cy - U * 0.04, 0.6, {steam: pw > 0}); }
    if (o.lamp !== false && v !== 'kitchen') lampCeiling(env, W * (o.window === 'left' ? 0.7 : 0.35), wb - U * 1.55, o, pw);
    else if (o.lamp !== false) lampCeiling(env, W * 0.42, wb - U * 1.6, o, pw);
  });
}, front(env, o) { if (!o.fg) return; const {W, H, U} = env; env.L(1.3, () => T.soft(env, 10, ctx => { ctx.fillStyle = shade('#4F7A45', -0.4);
  [[0.02, 0.9], [0.1, 0.96], [0.95, 0.93]].forEach(([x, y]) => { ell(ctx, x * W, y * H, U * 0.25, U * 0.12, 0.5); ctx.fill(); }); })); }};
S.kitchen = {ground: 0.84, ground_l: 0.88, draw(env, o) { S.room.draw(env, Object.assign({variant: 'kitchen'}, o)); }};

// ---------------------------------------------------------------- facade: panel apartment block at night, windows go dark
S.facade = {ground: 0.86, ground_l: 0.9, draw(env, o) {
  const {ctx, W, H, U, P, lt} = env, g = env.ground, n = night(env), pw = power(env, o), tm = timeOf(env);
  env.L(0, () => { sky(env, o); if (n) stars(env); sun(env, W * 0.8, H * 0.1, U * 0.07); if (!n) clouds(env, 0.05, 0.2, 4, 11, rgba('#FFFFFF', 0.55)); });
  env.L(0.25, () => { skyline(env, g - H * 0.04, 0.18, 0.34, shade(P.far, n ? 0 : 0.05), 23, n ? 0.25 : 0, o.city_power != null ? o.city_power : pw); haze(env, g - H * 0.35, g, n ? 0.25 : 0.45); });
  env.L(0.55, () => { skyline(env, g - H * 0.02, 0.1, 0.22, shade(P.mid, n ? 0.05 : 0.15), 29, n ? 0.3 : 0, o.city_power != null ? o.city_power : pw); });
  env.L(1, () => {
    const bw = env.portrait ? W * 0.86 : W * 0.5, bx = (W - bw) / 2 + (o.shift || 0) * W, cols = o.cols || (env.portrait ? 5 : 6), floors = o.floors || 9;
    const fh = (g - H * 0.06) / (floors + 0.6), top = g - fh * (floors + 0.3), cw = bw / cols, wall = o.wall || (n ? '#5E6672' : '#C9C4B8');
    rect(ctx, bx, top, bw, g - top, wall, oc(env, wall)); ctx.fillStyle = shade(wall, 0.08); ctx.fillRect(bx, top - fh * 0.12, bw, fh * 0.14);
    ctx.strokeStyle = rgba(shade(wall, -0.4), 0.35); ctx.lineWidth = 3;
    for (let c = 1; c < cols; c++) { ctx.beginPath(); ctx.moveTo(bx + c * cw, top); ctx.lineTo(bx + c * cw, g); ctx.stroke(); }
    const R = rng(hash(o.seed || 'facade')), lit = o.lit != null ? o.lit : (n ? 0.62 : tm === 'dusk' ? 0.4 : 0), hw = o.hero_window;
    for (let r = 0; r < floors; r++) { const y = g - fh * (r + 1) - fh * 0.05; ctx.beginPath(); ctx.moveTo(bx, y + fh); ctx.lineTo(bx + bw, y + fh); ctx.stroke();
      for (let c = 0; c < cols; c++) { const ww = cw * 0.5, wh = fh * 0.52, wx = bx + c * cw + (cw - ww) / 2, wy = y + fh * 0.22; let on = R() < lit ? 1 : 0; const off = R();
        const hero = hw && hw[0] === c && hw[1] === r;
        if (o.lights_out != null && !hero) { const tt = o.lights_out + off * (o.cascade || 1.4); if (lt > tt) on = 0; else if (lt > tt - 0.25 && on) on = vnoise(c * 13 + r, lt * 40) > 0.5 ? 1 : 0; }
        if (pw === 0 && o.lights_out == null && !hero) on = R() < (o.others != null ? o.others : 0.06) ? 0.45 : 0;   // candles in other flats
        if (hero) on = o.hero_light != null ? o.hero_light : 1;
        const warm = hero ? '#FFB84D' : ['#FFC870', '#FFD9A0', '#F7B96A', '#BFD8FF'][Math.floor(off * 4)];
        rect(ctx, wx, wy, ww, wh, on ? mix(warm, '#FFFFFF', 0.1) : (n ? '#1B2433' : '#8FB0C4'), oc(env, wall), 2);
        if (on) { ctx.fillStyle = rgba(shade(warm, -0.4), 0.35); ctx.fillRect(wx, wy, ww * 0.3, wh); winLight(env, wx, wy, ww, wh, on * (hero ? 1.4 : 0.8), warm); }
        else if (!n) { ctx.fillStyle = rgba('#FFFFFF', 0.25); ctx.beginPath(); ctx.moveTo(wx + ww * 0.15, wy + wh); ctx.lineTo(wx + ww * 0.55, wy); ctx.lineTo(wx + ww * 0.75, wy); ctx.lineTo(wx + ww * 0.35, wy + wh); ctx.fill(); }
        ctx.strokeStyle = rgba(shade(wall, -0.5), 0.5); ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(wx + ww / 2, wy); ctx.lineTo(wx + ww / 2, wy + wh); ctx.stroke();
        if ((c + r) % 3 === 1 && r > 0) { rect(ctx, wx - cw * 0.12, wy + wh * 0.62, ww + cw * 0.24, wh * 0.5, shade(wall, -0.12), oc(env, wall), 2); }
        if (hero && o.hero_mark !== false) { const a = 0.5 + 0.5 * Math.sin(env.t * 4); ctx.strokeStyle = rgba(T.UI.warn, 0.6 + 0.4 * a); ctx.lineWidth = 6; rr(ctx, wx - 10, wy - 10, ww + 20, wh + 20, 8); ctx.stroke(); }
      } ctx.strokeStyle = rgba(shade(wall, -0.4), 0.35); ctx.lineWidth = 3; }
    // entrance
    const ex = bx + bw / 2 - cw * 0.35; rect(ctx, ex, g - fh * 0.85, cw * 0.7, fh * 0.85, '#3A3F46', oc(env, '#3A3F46'), 3); rect(ctx, ex - cw * 0.12, g - fh * 0.95, cw * 0.94, fh * 0.1, shade(wall, -0.2), oc(env, wall), 3);
    if (pw > 0) T.addLight(ctx, ex + cw * 0.35, g - fh * 0.9, {kind: 'point', r: U * 1.2, color: '#FFE2A8', a: 0.8 * pw});
    // street
    ctx.fillStyle = shade(P.ground, n ? 0.05 : 0.25); ctx.fillRect(-W, g, W * 3, H); ctx.fillStyle = shade(P.ground, n ? -0.2 : 0); ctx.fillRect(-W, g + U * 0.18, W * 3, H);
    ctx.fillStyle = rgba('#FFFFFF', 0.35); for (let x = -W; x < W * 2; x += U * 0.6) ctx.fillRect(x, g + U * 0.4, U * 0.3, U * 0.03);
  });
  env.L(1.0, () => { const unit = U / 1000; [[0.08, g + U * 0.02, 'lamp_post', 0.55], [0.86, g + U * 0.02, 'lamp_post', 0.55]].forEach(([x, y, id, s]) => {
    ctx.save(); ctx.translate(x * W, y); ctx.scale(unit * s, unit * s); T.ITEMS[id].draw(ctx, () => null, {on: pw > 0.5}, env); ctx.restore(); });
    if (o.cars !== false) { ctx.save(); ctx.translate(W * 0.28, g + U * 0.3); ctx.scale(unit * 0.42, unit * 0.42); T.ITEMS.car.draw(ctx, c => oc(env, c), {color: '#5A6F8A', dark: n}, env); ctx.restore(); }
  });
}, front(env, o) { const {W, H, U, P} = env; if (!o.trees) return; env.L(1.35, () => T.soft(env, 8, (ctx, e) => { const unit = U / 1000;
  [[-0.04, 1.02, 1.3], [1.04, 1.03, 1.5]].forEach(([x, y, s]) => { ctx.save(); ctx.translate(x * W, y * H); ctx.scale(unit * s, unit * s); T.ITEMS.tree.draw(ctx, () => null, {color: shade(P.olive || '#3B3D24', -0.2)}, e); ctx.restore(); }); })); }, ambk: 0.72};

// ---------------------------------------------------------------- stairwell (Soviet podъезд: two-tone wall, zigzag flight)
S.stairwell = {ground: 0.86, ground_l: 0.9, draw(env, o) {
  const {ctx, W, H, U, P} = env, g = env.ground, pw = power(env, o);
  const low = o.paint || '#4F7A6E', up = '#D6D0C2', split = g - U * 0.95;
  env.L(1, () => {
    ctx.fillStyle = up; ctx.fillRect(-W, -H, W * 3, split + H); ctx.fillStyle = low; ctx.fillRect(-W, split, W * 3, H); ctx.fillStyle = shade(low, -0.3); ctx.fillRect(-W, split - 6, W * 3, 10);
    ctx.fillStyle = rgba('#000', 0.06); const R = rng(5); for (let i = 0; i < 30; i++) { ell(ctx, R() * W, R() * split, U * 0.1 * R(), U * 0.06 * R()); ctx.fill(); }
    // floor number stencil
    if (o.floor != null) { ctx.save(); ctx.font = T.font(900, U * 0.42, 'Unbounded'); ctx.fillStyle = rgba(o.floor_color || '#B23A30', 0.85); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(String(o.floor), W * (env.portrait ? 0.26 : 0.2), split - U * 0.62); ctx.restore(); }
    // window on landing
    const wx = W * (env.portrait ? 0.66 : 0.7), wy = g - U * 2.3; rect(ctx, wx, wy, U * 0.5, U * 0.62, night(env) ? '#1B2433' : '#B9CCD6', oc(env, '#B9CCD6'), 4);
    ctx.strokeStyle = '#EDE9E0'; ctx.lineWidth = 8; ctx.strokeRect(wx, wy, U * 0.5, U * 0.62); ctx.beginPath(); ctx.moveTo(wx + U * 0.25, wy); ctx.lineTo(wx + U * 0.25, wy + U * 0.62); ctx.stroke();
    // flight of stairs: bottom-left -> upper-right
    const x0 = W * (env.portrait ? 0.4 : 0.45), x1 = W * (env.portrait ? 1.0 : 0.9), y0 = g + U * 0.02, y1 = g - U * 1.15, steps = 9, sw = (x1 - x0) / steps, sh = (y0 - y1) / steps;
    ctx.beginPath(); ctx.moveTo(x0, H * 1.2); ctx.lineTo(x0, y0); for (let i = 0; i < steps; i++) { ctx.lineTo(x0 + i * sw, y0 - (i + 1) * sh); ctx.lineTo(x0 + (i + 1) * sw, y0 - (i + 1) * sh); }
    ctx.lineTo(W * 1.5, y1); ctx.lineTo(W * 1.5, H * 1.2); ctx.closePath(); fill(ctx, '#9A958C', oc(env, '#9A958C'));
    ctx.fillStyle = rgba('#000', 0.12); for (let i = 0; i < steps; i++) ctx.fillRect(x0 + i * sw, y0 - (i + 1) * sh, sw, sh * 0.25);
    // railing
    ctx.strokeStyle = '#3A3F46'; ctx.lineWidth = 6; for (let i = 0; i <= steps; i++) { const x = x0 + i * sw + sw * 0.5, yb = y0 - (i + 1) * sh; ctx.beginPath(); ctx.moveTo(x, yb); ctx.lineTo(x, yb - U * 0.5); ctx.stroke(); }
    ctx.strokeStyle = '#7A4A2A'; ctx.lineWidth = 16; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x0, y0 - sh - U * 0.5); ctx.lineTo(x1 + sw, y1 - U * 0.5 - sh); ctx.stroke();
    // mailboxes + panel
    rect(ctx, W * 0.04, split - U * 0.42, U * 0.5, U * 0.32, '#3F6EA8', oc(env, '#3F6EA8'), 3); ctx.strokeStyle = shade('#3F6EA8', -0.3); ctx.lineWidth = 3; for (let i = 1; i < 4; i++) { ctx.beginPath(); ctx.moveTo(W * 0.04 + i * U * 0.125, split - U * 0.42); ctx.lineTo(W * 0.04 + i * U * 0.125, split - U * 0.1); ctx.stroke(); }
    rect(ctx, W * 0.8, split - U * 0.7, U * 0.3, U * 0.4, '#8C949B', oc(env, '#8C949B'), 3); ctx.fillStyle = T.UI.warn; ctx.beginPath(); ctx.moveTo(W * 0.8 + U * 0.15, split - U * 0.62); ctx.lineTo(W * 0.8 + U * 0.24, split - U * 0.46); ctx.lineTo(W * 0.8 + U * 0.06, split - U * 0.46); ctx.closePath(); ctx.fill();
    // wall lamp
    const lx = W * 0.5, ly = split - U * 1.2; ell(ctx, lx, ly, U * 0.07, U * 0.09); ctx.fillStyle = pw > 0.5 ? '#FFF2C8' : '#6B6F75'; ctx.fill(); ctx.strokeStyle = '#2A2E36'; ctx.lineWidth = 4; ell(ctx, lx, ly, U * 0.08, U * 0.1); ctx.stroke();
    if (pw > 0) T.addLight(ctx, lx, ly, {kind: 'point', r: U * 2.4, color: '#FFE2A8', a: 0.8 * pw, flicker: o.flicker ? 1 : 0});
  });
}};
S.stairwell.ambk = 0.85;

// ---------------------------------------------------------------- dacha / farm (log house, fence, garden beds); snow with time: winter or snow: true
S.dacha = {ground: 0.82, ground_l: 0.86, draw(env, o) {
  const {ctx, W, H, U, P} = env, g = env.ground, n = night(env), snow = o.snow || timeOf(env) === 'winter', pw = power(env, o);
  env.L(0, () => { sky(env, o); if (n) stars(env); sun(env, W * 0.78, H * 0.12, U * 0.08); if (!n) clouds(env, 0.06, 0.22, 4, 7, rgba('#FFFFFF', 0.6)); });
  env.L(0.2, () => { hills(env, g - H * 0.12, H * 0.06, snow ? '#C9D3DA' : P.far, 3); haze(env, g - H * 0.22, g - H * 0.08, 0.35); treeLine(env, g - H * 0.09, U * 0.55, shade(P.olive || '#3B3D24', n ? 0 : 0.1), 13, snow); });
  env.L(0.5, () => { ctx.fillStyle = snow ? '#E3E9EE' : P.ground; ctx.fillRect(-W, g - H * 0.08, W * 3, H); haze(env, g - H * 0.1, g - H * 0.05, 0.25);
    if (o.barn) { const bx = W * 0.05, by = g - H * 0.075; rect(ctx, bx, by - U * 0.55, U * 0.7, U * 0.55, '#A8322A', oc(env, '#A8322A'), 2); ctx.beginPath(); ctx.moveTo(bx - U * 0.06, by - U * 0.55); ctx.lineTo(bx + U * 0.35, by - U * 0.85); ctx.lineTo(bx + U * 0.76, by - U * 0.55); ctx.closePath(); fill(ctx, snow ? '#F2F5F7' : '#5A3E2E', oc(env, '#5A3E2E')); } });
  env.L(1, () => {
    const hx = (o.house_x != null ? o.house_x : (env.portrait ? 0.52 : 0.6)) * W, hw = U * 1.5, hh = U * 1.0, hy = g - U * 0.12;
    // house
    const logC = o.wood || '#8A5A3A'; rect(ctx, hx - hw / 2, hy - hh, hw, hh, logC, oc(env, logC), 2); ctx.strokeStyle = rgba(shade(logC, -0.5), 0.45); ctx.lineWidth = 4;
    for (let y = hy - hh + U * 0.08; y < hy; y += U * 0.08) { ctx.beginPath(); ctx.moveTo(hx - hw / 2, y); ctx.lineTo(hx + hw / 2, y); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(hx - hw / 2 - U * 0.12, hy - hh); ctx.lineTo(hx, hy - hh - U * 0.62); ctx.lineTo(hx + hw / 2 + U * 0.12, hy - hh); ctx.closePath(); fill(ctx, o.roof || '#4F6E5A', oc(env, '#4F6E5A'));
    if (snow) { ctx.beginPath(); ctx.moveTo(hx - hw / 2 - U * 0.14, hy - hh + 4); ctx.lineTo(hx, hy - hh - U * 0.64); ctx.lineTo(hx + hw / 2 + U * 0.14, hy - hh + 4); ctx.lineTo(hx + hw / 2, hy - hh - U * 0.06); ctx.lineTo(hx, hy - hh - U * 0.5); ctx.lineTo(hx - hw / 2, hy - hh - U * 0.06); ctx.closePath(); ctx.fillStyle = '#F4F7FA'; ctx.fill(); }
    ctx.beginPath(); ctx.moveTo(hx - U * 0.2, hy - hh - U * 0.1); ctx.lineTo(hx, hy - hh - U * 0.38); ctx.lineTo(hx + U * 0.2, hy - hh - U * 0.1); ctx.closePath(); fill(ctx, '#EDE6D6', oc(env, '#EDE6D6'));
    rect(ctx, hx + hw * 0.22, hy - hh - U * 0.62, U * 0.14, U * 0.4, '#8A5A4A', oc(env, '#8A5A4A'), 2);
    if (o.smoke !== false && (snow || n || o.smoke)) T.FX.smoke(Object.assign({}, env), {at: [(hx + hw * 0.22 + U * 0.07) / W, (hy - hh - U * 0.64) / H], size: 0.5, wind: 0.6});
    // windows with carved frames (nalichnik)
    [-0.26, 0.26].forEach(k => { const wx = hx + k * hw - U * 0.15, wy = hy - hh * 0.72; const lit = (n || timeOf(env) === 'dusk') && pw > 0 ? 1 : (o.candle && n ? 0.5 : 0);
      rect(ctx, wx, wy, U * 0.3, U * 0.36, lit ? '#FFC870' : (n ? '#1B2433' : '#9FC3D6'), oc(env, '#EDE6D6'), 2); if (lit) winLight(env, wx, wy, U * 0.3, U * 0.36, lit);
      ctx.strokeStyle = '#EDE6D6'; ctx.lineWidth = 8; ctx.strokeRect(wx, wy, U * 0.3, U * 0.36); ctx.beginPath(); ctx.moveTo(wx + U * 0.15, wy); ctx.lineTo(wx + U * 0.15, wy + U * 0.36); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(wx - U * 0.05, wy - U * 0.02); ctx.lineTo(wx + U * 0.15, wy - U * 0.12); ctx.lineTo(wx + U * 0.35, wy - U * 0.02); ctx.closePath(); fill(ctx, '#EDE6D6', oc(env, '#EDE6D6')); });
    // porch + door
    rect(ctx, hx - U * 0.14, hy - U * 0.62, U * 0.28, U * 0.62, '#6A4B30', oc(env, '#6A4B30'), 2); rect(ctx, hx - U * 0.22, hy - U * 0.04, U * 0.44, U * 0.08, '#7A5A3C', oc(env, '#7A5A3C'), 2);
    if (pw > 0 && n) T.addLight(ctx, hx, hy - U * 0.7, {kind: 'point', r: U * 1.0, color: '#FFD28A', a: 0.7 * pw});
    // fence
    const fy = g - U * 0.02; ctx.fillStyle = snow ? '#E8EDF1' : P.ground; ctx.fillRect(-W, hy, W * 3, H);
    for (let x = -W * 0.2; x < W * 1.2; x += U * 0.12) { ctx.beginPath(); ctx.moveTo(x, fy); ctx.lineTo(x, fy - U * 0.38); ctx.lineTo(x + U * 0.04, fy - U * 0.44); ctx.lineTo(x + U * 0.08, fy - U * 0.38); ctx.lineTo(x + U * 0.08, fy); ctx.closePath();
      fill(ctx, o.fence || '#B8A07A', oc(env, '#B8A07A')); if (snow) { ctx.fillStyle = '#F4F7FA'; ctx.fillRect(x, fy - U * 0.4, U * 0.08, U * 0.03); } }
    ctx.fillStyle = shade(o.fence || '#B8A07A', -0.2); ctx.fillRect(-W, fy - U * 0.3, W * 3, U * 0.04); ctx.fillRect(-W, fy - U * 0.12, W * 3, U * 0.04);
    // ground in front of the fence + garden beds
    ctx.fillStyle = vgrad(ctx, fy, H, [[0, snow ? '#EEF2F5' : P.ground], [1, snow ? '#DCE4EA' : shade(P.ground, -0.18)]]); ctx.fillRect(-W, fy, W * 3, H);
    if (o.beds !== false && !snow) { for (let i = 0; i < 3; i++) { const by = fy + U * (0.12 + i * 0.12) + (H - fy) * 0.0; const bx = W * 0.05; rect(ctx, bx, by, W * 0.42, U * 0.07, '#6B4A33', null, 30);
      for (let x = bx + U * 0.06; x < bx + W * 0.4; x += U * 0.13) { ctx.fillStyle = P.grass || '#505D36'; ell(ctx, x, by + U * 0.01, U * 0.04, U * 0.03); ctx.fill(); } } }
  });
}, front(env, o) { const {W, H, U, P} = env, snow = o.snow || timeOf(env) === 'winter'; if (snow || o.fg === false) return;
  env.L(1.35, () => grassTufts(env, H * 1.0, 14, shade(P.grass || '#505D36', -0.25), 77, 6)); }};

// ---------------------------------------------------------------- forest
function pine(ctx, x, base, h, c, snow, tiers = 3) { const w = h * 0.36; ctx.fillStyle = shade(c, -0.25); ctx.fillRect(x - h * 0.025, base - h * 0.16, h * 0.05, h * 0.18);
  for (let i = 0; i < tiers; i++) { const k = i / tiers, yb = base - h * (0.12 + k * 0.62), ww = w * (1 - k * 0.55), th = h * 0.42;
    ctx.beginPath(); ctx.moveTo(x - ww, yb); ctx.quadraticCurveTo(x - ww * 0.4, yb - th * 0.45, x, yb - th); ctx.quadraticCurveTo(x + ww * 0.4, yb - th * 0.45, x + ww, yb);
    ctx.quadraticCurveTo(x, yb - th * 0.12, x - ww, yb); ctx.closePath(); ctx.fillStyle = shade(c, k * 0.08); ctx.fill();
    if (snow) { ctx.save(); ctx.clip(); ctx.fillStyle = rgba('#F4F7FA', 0.9); ctx.fillRect(x - ww, yb - th, ww * 2, th * 0.3); ctx.restore(); } } }
function pineRow(env, base, hmin, hmax, c, seed, snow, gap = 0.5) { const {ctx, W} = env, R = rng(seed); const items = [];
  for (let x = -W * 0.5; x < W * 1.5; x += hmax * gap * (0.5 + R() * 0.7)) items.push([x + (R() - 0.5) * hmax * 0.2, lerp(hmin, hmax, R()), base + R() * hmax * 0.06]);
  items.sort((a, b) => a[2] - b[2]).forEach(([x, h, b]) => pine(ctx, x, b, h, c, snow)); }
S.forest = {ground: 0.84, ground_l: 0.88, ambk: 0.78, draw(env, o) {
  const {ctx, W, H, U, P} = env, g = env.ground, n = night(env), snow = o.snow || timeOf(env) === 'winter';
  const tc = o.trees || (n ? '#1E2B33' : '#3F5E45');
  env.L(0, () => { sky(env, o); if (n) stars(env, 60); sun(env, W * 0.7, H * 0.1, U * 0.07); if (!n) clouds(env, 0.05, 0.18, 3, 33, rgba('#FFFFFF', 0.5)); });
  env.L(0.15, () => { hills(env, g - H * 0.18, H * 0.05, mix(P.far, P.haze || P.sky[1], 0.3), 35); pineRow(env, g - H * 0.14, U * 0.4, U * 0.7, mix(tc, P.haze || P.sky[1], 0.62), 31, snow, 0.35); haze(env, g - H * 0.35, g - H * 0.1, 0.35); });
  env.L(0.35, () => { pineRow(env, g - H * 0.08, U * 0.8, U * 1.3, mix(tc, P.haze || P.sky[1], 0.42), 37, snow, 0.45); haze(env, g - H * 0.3, g - H * 0.05, 0.3 + (o.fog ? 0.3 : 0)); });
  env.L(0.65, () => { pineRow(env, g - H * 0.04, U * 1.4, U * 2.1, mix(tc, P.haze || P.sky[1], 0.18), 41, snow, 0.6); haze(env, g - H * 0.25, g, 0.12 + (o.fog ? 0.3 : 0)); });
  env.L(1, () => { ctx.fillStyle = vgrad(ctx, g - H * 0.05, H, [[0, snow ? '#E3E9EE' : shade(P.ground, -0.05)], [1, snow ? '#D2DCE3' : shade(P.ground, -0.3)]]); ctx.fillRect(-W, g - H * 0.05, W * 3, H);
    ctx.fillStyle = snow ? rgba('#FFFFFF', 0.6) : rgba(shade(P.ground, 0.3), 0.45); ctx.beginPath(); ctx.moveTo(W * 0.44, g - H * 0.05); ctx.quadraticCurveTo(W * 0.3, g + H * 0.05, W * 0.12, H * 1.05); ctx.lineTo(W * 0.88, H * 1.05); ctx.quadraticCurveTo(W * 0.62, g + H * 0.05, W * 0.54, g - H * 0.05); ctx.closePath(); ctx.fill();
    if (!snow) grassTufts(env, g + H * 0.02, 10, shade(P.grass || '#505D36', -0.1), 43, 0); });
}, front(env, o) { const {W, H, U, P} = env, snow = o.snow || timeOf(env) === 'winter', n = night(env); env.L(1.35, () => T.soft(env, 9, ctx => {
  const c = shade(o.trees || (n ? '#1E2B33' : '#3F5E45'), -0.35); pine(ctx, -W * 0.04, H * 1.02, U * 2.4, c, snow, 4); pine(ctx, W * 1.05, H * 1.04, U * 2.7, c, snow, 4); })); }};

// ---------------------------------------------------------------- street (city) / ruined
S.street = {ground: 0.84, ground_l: 0.88, draw(env, o) {
  const {ctx, W, H, U, P} = env, g = env.ground, n = night(env), pw = power(env, o), ru = o.ruined;
  env.L(0, () => { sky(env, o); if (n) stars(env, 40); sun(env, W * 0.2, H * 0.1, U * 0.07); if (!n && !ru) clouds(env, 0.05, 0.18, 3, 19, rgba('#FFFFFF', 0.5)); });
  env.L(0.3, () => { skyline(env, g - U * 0.5, 0.2, 0.4, shade(P.far, ru ? -0.1 : 0), 43, n ? 0.25 : 0, pw); haze(env, g - H * 0.45, g, ru ? 0.55 : 0.35); });
  env.L(1, () => {
    const R = rng(hash(o.seed || 'street')); let x = -W * 0.1; const cols = ['#C98E6B', '#8FA6A0', '#D9C49A', '#9C7E9A', '#A7B08A'];
    while (x < W * 1.1) { const bw = U * (0.9 + R() * 0.6), bh = U * (1.5 + R() * 1.0), c = cols[Math.floor(R() * cols.length)], wallC = n ? shade(c, -0.35) : c;
      rect(ctx, x, g - U * 0.25 - bh, bw, bh, wallC, oc(env, c), 2);
      for (let r = 0; r < 3; r++) for (let q = 0; q < 2; q++) { const wx = x + bw * (0.15 + q * 0.45), wy = g - U * 0.25 - bh + U * 0.2 + r * U * 0.42; if (wy > g - U * 1.0) continue;
        const lit = n && pw > 0 && R() < 0.5; const broken = ru && R() < 0.5;
        rect(ctx, wx, wy, bw * 0.3, U * 0.28, lit ? '#FFC870' : (n || ru ? '#1B2433' : '#9FC3D6'), oc(env, c), 2); if (lit) winLight(env, wx, wy, bw * 0.3, U * 0.28, 0.8);
        if (broken) { ctx.fillStyle = rgba('#DDF1FF', 0.5); ctx.beginPath(); ctx.moveTo(wx, wy); ctx.lineTo(wx + bw * 0.12, wy + U * 0.1); ctx.lineTo(wx, wy + U * 0.16); ctx.fill(); }
        if (ru && R() < 0.3) { ctx.save(); ctx.translate(wx + bw * 0.15, wy + U * 0.14); ctx.rotate(0.2); rect(ctx, -bw * 0.2, -U * 0.03, bw * 0.4, U * 0.06, '#A87B48', null, 2); ctx.restore(); } }
      // shopfront
      const sy = g - U * 1.0; rect(ctx, x + bw * 0.08, sy, bw * 0.84, U * 0.72, ru ? '#1B2433' : (n ? (pw > 0 ? '#E8D9A8' : '#1B2433') : '#B9D6E2'), oc(env, '#3A3F46'), 2);
      if (n && pw > 0 && !ru) winLight(env, x + bw * 0.08, sy, bw * 0.84, U * 0.72, 0.9, '#FFE2A8');
      const aw = ['#C8372D', '#2F6FB5', '#3E7B4F', '#E2A33B'][Math.floor(R() * 4)]; ctx.beginPath(); ctx.moveTo(x + bw * 0.04, sy - U * 0.02); ctx.lineTo(x + bw * 0.96, sy - U * 0.02); ctx.lineTo(x + bw, sy + U * 0.14); ctx.lineTo(x, sy + U * 0.14); ctx.closePath();
      fill(ctx, ru ? shade(aw, -0.4) : aw, oc(env, aw)); ctx.fillStyle = rgba('#FFFFFF', ru ? 0.15 : 0.6); for (let k = 0; k < 6; k += 2) ctx.fillRect(x + bw * k / 6, sy - U * 0.02, bw / 6, U * 0.16);
      x += bw + U * 0.04; }
    ctx.fillStyle = shade(P.ground, n ? 0.08 : 0.3); ctx.fillRect(-W, g - U * 0.28, W * 3, U * 0.3); ctx.fillStyle = shade('#5E646B', n ? -0.4 : -0.1); ctx.fillRect(-W, g + U * 0.02, W * 3, H);
    ctx.fillStyle = rgba('#F2F2F2', ru ? 0.25 : 0.55); for (let xx = -W; xx < W * 2; xx += U * 0.7) ctx.fillRect(xx, g + U * 0.35, U * 0.35, U * 0.04);
    if (ru) { const R2 = rng(97); for (let i = 0; i < 7; i++) { const rx = R2() * W, ry = g + U * (0.1 + R2() * 0.4), rs = U * (0.1 + R2() * 0.15); ctx.beginPath(); ctx.moveTo(rx - rs, ry); ctx.lineTo(rx - rs * 0.4, ry - rs * 0.7); ctx.lineTo(rx + rs * 0.3, ry - rs * 0.5); ctx.lineTo(rx + rs, ry); ctx.closePath(); fill(ctx, ['#7D7A73', '#8A8F94', '#6B5A4A'][i % 3], oc(env, '#7D7A73')); }
      const unit = U / 1000; ctx.save(); ctx.translate(W * 0.7, g + U * 0.25); ctx.rotate(-0.1); ctx.scale(unit * 0.5, unit * 0.5); T.ITEMS.car.draw(ctx, c => oc(env, c), {color: '#6B7A6E', dark: true}, env); ctx.restore(); }
  });
  if (ru) { T.FX.smoke(env, {at: [0.15, 0.55], dark: true, size: 1.2}); T.FX.smoke(env, {at: [0.85, 0.5], dark: true, size: 0.9}); }
}};

// ---------------------------------------------------------------- mall interior (glass storefronts, tiles, ceiling lights)
S.mall = {ground: 0.86, ground_l: 0.9, draw(env, o) {
  const {ctx, W, H, U, P} = env, g = env.ground, pw = power(env, o), wb = g - U * 0.3;
  env.L(1, () => {
    ctx.fillStyle = vgrad(ctx, 0, wb, [[0, '#B9BDC2'], [1, '#D9DCDF']]); ctx.fillRect(-W, -H, W * 3, wb + H);
    ctx.fillStyle = '#8E949A'; ctx.fillRect(-W, wb - U * 2.05, W * 3, U * 0.12);
    const sw = U * 1.15; for (let x = -U * 0.3, i = 0; x < W + U; x += sw + U * 0.12, i++) {
      rect(ctx, x, wb - U * 1.7, sw, U * 0.22, ['#2F6FB5', '#C8372D', '#3E7B4F', '#E2A33B', '#7A4A8A'][i % 5], oc(env, '#2F6FB5'), 4);
      ctx.save(); rr(ctx, x, wb - U * 1.42, sw, U * 1.42, 2); ctx.clip(); ctx.fillStyle = vgrad(ctx, wb - U * 1.42, wb, [[0, pw ? '#DDEFF7' : '#1E2633'], [1, pw ? '#BFD9E6' : '#141A24']]); ctx.fillRect(x, wb - U * 1.42, sw, U * 1.42);
      ctx.fillStyle = rgba('#FFFFFF', pw ? 0.35 : 0.08); ctx.beginPath(); ctx.moveTo(x + sw * 0.1, wb); ctx.lineTo(x + sw * 0.5, wb - U * 1.42); ctx.lineTo(x + sw * 0.62, wb - U * 1.42); ctx.lineTo(x + sw * 0.22, wb); ctx.fill();
      ctx.fillStyle = rgba('#000', 0.18); for (let k = 0; k < 3; k++) ctx.fillRect(x + sw * 0.1, wb - U * (0.35 + k * 0.38), sw * 0.8, U * 0.04); ctx.restore();
      ctx.strokeStyle = '#7D848B'; ctx.lineWidth = 8; ctx.strokeRect(x, wb - U * 1.42, sw, U * 1.42); }
    // floor tiles
    ctx.fillStyle = '#E6E2DA'; ctx.fillRect(-W, wb, W * 3, H); ctx.strokeStyle = rgba('#9A958C', 0.5); ctx.lineWidth = 3; const vx = W / 2, vy = wb - U * 2;
    for (let i = -12; i <= 12; i++) { ctx.beginPath(); ctx.moveTo(vx + (i * U * 0.3) * 0.15, wb); ctx.lineTo(vx + i * U * 0.6, H * 1.2); ctx.stroke(); }
    for (let k = 0; k < 6; k++) { const y = wb + (H - wb) * Math.pow(k / 6, 1.6); ctx.beginPath(); ctx.moveTo(-W, y); ctx.lineTo(W * 2, y); ctx.stroke(); }
    ctx.fillStyle = rgba('#FFFFFF', 0.25); ctx.fillRect(-W, wb + U * 0.02, W * 3, U * 0.05);
    for (let x = W * 0.1; x < W; x += W * 0.3) { rect(ctx, x, -10, U * 0.4, U * 0.06, pw ? '#FFFBEA' : '#5A5F66', null, 3); if (pw) T.addLight(ctx, x + U * 0.2, U * 0.05, {kind: 'cone', r: U * 3, ang: Math.PI / 2, spread: 0.5, color: '#FFF6DE', a: 0.5 * pw}); }
    if (!pw) { ctx.fillStyle = '#2E9E5B'; rr(ctx, W * 0.8, wb - U * 1.95, U * 0.3, U * 0.13, 4); ctx.fill(); T.addLight(ctx, W * 0.8 + U * 0.15, wb - U * 1.9, {kind: 'point', r: U * 0.9, color: '#3DDC84', a: 0.8}); }
  });
}};

// ---------------------------------------------------------------- train / metro car (moving view)
S.train = {ground: 0.84, ground_l: 0.88, draw(env, o) {
  const {ctx, W, H, U, P, lt} = env, g = env.ground, pw = power(env, o), tunnel = o.view !== 'outside', sway = Math.sin(lt * 2.1) * U * 0.004;
  env.L(1, () => { ctx.save(); ctx.translate(0, sway);
    const wy = g - U * 1.55, wh = U * 0.62; ctx.fillStyle = '#C9D1D6'; ctx.fillRect(-W, -H, W * 3, H * 3);
    const ww = U * 0.9; for (let x = -U * 0.2; x < W + U; x += ww + U * 0.35) {
      ctx.save(); rr(ctx, x, wy, ww, wh, 26); ctx.clip();
      if (tunnel) { ctx.fillStyle = '#10141B'; ctx.fillRect(x, wy, ww, wh); const sp = (lt * W * 1.8) % (U * 1.6); for (let k = -1; k < 3; k++) { const lx = x + ww - (sp + k * U * 1.6) % (ww + U * 1.6);
          ctx.fillStyle = rgba('#FFD28A', 0.8); ctx.fillRect(lx, wy + wh * 0.4, U * 0.4, 6); } ctx.fillStyle = rgba('#3A4250', 0.8); ctx.fillRect(x, wy + wh * 0.7, ww, 4); }
      else { ctx.fillStyle = vgrad(ctx, wy, wy + wh, [[0, P.sky[0]], [1, P.sky[1]]]); ctx.fillRect(x, wy, ww, wh); const sp = lt * W * 0.6;
        ctx.fillStyle = P.far; for (let k = 0; k < 6; k++) { const hx = x + ((k * U * 0.5 - sp * 0.3) % (ww + U) + ww + U) % (ww + U) - U * 0.3; ell(ctx, hx, wy + wh * 0.85, U * 0.3, U * 0.12); ctx.fill(); }
        ctx.fillStyle = '#4A4F55'; for (let k = 0; k < 4; k++) { const px = x + ((k * U * 0.6 - sp) % (ww + U * 0.6) + ww + U * 0.6) % (ww + U * 0.6) - U * 0.1; ctx.fillRect(px, wy, 6, wh); } }
      ctx.restore(); ctx.strokeStyle = '#8C949B'; ctx.lineWidth = 12; rr(ctx, x, wy, ww, wh, 26); ctx.stroke(); }
    ctx.fillStyle = '#AEB7BE'; ctx.fillRect(-W, g - U * 0.75, W * 3, U * 0.75);
    for (let x = -U * 0.1; x < W + U; x += U * 0.55) { rect(ctx, x, g - U * 0.5, U * 0.5, U * 0.16, o.seat || '#3F6EA8', oc(env, '#3F6EA8'), 10); rect(ctx, x, g - U * 0.86, U * 0.5, U * 0.38, shade(o.seat || '#3F6EA8', 0.1), oc(env, '#3F6EA8'), 10); }
    ctx.fillStyle = '#6E757C'; ctx.fillRect(-W, g - U * 0.02, W * 3, H);
    ctx.strokeStyle = '#D8DDE1'; ctx.lineWidth = 14; for (let x = U * 0.3; x < W; x += U * 1.3) { ctx.beginPath(); ctx.moveTo(x, -10); ctx.lineTo(x, g); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(-W, wy - U * 0.25); ctx.lineTo(W * 2, wy - U * 0.25); ctx.stroke();
    for (let x = W * 0.15; x < W; x += W * 0.35) { rect(ctx, x, U * 0.02, U * 0.5, U * 0.06, pw ? '#FFFBEA' : '#5A5F66', null, 4); if (pw) T.addLight(ctx, x + U * 0.25, U * 0.08, {kind: 'point', r: U * 2.2, color: '#F4F8FF', a: 0.55 * pw, flicker: o.flicker ? 1 : 0}); }
    ctx.restore(); });
}};

// ---------------------------------------------------------------- bunker / basement
S.bunker = {ground: 0.85, ground_l: 0.88, draw(env, o) {
  const {ctx, W, H, U, P, t} = env, g = env.ground, pw = power(env, Object.assign({power: true}, o)), wb = g - U * 0.12;
  env.L(1, () => { ctx.fillStyle = '#8E918C'; ctx.fillRect(-W, -H, W * 3, wb + H); ctx.strokeStyle = rgba('#5A5D58', 0.6); ctx.lineWidth = 4;
    for (let y = wb, r = 0; y > -H * 0.2; y -= U * 0.2, r++) { ctx.beginPath(); ctx.moveTo(-W, y); ctx.lineTo(W * 2, y); ctx.stroke(); for (let x = (r % 2) * U * 0.2 - W * 0.2; x < W * 1.2; x += U * 0.4) { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - U * 0.2); ctx.stroke(); } }
    ctx.strokeStyle = '#5E6A73'; ctx.lineWidth = U * 0.07; ctx.beginPath(); ctx.moveTo(-W, U * 0.12); ctx.lineTo(W * 2, U * 0.12); ctx.stroke(); ctx.lineWidth = U * 0.04; ctx.beginPath(); ctx.moveTo(-W, U * 0.26); ctx.lineTo(W * 2, U * 0.26); ctx.stroke();
    const unit = U / 1000; const put = (id, x, sc, k) => { ctx.save(); ctx.translate(x, wb + U * 0.03); ctx.scale(unit * sc, unit * sc); T.ITEMS[id].draw(ctx, c => oc(env, c), Object.assign({seed: 'bunker'}, k || {}), env); ctx.restore(); };
    put('shelf', W * 0.2, 1.0, {full: o.full == null ? 0.85 : o.full}); put('barrel', W * 0.78, 0.9); put('barrel', W * 0.9, 0.9, {color: '#4F6E5A'});
    ctx.fillStyle = vgrad(ctx, wb, H, [[0, '#7A7D78'], [1, '#5E615C']]); ctx.fillRect(-W, wb, W * 3, H);
    const lx = W * 0.55, sw = Math.sin(t * 1.3) * 0.05, ly = U * 0.9; ctx.save(); ctx.translate(lx, 0); ctx.rotate(sw); ctx.strokeStyle = '#2A2E36'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, ly); ctx.stroke();
    ell(ctx, 0, ly + U * 0.05, U * 0.045, U * 0.06); ctx.fillStyle = pw ? '#FFF2C8' : '#6B6F75'; ctx.fill(); if (pw) T.addLight(ctx, 0, ly + U * 0.05, {kind: 'point', r: U * 2.4, color: '#FFD9A0', a: 0.9 * pw, flicker: 0.4}); ctx.restore(); });
}};

// ---------------------------------------------------------------- roof
S.roof = {ground: 0.86, ground_l: 0.9, draw(env, o) {
  const {ctx, W, H, U, P} = env, g = env.ground, n = night(env), pw = power(env, o);
  env.L(0, () => { sky(env, Object.assign({sky_h: 0.9}, o)); if (n) stars(env, 110); sun(env, W * 0.25, H * 0.14, U * 0.08); });
  env.L(0.2, () => { skyline(env, g - U * 0.3, 0.15, 0.3, shade(P.far, -0.05), 53, n ? 0.4 : 0, pw); haze(env, g - H * 0.32, g, 0.4); });
  env.L(0.5, () => { skyline(env, g - U * 0.15, 0.08, 0.18, shade(P.mid, 0.05), 59, n ? 0.45 : 0, pw); });
  env.L(1, () => { ctx.fillStyle = '#6E6A64'; ctx.fillRect(-W, g - U * 0.05, W * 3, H); rect(ctx, -W, g - U * 0.3, W * 3, U * 0.26, '#8F8A82', oc(env, '#8F8A82')); ctx.fillStyle = '#B9B4AA'; ctx.fillRect(-W, g - U * 0.32, W * 3, U * 0.05);
    const tx = W * 0.78; rect(ctx, tx - U * 0.35, g - U * 1.3, U * 0.7, U * 0.6, '#7A8088', oc(env, '#7A8088'), U * 0.12); ctx.fillStyle = rgba('#000', 0.15); ctx.fillRect(tx - U * 0.35, g - U * 1.05, U * 0.7, U * 0.05); ctx.fillRect(tx - U * 0.35, g - U * 0.88, U * 0.7, U * 0.05); ctx.strokeStyle = '#4A5058'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(tx - U * 0.3, g - U * 0.7); ctx.lineTo(tx - U * 0.3, g - U * 0.3); ctx.moveTo(tx + U * 0.3, g - U * 0.7); ctx.lineTo(tx + U * 0.3, g - U * 0.3); ctx.stroke();
    ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(W * 0.15, g - U * 0.3); ctx.lineTo(W * 0.15, g - U * 1.6); ctx.moveTo(W * 0.15 - U * 0.15, g - U * 1.4); ctx.lineTo(W * 0.15 + U * 0.15, g - U * 1.4); ctx.moveTo(W * 0.15 - U * 0.1, g - U * 1.5); ctx.lineTo(W * 0.15 + U * 0.1, g - U * 1.5); ctx.stroke();
    ell(ctx, W * 0.15, g - U * 1.62, 6, 6); ctx.fillStyle = '#E53935'; ctx.fill(); if (n) T.addLight(ctx, W * 0.15, g - U * 1.62, {kind: 'point', r: U * 0.3, color: '#FF4A3D', a: 0.5 + 0.5 * Math.sin(env.t * 3)}); });
}};

// ---------------------------------------------------------------- beach (+ tsunami wave: set.wave = scene time it starts)
S.beach = {ground: 0.84, ground_l: 0.88, draw(env, o) {
  const {ctx, W, H, U, P, lt, t} = env, g = env.ground, n = night(env), hz = g - H * 0.22;
  env.L(0, () => { sky(env, o); if (n) stars(env); sun(env, W * 0.7, hz - H * 0.12, U * 0.1); if (!n) clouds(env, 0.06, 0.2, 3, 61, rgba('#FFFFFF', 0.6)); });
  env.L(0.3, () => { ctx.fillStyle = vgrad(ctx, hz, g, [[0, n ? '#1B3550' : '#3F8FB5'], [1, n ? '#245070' : '#5FB4D3']]); ctx.fillRect(-W, hz, W * 3, H);
    ctx.strokeStyle = rgba('#FFFFFF', 0.45); ctx.lineWidth = 4; for (let i = 0; i < 6; i++) { const y = hz + (g - hz) * (0.15 + i * 0.15); ctx.beginPath(); for (let x = -W; x < W * 2; x += 30) ctx.lineTo(x, y + Math.sin(x / 60 + t * 1.5 + i) * 4); ctx.stroke(); }
    if (o.wave != null && lt > o.wave) { const k = E.io(clamp((lt - o.wave) / 4)), wh = H * 0.32 * k; ctx.beginPath(); ctx.moveTo(-W, hz + 4); for (let x = -W; x <= W * 2; x += 20) ctx.lineTo(x, hz - wh * (0.8 + 0.2 * Math.sin(x / 120 + t))); ctx.lineTo(W * 2, hz + 4); ctx.closePath();
      ctx.fillStyle = vgrad(ctx, hz - wh, hz, [[0, '#DDEFF5'], [0.12, '#4F9DC0'], [1, '#2A6F93']]); ctx.fill(); } });
  env.L(1, () => { ctx.fillStyle = vgrad(ctx, g - H * 0.06, H, [[0, n ? '#6B6450' : '#E9D7A8'], [1, n ? '#4F4A3B' : '#D9C08A']]); ctx.beginPath(); ctx.moveTo(-W, g - H * 0.04);
    for (let x = -W; x <= W * 2; x += 30) ctx.lineTo(x, g - H * 0.04 + Math.sin(x / 90 + t * 1.2) * 6); ctx.lineTo(W * 2, H * 2); ctx.lineTo(-W, H * 2); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = rgba('#FFFFFF', 0.7); ctx.lineWidth = 6; ctx.beginPath(); for (let x = -W; x <= W * 2; x += 30) ctx.lineTo(x, g - H * 0.04 + Math.sin(x / 90 + t * 1.2) * 6); ctx.stroke(); });
}};

// ---------------------------------------------------------------- field / road
S.road = {ground: 0.84, ground_l: 0.88, draw(env, o) {
  const {ctx, W, H, U, P} = env, g = env.ground, n = night(env), snow = o.snow || timeOf(env) === 'winter', hz = g - H * 0.2;
  env.L(0, () => { sky(env, o); if (n) stars(env); sun(env, W * 0.75, hz - H * 0.15, U * 0.09); if (!n) clouds(env, 0.05, 0.22, 4, 67, rgba('#FFFFFF', 0.6)); });
  env.L(0.2, () => { treeLine(env, hz, U * 0.4, shade(P.olive || '#3B3D24', n ? 0 : 0.15), 71, snow); haze(env, hz - U * 0.4, hz + 4, 0.4); });
  env.L(1, () => { ctx.fillStyle = vgrad(ctx, hz, H, [[0, snow ? '#E3E9EE' : P.ground], [1, snow ? '#D2DCE3' : shade(P.grass || P.ground, -0.1)]]); ctx.fillRect(-W, hz, W * 3, H * 2);
    if (!snow) { ctx.strokeStyle = rgba(shade(P.ground, -0.3), 0.3); ctx.lineWidth = 3; for (let i = -10; i <= 10; i++) { ctx.beginPath(); ctx.moveTo(W / 2 + i * 8, hz); ctx.lineTo(W / 2 + i * W * 0.25, H * 1.1); ctx.stroke(); } }
    ctx.fillStyle = n ? '#2A2E35' : '#5E646B'; ctx.beginPath(); ctx.moveTo(W * 0.48, hz); ctx.lineTo(W * 0.52, hz); ctx.lineTo(W * 1.12, H * 1.4); ctx.lineTo(-W * 0.12, H * 1.4); ctx.closePath(); ctx.fill();
    ctx.fillStyle = rgba('#F2F2F2', 0.8); for (let k = 0; k < 8; k++) { const a = Math.pow(k / 8, 2), b = Math.pow((k + 0.5) / 8, 2), ya = lerp(hz, H * 1.3, a), yb = lerp(hz, H * 1.3, b), wa = lerp(2, 18, a), wb2 = lerp(2, 18, b);
      ctx.beginPath(); ctx.moveTo(W / 2 - wa, ya); ctx.lineTo(W / 2 + wa, ya); ctx.lineTo(W / 2 + wb2, yb); ctx.lineTo(W / 2 - wb2, yb); ctx.closePath(); ctx.fill(); }
    ctx.strokeStyle = '#4A3B2E'; for (let k = 0; k < 6; k++) { const a = Math.pow(k / 6, 2), x = lerp(W * 0.6, W * 1.2, a), y = lerp(hz, H * 1.05, a), ph = lerp(20, U * 1.6, a); ctx.lineWidth = lerp(2, 14, a); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - ph); ctx.stroke(); } });
}};

// ---------------------------------------------------------------- meadow (bright, for kids cartoons)
S.meadow = {ground: 0.82, ground_l: 0.86, draw(env, o) {
  const {ctx, W, H, U, P, t} = env, g = env.ground;
  env.L(0, () => { sky(env, o); const sx = W * 0.8, sy = H * 0.11, r = U * 0.11; ctx.save(); ctx.translate(sx, sy); ctx.rotate(t * 0.2); ctx.fillStyle = rgba('#FFE066', 0.5);
    for (let i = 0; i < 12; i++) { ctx.rotate(Math.PI / 6); ctx.beginPath(); ctx.moveTo(r * 1.2, -r * 0.12); ctx.lineTo(r * 1.8, 0); ctx.lineTo(r * 1.2, r * 0.12); ctx.fill(); } ctx.restore();
    ell(ctx, sx, sy, r, r); fill(ctx, '#FFD84D', oc(env, '#FFD84D')); clouds(env, 0.05, 0.25, 5, 89, '#FFFFFF'); });
  env.L(0.3, () => hills(env, g - H * 0.1, H * 0.08, '#9EDB8B', 91, 0.6));
  env.L(0.6, () => hills(env, g - H * 0.04, H * 0.06, '#7CCB5B', 93, 0.8));
  env.L(1, () => { ctx.fillStyle = vgrad(ctx, g - H * 0.02, H, [[0, '#6CC36A'], [1, '#4FA845']]); ctx.fillRect(-W, g - H * 0.02, W * 3, H); const R = rng(95);
    for (let i = 0; i < 40; i++) { const x = R() * W * 1.2 - W * 0.1, y = g + R() * (H - g); ctx.fillStyle = ['#FFFFFF', '#FFD84D', '#FF7AC8'][i % 3]; ell(ctx, x, y, 6 + R() * 6, 6 + R() * 6); ctx.fill(); } });
}};
T.SET_NAMES = Object.keys(S);
})();
