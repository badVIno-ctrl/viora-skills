/* TOON props: hand items and world props. Units: 1000 = default human height. Origin = base centre (on the ground).
   ITEMS[name] = {grip: [x, y] (hand point, relative to base), point: true if it aligns with the forearm, draw(ctx, o, k)} */
'use strict';
(function () {
const T = window.TOON, {clamp, lerp, E, hash, rng, vnoise, mix, shade, rgba, rr, ell, poly} = T.h;
const OUTW = {none: 0, thin: 9, thick: 17};
function inkOf(style) { return c => { const w = OUTW[style.outline] == null ? OUTW.thin : OUTW[style.outline]; return w ? {w, c: style.outline === 'thick' ? '#15171C' : shade(c, -0.55)} : null; }; }
function paint(ctx, color, o) { ctx.fillStyle = color; ctx.fill(); if (o) { ctx.lineWidth = o.w; ctx.strokeStyle = o.c; ctx.lineJoin = 'round'; ctx.stroke(); } }
function box(ctx, x, y, w, h, r, c, o) { rr(ctx, x, y, w, h, r); paint(ctx, c, o(c)); }
function flame(ctx, x, y, s, t, seed) { const f = 0.85 + vnoise(seed, t * 9) * 0.3, sw = (vnoise(seed + 3, t * 7) - 0.5) * 0.3;
  ctx.save(); ctx.translate(x, y); ctx.rotate(sw * 0.4); ctx.scale(s, s * f);
  ctx.beginPath(); ctx.moveTo(0, -60); ctx.bezierCurveTo(26, -30, 24, 0, 0, 2); ctx.bezierCurveTo(-24, 0, -26, -30, 0, -60); ctx.fillStyle = '#FFB13B'; ctx.fill();
  ctx.beginPath(); ctx.moveTo(0, -34); ctx.bezierCurveTo(12, -18, 12, 0, 0, 0); ctx.bezierCurveTo(-12, 0, -12, -18, 0, -34); ctx.fillStyle = '#FFF3C4'; ctx.fill(); ctx.restore(); }
// light registration: local coords -> screen coords (works under any camera/actor transform)
T.LIGHTS = [];
T.addLight = function (ctx, x, y, L) {
  const m = ctx.getTransform(), p = m.transformPoint(new DOMPoint(x, y)), sc = Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
  const o = Object.assign({kind: 'point', r: 300, color: '#FFB84D', a: 0.9}, L, {x: p.x, y: p.y, r: (L.r || 300) * sc});
  if (o.kind === 'cone') { const q = m.transformPoint(new DOMPoint(x + Math.cos(L.ang || 0) * 100, y + Math.sin(L.ang || 0) * 100)); o.ang = Math.atan2(q.y - p.y, q.x - p.x); }
  T.LIGHTS.push(o);
};
const I = T.ITEMS = {
  can: {grip: [0, -60], draw(ctx, o, k) { const c = k.color || '#C9473A'; box(ctx, -45, -120, 90, 120, 12, '#B9C0C6', o);
    rr(ctx, -45, -95, 90, 66, 4); paint(ctx, c); ell(ctx, 0, -120, 45, 12); paint(ctx, '#DDE2E6', o('#B9C0C6')); ctx.fillStyle = rgba('#FFFFFF', 0.25); ctx.fillRect(-30, -95, 14, 66); }},
  bottle: {grip: [0, -90], draw(ctx, o, k) { const lvl = k.level == null ? 0.8 : k.level;
    ctx.beginPath(); ctx.moveTo(-40, -150); ctx.quadraticCurveTo(-42, -170, -18, -185); ctx.lineTo(-18, -212); ctx.lineTo(18, -212); ctx.lineTo(18, -185); ctx.quadraticCurveTo(42, -170, 40, -150);
    ctx.lineTo(40, -8); ctx.quadraticCurveTo(40, 0, 30, 0); ctx.lineTo(-30, 0); ctx.quadraticCurveTo(-40, 0, -40, -8); ctx.closePath(); paint(ctx, rgba('#CFE8F5', 0.85), o('#8DB8D0'));
    ctx.save(); ctx.clip(); ctx.fillStyle = '#5DB4E3'; ctx.fillRect(-45, -150 * lvl, 90, 160); ctx.restore();
    rr(ctx, -21, -236, 42, 28, 6); paint(ctx, '#2F6FB5', o('#2F6FB5')); rr(ctx, -40, -110, 80, 40, 2); paint(ctx, rgba('#FFFFFF', 0.85)); ctx.fillStyle = rgba('#FFFFFF', 0.4); ctx.fillRect(-28, -140, 10, 120); }},
  jerrycan: {grip: [10, -250], draw(ctx, o, k) { const c = k.color || '#3E7B4F'; box(ctx, -95, -230, 190, 230, 22, c, o);
    ctx.strokeStyle = shade(c, -0.3); ctx.lineWidth = 10; ctx.beginPath(); ctx.moveTo(-70, -200); ctx.lineTo(70, -30); ctx.moveTo(70, -200); ctx.lineTo(-70, -30); ctx.stroke();
    rr(ctx, -40, -270, 110, 50, 16); ctx.lineWidth = 18; ctx.strokeStyle = shade(c, -0.15); ctx.stroke(); rr(ctx, -85, -262, 36, 40, 6); paint(ctx, '#C9A23A', o('#C9A23A')); }},
  flashlight: {grip: [0, -60], point: true, draw(ctx, o, k, env) { box(ctx, -24, -130, 48, 130, 10, '#2C3138', o); ctx.beginPath(); ctx.moveTo(-26, -130); ctx.lineTo(-40, -185); ctx.lineTo(40, -185); ctx.lineTo(26, -130);
    ctx.closePath(); paint(ctx, '#3A414A', o('#3A414A')); ell(ctx, 0, -186, 40, 9); paint(ctx, k.on === false ? '#7A8088' : '#FFF6D8'); box(ctx, -12, -100, 24, 34, 6, '#E2A33B', o);
    if (k.on !== false) T.addLight(ctx, 0, -190, {kind: 'cone', r: k.reach || 1500, ang: -Math.PI / 2, spread: k.spread || 0.30, color: '#FFF1CF', a: 0.95}); }},
  candle: {grip: [0, -50], draw(ctx, o, k, env) { box(ctx, -22, -110, 44, 110, 8, '#F2EBDD', o); ctx.strokeStyle = '#2A2A2A'; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(0, -110); ctx.lineTo(0, -124); ctx.stroke();
    if (k.on !== false) { flame(ctx, 0, -118, 0.9, env.t, 11); T.addLight(ctx, 0, -150, {kind: 'point', r: k.reach || 560, color: '#FFB24A', a: 0.95, flicker: 1}); } }},
  lantern: {grip: [0, -300], draw(ctx, o, k, env) { box(ctx, -60, -40, 120, 40, 10, '#3A3F46', o); ctx.beginPath(); ctx.moveTo(-50, -40); ctx.lineTo(-44, -190); ctx.lineTo(44, -190); ctx.lineTo(50, -40); ctx.closePath();
    paint(ctx, rgba('#FFE9B0', k.on === false ? 0.3 : 0.75), o('#3A3F46')); box(ctx, -66, -220, 132, 34, 12, '#3A3F46', o); ctx.strokeStyle = '#3A3F46'; ctx.lineWidth = 12; ctx.beginPath(); ctx.arc(0, -232, 52, Math.PI, 0); ctx.stroke();
    if (k.on !== false) { flame(ctx, 0, -70, 1.0, env.t, 12); T.addLight(ctx, 0, -110, {kind: 'point', r: k.reach || 820, color: '#FFC266', a: 0.95, flicker: 0.5}); } }},
  phone: {grip: [0, -40], draw(ctx, o, k, env) { box(ctx, -34, -120, 68, 120, 14, '#1E2228', o); const on = k.on !== false; rr(ctx, -27, -110, 54, 100, 8); paint(ctx, on ? (k.alert ? '#E53935' : '#8FD3FF') : '#2B3038');
    if (on && k.alert) { ctx.fillStyle = '#FFF'; ctx.fillRect(-4, -92, 8, 40); ctx.fillRect(-4, -44, 8, 8); }
    if (on) T.addLight(ctx, 0, -60, {kind: 'point', r: 300, color: k.alert ? '#FF5A4F' : '#9AD8FF', a: 0.55}); }},
  radio: {grip: [0, -150], draw(ctx, o, k) { box(ctx, -100, -130, 200, 130, 16, k.color || '#7A5A3C', o); rr(ctx, -84, -112, 90, 94, 10); paint(ctx, '#3A2E26');
    ctx.fillStyle = rgba('#000', 0.35); for (let i = 0; i < 4; i++) ctx.fillRect(-76, -100 + i * 22, 74, 8); ell(ctx, 50, -86, 22, 22); paint(ctx, '#E2C08A', o('#E2C08A')); box(ctx, 22, -48, 60, 18, 6, '#E2C08A', o);
    ctx.strokeStyle = '#3A3F46'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(70, -130); ctx.lineTo(120, -250); ctx.stroke(); }},
  backpack: {grip: [0, -270], draw(ctx, o, k) { const c = k.color || '#C2553A'; box(ctx, -100, -260, 200, 260, 50, c, o); box(ctx, -72, -120, 144, 100, 24, shade(c, -0.15), o); box(ctx, -60, -290, 120, 50, 20, shade(c, -0.25), o); }},
  box: {grip: [0, -130], draw(ctx, o, k) { const c = k.color || '#C89A62'; box(ctx, -130, -200, 260, 200, 8, c, o); ctx.fillStyle = shade(c, 0.2); ctx.fillRect(-26, -200, 52, 200);
    ctx.fillStyle = rgba(shade(c, -0.5), 0.2); ctx.fillRect(-130, -200, 260, 26); }},
  firstaid: {grip: [0, -150], draw(ctx, o, k) { box(ctx, -95, -140, 190, 140, 18, '#F4F4F2', o); box(ctx, -35, -168, 70, 30, 10, '#9AA3AA', o);
    ctx.fillStyle = '#2E9E5B'; ctx.fillRect(-14, -112, 28, 84); ctx.fillRect(-42, -84, 84, 28); }},
  planks: {grip: [0, -60], draw(ctx, o, k) { for (let i = 0; i < 3; i++) { ctx.save(); ctx.translate(0, -30 - i * 34); ctx.rotate((i - 1) * 0.04); box(ctx, -250, -15, 500, 30, 4, i % 2 ? '#B98A55' : '#A87B48', o); ctx.restore(); } }},
  hammer: {grip: [0, -40], point: true, draw(ctx, o, k) { box(ctx, -12, -190, 24, 190, 8, '#A8743F', o); box(ctx, -55, -230, 110, 46, 10, '#59616B', o); }},
  shovel: {grip: [0, -420], point: true, draw(ctx, o, k) { box(ctx, -12, -620, 24, 520, 8, '#A8743F', o); box(ctx, -40, -660, 80, 40, 12, '#3A3F46', o);
    ctx.beginPath(); ctx.moveTo(-60, -110); ctx.lineTo(60, -110); ctx.lineTo(54, -20); ctx.quadraticCurveTo(0, 30, -54, -20); ctx.closePath(); paint(ctx, '#7D8790', o('#7D8790')); }},
  bucket: {grip: [0, -230], draw(ctx, o, k) { ctx.beginPath(); ctx.moveTo(-90, -170); ctx.lineTo(90, -170); ctx.lineTo(70, 0); ctx.lineTo(-70, 0); ctx.closePath(); paint(ctx, k.color || '#8C98A3', o(k.color || '#8C98A3'));
    ell(ctx, 0, -170, 90, 20); paint(ctx, k.water ? '#5DB4E3' : '#5B656E', o('#8C98A3')); ctx.strokeStyle = '#4A525A'; ctx.lineWidth = 8; ctx.beginPath(); ctx.arc(0, -170, 90, Math.PI * 1.05, Math.PI * 1.95); ctx.stroke(); }},
  battery: {grip: [0, -40], draw(ctx, o, k) { box(ctx, -24, -90, 48, 90, 10, '#2C3138', o); rr(ctx, -24, -90, 48, 30, 8); paint(ctx, '#E2A33B'); box(ctx, -9, -102, 18, 14, 4, '#B9C0C6', o); }},
  key: {grip: [0, -20], point: true, draw(ctx, o, k) { ell(ctx, 0, -100, 34, 34); paint(ctx, '#E2B544', o('#E2B544')); ell(ctx, 0, -100, 12, 12); ctx.fillStyle = rgba('#000', 0.45); ctx.fill();
    box(ctx, -8, -70, 16, 70, 4, '#E2B544', o); ctx.fillStyle = '#E2B544'; ctx.fillRect(8, -30, 18, 10); ctx.fillRect(8, -12, 12, 10); }},
  map: {grip: [0, -90], draw(ctx, o, k) { const c = '#EFE3C6'; ctx.beginPath(); ctx.moveTo(-130, -170); ctx.lineTo(-45, -150); ctx.lineTo(45, -170); ctx.lineTo(130, -150); ctx.lineTo(130, 0); ctx.lineTo(45, -20); ctx.lineTo(-45, 0); ctx.lineTo(-130, -20); ctx.closePath(); paint(ctx, c, o(c));
    ctx.strokeStyle = '#C9473A'; ctx.lineWidth = 7; ctx.setLineDash([14, 10]); ctx.beginPath(); ctx.moveTo(-100, -40); ctx.quadraticCurveTo(-20, -150, 90, -100); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = '#C9473A'; ell(ctx, 90, -100, 14, 14); ctx.fill(); }},
  book: {grip: [0, -80], draw(ctx, o, k) { box(ctx, -110, -150, 220, 150, 8, k.color || '#3B6EA8', o); ctx.fillStyle = '#F4EFE3'; ctx.fillRect(-100, -142, 200, 10); }},
  cup: {grip: [0, -50], draw(ctx, o, k, env) { box(ctx, -45, -100, 90, 100, 14, k.color || '#E8E2D4', o); ctx.strokeStyle = shade(k.color || '#E8E2D4', -0.2); ctx.lineWidth = 14; ctx.beginPath(); ctx.arc(52, -55, 24, -1.3, 1.3); ctx.stroke();
    if (k.steam !== false) { ctx.strokeStyle = rgba('#FFFFFF', 0.45); ctx.lineWidth = 8; for (let i = 0; i < 2; i++) { ctx.beginPath(); const ox = -14 + i * 26, w = Math.sin(env.t * 3 + i) * 8; ctx.moveTo(ox, -110); ctx.quadraticCurveTo(ox + w + 14, -140, ox - w, -175); ctx.stroke(); } } }},
  watering_can: {grip: [0, -230], draw(ctx, o, k) { const c = k.color || '#3E8E7E'; box(ctx, -90, -170, 160, 170, 24, c, o); ctx.strokeStyle = c; ctx.lineWidth = 22; ctx.beginPath(); ctx.moveTo(60, -40); ctx.lineTo(170, -190); ctx.stroke();
    ctx.lineWidth = 16; ctx.beginPath(); ctx.arc(-10, -170, 70, Math.PI, 0); ctx.stroke(); }},
  pot: {grip: [0, -100], draw(ctx, o, k, env) { const sw = Math.sin(env.t * 1.5) * 0.04; ctx.save(); ctx.translate(0, -130); ctx.rotate(sw);
    [[-50, -120, -0.6], [40, -140, 0.5], [0, -190, 0]].forEach(([x, y, a]) => { ctx.save(); ctx.translate(0, 0); ctx.rotate(a); ell(ctx, 0, y * 0.6, 34, 70); paint(ctx, '#4F9A45', o('#4F9A45')); ctx.restore(); });
    if (k.berries) { ['#D93A3A', '#E54848'].forEach((c, i) => { ell(ctx, -30 + i * 60, -10, 22, 26); paint(ctx, c, o(c)); }); }
    ctx.restore(); ctx.beginPath(); ctx.moveTo(-80, -140); ctx.lineTo(80, -140); ctx.lineTo(60, 0); ctx.lineTo(-60, 0); ctx.closePath(); paint(ctx, k.color || '#C26A3E', o(k.color || '#C26A3E')); box(ctx, -90, -160, 180, 32, 8, shade(k.color || '#C26A3E', 0.1), o); }},
  seeds: {grip: [0, -70], draw(ctx, o, k) { box(ctx, -60, -150, 120, 150, 8, '#F2D16B', o); ell(ctx, 0, -80, 30, 30); paint(ctx, '#D9603A'); }},
  umbrella: {grip: [0, -60], draw(ctx, o, k) { ctx.strokeStyle = '#3A3F46'; ctx.lineWidth = 12; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -520); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-300, -470); ctx.quadraticCurveTo(0, -720, 300, -470); for (let i = 3; i >= -3; i--) ctx.quadraticCurveTo(i * 100 + 50, -500, i * 100 - 0, -470); ctx.closePath(); paint(ctx, k.color || '#C8372D', o(k.color || '#C8372D')); }},
  rope: {grip: [0, -60], draw(ctx, o, k) { ctx.strokeStyle = '#C9A46A'; ctx.lineWidth = 16; for (let i = 0; i < 3; i++) { ell(ctx, 0, -60, 70 - i * 18, 50 - i * 12); ctx.stroke(); } }},
  clock: {grip: [0, -90], draw(ctx, o, k, env) { ell(ctx, 0, -90, 90, 90); paint(ctx, '#F4F1E8', o('#9AA3AA')); const hh = k.time ? k.time.split(':').map(Number) : [6, 15];
    const ang = (v, n) => v / n * Math.PI * 2 - Math.PI / 2; ctx.strokeStyle = '#1E2228'; ctx.lineCap = 'round';
    ctx.lineWidth = 12; ctx.beginPath(); ctx.moveTo(0, -90); ctx.lineTo(Math.cos(ang(hh[0] % 12 + hh[1] / 60, 12)) * 45, -90 + Math.sin(ang(hh[0] % 12 + hh[1] / 60, 12)) * 45); ctx.stroke();
    ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(0, -90); ctx.lineTo(Math.cos(ang(hh[1] + (k.run ? env.lt * 60 : 0), 60)) * 70, -90 + Math.sin(ang(hh[1] + (k.run ? env.lt * 60 : 0), 60)) * 70); ctx.stroke(); }},
  // ---- world props (bigger)
  table: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#8A6A4A'; box(ctx, -300, -330, 600, 40, 8, c, o); box(ctx, -270, -300, 36, 300, 6, shade(c, -0.2), o); box(ctx, 234, -300, 36, 300, 6, shade(c, -0.2), o); }},
  chair: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#8A6A4A'; box(ctx, -110, -190, 220, 34, 6, c, o); box(ctx, -110, -460, 34, 300, 6, shade(c, -0.1), o); box(ctx, 76, -160, 30, 160, 6, shade(c, -0.2), o); box(ctx, -104, -160, 30, 160, 6, shade(c, -0.2), o); }},
  bed: {grip: [0, -300], draw(ctx, o, k) { box(ctx, -450, -200, 900, 120, 16, '#7A5A3C', o); box(ctx, -440, -260, 880, 80, 30, '#E9E4DA', o); box(ctx, -440, -270, 200, 70, 30, '#FFFFFF', o);
    box(ctx, -200, -265, 640, 90, 30, k.color || '#4F7FA6', o); box(ctx, -470, -380, 50, 380, 10, '#6A4B30', o); box(ctx, 420, -260, 50, 260, 10, '#6A4B30', o); }},
  sofa: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#B0563F'; box(ctx, -420, -380, 840, 200, 60, shade(c, -0.1), o); box(ctx, -400, -230, 800, 150, 40, c, o);
    box(ctx, -470, -300, 110, 260, 50, c, o); box(ctx, 360, -300, 110, 260, 50, c, o); }},
  shelf: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#8A6A4A', R = rng(hash(k.seed || 'shelf')), full = k.full == null ? 0.8 : k.full; box(ctx, -260, -820, 520, 820, 8, shade(c, -0.25), o);
    for (let i = 0; i < 4; i++) { const y = -40 - i * 200; box(ctx, -250, y - 18, 500, 20, 4, c, o);
      for (let j = 0; j < 6; j++) if (R() < full) { const kind = R(); ctx.save(); ctx.translate(-200 + j * 80, y - 18); ctx.scale(0.62, 0.62);
        (kind < 0.45 ? I.can : kind < 0.75 ? I.bottle : I.box).draw(ctx, () => null, {color: ['#C9473A', '#3E7B4F', '#E2A33B', '#3B6EA8'][j % 4]}, {t: 0, lt: 0}); ctx.restore(); } } }},
  fridge: {grip: [0, -300], draw(ctx, o, k) { box(ctx, -170, -780, 340, 780, 30, '#E6EBEE', o); ctx.strokeStyle = '#B9C2C8'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(-170, -500); ctx.lineTo(170, -500); ctx.stroke();
    box(ctx, 120, -720, 20, 160, 8, '#9AA3AA', o); box(ctx, 120, -460, 20, 160, 8, '#9AA3AA', o); if (k.open) { ctx.fillStyle = rgba('#000', 0.6); ctx.fillRect(-160, -490, 270, 480); } }},
  door: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#7A5A3C'; box(ctx, -210, -1000, 420, 1000, 6, shade(c, -0.35), o); box(ctx, -190, -980, 380, 980, 4, c, o);
    box(ctx, -150, -920, 300, 360, 8, shade(c, -0.08), o); box(ctx, -150, -500, 300, 400, 8, shade(c, -0.08), o); ell(ctx, 140, -480, 22, 22); paint(ctx, '#E2B544', o('#E2B544'));
    if (k.locked) { box(ctx, 100, -560, 70, 40, 6, '#59616B', o); } }},
  car: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#C9473A'; ctx.beginPath(); ctx.moveTo(-620, -120); ctx.lineTo(-600, -300); ctx.lineTo(-330, -320); ctx.lineTo(-200, -500); ctx.lineTo(260, -500);
    ctx.lineTo(420, -320); ctx.lineTo(600, -290); ctx.lineTo(630, -120); ctx.closePath(); paint(ctx, c, o(c));
    ctx.beginPath(); ctx.moveTo(-170, -470); ctx.lineTo(10, -470); ctx.lineTo(10, -330); ctx.lineTo(-290, -330); ctx.closePath(); paint(ctx, k.dark ? '#1A2230' : '#9FC3D6', o('#3A3F46'));
    ctx.beginPath(); ctx.moveTo(40, -470); ctx.lineTo(240, -470); ctx.lineTo(360, -330); ctx.lineTo(40, -330); ctx.closePath(); paint(ctx, k.dark ? '#1A2230' : '#9FC3D6', o('#3A3F46'));
    [-370, 370].forEach(x => { ell(ctx, x, -110, 110, 110); paint(ctx, '#1E2228', o('#1E2228')); ell(ctx, x, -110, 50, 50); paint(ctx, '#9AA3AA'); });
    box(ctx, 560, -270, 60, 40, 8, '#FFE9A8', o); if (k.lights) T.addLight(ctx, 620, -250, {kind: 'cone', r: 1600, ang: 0.08, spread: 0.32, color: '#FFF1CF', a: 0.9}); }},
  tent: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#E2702A'; ctx.beginPath(); ctx.moveTo(-480, 0); ctx.lineTo(0, -520); ctx.lineTo(480, 0); ctx.closePath(); paint(ctx, c, o(c));
    ctx.beginPath(); ctx.moveTo(-120, 0); ctx.lineTo(0, -380); ctx.lineTo(120, 0); ctx.closePath(); paint(ctx, shade(c, -0.45)); }},
  campfire: {grip: [0, -300], draw(ctx, o, k, env) { [[-0.4], [0.4], [0]].forEach(([a], i) => { ctx.save(); ctx.rotate(a); box(ctx, -160, -40, 320, 50, 20, '#6A4B30', o); ctx.restore(); });
    flame(ctx, -40, -40, 3.2, env.t, 21); flame(ctx, 50, -40, 2.6, env.t + 0.4, 22); flame(ctx, 0, -50, 4.0, env.t + 0.9, 23);
    T.addLight(ctx, 0, -180, {kind: 'point', r: k.reach || 1300, color: '#FF9A3D', a: 1, flicker: 1}); }},
  barrel: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#3F6A8A'; box(ctx, -130, -360, 260, 360, 30, c, o); ctx.fillStyle = shade(c, -0.25); ctx.fillRect(-130, -290, 260, 20); ctx.fillRect(-130, -90, 260, 20); }},
  crate: {grip: [0, -300], draw(ctx, o, k) { box(ctx, -170, -320, 340, 320, 6, '#A87B48', o); ctx.strokeStyle = '#7A5530'; ctx.lineWidth = 16; ctx.beginPath(); ctx.moveTo(-150, -300); ctx.lineTo(150, -20); ctx.stroke(); rr(ctx, -150, -300, 300, 280, 4); ctx.stroke(); }},
  sandbags: {grip: [0, -300], draw(ctx, o, k) { for (let r2 = 0; r2 < 3; r2++) for (let i = 0; i < 4 - r2; i++) { ell(ctx, -270 + r2 * 90 + i * 180, -60 - r2 * 100, 100, 60); paint(ctx, '#B8A77E', o('#B8A77E')); } }},
  trashcan: {grip: [0, -300], draw(ctx, o, k) { box(ctx, -110, -300, 220, 300, 16, '#5E6B73', o); box(ctx, -125, -330, 250, 40, 12, '#4B565D', o); }},
  lamp_post: {grip: [0, -300], draw(ctx, o, k) { box(ctx, -18, -1500, 36, 1500, 10, '#2F353C', o); box(ctx, -18, -1500, 220, 26, 10, '#2F353C', o); box(ctx, 150, -1480, 90, 40, 12, k.on === false ? '#59616B' : '#FFE9A8', o);
    if (k.on !== false) T.addLight(ctx, 195, -1440, {kind: 'cone', r: 1700, ang: Math.PI / 2, spread: 0.55, color: '#FFD28A', a: 0.8}); }},
  tree: {grip: [0, -300], draw(ctx, o, k, env) { const c = k.color || '#4F7A45', sw = Math.sin(env.t * 0.8 + (k.seed || 0)) * 0.015; box(ctx, -40, -520, 80, 520, 20, '#6A4B30', o);
    ctx.save(); ctx.translate(0, -520); ctx.rotate(sw); [[0, -330, 330], [-200, -150, 240], [200, -160, 250], [0, -60, 260]].forEach(([x, y, r]) => { ell(ctx, x, y, r, r * 0.85); paint(ctx, c, o(c)); });
    ctx.fillStyle = rgba('#FFFFFF', 0.08); ell(ctx, -80, -420, 160, 90, -0.3); ctx.fill(); ctx.restore(); }},
  pine: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#2F5A3F'; box(ctx, -30, -200, 60, 200, 10, '#5A3E28', o);
    for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.moveTo(-300 + i * 60, -150 - i * 260); ctx.lineTo(0, -560 - i * 260); ctx.lineTo(300 - i * 60, -150 - i * 260); ctx.closePath(); paint(ctx, shade(c, i * 0.06), o(c)); }
    if (k.snow) { ctx.fillStyle = '#F2F6F8'; for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.moveTo(-90 + i * 18, -420 - i * 260); ctx.lineTo(0, -560 - i * 260); ctx.lineTo(90 - i * 18, -420 - i * 260); ctx.closePath(); ctx.fill(); } } }},
  bush: {grip: [0, -300], draw(ctx, o, k) { const c = k.color || '#5C8A4A'; [[-120, -110, 140], [110, -110, 140], [0, -170, 170]].forEach(([x, y, r]) => { ell(ctx, x, y, r, r * 0.8); paint(ctx, c, o(c)); }); }},
  rock: {grip: [0, -300], draw(ctx, o, k) { ctx.beginPath(); ctx.moveTo(-200, 0); ctx.lineTo(-170, -130); ctx.lineTo(-40, -200); ctx.lineTo(120, -170); ctx.lineTo(210, 0); ctx.closePath(); paint(ctx, k.color || '#8A8F94', o(k.color || '#8A8F94')); }},
  tv: {grip: [0, -300], draw(ctx, o, k, env) { box(ctx, -320, -420, 640, 380, 20, '#1E2228', o); rr(ctx, -295, -395, 590, 330, 8); paint(ctx, k.on ? '#6FA8DC' : '#2B3038'); box(ctx, -120, -40, 240, 40, 8, '#2B3038', o);
    if (k.on) T.addLight(ctx, 0, -230, {kind: 'point', r: 700, color: '#9AD8FF', a: 0.6}); }},
  generator: {grip: [0, -300], draw(ctx, o, k) { box(ctx, -230, -300, 460, 280, 20, '#E2A33B', o); box(ctx, -200, -260, 220, 180, 12, '#3A3F46', o); box(ctx, -250, -30, 500, 30, 8, '#2F353C', o); }},
  well: {grip: [0, -300], draw(ctx, o, k) { box(ctx, -230, -300, 460, 300, 30, '#8A8F94', o); box(ctx, -260, -330, 520, 50, 16, '#6D7277', o); box(ctx, -220, -720, 30, 400, 8, '#6A4B30', o); box(ctx, 190, -720, 30, 400, 8, '#6A4B30', o);
    ctx.beginPath(); ctx.moveTo(-300, -700); ctx.lineTo(0, -900); ctx.lineTo(300, -700); ctx.closePath(); paint(ctx, '#A8322A', o('#A8322A')); }},
};
T.ITEM_NAMES = Object.keys(I);

// held item: called by chars.js inside the hand transform (origin = hand centre, y axis = forearm direction rotated)
T.drawItem = function (ctx, name, st, env, which) {
  const it = I[name]; if (!it) return; const o = inkOf(Object.assign({}, env.style, st.look.style || {}));
  ctx.save();
  // undo the forearm rotation for upright items: chars.js rotated by (fa + pi/2); rotate back to world-up
  const m = ctx.getTransform(); const flip = Math.sign(m.a * m.d - m.b * m.c) || 1;
  if (!it.point) { const ang = Math.atan2(m.b, m.a); ctx.rotate(flip > 0 ? -ang : ang - Math.PI); }
  const g = it.grip || [0, -60]; ctx.translate(-g[0], -g[1]);
  it.draw(ctx, o, st.a.item || {}, env); ctx.restore();
};

// world prop: {id, at: [x, y], scale, face, z, pop: t, glow, on, ...}
T.drawProp = function (env, p, i) {
  const {ctx, W, H, lt} = env, story = T.story, portrait = story.H >= story.W;
  if (p.id === 'crowd') return T.drawCrowd(env, p);
  const it = I[p.id]; if (!it) return;
  const unit = (portrait ? 0.30 : 0.50) * H / 1000 * (p.scale || 1);
  let k = 1; if (p.pop != null) k = lt < p.pop ? 0 : E.back((lt - p.pop) / 0.35); if (k <= 0) return;
  ctx.save(); ctx.translate((p.at && p.at[0] != null ? p.at[0] : 0.5) * W, p.at && p.at[1] != null ? p.at[1] * H : (env.ground || 0.8 * H));
  if (p.float) ctx.translate(0, Math.sin(env.t * 2 + i) * 10);
  ctx.scale(unit * k * (p.face === 'left' ? -1 : 1), unit * k); if (p.rot) ctx.rotate(p.rot);
  if (p.shadow !== false) T.h.shadowBlob(ctx, 0, 0, 260 * (p.shadow || 1), 0.22);
  if (p.glow) { const r = 260 + 30 * Math.sin(env.t * 5); ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = T.h.rgrad(ctx, 0, -150, 0, r * 1.6, [[0, rgba(p.glow === true ? '#FFD966' : p.glow, 0.5)], [1, rgba('#FFD966', 0)]]);
    ctx.fillRect(-r * 1.6, -150 - r * 1.6, r * 3.2, r * 3.2); ctx.restore(); }
  it.draw(ctx, inkOf(env.style), p, env);
  ctx.restore();
};
})();
