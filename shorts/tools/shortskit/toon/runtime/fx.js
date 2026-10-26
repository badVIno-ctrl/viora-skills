/* TOON fx: light pass (darkness with light holes + additive glow) and particle effects.
   scene.fx = ["rain", {"type": "snow", "amount": 0.6}, {"type": "smoke", "at": [0.7, 0.4]}, ...] */
'use strict';
(function () {
const T = window.TOON, {clamp, lerp, E, hash, rng, vnoise, mix, shade, rgba, rgrad, ell} = T.h;
const BUFS = {};
function buf(name, W, H) { let c = BUFS[name]; if (!c || c.width !== W || c.height !== H) { c = document.createElement('canvas'); c.width = W; c.height = H; BUFS[name] = c; } return c; }

// ------------------------------------------------------------------ light pass
T.lights = function (env) {
  const {ctx, W, H, P, sc, t} = env;
  const sdef = T.SETS[(sc.set && sc.set.id) || 'plain'] || {};
  const amb = clamp(sc.dark != null ? sc.dark : (sc.set && sc.set.dark != null ? sc.set.dark : P.amb * (sdef.ambk || 1)));
  const Ls = T.LIGHTS || [];
  if (amb < 0.01) { glows(ctx, Ls, t, 0.6); return; }
  const D = buf('dark', W, H), d = D.getContext('2d', {willReadFrequently: true});
  d.globalCompositeOperation = 'source-over'; d.clearRect(0, 0, W, H);
  d.fillStyle = rgba(P.darkc || '#04060E', amb); d.fillRect(0, 0, W, H);
  d.globalCompositeOperation = 'destination-out';
  for (const L of Ls) {
    const f = flick(L, t) * (L.a == null ? 1 : L.a);
    if (L.kind === 'cone') {
      for (const [sp, al] of [[L.spread * 1.35, 0.35], [L.spread, 0.85]]) {
        d.save(); d.beginPath(); d.moveTo(L.x, L.y); d.arc(L.x, L.y, L.r, L.ang - sp, L.ang + sp); d.closePath(); d.clip();
        d.fillStyle = rgrad(d, L.x, L.y, 0, L.r, [[0, `rgba(0,0,0,${al * f})`], [0.55, `rgba(0,0,0,${al * f * 0.7})`], [1, 'rgba(0,0,0,0)']]);
        d.fillRect(L.x - L.r, L.y - L.r, 2 * L.r, 2 * L.r); d.restore();
      }
      d.fillStyle = rgrad(d, L.x, L.y, 0, L.r * 0.16, [[0, `rgba(0,0,0,${f})`], [1, 'rgba(0,0,0,0)']]); d.fillRect(L.x - L.r, L.y - L.r, 2 * L.r, 2 * L.r);
    } else {
      d.fillStyle = rgrad(d, L.x, L.y, 0, L.r, [[0, `rgba(0,0,0,${f})`], [0.45, `rgba(0,0,0,${f * 0.6})`], [1, 'rgba(0,0,0,0)']]);
      d.fillRect(L.x - L.r, L.y - L.r, 2 * L.r, 2 * L.r);
    }
  }
  ctx.drawImage(D, 0, 0);
  glows(ctx, Ls, t, 1);
};
function flick(L, t) { if (!L.flicker) return 1; const s = hash(String(Math.round(L.x)) + 'f'); return 1 - L.flicker * (0.10 + 0.12 * vnoise(s, t * 11) + 0.06 * vnoise(s + 5, t * 23)); }
function glows(ctx, Ls, t, k) {
  if (!Ls.length) return;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const L of Ls) {
    const f = flick(L, t) * (L.a == null ? 1 : L.a) * k;
    if (L.kind === 'cone') {
      ctx.save(); ctx.beginPath(); ctx.moveTo(L.x, L.y); ctx.arc(L.x, L.y, L.r, L.ang - L.spread, L.ang + L.spread); ctx.closePath(); ctx.clip();
      ctx.fillStyle = rgrad(ctx, L.x, L.y, 0, L.r, [[0, rgba(L.color, 0.30 * f)], [0.5, rgba(L.color, 0.10 * f)], [1, rgba(L.color, 0)]]);
      ctx.fillRect(L.x - L.r, L.y - L.r, 2 * L.r, 2 * L.r); ctx.restore();
      const r0 = L.r * 0.08; ctx.fillStyle = rgrad(ctx, L.x, L.y, 0, r0, [[0, rgba('#FFFFFF', 0.8 * f)], [1, rgba(L.color, 0)]]); ctx.fillRect(L.x - r0, L.y - r0, 2 * r0, 2 * r0);
    } else {
      const r = L.r * (L.glow || 0.55);
      ctx.fillStyle = rgrad(ctx, L.x, L.y, 0, r, [[0, rgba(L.color, 0.42 * f)], [0.35, rgba(L.color, 0.16 * f)], [1, rgba(L.color, 0)]]);
      ctx.fillRect(L.x - r, L.y - r, 2 * r, 2 * r);
    }
  }
  ctx.restore();
}

// ------------------------------------------------------------------ particles (deterministic: positions are functions of t)
const FX = T.FX = {};
function norm(f) { return typeof f === 'string' ? {type: f} : f; }
FX.rain = (env, f) => { const {ctx, W, H, t} = env, n = Math.round(260 * (f.amount || 1)), R = rng(41), wind = f.wind == null ? 0.18 : f.wind;
  ctx.save(); ctx.lineCap = 'round';
  for (let i = 0; i < n; i++) { const z = 0.4 + R() * 0.9, sp = H * (1.4 + z), x0 = R() * W * 1.3 - W * 0.15, y0 = R() * H, len = 40 * z + 20;
    const y = (y0 + t * sp) % (H + 200) - 100, x = x0 + (y - y0) * wind;
    ctx.strokeStyle = rgba('#CFE3F5', 0.18 + 0.25 * z); ctx.lineWidth = 1.5 + 2 * z; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + len * wind, y + len); ctx.stroke(); }
  ctx.restore(); };
FX.snow = (env, f) => { const {ctx, W, H, t} = env, n = Math.round(170 * (f.amount || 1)), R = rng(43);
  ctx.save(); for (let i = 0; i < n; i++) { const z = 0.3 + R() * 1.0, x0 = R() * W, y0 = R() * H, sp = 60 + 110 * z, r = 2 + 6 * z;
    const y = (y0 + t * sp) % (H + 40) - 20, x = x0 + Math.sin(t * (0.6 + z) + i) * 30 * z + t * 12;
    ctx.fillStyle = rgba('#FFFFFF', 0.45 + 0.45 * Math.min(1, z)); ell(ctx, ((x % W) + W) % W, y, r, r); ctx.fill(); }
  ctx.restore(); };
FX.dust = (env, f) => { const {ctx, W, H, t} = env, n = Math.round(60 * (f.amount || 1)), R = rng(47);
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < n; i++) { const x = (R() * W + Math.sin(t * 0.3 + i) * 40 + t * 8) % W, y = (R() * H - t * 6 + H) % H, r = 1.5 + R() * 3.5;
    ctx.fillStyle = rgba('#FFF2D0', 0.15 + 0.25 * vnoise(i, t * 0.8)); ell(ctx, x, y, r, r); ctx.fill(); } ctx.restore(); };
FX.embers = (env, f) => { const {ctx, W, H, t} = env, n = Math.round(50 * (f.amount || 1)), R = rng(53);
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < n; i++) { const life = 3 + R() * 3, ph = (t / life + R()) % 1, x = R() * W + Math.sin(ph * 6 + i) * 40, y = H * (1.02 - ph * 0.9), r = 2 + R() * 4;
    ctx.fillStyle = rgba(ph < 0.5 ? '#FFC34D' : '#FF6A2A', 0.8 * (1 - ph)); ell(ctx, x, y, r, r); ctx.fill(); } ctx.restore(); };
FX.fog = (env, f) => { const {ctx, W, H, t} = env, a = f.amount || 0.6, y0 = (f.y || 0.62) * H;
  ctx.save(); for (let i = 0; i < 7; i++) { const x = ((i * 0.37 * W + t * (12 + i * 5)) % (W * 1.6)) - W * 0.3, y = y0 + (i % 3) * H * 0.05;
    ctx.fillStyle = rgrad(ctx, x, y, 0, W * 0.45, [[0, rgba(f.color || '#C8D2DC', 0.22 * a)], [1, rgba(f.color || '#C8D2DC', 0)]]); ctx.fillRect(x - W * 0.5, y - W * 0.5, W, W); }
  ctx.restore(); };
FX.smoke = (env, f) => { const {ctx, W, H, t} = env, at = f.at || [0.7, 0.5], R = rng(59), n = 26, dark = f.dark, sz = f.size || 1;
  ctx.save(); for (let i = 0; i < n; i++) { const life = 6, ph = (t / life + i / n) % 1, x = at[0] * W + Math.sin(ph * 5 + i) * 14 * sz + ph * W * 0.12 * (f.wind == null ? 1 : f.wind) * sz, y = at[1] * H - ph * H * 0.22 * sz;
    const r = W * (0.018 + ph * 0.06) * sz; ctx.fillStyle = rgba(dark ? '#2A2C30' : '#C9CED4', (dark ? 0.5 : 0.42) * (1 - ph) * Math.min(1, ph * 8)); ell(ctx, x, y, r, r); ctx.fill(); }
  ctx.restore(); };
FX.sparks = (env, f) => { const {ctx, W, H, lt} = env, at = f.at || [0.5, 0.4], t0 = f.t || 0.2, R = rng(61); if (lt < t0) return;
  const k = lt - t0; if (k > 1.2) return; ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 26; i++) { const a = R() * Math.PI * 2, sp = 300 + R() * 700, x = at[0] * W + Math.cos(a) * sp * k, y = at[1] * H + Math.sin(a) * sp * k + 900 * k * k;
    ctx.strokeStyle = rgba('#FFE08A', clamp(1 - k / 1.2)); ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - Math.cos(a) * 24, y - Math.sin(a) * 24); ctx.stroke(); }
  ctx.restore(); };
FX.shards = (env, f) => { const {ctx, W, H, lt} = env, at = f.at || [0.5, 0.4], t0 = f.t || 0.2, R = rng(67); if (lt < t0) return;
  const k = lt - t0; if (k > 1.6) return; ctx.save();
  for (let i = 0; i < 22; i++) { const a = -Math.PI * (0.1 + R() * 0.8), sp = 250 + R() * 600, x = at[0] * W + Math.cos(a) * sp * k, y = at[1] * H + Math.sin(a) * sp * k + 1400 * k * k, s = 10 + R() * 26;
    ctx.save(); ctx.translate(x, y); ctx.rotate(k * (4 + i)); ctx.fillStyle = rgba('#DDF1FF', 0.75 * clamp(1.6 - k)); ctx.beginPath(); ctx.moveTo(0, -s); ctx.lineTo(s * 0.6, s * 0.4); ctx.lineTo(-s * 0.5, s * 0.6); ctx.closePath(); ctx.fill(); ctx.restore(); }
  ctx.restore(); };
FX.leaves = (env, f) => { const {ctx, W, H, t} = env, n = Math.round(24 * (f.amount || 1)), R = rng(71);
  ctx.save(); for (let i = 0; i < n; i++) { const x0 = R() * W, y0 = R() * H, y = (y0 + t * (70 + R() * 60)) % (H + 60) - 30, x = x0 + Math.sin(t * 1.3 + i) * 60;
    ctx.save(); ctx.translate(x, y); ctx.rotate(Math.sin(t * 2 + i) * 1.2); ctx.fillStyle = ['#D9822B', '#C9473A', '#E2B544'][i % 3]; ell(ctx, 0, 0, 16, 8); ctx.fill(); ctx.restore(); }
  ctx.restore(); };
FX.flood = (env, f) => { const {ctx, W, H, lt, sc} = env, dur = sc.t1 - sc.t0, from = f.from == null ? 1.0 : f.from, to = f.to == null ? 0.75 : f.to;
  const lvl = lerp(from, to, E.io(clamp(lt / (f.dur || dur)))) * H;
  ctx.save(); ctx.beginPath(); ctx.moveTo(0, H); for (let x = 0; x <= W; x += 20) ctx.lineTo(x, lvl + Math.sin(x / 70 + lt * 2.4) * 10 + Math.sin(x / 31 - lt * 3.1) * 5); ctx.lineTo(W, H); ctx.closePath();
  ctx.fillStyle = rgba(f.color || '#3F7FA6', 0.62); ctx.fill(); ctx.strokeStyle = rgba('#DFF2FF', 0.55); ctx.lineWidth = 5; ctx.stroke(); ctx.restore(); };
FX.confetti = (env, f) => { const {ctx, W, H, lt} = env, R = rng(73), n = 90; ctx.save();
  for (let i = 0; i < n; i++) { const x = R() * W + Math.sin(lt * 2 + i) * 30, y = -50 + ((R() * H * 0.6 + lt * (220 + R() * 200))), s = 10 + R() * 10;
    if (y > H + 20) continue; ctx.save(); ctx.translate(x, y); ctx.rotate(lt * 4 + i); ctx.fillStyle = ['#F5C518', '#E53935', '#3B8EEA', '#3DDC84', '#FF7AC8'][i % 5]; ctx.fillRect(-s / 2, -s / 4, s, s / 2); ctx.restore(); }
  ctx.restore(); };
FX.speedlines = (env, f) => { const {ctx, W, H, t} = env, R = rng(79), c = [W / 2, H * 0.45]; ctx.save(); ctx.strokeStyle = rgba('#FFFFFF', 0.5);
  for (let i = 0; i < 48; i++) { const a = R() * Math.PI * 2, r0 = Math.max(W, H) * (0.32 + 0.1 * vnoise(i, t * 6)), r1 = Math.max(W, H) * 0.9; ctx.lineWidth = 2 + R() * 6;
    ctx.beginPath(); ctx.moveTo(c[0] + Math.cos(a) * r0, c[1] + Math.sin(a) * r0); ctx.lineTo(c[0] + Math.cos(a) * r1, c[1] + Math.sin(a) * r1); ctx.stroke(); } ctx.restore(); };
FX.stars = (env, f) => { const {ctx, W, H, t} = env, R = rng(83); ctx.save(); for (let i = 0; i < 90; i++) { const x = R() * W, y = R() * H * 0.5, r = 1 + R() * 2.4;
  ctx.fillStyle = rgba('#FFFFFF', 0.3 + 0.6 * vnoise(i, t * 0.7)); ell(ctx, x, y, r, r); ctx.fill(); } ctx.restore(); };
// rainbow: grows as an arc from the left, sits in the sky layer (behind hills/actors) when the set has a sky
const RAINBOW = ['#FF4B4B', '#FF9A3C', '#FFE04D', '#5ED36A', '#5BC8F5', '#3B6FE0', '#9B5BE0'];
FX.rainbow = (env, f) => { const {ctx, W, H, lt} = env, t0 = f.t || 0, grow = f.grow == null ? 1.4 : f.grow;
  const k = grow > 0 ? E.io(clamp((lt - t0) / grow)) : (lt >= t0 ? 1 : 0); if (k <= 0) return;
  const at = f.at || [0.5, 0.7], cx = at[0] * W, cy = at[1] * H, r = (f.r || 0.62) * Math.min(W, H), bw = r * (f.band || 0.045), a = f.amount == null ? 0.85 : f.amount;
  const a0 = Math.PI, a1 = Math.PI * (1 + k); ctx.save(); ctx.lineCap = 'butt';
  ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = rgba('#FFFFFF', 0.10 * a); ctx.lineWidth = bw * 9; ctx.beginPath(); ctx.arc(cx, cy, r - 3 * bw, a0, a1); ctx.stroke();
  ctx.globalCompositeOperation = 'source-over';
  RAINBOW.forEach((c, i) => { ctx.strokeStyle = rgba(c, a); ctx.lineWidth = bw * 1.06; ctx.beginPath(); ctx.arc(cx, cy, r - i * bw, a0, a1); ctx.stroke(); });
  ctx.restore(); };
// sparkle: twinkling 4-point stars around a spot (magic, "aha", kids)
FX.sparkle = (env, f) => { const {ctx, W, H, lt} = env, at = f.at || [0.5, 0.45], t0 = f.t || 0, R = rng(89), n = Math.round(14 * (f.amount || 1)), rad = (f.r || 0.22) * W;
  if (lt < t0) return; ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < n; i++) { const ang = R() * Math.PI * 2, d = rad * (0.3 + R() * 0.7), ph = (lt - t0) * (1.2 + R()) + R() * 6, tw = Math.max(0, Math.sin(ph * Math.PI));
    const x = at[0] * W + Math.cos(ang) * d, y = at[1] * H + Math.sin(ang) * d * 0.8, s = (10 + R() * 16) * tw; if (s < 1) continue;
    ctx.fillStyle = rgba(f.color || '#FFF6C8', 0.9 * tw); ctx.beginPath(); ctx.moveTo(x, y - s); ctx.quadraticCurveTo(x, y, x + s, y); ctx.quadraticCurveTo(x, y, x, y + s);
    ctx.quadraticCurveTo(x, y, x - s, y); ctx.quadraticCurveTo(x, y, x, y - s); ctx.fill(); }
  ctx.restore(); };
// spray: water jet from a point in WORLD coords (follows the camera), e.g. watering can / hose; dir in degrees (0 = right, -90 = up)
FX.spray = (env, f) => { const {ctx, W, H, lt} = env, at = f.at || [0.5, 0.6], t0 = f.t || 0, n = Math.round(90 * (f.amount || 1)), R = rng(97); if (lt < t0) return;
  const ang = (f.dir == null ? -40 : f.dir) * Math.PI / 180, sp = (f.speed || 1) * H * 0.55, g = H * 0.9, ramp = clamp((lt - t0) / 0.3);
  env.L(f.depth || 1, () => { ctx.save();
    for (let i = 0; i < n; i++) { const life = 0.9 + R() * 0.3, ph = ((lt - t0) / life + i / n) % 1, a = ang + (R() - 0.5) * 0.22, v = sp * (0.8 + R() * 0.4), tt = ph * life;
      if (tt > lt - t0) continue; const x = at[0] * W + Math.cos(a) * v * tt, y = at[1] * H + Math.sin(a) * v * tt + 0.5 * g * tt * tt, r = (6 + R() * 8) * (1 - ph * 0.4) * (f.size || 1);
      ctx.fillStyle = rgba(i % 4 ? '#7CC8F2' : '#DDF3FF', 0.85 * ramp * (1 - ph * 0.6)); ell(ctx, x, y, r, r * 1.2); ctx.fill(); }
    ctx.restore(); }); };
FX.lightning = () => {};   // screen pass
FX.flicker = () => {};
FX.alarm = () => {};

const SKY = {rainbow: 1};
T.skyFx = function (env) { for (const f0 of env.sc.fx || []) { const f = norm(f0); if (SKY[f.type] && f.front !== true) { FX[f.type](env, f); env._skyfx = true; } } };
T.fxWorld = function (env, list) { for (const f0 of list || []) { const f = norm(f0); if (!FX[f.type] || (SKY[f.type] && env._skyfx && f.front !== true)) continue; FX[f.type](env, f); } };
T.fxScreen = function (ctx, sc, lt, t, W, H) {
  for (const f0 of sc.fx || []) { const f = norm(f0);
    if (f.type === 'lightning') { const per = f.every || 3.2, ph = (lt + (f.offset || 0.6)) % per; if (ph < 0.32) { const a = ph < 0.08 ? 0.75 : ph < 0.16 ? 0.15 : ph < 0.22 ? 0.5 : 0;
      ctx.save(); ctx.fillStyle = rgba('#E8F0FF', a); ctx.fillRect(0, 0, W, H); ctx.restore(); } }
    if (f.type === 'flicker') { const s = 0.5 * vnoise(17, lt * 14) + 0.5 * vnoise(23, lt * 31); if (s > (f.threshold || 0.62)) { ctx.save(); ctx.fillStyle = rgba('#000000', 0.55 * (f.amount || 1)); ctx.fillRect(0, 0, W, H); ctx.restore(); } }
    if (f.type === 'alarm') { const a = (0.5 + 0.5 * Math.sin(lt * Math.PI * 2 / (f.period || 1.1))) * 0.22 * (f.amount || 1);
      ctx.save(); ctx.fillStyle = rgrad(ctx, W / 2, H / 2, Math.min(W, H) * 0.3, Math.hypot(W, H) * 0.6, [[0, 'rgba(229,57,53,0)'], [1, `rgba(229,57,53,${a * 2.5})`]]); ctx.fillRect(0, 0, W, H); ctx.restore(); }
    if (f.type === 'blackout') { const t0 = f.t || 0.5, k = clamp((lt - t0) / 0.12); if (lt > t0 - 0.4) { const fl = lt < t0 ? (vnoise(29, lt * 25) > 0.55 ? 0.6 : 0) : k * (f.amount || 0.85);
      ctx.save(); ctx.fillStyle = rgba('#000000', fl); ctx.fillRect(0, 0, W, H); ctx.restore(); } }
  }
};
T.FX_NAMES = Object.keys(FX).concat(['blackout']);
})();
