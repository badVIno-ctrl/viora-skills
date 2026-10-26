/* TOON chars: human rig (hero, kid, elder, zombie...) and border-collie dog. Local units: 1000 = actor height,
   feet at y=0, facing right (mirrored for left). Same story => same pixels (blink/breath are functions of t). */
'use strict';
(function () {
const T = window.TOON, {clamp, lerp, E, hash, rng, vnoise, mix, shade, rgba, rr, ell} = T.h;

// ------------------------------------------------------------------ looks (cast presets)
T.LOOKS = {
  hero:   {skin: '#F1C7A1', hair: '#3B2A22', hair_style: 'short', hat: 'cap', hat_color: '#2E4756', top: 'hoodie', top_color: '#E39B35',
           pants: '#3E5878', shoes: '#4A3426', detail: 'scarf', detail_color: '#C8372D', stubble: true},
  heroine:{skin: '#F3CDAE', hair: '#6B3B24', hair_style: 'ponytail', hat: 'none', top: 'jacket', top_color: '#3F7F7A', pants: '#2F3B52', shoes: '#3A2A22', detail: 'backpack', detail_color: '#C2553A'},
  kid:    {skin: '#F4D0B0', hair: '#C98A3A', hair_style: 'messy', hat: 'none', top: 'tshirt', top_color: '#4C9BE8', pants: '#33475E', shoes: '#E8E8E8', build: 'kid'},
  elder:  {skin: '#E9BE9C', hair: '#D9D9D9', hair_style: 'bald_sides', hat: 'none', top: 'sweater', top_color: '#7B6A58', pants: '#4B4B4B', shoes: '#2A2A2A', detail: 'glasses', beard: 'mustache', build: 'big'},
  granny: {skin: '#EEC6A6', hair: '#E3E3E3', hair_style: 'bun', hat: 'scarf', hat_color: '#B5473A', top: 'dress', top_color: '#5E7FA6', pants: '#5E7FA6', shoes: '#3A2A22', detail: 'apron', detail_color: '#F2E6C9'},
  worker: {skin: '#D9A07A', hair: '#2A1E18', hair_style: 'short', hat: 'helmet', hat_color: '#F2B630', top: 'jacket', top_color: '#E2702A', pants: '#2F3B52', shoes: '#2A2A2A', beard: 'stubble'},
  soldier:{skin: '#E2B58F', hair: '#2A1E18', hair_style: 'short', hat: 'helmet', hat_color: '#4F5B3A', top: 'jacket', top_color: '#5C6B45', pants: '#4A5536', shoes: '#2A2A2A'},
  doctor: {skin: '#F0C8A6', hair: '#2A1E18', hair_style: 'short', hat: 'none', top: 'coat', top_color: '#F2F4F5', pants: '#4E6A84', shoes: '#2A2A2A', detail: 'mask', detail_color: '#8FC9D9'},
  ushanka:{skin: '#F1C7A1', hair: '#3B2A22', hair_style: 'short', hat: 'ushanka', hat_color: '#B83A2E', top: 'coat', top_color: '#5A4636', pants: '#3B3B44', shoes: '#2A2A2A', stubble: true},
  zombie: {skin: '#9DB08A', hair: '#2E3328', hair_style: 'messy', hat: 'none', top: 'tshirt', top_color: '#6E7F86', pants: '#4A4F45', shoes: '#33352F', zombie: true},
  zombie2:{skin: '#A3A98C', hair: '#4A3B2B', hair_style: 'long', hat: 'none', top: 'jacket', top_color: '#7A5A4C', pants: '#3E4652', shoes: '#33352F', zombie: true},
  dog:    {kind: 'dog', coat: '#1D2026', white: '#F2EFE8', eye: '#3A2516'},
  dog_tan:{kind: 'dog', coat: '#B8763D', white: '#F4EBDD', eye: '#2B1A10'},
  cat:    {kind: 'cat', coat: '#E39B4A', white: '#FBF3E6', eye: '#3B7A3A'},
};

// ------------------------------------------------------------------ poses (side view; radians; arms: [shoulder, elbow], legs: [hip, knee])
// shoulder 0 = hanging down, + = forward/up. elbow + = forearm bends forward/up. hip + = thigh forward. knee + = shin bends back.
const P0 = {na: [0.10, 0.20], fa: [-0.06, 0.25], nl: [0.05, 0.04], fl: [-0.05, 0.05], lean: 0, tilt: 0, sh: 0};
const POSES = {
  stand: {}, idle: {},
  point: {na: [1.45, 0.05], lean: 0.04, tilt: -0.04},
  hold: {na: [0.55, 1.05], fa: [0.45, 1.15]},
  phone: {na: [0.30, 2.30], tilt: 0.16},
  call: {na: [0.15, 2.85], tilt: 0.06},
  scared: {na: [0.70, 2.25], fa: [0.60, 2.35], nl: [0.12, 0.30], fl: [-0.14, 0.24], lean: -0.10, tilt: -0.08},
  think: {na: [0.22, 2.70], fa: [0.55, 1.55], tilt: 0.10},
  wave: {na: [2.55, 0.45]},
  hands_up: {na: [2.85, 0.15], fa: [2.75, 0.20], lean: -0.04},
  cheer: {na: [2.55, -0.15], fa: [2.45, -0.15], tilt: -0.10},
  carry: {na: [0.72, 0.95], fa: [0.62, 1.00], lean: -0.04},
  sit: {na: [0.55, 0.95], fa: [0.45, 1.00], nl: [1.52, 1.52], fl: [1.45, 1.45], lean: 0.02},
  sit_floor: {na: [0.40, 0.60], fa: [0.30, 0.60], nl: [1.45, 0.25], fl: [1.38, 0.35], lean: -0.05},
  hug_knees: {na: [0.95, 1.30], fa: [0.90, 1.35], nl: [1.20, 2.55], fl: [1.10, 2.50], lean: 0.25, tilt: 0.15},
  crouch: {na: [0.70, 1.20], fa: [0.55, 1.30], nl: [1.25, 2.30], fl: [0.90, 2.00], lean: 0.30},
  kneel: {na: [0.60, 1.00], fa: [0.40, 1.00], nl: [1.40, 1.45], fl: [0.05, 1.55], lean: 0.10},
  shrug: {na: [0.35, 1.70], fa: [0.30, 1.70], tilt: 0.10, sh: 1},
  facepalm: {na: [0.42, 2.62], tilt: 0.22},
  knock: {na: [1.20, 1.30]},
  push: {na: [1.40, 0.40], fa: [1.35, 0.45], nl: [0.35, 0.30], fl: [-0.45, 0.05], lean: 0.25},
  dig: {na: [0.95, 0.60], fa: [0.70, 0.95], nl: [0.30, 0.40], fl: [-0.20, 0.10], lean: 0.35},
  write: {na: [0.78, 1.30], fa: [0.70, 1.35], tilt: 0.16},
  drink: {na: [0.55, 2.55], tilt: -0.22},
  eat: {na: [0.45, 2.45], tilt: 0.05},
  listen: {na: [0.25, 2.75], tilt: 0.12},
  flashlight: {na: [1.25, 0.12]},
  look_back: {},
  zombie: {na: [1.45, 0.15], fa: [1.35, 0.20], tilt: 0.22, lean: 0.08},
  lie: {na: [0.15, 0.10], fa: [0.05, 0.10], nl: [0.02, 0.02], fl: [-0.02, 0.02]},
  sleep: {na: [0.15, 0.10], fa: [0.05, 0.10], nl: [0.02, 0.02], fl: [-0.02, 0.02]},
};
// front view arm overrides ([outward shoulder, elbow toward centre])
const FRONT = {
  stand: {r: [0.10, 0.08], l: [0.10, 0.08]},
  hold: {r: [0.18, 1.55], l: [0.18, 1.55]}, carry: {r: [0.25, 1.40], l: [0.25, 1.40]}, write: {r: [0.18, 1.6], l: [0.18, 1.6]},
  phone: {r: [0.12, 2.35], l: [0.10, 0.08]}, call: {r: [0.30, 2.75], l: [0.10, 0.08]}, eat: {r: [0.12, 2.4], l: [0.10, 0.08]}, drink: {r: [0.12, 2.5], l: [0.10, 0.08]},
  scared: {r: [0.35, 2.30], l: [0.35, 2.30]}, think: {r: [0.15, 2.60], l: [0.20, 1.45]}, facepalm: {r: [0.10, 2.70], l: [0.10, 0.08]},
  wave: {r: [2.30, -0.55], l: [0.10, 0.08]}, hands_up: {r: [2.75, 0.15], l: [2.75, 0.15]}, cheer: {r: [2.45, -0.20], l: [2.45, -0.20]},
  point: {r: [1.50, 0.00], l: [0.10, 0.08]}, shrug: {r: [0.55, -1.20], l: [0.55, -1.20]}, flashlight: {r: [0.45, 1.20], l: [0.10, 0.08]},
  listen: {r: [0.30, 2.80], l: [0.10, 0.08]}, zombie: {r: [0.30, 1.30], l: [0.30, 1.30]}, knock: {r: [0.5, 1.9], l: [0.10, 0.08]},
};
T.POSES = POSES; T.POSE_NAMES = Object.keys(POSES).concat(['walk', 'run', 'bark']);   // bark: dogs only
// grip: how the near arm holds an item when the pose does not say otherwise
const GRIP = {flashlight: [1.20, 0.15], phone: [0.30, 2.30], lantern: [0.35, 0.30], candle: [0.55, 1.55], can: [0.55, 1.35], bottle: [0.55, 1.30],
  radio: [0.50, 1.50], map: [0.70, 1.15], box: [0.72, 0.95], bag: [0.05, 0.10], jerrycan: [0.05, 0.10], bucket: [0.05, 0.10],
  hammer: [0.65, 1.20], shovel: [0.95, 0.60], firstaid: [0.08, 0.10], key: [0.90, 0.90], battery: [0.65, 1.30], planks: [0.72, 0.95], book: [0.70, 1.25],
  cup: [0.55, 1.45], seeds: [0.60, 1.20], watering_can: [0.45, 0.65], rope: [0.10, 0.15], umbrella: [0.75, 1.35], torch: [1.0, 0.6]};
const TWO_HANDS = {box: 1, map: 1, planks: 1, shovel: 1, book: 1};

const EMO = {
  neutral: {eye: 'dot', brow: [0, 0], mouth: 'line', curve: 0.18},
  calm: {eye: 'dot', brow: [-0.05, -2], mouth: 'line', curve: 0.35},
  happy: {eye: 'arc', brow: [-0.18, -8], mouth: 'smile', blush: 1},
  smile: {eye: 'dot', brow: [-0.1, -4], mouth: 'smile', blush: 0.6},
  scared: {eye: 'wide', brow: [-0.50, -10], mouth: 'wavy'},
  worried: {eye: 'dot', brow: [-0.42, -6], mouth: 'line', curve: -0.25},
  sad: {eye: 'droop', brow: [-0.45, 0], mouth: 'frown'},
  angry: {eye: 'dot', brow: [0.55, 8], mouth: 'flat', curve: -0.35},
  surprised: {eye: 'wide', brow: [-0.12, -18], mouth: 'o'},
  determined: {eye: 'narrow', brow: [0.32, 5], mouth: 'line', curve: -0.05},
  tired: {eye: 'half', brow: [-0.18, 2], mouth: 'line', curve: -0.1},
  think: {eye: 'up', brow: [0.25, -6], mouth: 'side'},
  shout: {eye: 'narrow', brow: [0.45, 6], mouth: 'shout'},
  sleep: {eye: 'closed', brow: [0, 2], mouth: 'line', curve: 0.1},
  zombie: {eye: 'blank', brow: [0.15, 4], mouth: 'zombie'},
};
T.EMOTIONS = Object.keys(EMO);

// ------------------------------------------------------------------ helpers
const OUT = {none: 0, thin: 9, thick: 17};
function ink(st, c) { const w = OUT[st.outline] == null ? OUT.thin : OUT[st.outline]; if (!w) return null;
  return {w, c: st.outline === 'thick' ? '#15171C' : shade(c, -0.55)}; }
function paint(ctx, color, o) { ctx.fillStyle = color; ctx.fill(); if (o) { ctx.lineWidth = o.w; ctx.strokeStyle = o.c; ctx.lineJoin = 'round'; ctx.stroke(); } }
function hose(ctx, pts, w, color, o) {            // rubber-hose limb through joints
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  const path = () => { ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
    if (pts.length === 3) ctx.quadraticCurveTo(pts[1][0] * 1.0, pts[1][1], pts[2][0], pts[2][1]); else pts.slice(1).forEach(p => ctx.lineTo(p[0], p[1])); };
  // quadratic through the joint: control point pushed so the curve passes the knee/elbow
  if (pts.length === 3) { const [a, b, c] = pts; const cx = 2 * b[0] - (a[0] + c[0]) / 2, cy = 2 * b[1] - (a[1] + c[1]) / 2;
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.quadraticCurveTo(lerp(b[0], cx, 0.55), lerp(b[1], cy, 0.55), c[0], c[1]); }
  else path();
  if (o) { ctx.strokeStyle = o.c; ctx.lineWidth = w + o.w * 2; ctx.stroke(); }
  ctx.strokeStyle = color; ctx.lineWidth = w; ctx.stroke();
}
function seg(p, len, ang, dir = 1) { return [p[0] + Math.sin(ang) * len * dir, p[1] + Math.cos(ang) * len]; }
function blink(id, t) { const s = hash(id) % 1000 / 1000, per = 3.1 + s * 1.9, ph = (t + s * per) % per; return ph < 0.13 ? 1 - Math.abs(ph - 0.065) / 0.065 : 0; }
function talkOpen(t, a) {                          // mouth opening from the voice word timings (0..1)
  const W = T.story.words || [];
  if (!a._talk) return 0;
  const [ta, tb] = a._talk; if (t < ta || t > tb) return 0;
  let lo = 0, hi = W.length - 1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (W[m].e < t) lo = m + 1; else if (W[m].s > t) hi = m - 1; else {
    const w = W[m], k = (t - w.s) / Math.max(0.06, w.e - w.s); return Math.sin(Math.PI * k) * (0.55 + 0.45 * Math.abs(Math.sin((t - w.s) * 21))); } }
  return 0;
}
function lerpPose(a, b, k) { const o = {}; for (const key of Object.keys(P0)) { const x = a[key], y = b[key];
  o[key] = Array.isArray(x) ? [lerp(x[0], y[0], k), lerp(x[1], y[1], k)] : lerp(x, y, k); } return o; }
function poseOf(name) { return Object.assign({}, P0, POSES[name] || {}); }

// ------------------------------------------------------------------ actor state over time
function actorState(env, a) {
  const {W, H, lt} = env, story = T.story, portrait = story.H >= story.W;
  const look = Object.assign({}, T.LOOKS[(story.cast && story.cast[a.id] && story.cast[a.id].look) || a.look || a.id] ||
    (a.kind === 'dog' ? T.LOOKS.dog : T.LOOKS.hero), (story.cast && story.cast[a.id]) || {}, a.style || {});
  const kind = look.kind || a.kind || 'human';
  const defH = kind === 'dog' || kind === 'cat' ? (portrait ? 0.15 : 0.24) : (portrait ? 0.30 : 0.50);
  const h = (a.h || look.h || defH) * H;
  let x = (a.at && a.at[0] != null ? a.at[0] : 0.5) * W, y = a.at && a.at[1] != null ? a.at[1] * H : (env.ground || (portrait ? 0.80 : 0.86) * H), speed = 0, dist = 0;
  // movement: to + move [t0, t1] or path [[t, x, y], ...]
  let keys = null;
  if (a.path) keys = a.path.map(p => [p[0], p[1] * W, p[2] == null ? y : p[2] * H]);
  else if (a.to) { const m = a.move || [0, Math.max(0.6, (env.sc.t1 - env.sc.t0) - 0.2)]; keys = [[m[0], x, y], [m[1], a.to[0] * W, a.to[1] == null ? y : a.to[1] * H]]; }
  let dir = a.face === 'left' ? -1 : 1, moving = 0;
  if (keys && keys.length > 1) {
    let tot = 0; const seglen = [];
    for (let i = 1; i < keys.length; i++) { const d = Math.hypot(keys[i][1] - keys[i - 1][1], keys[i][2] - keys[i - 1][2]); seglen.push(d); tot += d; }
    let i = 0; while (i < keys.length - 2 && lt > keys[i + 1][0]) i++;
    const k0 = keys[i], k1 = keys[i + 1], span = Math.max(0.01, k1[0] - k0[0]);
    const raw = clamp((lt - k0[0]) / span), ke = keys.length === 2 ? E.io(raw) : raw;
    x = lerp(k0[1], k1[1], ke); y = lerp(k0[2], k1[2], ke);
    dist = seglen.slice(0, i).reduce((s, v) => s + v, 0) + seglen[i] * ke;
    const dke = keys.length === 2 ? Math.PI / 2 * Math.sin(Math.PI * raw) : 1;   // derivative of ease
    speed = raw > 0 && raw < 1 ? seglen[i] / span * dke : 0;
    if (!a.face && Math.abs(k1[1] - k0[1]) > 2) dir = k1[1] > k0[1] ? 1 : -1;
    moving = clamp(speed / (h * 0.35));
  }
  // pose timeline: pose + acts [[t, pose], ...] blended over 0.35 s
  const acts = [[-1, a.pose || (look.zombie ? 'zombie' : 'stand')]].concat(a.acts || []);
  let j = 0; while (j < acts.length - 1 && lt >= acts[j + 1][0]) j++;
  let pose = poseOf(acts[j][1]), pname = acts[j][1];
  if (j > 0) { const k = clamp((lt - acts[j][0]) / 0.35); if (k < 1) pose = lerpPose(poseOf(acts[j - 1][1]), pose, E.io(k)); }
  // emotion timeline: emotion + feel [[t, emotion], ...]
  const feels = [[-1, a.emotion || (look.zombie ? 'zombie' : 'neutral')]].concat(a.feel || []);
  let q = 0; while (q < feels.length - 1 && lt >= feels[q + 1][0]) q++;
  const gait = a.gait || (look.zombie ? 'shamble' : (speed > h * 1.25 ? 'run' : 'walk'));
  return {look, kind, h, x, y, dir, view: a.view || (a.face === 'front' ? 'front' : a.face === 'back' ? 'back' : 'side'), pose, pname, dist, speed, moving,
    gait, emo: feels[q][1], t: env.t, id: a.id || 'a', hold: a.hold, hold2: a.hold2, lookCam: a.gaze === 'camera' || a.look === 'camera', a};
}

// ------------------------------------------------------------------ human
function locomotion(st, pose) {
  if (!st.moving) return {pose, bob: 0};
  const L = 340, run = st.gait === 'run', sh = st.gait === 'shamble';
  const amp = run ? 0.72 : sh ? 0.28 : 0.42, stride = 2 * 2 * L * Math.sin(amp) * (run ? 1.25 : 1) * st.h / 1000;
  const ph = st.dist / Math.max(1, stride) * Math.PI * 2, s = Math.sin(ph), c = Math.cos(ph), m = st.moving;
  const P = Object.assign({}, pose);
  const legA = (sgn) => { const sw = sgn * s; return [amp * sw, (run ? 1.25 : 0.55) * Math.max(0, sgn * c) + (sh ? 0.12 : 0.05)]; };
  P.nl = mixA(pose.nl, legA(1), m); P.fl = mixA(pose.fl, legA(-1), m);
  if (!st.busyArms) { const aa = run ? 0.95 : 0.38; P.na = mixA(pose.na, [-aa * s, run ? 1.55 : 0.32], m); P.fa = mixA(pose.fa, [aa * s, run ? 1.55 : 0.32], m); }
  P.lean = lerp(pose.lean, run ? 0.20 : sh ? 0.12 : 0.04, m);
  return {pose: P, bob: (run ? 34 : 16) * Math.abs(c) * m};
}
function mixA(a, b, k) { return [lerp(a[0], b[0], k), lerp(a[1], b[1], k)]; }

function drawHuman(env, st) {
  const ctx = env.ctx, L = st.look, sty = Object.assign({}, env.style, L.style || {}), t = st.t, id = st.id;
  const kid = L.build === 'kid', big = L.build === 'big';
  const headR = kid ? 190 : 165, legL = kid ? 300 : 340, armU = kid ? 130 : 150, armF = kid ? 125 : 140;
  const torsoW = (big ? 1.18 : kid ? 0.92 : 1) * 118, limbW = big ? 82 : 72, legW = big ? 96 : 88;
  let pose = st.pose; const zombie = !!L.zombie;
  st.busyArms = !!st.hold && st.pname !== 'walk';
  if (st.hold && GRIP[st.hold] && ['stand', 'idle', 'walk', 'run', 'look_back'].includes(st.pname)) {
    pose = Object.assign({}, pose, {na: GRIP[st.hold]}); if (TWO_HANDS[st.hold]) pose.fa = [GRIP[st.hold][0] - 0.08, GRIP[st.hold][1] + 0.05];
  }
  const lo = locomotion(st, pose); pose = lo.pose;
  const lying = st.pname === 'lie' || st.pname === 'sleep';
  // breathing + idle sway
  const br = Math.sin(t * Math.PI * 2 / 3.4 + hash(id) % 7), sway = (vnoise(hash(id), t * 0.5) - 0.5) * 0.03;
  ctx.save(); ctx.translate(st.x, st.y); const s = st.h / 1000; ctx.scale(s * st.dir, s);
  if (st.a.alpha != null) ctx.globalAlpha = st.a.alpha;
  T.h.shadowBlob(ctx, 0, 0, lying ? 520 : 230, 0.25);
  if (lying) { ctx.translate(480, -60); ctx.rotate(-Math.PI / 2); }          // body centred on the actor x, head towards -dir
  // legs: find hip height so the lowest foot stands on the ground
  const legPts = (lg, hx, hy) => { const k = [hx + Math.sin(lg[0]) * legL / 2, hy + Math.cos(lg[0]) * legL / 2]; const a2 = lg[0] - lg[1];
    return [[hx, hy], k, [k[0] + Math.sin(a2) * legL / 2, k[1] + Math.cos(a2) * legL / 2]]; };
  const fy = Math.max(legPts(pose.nl, 0, 0)[2][1], legPts(pose.fl, 0, 0)[2][1]);
  const hipY = -fy - lo.bob + (st.a.jump ? -st.a.jump * 300 * Math.max(0, Math.sin(Math.PI * clamp((env.lt - (st.a.jump_t || 0)) / 0.5))) : 0);
  const hipX = 0, lean = pose.lean + sway * (st.moving ? 0 : 1);
  const torsoH = kid ? 270 : 300;
  const rot = (px, py) => { const dx = px - hipX, dy = py - hipY, c = Math.cos(lean), sn = Math.sin(lean); return [hipX + dx * c + dy * sn, hipY - dx * sn + dy * c]; };
  // lean > 0 tilts the upper body forward (towards +x): rotate points around the hip
  const rotF = (px, py) => { const dx = px, dy = py; const c = Math.cos(lean), sn = Math.sin(lean); return [hipX + dx * c - dy * sn, hipY + dx * sn + dy * c]; };
  const up = (lx, ly) => rotF(lx, ly);           // local coords relative to hip, y up negative
  const shY = -torsoH + 30 - (pose.sh ? 26 : 0) + br * 3;
  const front = st.view === 'front' || st.view === 'back', back = st.view === 'back';
  const skin = L.skin, topC = L.top_color || '#E39B35', sleeve = L.top === 'tshirt' ? null : topC;
  const o = c => ink(sty, c);
  const farShade = c => shade(c, -0.22);

  const drawLeg = (lg, hx, color, far) => {
    const pts = legPts(lg, hx, hipY); const pc = far ? farShade(L.pants) : L.pants;
    const k2 = pts[1], f2 = pts[2], dl = Math.hypot(f2[0] - k2[0], f2[1] - k2[1]) || 1, cut = 34 / dl;
    hose(ctx, [pts[0], k2, [f2[0] - (f2[0] - k2[0]) * cut, f2[1] - (f2[1] - k2[1]) * cut]], legW, pc, o(L.pants));
    const f = pts[2], ang = Math.max(-0.5, Math.min(0.5, (lg[0] - lg[1]) * 0.6));   // shoe
    ctx.save(); ctx.translate(f[0], f[1]); if (!front) ctx.rotate(-ang * 0.5);
    const sc = far ? farShade(L.shoes) : L.shoes;
    if (front) { ell(ctx, 0, -6, 52, 30); } else { ctx.beginPath(); ctx.moveTo(-40, -36); ctx.quadraticCurveTo(-46, 8, -20, 10); ctx.lineTo(70, 10);
      ctx.quadraticCurveTo(92, 6, 80, -16); ctx.quadraticCurveTo(60, -40, 20, -40); ctx.closePath(); }
    paint(ctx, sc, o(L.shoes)); ctx.restore();
  };
  const armPts = (ar, sx, sy, frontSide) => {        // returns shoulder, elbow, hand (in body space, before lean)
    if (frontSide) { const d = frontSide; const e = [sx + Math.sin(ar[0]) * armU * d, sy + Math.cos(ar[0]) * armU];
      const a2 = ar[0] - ar[1]; return [[sx, sy], e, [e[0] + Math.sin(a2) * armF * d, e[1] + Math.cos(a2) * armF]]; }
    const e = [sx + Math.sin(ar[0]) * armU, sy + Math.cos(ar[0]) * armU], a2 = ar[0] + ar[1];
    return [[sx, sy], e, [e[0] + Math.sin(a2) * armF, e[1] + Math.cos(a2) * armF]];
  };
  const drawArm = (pts, far, item, which) => {
    const P = pts.map(p => up(p[0], p[1] - hipY));
    const sc = sleeve ? (far ? farShade(sleeve) : sleeve) : (far ? farShade(skin) : skin);
    if (sleeve) hose(ctx, P, limbW, sc, o(sleeve));
    else { hose(ctx, [P[0], P[1]], limbW + 6, far ? farShade(topC) : topC, o(topC)); hose(ctx, [P[1], P[2]], limbW - 8, far ? farShade(skin) : skin, o(skin)); }
    const hd = P[2], fa = Math.atan2(P[2][1] - P[1][1], P[2][0] - P[1][0]);
    if (item && T.drawItem) { ctx.save(); ctx.translate(hd[0], hd[1]); ctx.rotate(fa - Math.PI / 2 + Math.PI); T.drawItem(ctx, item, st, env, which); ctx.restore(); }
    ell(ctx, hd[0], hd[1], 38, 38); paint(ctx, far ? farShade(skin) : skin, o(skin));
    if (zombie && !far) { ctx.strokeStyle = shade(skin, -0.35); ctx.lineWidth = 7; ctx.beginPath(); ctx.moveTo(hd[0] + 10, hd[1] - 20); ctx.lineTo(hd[0] + 38, hd[1] - 4); ctx.stroke(); }
  };
  // ------------- draw order
  const naName = st.pname, fr = FRONT[naName] || FRONT.stand;
  if (front) {
    const hx = 62;
    // legs front: walking = alternate knee lift
    const lift = st.moving ? Math.sin(st.dist / Math.max(1, st.h * 0.55) * Math.PI * 2) : 0;
    const legF = (side, l) => { const top = [side * hx, hipY], ky = hipY + legL / 2 - Math.max(0, l) * 60, fy2 = Math.min(0, -Math.max(0, l) * 70);
      hose(ctx, [top, [side * (hx + 6), ky], [side * (hx + 8), fy2 - 40]], legW, L.pants, o(L.pants));
      ctx.save(); ctx.translate(side * (hx + 12), fy2); ell(ctx, 0, -6, 50, 30); paint(ctx, L.shoes, o(L.shoes)); ctx.restore(); };
    if (pose.nl[0] > 0.9) {                          // sitting front: short thighs
      [-1, 1].forEach(side => { hose(ctx, [[side * hx, hipY], [side * (hx + 10), hipY + 40], [side * (hx + 14), -40]], legW, L.pants, o(L.pants));
        ctx.save(); ctx.translate(side * (hx + 16), 0); ell(ctx, 0, -6, 50, 30); paint(ctx, L.shoes, o(L.shoes)); ctx.restore(); });
    } else { legF(-1, -lift); legF(1, lift); }
    if (L.detail === 'backpack' && !back) { rr(ctx, -torsoW - 18, hipY - torsoH + 40, 36, 150, 16); paint(ctx, shade(L.detail_color || '#C2553A', -0.1), o(L.detail_color || '#C2553A'));
      rr(ctx, torsoW - 18, hipY - torsoH + 40, 36, 150, 16); paint(ctx, shade(L.detail_color || '#C2553A', -0.1), o(L.detail_color || '#C2553A')); }
    if (back && L.detail === 'backpack') {}
    drawTorso(ctx, L, st, hipX, hipY, torsoW, torsoH, lean, o, front, back, br);
    const sy = hipY + shY;
    const ra = armPts(fr.r, torsoW - 18, sy, 1), la = armPts(fr.l, -torsoW + 18, sy, -1);
    if (back && L.detail === 'backpack') { rr(ctx, -95, hipY - torsoH + 50, 190, 210, 40); paint(ctx, L.detail_color || '#C2553A', o(L.detail_color || '#C2553A'));
      rr(ctx, -70, hipY - torsoH + 150, 140, 80, 22); paint(ctx, shade(L.detail_color || '#C2553A', -0.15), o(L.detail_color || '#C2553A')); }
    drawArm(la, false, st.hold2, 'far'); drawArm(ra, false, st.hold, 'near');
    if (zombie && st.moving) {}
    drawHead(ctx, env, st, up(0, shY - 40 - headR + 25 - hipY + hipY), headR, pose.tilt, 'front', back, o);
  } else {
    const fa = armPts(pose.fa, -14, hipY + shY), na = armPts(pose.na, 16, hipY + shY);
    const farItem = st.hold2 || (TWO_HANDS[st.hold] ? null : null);
    drawArm(fa, true, farItem, 'far');
    drawLeg(pose.fl, -10, L.pants, true);
    drawLeg(pose.nl, 12, L.pants, false);
    if (L.detail === 'backpack') { const bp = up(-torsoW + 8, -torsoH + 70 + 80); rr(ctx, bp[0] - 70, bp[1] - 95, 105, 200, 34);
      paint(ctx, L.detail_color || '#C2553A', o(L.detail_color || '#C2553A')); rr(ctx, bp[0] - 82, bp[1] + 10, 50, 70, 16); paint(ctx, shade(L.detail_color || '#C2553A', -0.18), o(L.detail_color || '#C2553A')); }
    drawTorso(ctx, L, st, hipX, hipY, torsoW, torsoH, lean, o, false, false, br);
    const lb = st.pname === 'look_back';
    const headC = up(8, shY - 40 - headR + 25);
    drawHead(ctx, env, st, headC, headR, pose.tilt, st.lookCam ? 'front' : 'side', false, o, lb);
    drawArm(na, false, st.hold, 'near');
    if (TWO_HANDS[st.hold] && st.hold !== 'shovel') {}
  }
  ctx.restore();
}

function drawTorso(ctx, L, st, hx, hy, tw, th, lean, o, front, back, br) {
  const c = L.top_color || '#E39B35', top = L.top || 'hoodie';
  ctx.save(); ctx.translate(hx, hy); ctx.rotate(lean);
  const sy = 1 + br * 0.006;
  ctx.scale(1, sy);
  const hem = top === 'coat' ? 150 : top === 'dress' ? 170 : 30;
  // hood behind the neck
  if (top === 'hoodie' && !back) { ell(ctx, front ? 0 : -40, -th + 6, front ? 112 : 86, 52); paint(ctx, shade(c, -0.12), o(c)); }
  ctx.beginPath();
  if (front) { ctx.moveTo(-tw + 10, -th + 20); ctx.quadraticCurveTo(-tw - 6, -th / 2, -tw + (top === 'dress' ? -40 : 6), hem); ctx.lineTo(tw - (top === 'dress' ? -40 : 6), hem);
    ctx.quadraticCurveTo(tw + 6, -th / 2, tw - 10, -th + 20); ctx.quadraticCurveTo(0, -th - 18, -tw + 10, -th + 20); }
  else { const w = tw * 0.86; ctx.moveTo(-w + 8, -th + 22); ctx.quadraticCurveTo(-w - 18, -th * 0.45, -w + (top === 'dress' ? -40 : 4), hem);
    ctx.lineTo(w + (top === 'dress' ? 46 : 8), hem); ctx.quadraticCurveTo(w + 22, -th * 0.5, w - 4, -th + 26); ctx.quadraticCurveTo(0, -th - 16, -w + 8, -th + 22); }
  ctx.closePath(); paint(ctx, c, o(c));
  // soft shading on the back side + rim
  ctx.save(); ctx.clip(); ctx.fillStyle = rgba(shade(c, -0.5), 0.22); ctx.fillRect(front ? tw * 0.35 : -tw * 1.6, -th - 40, tw * 1.25, th + hem + 80);
  ctx.strokeStyle = rgba('#FFE2B0', front ? 0.25 : 0.45); ctx.lineWidth = 14; ctx.beginPath(); ctx.moveTo(front ? -tw + 4 : -tw * 0.86 - 4, -th + 30); ctx.quadraticCurveTo(front ? -tw - 10 : -tw * 0.86 - 22, -th * 0.45, front ? -tw + 6 : -tw * 0.86 + 2, hem - 10); ctx.stroke();
  ctx.restore();
  // details
  ctx.lineCap = 'round'; ctx.strokeStyle = shade(c, -0.35); ctx.lineWidth = 7;
  if (top === 'hoodie' && !back) {
    if (front) { rr(ctx, -70, -110, 140, 70, 22); ctx.stroke(); ctx.beginPath(); ctx.moveTo(-26, -th + 10); ctx.lineTo(-30, -th + 90); ctx.moveTo(26, -th + 10); ctx.lineTo(30, -th + 90); ctx.stroke(); }
    else { ctx.beginPath(); ctx.moveTo(20, -100); ctx.quadraticCurveTo(70, -98, 86, -60); ctx.stroke(); }
  } else if (top === 'jacket' || top === 'coat') {
    if (front && !back) { ctx.beginPath(); ctx.moveTo(0, -th + 12); ctx.lineTo(0, hem - 4); ctx.stroke(); ell(ctx, -40, -th + 28, 40, 22, 0.5); ctx.stroke(); ell(ctx, 40, -th + 28, 40, 22, -0.5); ctx.stroke(); }
    else if (!back) { ctx.beginPath(); ctx.moveTo(tw * 0.55, -th + 30); ctx.lineTo(tw * 0.62, hem - 6); ctx.stroke(); ctx.beginPath(); ctx.moveTo(10, -th + 8); ctx.lineTo(70, -th + 50); ctx.stroke(); }
  } else if (top === 'sweater') { for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.moveTo(-tw + 20, -th + 90 + i * 60); ctx.lineTo(tw - 20, -th + 90 + i * 60); ctx.globalAlpha = 0.35; ctx.stroke(); ctx.globalAlpha = 1; } }
  if (L.detail === 'apron' && !back) { rr(ctx, front ? -80 : -20, -th + 70, front ? 160 : 110, th + hem - 60, 18); paint(ctx, L.detail_color || '#F2E6C9', o(L.detail_color || '#F2E6C9')); }
  if (L.zombie) { ctx.fillStyle = shade(c, -0.3); for (let i = 0; i < 4; i++) { ctx.beginPath(); const x0 = -tw + 30 + i * 55; ctx.moveTo(x0, hem + 1); ctx.lineTo(x0 + 22, hem - 34); ctx.lineTo(x0 + 40, hem + 1); ctx.fill(); } }
  if (L.detail === 'scarf' && !back) { const sc = L.detail_color || '#C8372D'; rr(ctx, front ? -92 : -70, -th - 12, front ? 184 : 150, 50, 24); paint(ctx, sc, o(sc));
    ctx.save(); ctx.translate(front ? 40 : -50, -th + 20); ctx.rotate(front ? -0.08 : 0.25 + Math.sin(st.t * 3) * 0.06); rr(ctx, -20, 0, 44, 120, 14); paint(ctx, shade(sc, -0.12), o(sc)); ctx.restore(); }
  ctx.restore();
}

function drawHead(ctx, env, st, c, r, tilt, view, back, o, lookBack) {
  const L = st.look, skin = L.skin, t = st.t;
  ctx.save(); ctx.translate(c[0], c[1] + r * 0.15); ctx.rotate(tilt * 0.6); ctx.translate(0, -r * 0.15);
  if (lookBack) ctx.scale(-1, 1);
  const front = view === 'front';
  // neck
  rr(ctx, -34, r * 0.55, 68, 70, 20); paint(ctx, shade(skin, -0.15), o(skin));
  // long hair behind
  const hc = L.hair, hs = L.hair_style || 'short';
  if (hs === 'long' && L.hat !== 'hood') { ctx.beginPath(); ctx.moveTo(-r * 1.02, -r * 0.1); ctx.quadraticCurveTo(-r * 1.15, r * 1.25, -r * 0.2, r * 1.05);
    ctx.lineTo(front ? r * 1.0 : r * 0.1, r * 1.05); ctx.quadraticCurveTo(r * 1.12, r * 0.6, r * 0.95, -r * 0.1); ctx.closePath(); paint(ctx, shade(hc, -0.1), o(hc)); }
  if (hs === 'ponytail' && !front) { ctx.beginPath(); ctx.moveTo(-r * 0.8, -r * 0.35); ctx.quadraticCurveTo(-r * 1.6, -r * 0.1 + Math.sin(t * 4) * 8, -r * 1.25, r * 0.75);
    ctx.quadraticCurveTo(-r * 1.0, r * 0.2, -r * 0.6, -r * 0.05); ctx.closePath(); paint(ctx, hc, o(hc)); }
  if (L.hat === 'hood') { ell(ctx, front ? 0 : -r * 0.12, -r * 0.02, r * 1.22, r * 1.2); paint(ctx, shade(L.top_color || '#E39B35', -0.18), o(L.top_color || '#E39B35')); }
  if (L.hat === 'ushanka') { [-1, 1].forEach(sd => { if (!front && sd > 0) return; rr(ctx, (front ? sd * r * 0.95 : -r * 0.35) - 34, -r * 0.2, 68, r * 1.05, 30); paint(ctx, shade(L.hat_color || '#B83A2E', -0.12), o(L.hat_color)); }); }
  // head (side view: nose bump first, the head circle covers its inner half)
  ell(ctx, 0, 0, r, r); paint(ctx, skin, o(skin));
  ctx.save(); ell(ctx, 0, 0, r, r); ctx.clip();
  { const gx = front ? r * 0.75 : -r * 0.95, gy = r * 0.55; ctx.fillStyle = T.h.rgrad(ctx, gx, gy, r * 0.2, r * 1.25, [[0, rgba(shade(skin, -0.6), 0.22)], [1, rgba(shade(skin, -0.6), 0)]]);
    ctx.fillRect(-r, -r, 2 * r, 2 * r); }
  ctx.strokeStyle = rgba('#FFE2B0', 0.5); ctx.lineWidth = 16; ctx.beginPath(); ctx.arc(0, 0, r - 4, Math.PI * 0.62, Math.PI * 1.22); ctx.stroke();
  ctx.restore();
  // ear (side)
  if (!front && !back && L.hat !== 'hood' && L.hat !== 'ushanka') { ell(ctx, -r * 0.42, r * 0.14, r * 0.12, r * 0.17); paint(ctx, shade(skin, -0.06), o(skin));
    ctx.strokeStyle = shade(skin, -0.3); ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(-r * 0.42, r * 0.14, r * 0.06, -1.2, 1.4); ctx.stroke(); }
  if (front && !back && L.hat !== 'hood' && L.hat !== 'ushanka') { [-1, 1].forEach(sd => { ell(ctx, sd * r * 0.98, r * 0.08, r * 0.14, r * 0.2); paint(ctx, shade(skin, -0.08), o(skin)); }); }
  if (back) { drawHair(ctx, L, r, 'back', o); drawHat(ctx, L, r, 'back', o, t); ctx.restore(); return; }
  drawFace(ctx, env, st, r, front, o);
  drawHair(ctx, L, r, front ? 'front' : 'side', o);
  drawHat(ctx, L, r, front ? 'front' : 'side', o, t);
  if (L.detail === 'glasses') { ctx.strokeStyle = '#1E2229'; ctx.lineWidth = 8; const ex = front ? [-r * 0.36, r * 0.36] : [r * 0.2, r * 0.62];
    ex.forEach(x => { ell(ctx, x, r * 0.02, r * 0.2, r * 0.17); ctx.stroke(); }); ctx.beginPath(); ctx.moveTo(ex[0] + r * 0.2, 0); ctx.lineTo(ex[1] - r * 0.2, 0); ctx.stroke(); }
  if (L.detail === 'mask') { ctx.beginPath(); const mx = front ? 0 : r * 0.45; ctx.ellipse(mx, r * 0.45, r * (front ? 0.55 : 0.5), r * 0.32, 0, 0, Math.PI * 2); paint(ctx, L.detail_color || '#8FC9D9', o(L.detail_color || '#8FC9D9')); }
  if (L.detail === 'headphones') { ctx.strokeStyle = '#2A2E36'; ctx.lineWidth = 20; ctx.beginPath(); ctx.arc(0, 0, r * 1.05, Math.PI * 1.05, Math.PI * 1.95); ctx.stroke(); ell(ctx, front ? -r : -r * 0.15, 0, 34, 52); paint(ctx, '#2A2E36'); }
  if (L.detail === 'headlamp') { ctx.fillStyle = '#2A2E36'; ctx.fillRect(-r, -r * 0.45, 2 * r, 22); rr(ctx, front ? -26 : r * 0.72, -r * 0.55, 52, 44, 10); paint(ctx, '#F2F2F2');
    if (T.addLight) T.addLight(ctx, front ? 0 : r * 0.95, -r * 0.33, {kind: 'cone', r: 900, ang: front ? Math.PI / 2 : 0, spread: 0.32, color: '#FFF4D6', a: 0.9}); }
  ctx.restore();
}

function drawFace(ctx, env, st, r, front, o) {
  const L = st.look, t = st.t, emo = EMO[st.emo] || EMO.neutral, ink2 = '#1F1A1C';
  const bl = st.emo === 'sleep' ? 1 : blink(st.id, t), open = talkOpen(t, st.a);
  const eyes = front ? [[-r * 0.36, 1], [r * 0.36, -1]] : [[r * 0.16, 1, 0.9], [r * 0.58, -1, 1]];
  const ey = r * 0.02 + (emo.eye === 'up' ? -6 : 0);
  eyes.forEach(([ex, inner, sc]) => {
    sc = sc || 1; const sz = r * 0.095 * sc;
    if (bl > 0.5 || emo.eye === 'closed') { ctx.strokeStyle = ink2; ctx.lineWidth = 9; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(ex - sz * 1.3, ey + 2); ctx.quadraticCurveTo(ex, ey + sz * 0.9, ex + sz * 1.3, ey + 2); ctx.stroke(); }
    else if (emo.eye === 'arc') { ctx.strokeStyle = ink2; ctx.lineWidth = 10; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(ex - sz * 1.4, ey + 6); ctx.quadraticCurveTo(ex, ey - sz * 1.6, ex + sz * 1.4, ey + 6); ctx.stroke(); }
    else if (emo.eye === 'wide' || emo.eye === 'blank') { ell(ctx, ex, ey, sz * 2.0, sz * 2.3); paint(ctx, emo.eye === 'blank' ? '#E8EDD8' : '#FFFFFF', {w: 6, c: ink2});
      if (emo.eye === 'wide') { ell(ctx, ex + (front ? 0 : sz * 0.4), ey + 2, sz * 0.85, sz * 0.95); paint(ctx, ink2); } }
    else { const hy = emo.eye === 'narrow' ? 0.62 : emo.eye === 'half' ? 0.45 : emo.eye === 'droop' ? 0.8 : 1;
      const lx = emo.eye === 'up' ? sz * 0.35 : (front ? 0 : sz * 0.25);
      ell(ctx, ex + lx, ey + (1 - hy) * sz * 0.6, sz, sz * 1.22 * hy); paint(ctx, ink2);
      ell(ctx, ex + lx - sz * 0.3, ey - sz * 0.4 * hy, sz * 0.32, sz * 0.32); ctx.fillStyle = '#FFFFFF'; ctx.fill();
      if (emo.eye === 'half') { ctx.strokeStyle = ink2; ctx.lineWidth = 7; ctx.beginPath(); ctx.moveTo(ex - sz * 1.4, ey - sz * 0.5); ctx.lineTo(ex + sz * 1.4, ey - sz * 0.5); ctx.stroke(); } }
    // brows
    const [ang, dy] = emo.brow, by = ey - r * 0.27 + dy - (open > 0.6 ? 3 : 0);
    ctx.save(); ctx.translate(ex, by); ctx.rotate(ang * inner * (front ? 1 : 1)); ctx.strokeStyle = shade(L.hair, -0.2); ctx.lineWidth = 13; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(-sz * 1.6, 0); ctx.lineTo(sz * 1.6, 0); ctx.stroke(); ctx.restore();
  });
  // nose
  ctx.strokeStyle = shade(L.skin, -0.32); ctx.lineWidth = 8; ctx.lineCap = 'round'; ctx.beginPath();
  if (front) { ctx.moveTo(-6, r * 0.2); ctx.quadraticCurveTo(4, r * 0.28, 8, r * 0.22); } else { ctx.moveTo(r * 0.74, r * 0.14); ctx.quadraticCurveTo(r * 0.86, r * 0.24, r * 0.74, r * 0.29); }
  ctx.stroke();
  if (emo.blush) { ctx.fillStyle = rgba('#FF7A7A', 0.22 * emo.blush); [front ? -r * 0.55 : r * 0.1, front ? r * 0.55 : r * 0.75].forEach(x => { ell(ctx, x, r * 0.3, r * 0.17, r * 0.1); ctx.fill(); }); }
  // mouth
  const mx = front ? 0 : r * 0.5, my = r * 0.5, mw = r * 0.26;
  ctx.save(); ctx.translate(mx, my); ctx.strokeStyle = ink2; ctx.lineWidth = 9; ctx.lineCap = 'round';
  const m = emo.mouth;
  if (open > 0.05 || m === 'shout' || m === 'o') {
    const oh = m === 'shout' ? 0.95 : m === 'o' ? 0.7 : open, w = m === 'o' ? mw * 0.55 : mw * (0.8 + oh * 0.3);
    ctx.beginPath(); if (m === 'smile' || (emo.curve || 0) > 0.25) { ctx.moveTo(-w, -4); ctx.quadraticCurveTo(0, -2, w, -4); ctx.quadraticCurveTo(w * 0.8, 10 + 34 * oh, 0, 12 + 36 * oh); ctx.quadraticCurveTo(-w * 0.8, 10 + 34 * oh, -w, -4); }
    else ctx.ellipse(0, 6 + 8 * oh, w, 6 + 22 * oh, 0, 0, Math.PI * 2);
    paint(ctx, '#5A2228', {w: 6, c: ink2});
    ctx.save(); ctx.clip(); ell(ctx, 0, 16 + 30 * oh, w * 0.7, 12 + 6 * oh); ctx.fillStyle = '#D9606A'; ctx.fill(); if (m === 'shout') { ctx.fillStyle = '#FFF'; ctx.fillRect(-w, -6, 2 * w, 10); } ctx.restore();
  } else if (m === 'smile') { ctx.beginPath(); ctx.moveTo(-mw, -4); ctx.quadraticCurveTo(0, mw * 0.9, mw, -4); ctx.stroke(); }
  else if (m === 'frown') { ctx.beginPath(); ctx.moveTo(-mw * 0.8, 10); ctx.quadraticCurveTo(0, -mw * 0.45, mw * 0.8, 10); ctx.stroke(); }
  else if (m === 'wavy') { ctx.beginPath(); ctx.moveTo(-mw * 0.8, 4); for (let i = 1; i <= 4; i++) ctx.lineTo(-mw * 0.8 + i * mw * 0.4, i % 2 ? -6 : 6); ctx.stroke(); }
  else if (m === 'side') { ctx.beginPath(); ctx.moveTo(-mw * 0.5, 4); ctx.quadraticCurveTo(mw * 0.3, 2, mw * 0.8, -8); ctx.stroke(); }
  else if (m === 'zombie') { ctx.beginPath(); ctx.moveTo(-mw * 0.8, 0); ctx.lineTo(mw * 0.8, 6); ctx.stroke(); }
  else { const cu = emo.curve || 0; ctx.beginPath(); ctx.moveTo(-mw * 0.75, 0); ctx.quadraticCurveTo(0, cu * mw, mw * 0.75, 0); ctx.stroke(); }
  ctx.restore();
  if (L.stubble || L.beard === 'stubble') { ctx.fillStyle = rgba(shade(L.hair, -0.1), 0.32); const R = rng(hash(st.id + 'st'));
    for (let i = 0; i < 16; i++) { const a = (front ? 0.2 : 0.05) * Math.PI + R() * (front ? 0.6 : 0.42) * Math.PI, rr2 = r * (0.7 + R() * 0.2); ell(ctx, Math.cos(a) * rr2 + (front ? 0 : r * 0.05), Math.sin(a) * rr2, 3.2, 3.2); ctx.fill(); } }
  if (L.beard === 'mustache') { ctx.fillStyle = L.hair; ell(ctx, mx - 22, my - 22, 34, 14, 0.2); ctx.fill(); ell(ctx, mx + 22, my - 22, 34, 14, -0.2); ctx.fill(); }
  if (L.beard === 'full') { ctx.beginPath(); ctx.moveTo(-r * 0.85, r * 0.1); ctx.quadraticCurveTo(-r * 0.6, r * 1.25, 0, r * 1.15); ctx.quadraticCurveTo(r * 0.75, r * 1.2, r * 0.95, r * 0.1); ctx.quadraticCurveTo(r * 0.5, r * 0.55, mx, my - 18); ctx.quadraticCurveTo(-r * 0.4, r * 0.55, -r * 0.85, r * 0.1); paint(ctx, L.hair, o(L.hair)); }
}

function drawHair(ctx, L, r, view, o) {
  const hc = L.hair, hs = L.hair_style || 'short'; if (hs === 'bald' || L.hat === 'hood' || L.hat === 'ushanka' || L.hat === 'helmet' && hs === 'short') return;
  ctx.save(); ell(ctx, 0, 0, r + 2, r + 2); ctx.restore();
  ctx.beginPath();
  if (hs === 'bald_sides') { if (view !== 'front') { ctx.moveTo(-r * 0.95, -r * 0.05); ctx.quadraticCurveTo(-r * 1.0, r * 0.35, -r * 0.55, r * 0.5); ctx.quadraticCurveTo(-r * 0.6, r * 0.1, -r * 0.4, -r * 0.2); ctx.closePath(); }
    else { [-1, 1].forEach(s => { ctx.moveTo(s * r * 0.98, -r * 0.1); ctx.quadraticCurveTo(s * r * 1.04, r * 0.3, s * r * 0.8, r * 0.45); ctx.quadraticCurveTo(s * r * 0.8, r * 0.05, s * r * 0.7, -r * 0.3); ctx.closePath(); }); }
    paint(ctx, hc, o(hc)); return; }
  if (view === 'back') { ctx.arc(0, 0, r + 4, Math.PI * 0.9, Math.PI * 2.1); ctx.quadraticCurveTo(r * 0.6, r * 0.5, 0, r * 0.62); ctx.quadraticCurveTo(-r * 0.6, r * 0.5, -r - 4, r * 0.1); paint(ctx, hc, o(hc)); return; }
  if (view === 'front') { ctx.moveTo(-r * 1.02, r * 0.05); ctx.quadraticCurveTo(-r * 1.08, -r * 1.12, 0, -r * 1.06); ctx.quadraticCurveTo(r * 1.08, -r * 1.12, r * 1.02, r * 0.05);
    ctx.quadraticCurveTo(r * 0.88, -r * 0.45, r * 0.35, -r * 0.5); ctx.quadraticCurveTo(0, -r * 0.3, -r * 0.3, -r * 0.55); ctx.quadraticCurveTo(-r * 0.85, -r * 0.45, -r * 1.02, r * 0.05); }
  else { ctx.moveTo(-r * 1.02, r * 0.25); ctx.quadraticCurveTo(-r * 1.15, -r * 1.05, r * 0.15, -r * 1.06); ctx.quadraticCurveTo(r * 0.95, -r * 1.02, r * 0.98, -r * 0.3);
    ctx.quadraticCurveTo(r * 0.6, -r * 0.62, r * 0.2, -r * 0.5); ctx.quadraticCurveTo(-r * 0.15, -r * 0.2, -r * 0.35, -r * 0.05); ctx.quadraticCurveTo(-r * 0.6, r * 0.2, -r * 1.02, r * 0.25); }
  ctx.closePath(); paint(ctx, hc, o(hc));
  if (hs === 'messy') { for (let i = 0; i < 5; i++) { const a = Math.PI * (1.12 + i * 0.17), c0 = [Math.cos(a) * r * 0.9, Math.sin(a) * r * 0.9];
      ctx.beginPath(); ctx.moveTo(Math.cos(a - 0.2) * r * 0.85, Math.sin(a - 0.2) * r * 0.85); ctx.lineTo(Math.cos(a + 0.05) * r * 1.22, Math.sin(a + 0.05) * r * 1.22);
      ctx.lineTo(Math.cos(a + 0.22) * r * 0.85, Math.sin(a + 0.22) * r * 0.85); ctx.closePath(); paint(ctx, hc, o(hc)); } }
  if (hs === 'curly') { for (let i = 0; i < 7; i++) { const a = Math.PI * (1.0 + i * 0.165); ell(ctx, Math.cos(a) * r * 0.97, Math.sin(a) * r * 0.97, r * 0.2, r * 0.2); paint(ctx, hc, o(hc)); } }
  if (hs === 'bun' && L.hat !== 'scarf') { ell(ctx, view === 'front' ? 0 : -r * 0.35, -r * 1.05, r * 0.34, r * 0.3); paint(ctx, hc, o(hc)); }
  if (hs === 'ponytail' && view === 'front') { ell(ctx, r * 0.95, r * 0.35, r * 0.18, r * 0.42); paint(ctx, hc, o(hc)); }
  if (hs === 'pigtails') { const bow = L.bow || '#FF5FA2'; (view === 'front' ? [-1, 1] : view === 'back' ? [-1, 1] : [-1]).forEach(sd => { const bx = sd * r * 0.96, by = -r * 0.22;
      ctx.beginPath(); ctx.moveTo(bx, by - r * 0.14); ctx.quadraticCurveTo(bx + sd * r * 0.62, by + r * 0.05, bx + sd * r * 0.46, by + r * 0.9); ctx.quadraticCurveTo(bx + sd * r * 0.14, by + r * 0.42, bx - sd * r * 0.04, by + r * 0.16);
      ctx.closePath(); paint(ctx, hc, o(hc)); [-1, 1].forEach(q => { ell(ctx, bx + sd * r * 0.06 + q * r * 0.13, by - r * 0.02, r * 0.14, r * 0.09, q * 0.5); paint(ctx, bow, o(bow)); }); }); }
  ctx.fillStyle = rgba('#FFFFFF', 0.12); ell(ctx, view === 'front' ? -r * 0.35 : r * 0.05, -r * 0.82, r * 0.35, r * 0.1, -0.2); ctx.fill();
}

function drawHat(ctx, L, r, view, o, t) {
  const h = L.hat, c = L.hat_color || '#2E4756'; if (!h || h === 'none' || h === 'hood') return;
  const side = view === 'side';
  ctx.beginPath();
  if (h === 'cap') { ctx.moveTo(-r * 1.0, -r * 0.18); ctx.quadraticCurveTo(-r * 1.02, -r * 1.12, 0, -r * 1.1); ctx.quadraticCurveTo(r * 1.02, -r * 1.1, r * 1.0, -r * 0.2); ctx.closePath(); paint(ctx, c, o(c));
    ctx.beginPath(); if (side) { ctx.moveTo(r * 0.55, -r * 0.3); ctx.quadraticCurveTo(r * 1.35, -r * 0.42, r * 1.55, -r * 0.18); ctx.quadraticCurveTo(r * 1.2, -r * 0.08, r * 0.6, -r * 0.14); ctx.closePath(); }
    else if (view === 'front') ctx.ellipse(0, -r * 0.2, r * 1.05, r * 0.2, 0, Math.PI, Math.PI * 2.0);
    if (view !== 'back') paint(ctx, shade(c, -0.15), o(c));
    ell(ctx, 0, -r * 1.08, r * 0.1, r * 0.06); ctx.fillStyle = shade(c, -0.25); ctx.fill(); }
  else if (h === 'beanie') { ctx.moveTo(-r * 1.04, -r * 0.2); ctx.quadraticCurveTo(-r * 1.0, -r * 1.25, 0, -r * 1.22); ctx.quadraticCurveTo(r * 1.0, -r * 1.25, r * 1.04, -r * 0.2); ctx.closePath(); paint(ctx, c, o(c));
    rr(ctx, -r * 1.08, -r * 0.42, r * 2.16, r * 0.32, r * 0.14); paint(ctx, shade(c, -0.12), o(c)); }
  else if (h === 'ushanka') { ctx.moveTo(-r * 1.12, -r * 0.15); ctx.quadraticCurveTo(-r * 1.1, -r * 1.3, 0, -r * 1.28); ctx.quadraticCurveTo(r * 1.1, -r * 1.3, r * 1.12, -r * 0.15); ctx.closePath(); paint(ctx, c, o(c));
    rr(ctx, -r * 1.16, -r * 0.5, r * 2.32, r * 0.4, r * 0.18); paint(ctx, shade(c, 0.12), o(c));
    ctx.fillStyle = rgba('#000', 0.12); for (let i = 0; i < 7; i++) { ell(ctx, -r * 0.9 + i * r * 0.3, -r * 0.3, r * 0.09, r * 0.05); ctx.fill(); } }
  else if (h === 'helmet') { ctx.moveTo(-r * 1.06, -r * 0.12); ctx.quadraticCurveTo(-r * 1.04, -r * 1.24, 0, -r * 1.22); ctx.quadraticCurveTo(r * 1.04, -r * 1.24, r * 1.06, -r * 0.12); ctx.closePath(); paint(ctx, c, o(c));
    rr(ctx, -r * 1.2, -r * 0.24, r * 2.4 + (side ? r * 0.2 : 0), r * 0.18, r * 0.08); paint(ctx, shade(c, -0.12), o(c));
    ctx.fillStyle = rgba('#FFFFFF', 0.25); ell(ctx, -r * 0.35, -r * 0.85, r * 0.3, r * 0.12, -0.4); ctx.fill(); }
  else if (h === 'scarf') { const fx = side ? r * 0.25 : 0;
    ctx.moveTo(-r * 1.12, r * 0.6); ctx.quadraticCurveTo(-r * 1.3, -r * 1.25, fx, -r * 1.2); ctx.quadraticCurveTo(r * 1.25, -r * 1.2, r * (side ? 0.9 : 1.12), r * (side ? -0.15 : 0.6));
    ctx.quadraticCurveTo(r * (side ? 0.55 : 0.85), -r * 0.62, fx, -r * 0.6); ctx.quadraticCurveTo(-r * (side ? 0.55 : 0.85), -r * 0.6, -r * (side ? 0.75 : 0.88), r * 0.6); ctx.closePath(); paint(ctx, c, o(c));
    ctx.fillStyle = rgba('#FFF', 0.4); for (let i = 0; i < 9; i++) { ell(ctx, -r * 0.8 + (i % 5) * r * 0.4 + (i > 4 ? r * 0.2 : 0), -r * (i > 4 ? 0.7 : 0.95), 7, 7); ctx.fill(); }
    if (!side) { ell(ctx, 0, r * 1.02, r * 0.16, r * 0.12); paint(ctx, shade(c, -0.1), o(c)); } }
}

// ------------------------------------------------------------------ dog (border collie) and cat: compact cartoon proportions
// local units: 1000 = height to the top of the head, feet at y=0, facing right
function drawDog(env, st) {
  const ctx = env.ctx, L = st.look, t = st.t, sty = env.style, o = c => ink(sty, c);
  const cat = st.kind === 'cat', coat = L.coat || (cat ? '#E39B4A' : '#1D2026'), wh = L.white || '#F2EFE8', dk = c => shade(c, -0.28);
  const pn = st.pname, sit = pn === 'sit', lie = pn === 'lie' || pn === 'sleep';
  const happy = st.emo === 'happy', scared = st.emo === 'scared';
  const br = Math.sin(t * Math.PI * 2 / (st.moving || happy ? 0.75 : 2.8)), bl = blink(st.id + 'd', t);
  const run = st.gait === 'run' || st.speed > st.h * 2.2, m = sit || lie ? 0 : st.moving;
  const stride = (run ? 1000 : 640) * st.h / 1000, ph = st.dist / Math.max(1, stride) * Math.PI * 2;
  const bob = m ? Math.abs(Math.sin(ph)) * (run ? 40 : 14) : 0;
  ctx.save(); ctx.translate(st.x, st.y); const s = st.h / 1000; ctx.scale(s * st.dir, s);
  T.h.shadowBlob(ctx, 0, 0, lie ? 430 : 360, 0.26);
  const lw = cat ? 66 : 84;
  const leg = (x0, y0, a1, a2, l1, l2, col, sock) => {
    const k = [x0 + Math.sin(a1) * l1, y0 + Math.cos(a1) * l1], aa = a1 + a2, f = [k[0] + Math.sin(aa) * l2, k[1] + Math.cos(aa) * l2];
    hose(ctx, [[x0, y0], k, [f[0], f[1] - 20]], lw, col, o(coat));
    ell(ctx, f[0] + 16, f[1] - 22, lw * 0.62, lw * 0.4); paint(ctx, sock && !cat ? wh : col, o(sock && !cat ? wh : coat));
  };
  const sw = (p) => m ? Math.sin(ph + p) * (run ? 0.75 : 0.42) : 0, lf = (p) => m ? Math.max(0, Math.cos(ph + p)) * (run ? 1.0 : 0.6) : 0;
  ctx.translate(0, -bob);
  // body pose
  const B = sit ? {x: -70, y: -390, rot: -1.05} : lie ? {x: -20, y: -170, rot: 0.0} : {x: -40, y: -440, rot: 0};
  const H = sit ? {x: 120, y: -800} : lie ? {x: 290, y: -400} : {x: 255, y: -730 + (scared ? 50 : 0) + (m ? Math.sin(ph * 2) * 10 : 0)};
  // tail
  const wagF = happy || m ? 13 : 4.5, wagA = scared ? 0.04 : happy ? 0.5 : 0.28, wag = Math.sin(t * wagF) * wagA;
  ctx.save();
  if (sit) ctx.translate(-180, -60); else if (lie) ctx.translate(-300, -190); else ctx.translate(-310, -500);
  ctx.rotate(wag + (scared ? 1.2 : 0) + (sit ? 1.1 : lie ? 0.9 : 0));
  ctx.beginPath(); ctx.moveTo(0, 0);
  if (cat) ctx.bezierCurveTo(-140, -20, -170, -220, -90, -330); else ctx.bezierCurveTo(-110, -20, -190, -120, -200, -260);
  ctx.lineCap = 'round'; const tw = cat ? 50 : 86;
  if (o(coat)) { ctx.lineWidth = tw + o(coat).w * 2; ctx.strokeStyle = o(coat).c; ctx.stroke(); }
  ctx.lineWidth = tw; ctx.strokeStyle = coat; ctx.stroke();
  if (!cat) { ell(ctx, -200, -262, 50, 54, 0.2); paint(ctx, wh, o(wh)); }
  ctx.restore();
  // far legs
  if (sit) { leg(140, -330, 0.05, -0.05, 160, 170, dk(coat), true); }
  else if (lie) { leg(180, -150, 1.5, 0.0, 120, 130, dk(coat), true); }
  else { leg(150, -330, sw(0), -lf(0) * 0.7, 160, 170, dk(coat), true); leg(-230, -340, -sw(0) * 0.9, lf(Math.PI) * 0.8, 160, 180, dk(coat), true); }
  // body (bean)
  ctx.save(); ctx.translate(B.x, B.y); ctx.rotate(B.rot); ctx.scale(1, 1 + br * 0.025);
  ctx.beginPath(); ctx.moveTo(-280, -40);
  ctx.bezierCurveTo(-300, -170, -120, -175, 40, -165); ctx.bezierCurveTo(200, -160, 300, -120, 300, 0);
  ctx.bezierCurveTo(300, 120, 190, 150, 60, 140); ctx.bezierCurveTo(-60, 130, -150, 150, -230, 120); ctx.bezierCurveTo(-300, 90, -275, 30, -280, -40);
  ctx.closePath(); paint(ctx, coat, o(coat));
  ctx.save(); ctx.clip();
  if (!cat) { ell(ctx, 250, 40, 120, 150, 0.2); ctx.fillStyle = wh; ctx.fill(); }
  else { ctx.strokeStyle = dk(coat); ctx.lineWidth = 22; for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(-200 + i * 105, -175); ctx.quadraticCurveTo(-180 + i * 105, -80, -215 + i * 105, 0); ctx.stroke(); } }
  ctx.fillStyle = rgba(shade(coat, -0.6), 0.22); ell(ctx, 0, 150, 340, 90); ctx.fill();
  ctx.strokeStyle = rgba(cat ? '#FFE6C0' : '#A9BCD2', 0.4); ctx.lineWidth = 18; ctx.beginPath(); ctx.moveTo(-250, -120); ctx.bezierCurveTo(-120, -168, 100, -165, 230, -120); ctx.stroke();
  ctx.restore(); ctx.restore();
  // near legs + haunch
  if (sit) { ell(ctx, -150, -150, 150, 140, -0.3); paint(ctx, coat, o(coat)); ell(ctx, 0, -30, 80, 38); paint(ctx, cat ? coat : wh, o(wh));
    leg(190, -330, -0.02, 0.0, 160, 170, coat, true); }
  else if (lie) { ell(ctx, -200, -110, 140, 100); paint(ctx, coat, o(coat)); leg(240, -150, 1.52, 0.0, 120, 140, coat, true); }
  else { leg(200, -330, sw(Math.PI), -lf(Math.PI) * 0.7, 160, 170, coat, true);
    ell(ctx, -200, -420, 120, 115, 0.2); paint(ctx, coat, null);
    leg(-190, -340, -sw(Math.PI) * 0.9, lf(0) * 0.8, 160, 180, coat, true); }
  // head
  const bark = Math.max(talkOpen(t, st.a), pn === 'bark' ? Math.max(0, Math.sin(env.lt * 13)) : 0);
  ctx.save(); ctx.translate(H.x, H.y); ctx.rotate((st.emo === 'curious' ? -0.3 : 0) + Math.sin(t * 1.1) * 0.03 + (scared ? 0.12 : 0) + (lie ? 0.05 : 0));
  // neck
  ctx.beginPath(); ctx.moveTo(-150, 60); ctx.quadraticCurveTo(-170, 230, -150, 300); ctx.lineTo(90, 270); ctx.quadraticCurveTo(110, 150, 80, 60); ctx.closePath(); paint(ctx, coat, o(coat));
  if (!cat) { ctx.beginPath(); ctx.moveTo(10, 80); ctx.quadraticCurveTo(110, 170, 70, 290); ctx.lineTo(-60, 290); ctx.quadraticCurveTo(-20, 170, 10, 80); ctx.fillStyle = wh; ctx.fill(); }
  const earLift = scared ? -0.55 : happy ? 0.12 : 0;
  const ear = (ex, farE) => { ctx.save(); ctx.translate(ex, -120); ctx.rotate(-0.12 + earLift * (farE ? 0.8 : 1) - (farE ? 0.15 : 0));
    ctx.beginPath(); ctx.moveTo(-62, 30); ctx.quadraticCurveTo(-68, -80, cat ? -14 : -24, cat ? -170 : -180);
    if (!cat) ctx.quadraticCurveTo(26, -168, 52, -128);
    ctx.quadraticCurveTo(64, -60, 62, 30); ctx.closePath(); paint(ctx, farE ? dk(coat) : coat, o(coat));
    if (!farE) { ctx.beginPath(); ctx.moveTo(-34, 14); ctx.quadraticCurveTo(-34, -80, -16, -130); ctx.quadraticCurveTo(24, -80, 34, 14); ctx.fillStyle = cat ? '#F0A7A0' : '#5A4448'; ctx.fill(); }
    ctx.restore(); };
  ear(-95, true);
  ell(ctx, 0, 0, 190, 175); paint(ctx, coat, o(coat));
  ctx.save(); ell(ctx, 0, 0, 190, 175); ctx.clip(); ctx.fillStyle = rgba(cat ? '#FFE6C0' : '#A9BCD2', 0.35); ell(ctx, -60, -120, 120, 50, -0.4); ctx.fill(); ctx.restore();
  if (!cat) { ctx.beginPath(); ctx.moveTo(10, -175); ctx.quadraticCurveTo(38, -80, 62, 20); ctx.lineTo(-20, 30); ctx.quadraticCurveTo(-16, -80, 10, -175); ctx.fillStyle = wh; ctx.fill(); }
  ear(35, false);
  // muzzle + jaw
  const jaw = Math.max(bark * 0.9, happy && !cat ? 0.38 + br * 0.06 : 0);
  ctx.save(); ctx.translate(120, 55);
  if (jaw > 0.04) { ctx.save(); ctx.translate(-20, 30); ctx.rotate(jaw * 0.5); ctx.beginPath(); ctx.ellipse(70, 10, 85, 34, 0, 0, Math.PI * 2); paint(ctx, cat ? shade(coat, 0.25) : wh, o(wh));
    if (!cat && happy) { ell(ctx, 80, 44, 34, 50); paint(ctx, '#E5737D', {w: 6, c: '#A3434C'}); } ctx.restore();
    ell(ctx, 50, 32, 70, 22 + jaw * 30); paint(ctx, '#4A2226'); }
  ell(ctx, 40, 0, cat ? 80 : 115, cat ? 58 : 72); paint(ctx, cat ? shade(coat, 0.3) : wh, o(wh));
  ell(ctx, cat ? 100 : 140, -28, cat ? 22 : 34, cat ? 16 : 25); paint(ctx, cat ? '#D98080' : '#16171A');
  ell(ctx, cat ? 95 : 130, -36, 9, 6); ctx.fillStyle = rgba('#FFFFFF', 0.6); ctx.fill();
  ctx.strokeStyle = '#2A1A1C'; ctx.lineWidth = 7; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(cat ? 100 : 138, -6); ctx.lineTo(cat ? 100 : 136, 22); ctx.stroke();
  if (cat) { ctx.strokeStyle = rgba('#FFFFFF', 0.85); ctx.lineWidth = 4; [-14, 8].forEach(dy => { ctx.beginPath(); ctx.moveTo(90, 8 + dy); ctx.lineTo(230, dy * 2.4); ctx.stroke(); }); }
  ctx.restore();
  // eye + brow tuft
  const ex = 70, ey = -40;
  if (bl > 0.5 || st.emo === 'sleep') { ctx.strokeStyle = '#0D0D0F'; ctx.lineWidth = 10; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(ex - 26, ey); ctx.quadraticCurveTo(ex, ey + 16, ex + 26, ey); ctx.stroke(); }
  else { ell(ctx, ex, ey, cat ? 30 : 29, cat ? 34 : 32); paint(ctx, cat ? (L.eye || '#3B7A3A') : '#2B1B10');
    if (cat) { ell(ctx, ex, ey, 8, 26); ctx.fillStyle = '#111'; ctx.fill(); }
    ell(ctx, ex - 10, ey - 12, 10, 10); ctx.fillStyle = '#FFF'; ctx.fill(); ell(ctx, ex + 8, ey + 10, 4, 4); ctx.fill(); }
  if (!cat) { ctx.fillStyle = shade(coat, 0.4); ell(ctx, ex + 2, ey - 50, 18, 10, scared ? -0.45 : 0.15); ctx.fill(); }
  ctx.restore();
  ctx.restore();
}

// ------------------------------------------------------------------ public
function drawRaw(env, a) {
  const st = actorState(env, a);
  const sc = env.sc; if (sc.speaker && (sc.speaker === a.id) && sc._words) st.a._talk = [sc.t0, sc.t1]; else st.a._talk = a.talk ? [sc.t0, sc.t1] : null;
  const ctx = env.ctx; ctx.save();
  if (st.kind === 'dog' || st.kind === 'cat') drawDog(env, st); else drawHuman(env, st);
  ctx.restore();
  return st;
}
// Silhouette / dim / blur: the figure is drawn ONCE into a small buffer and tinted there. (ctx.filter on every path of a
// figure costs seconds per frame on a CPU canvas; one composite op on a buffer costs ~1 ms.)
const FXB = {};
function fxBuffer(w, h) { let c = FXB.c; if (!c) c = FXB.c = document.createElement('canvas');
  if (c.width < w || c.height < h) { c.width = Math.max(c.width, w); c.height = Math.max(c.height, h); }
  const x = c.getContext('2d', {willReadFrequently: true}); x.setTransform(1, 0, 0, 1, 0, 0); x.globalCompositeOperation = 'source-over'; x.clearRect(0, 0, w + 2, h + 2); return [c, x]; }
function drawFx(env, a, o) {
  const {ctx} = env, st = actorState(env, a), m = ctx.getTransform(), lying = /^(lie|sleep)$/.test(st.pname);
  const x0 = st.x - st.h * (lying ? 1.3 : 0.95), x1 = st.x + st.h * (lying ? 1.3 : 0.95), y0 = st.y - st.h * 1.35, y1 = st.y + st.h * 0.15;
  const p = [[x0, y0], [x1, y0], [x0, y1], [x1, y1]].map(([x, y]) => m.transformPoint(new DOMPoint(x, y)));
  const pad = 6 + (o.blur || 0) * 2, sx = Math.floor(Math.min(...p.map(q => q.x))) - pad, sy = Math.floor(Math.min(...p.map(q => q.y))) - pad;
  const w = Math.ceil(Math.max(...p.map(q => q.x))) - sx + pad, h = Math.ceil(Math.max(...p.map(q => q.y))) - sy + pad;
  if (w <= 0 || h <= 0 || w > 5000 || h > 5000) return st;
  const [c, x] = fxBuffer(w, h); x.setTransform(m.a, m.b, m.c, m.d, m.e - sx, m.f - sy);
  const keep = T.addLight; if (o.sil || o.dim != null) T.addLight = () => {};
  let r; try { r = drawRaw(Object.assign({}, env, {ctx: x}), a); } finally { T.addLight = keep; }
  x.setTransform(1, 0, 0, 1, 0, 0);
  if (o.sil) { x.globalCompositeOperation = 'source-in'; x.fillStyle = o.sil; x.fillRect(0, 0, w, h); }
  else if (o.dim != null && o.dim < 1) { x.globalCompositeOperation = 'source-atop'; x.fillStyle = rgba('#080A10', 1 - o.dim); x.fillRect(0, 0, w, h); }
  x.globalCompositeOperation = 'source-over';
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); if (o.blur) ctx.filter = `blur(${o.blur}px)`; ctx.drawImage(c, 0, 0, w, h, sx, sy, w, h); ctx.restore();
  return r;
}
T.drawActor = function (env, a, i, dim) {
  if (a.silhouette || a.blur || (dim != null && dim < 0.99)) return drawFx(env, a, {sil: a.silhouette ? (typeof a.silhouette === 'string' ? a.silhouette : '#15181F') : null, blur: a.blur, dim});
  return drawRaw(env, a);
};
T.actorState = actorState;
// ------------------------------------------------------------------ shot framing: wide | medium | close | {type, on, at, z}
// Computes a static camera (normalised x, y + zoom) that frames the actors like a cartoon editor would:
// medium = whole figure ~half the frame, head top at 0.34 H; close = head and shoulders, face centre at 0.44 H.
// Frame bands (portrait): 0.09-0.30 HUD (clock, plates, stamps) | 0.33-0.60 faces + action | 0.61-0.70 captions | 0.72+ legs/floor
// (under the platform UI). Python picks the shot and moves HUD out of the face band.
const HEADF = {lie: 0.13, sleep: 0.13, sit_floor: 0.5, hug_knees: 0.46, crouch: 0.62, kneel: 0.66, sit: 0.62};
T.shotCam = function (sc, W, H, ground) {
  const o0 = sc.shot; if (!o0) return null;
  const o = typeof o0 === 'string' ? {type: o0} : o0, type = o.type || 'medium', portrait = H >= W;
  if (type === 'wide') {          // whole set, but the ground line moves up to 0.74 H so faces clear the caption band
    if (!portrait || !(sc.actors || []).length || o.lift === false) return null;
    const lift = o.lift != null ? o.lift : ground / H - 0.74; return lift > 0.005 ? {x: 0.5, y: 0.5 + lift, z: 1} : null; }
  const env = {W, H, lt: 0, t: sc.t0 || 0, sc, ground, portrait};
  const acts = (sc.actors || []).filter(a => !o.on || a.id === o.on);
  const info = acts.map(a => { const st = actorState(env, a), hf = HEADF[st.pname] || (st.kind === 'human' ? 0.86 : 0.7);
    const ly = st.kind === 'human' && /^(lie|sleep)$/.test(st.pname);
    return {x: st.x, hx: ly ? st.x - 0.4 * st.h * st.dir : st.x, dir: st.dir, y: st.y, h: st.h, head: st.y - hf * st.h, top: st.y - (hf + (ly ? 0.2 : 0.12)) * st.h}; });
  let fx, fy, z, sy;
  if (o.at) { fx = o.at[0] * W; z = o.z || (type === 'close' ? 2.2 : 1.5);       // at [x, null] = a thing on the floor: floor line just above the captions
    if (o.at[1] == null) { fy = ground; sy = 0.6; } else { fy = o.at[1] * H; sy = 0.42; } }
  else if (!info.length) return null;
  else if (type === 'close') { const f = info[0]; fx = f.hx; fy = f.head; sy = 0.44; z = o.z || Math.min(3.2, (portrait ? 0.66 : 0.9) * H / f.h); }
  else { const xs = info.map(i => i.x).concat((sc.props || []).filter(p => p.id !== 'crowd' && p.at != null && !o.on)
      .map(p => (Array.isArray(p.at) ? p.at[0] : p.at) * W)), span = Math.max(...xs) - Math.min(...xs), hmax = Math.max(...info.map(i => i.h));
    fx = (Math.min(...xs) + Math.max(...xs)) / 2; fy = Math.min(...info.map(i => i.top)); sy = 0.34;
    z = o.z || Math.min(2.4, (portrait ? 0.47 : 0.62) * H / hmax, W / (span + 0.3 * W)); }
  z = clamp(z, 1, 3.2); if (z < 1.04) return null;
  let cx = fx, cy = fy - (sy - 0.5) * H / z;
  if (!portrait && !o.at && info.length === 1 && o.center !== true) {   // landscape: rule of thirds, look room in front of the face
    const third = type === 'close' ? (info[0].dir > 0 ? 0.38 : 0.62) : (fx < W / 2 ? 0.36 : 0.64); cx = fx + (0.5 - third) * W / z; }
  cx = clamp(cx, W / (2 * z), W - W / (2 * z)); cy = clamp(cy, H / (2 * z), H - H / (2 * z) + 0.12 * H);   // floors run below the frame
  return {x: cx / W, y: cy / H, z};
};
T.drawCrowd = function (env, p) {                   // a crowd of small figures, back to front
  const R = rng(hash(p.seed || 'crowd')), n = p.n || 10, ar = p.area || [0.1, 0.62, 0.9, 0.74], items = [];
  for (let i = 0; i < n; i++) items.push({x: lerp(ar[0], ar[2], R()), y: lerp(ar[1], ar[3], R()), ph: R() * 10, look: R() < 0.5 ? (p.look || 'zombie') : (p.look2 || p.look || 'zombie2')});
  items.sort((a, b) => a.y - b.y).forEach((c, i) => {
    const depthK = (c.y - ar[1]) / Math.max(0.01, ar[3] - ar[1]);
    const a = {id: 'crowd' + i, look: c.look, at: [c.x + Math.sin(env.lt * 0.6 + c.ph) * 0.004 * (p.move || 1), c.y], h: (p.h || 0.12) * (0.75 + 0.35 * depthK),
      face: p.face || (c.x < 0.5 ? 'right' : 'left'), silhouette: p.silhouette, pose: p.pose, blur: p.blur};
    if (p.walk) { a.to = [c.x + p.walk * (0.6 + 0.4 * depthK), c.y]; a.move = [0, env.sc.t1 - env.sc.t0]; }
    T.drawActor(env, a, i, p.silhouette == null && p.dim !== false ? 0.55 + 0.45 * depthK : null);
  });
};
})();
