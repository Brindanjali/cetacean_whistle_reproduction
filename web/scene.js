/**
 * The film's research beats as one WebGL 2 scene, drawn only from real records: web/film/, written by
 * `python whistlecode/whistlecode.py export-film` (web/PLAN.md, WEB-5). As in the rest of the film, every frame is a pure
 * function of the scroll position (timings: shots.js VIZ) and one camera moves through all of it: nothing cuts.
 *
 *   01 Listen  one encounter-191 training image, cropped around its whistle: its pixel grid as a floor of fine dots (time
 *              across, pitch into the distance), the contour it was made from traced on that floor, and, at every frame
 *              of the image, a hairline rising to the image's level there; along their tops, the contour as one amber line.
 *              The camera tips over until the hairlines are points and the amber line lies on its trace: the shape
 *   02 Learn   the line shrinks into a point: that same whistle's place among all 63,490 whistles the model learned from
 *              (latent means on three principal axes). The others appear around it, coloured by mixture component
 *   03 Speak   the codebook's 16 families light up and unfold into their mean shapes; at the four pitches of a slot, a
 *              lattice of the 64 whistles a message is written with. "Hear it" plays one of them, cut from a real send
 *   04 Hide    the lattice dissolves into a river of time: every sound of one real send of the example message (data
 *              whistles, cover whistles as played, recorded clicks), all alike
 *   05 Hear    the key's whistles rise out of the river; the one the receiver misread in the sea shows, then is repaired;
 *              the message whistles become the letters (the receiver's own record of that send)
 *
 * The look (web/PLAN-SCENE.md, D-027): fine lines over the page's own blue water, white with one amber accent (the whistle
 * the film follows); things fade into the water with distance. Listen is redrawn that way; Learn and Speak keep their WEB-5
 * design, made bolder (crisp points drawn over the water; solid, thicker strokes); Hide and Hear are as in WEB-5.
 *
 * The 3D is on #gl (gl.js); labels, glows and letters on #sig (2D). Camera moves and colours are style: every shape, time
 * and point comes from film/film.json and film/learn.bin.
 */
(() => {
  const K = window.GLKit, M = K.Mat;
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const sm = (a, b, v) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
  const smoother = t => t * t * t * (t * (6 * t - 15) + 10);
  const lerp = (a, b, t) => a + (b - a) * t;
  const lerp3 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
  const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const ph = (w, p) => sm(w[0], w[1], p);
  const rgb = s => s.split(',').map(v => +v / 255);
  const S_INK = '234,246,251', S_PALE = '169,207,224', S_SUN = '242,208,150', S_CORAL = '240,150,128';
  const INK = rgb(S_INK), PALE = rgb(S_PALE), SUN = rgb(S_SUN), CORAL = rgb(S_CORAL);
  const HUES = ['143,212,232', '172,190,255', '124,222,200', '204,184,244', '169,207,224'].map(rgb);
  const hash = i => { let h = Math.imul(i ^ 0x9e3779b9, 0x85ebca6b); h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35); h ^= h >>> 16; return (h >>> 0) / 4294967296; };

  /* the world's layout, in scene units */
  const CLOUD = 1.35;          // Learn: the cloud's half-width on its widest axis
  const CROP_T = 22;           // Listen: image columns kept either side of the whistle
  const CROP_F = 26;           //         image rows kept either side of its centre
  const HMAX = 0.55;           //         a hairline's height at the image's full level
  const DOT = 2;               //         one floor dot per DOT x DOT image pixels
  const GAP = 0.22, TS = 0.42; // Speak: column spacing; units per second of a shape
  const HS = 1.3;              //         height spanned by the four pitches
  const KT = 0.13;             // Hide: units per second along the river
  const RIVER_HZ = [3000, 17000], RIVER_H = 1.5;

  const POINT_VS = `#version 300 es
layout(location = 0) in vec3 aP;
layout(location = 1) in float aK;
layout(location = 2) in float aSel;
uniform mat4 uM; uniform vec3 uO, uFocus; uniform vec3 uHue[5];
uniform float uScale, uPx, uReveal, uRevealR, uPick, uDim, uFollow, uA, uBase;
out vec4 vCol; out float vSize;
void main() {
  vec3 w = aP * uScale + uO;
  gl_Position = uM * vec4(w, 1.0);
  float shown = 1.0 - smoothstep(uReveal * uRevealR - 0.3, uReveal * uRevealR, distance(w, uFocus));
  vec3 c = uHue[int(mod(aK * 7.0 + floor(aK / 5.0), 5.0))];
  float a = uBase * shown * exp(-max(0.0, gl_Position.w - 3.4) * 0.45), pick = 0.0;
  if (aSel < 16.5) {
    pick = uPick;
    vec3 hi = abs(aSel - uFollow) < 0.5 ? vec3(0.949, 0.816, 0.588) : vec3(0.918, 0.965, 0.984);
    c = mix(c, hi, pick); a = mix(a, 0.9 * shown, pick);
  } else a *= 1.0 - uDim;
  vSize = max(1.0, uPx * (1.0 + 1.1 * pick) * clamp(3.2 / gl_Position.w, 0.9, 2.2));
  gl_PointSize = vSize + 1.0;
  vCol = vec4(c * a, a) * uA;
}`;
  /* a crisp round point, drawn over the water: where points crowd, the colour holds instead of burning white */
  const POINT_FS = `#version 300 es
precision highp float;
in vec4 vCol; in float vSize; out vec4 o;
${K.SHADE}
void main() {
  float d = length(gl_PointCoord - 0.5) * (vSize + 1.0), cov = clamp(0.5 * vSize - d + 0.5, 0.0, 1.0);
  if (cov <= 0.0) discard;
  o = vCol * cov * shade();
}`;

  /* ---- 01 Listen: the image's pixel grid as fine dots on the floor, fading towards the crop's edges and into the water */
  const DOT_VS = `#version 300 es
layout(location = 0) in vec4 aP;
uniform mat4 uM; uniform float uPx, uA; uniform vec2 uFog;
out float vA;
void main() {
  vec4 c = uM * vec4(aP.xyz, 1.0);
  gl_Position = c; gl_PointSize = uPx + 1.0;
  vA = uA * aP.w * exp(-max(0.0, c.w - uFog.x) * uFog.y);
}`;
  const DOT_FS = `#version 300 es
precision highp float;
in float vA; uniform float uPx; uniform vec3 uInk; out vec4 o;
${K.SHADE}
void main() {
  float r = length(gl_PointCoord - 0.5) * (uPx + 1.0), a = vA * clamp(0.5 * uPx - r + 0.5, 0.0, 1.0) * shade();
  o = vec4(uInk * a, a);
}`;

  /* a camera pose: the point it looks at, the turn around it (yaw), the tilt above it (pitch) and the distance */
  const pose = (t, yaw, pitch, dist) => ({ t, yaw, pitch, dist });
  const mixPose = (a, b, e) => ({ t: lerp3(a.t, b.t, e), yaw: lerp(a.yaw, b.yaw, e), pitch: lerp(a.pitch, b.pitch, e), dist: lerp(a.dist, b.dist, e) });
  function eyeOf(p) {
    const cp = Math.cos(p.pitch), sp = Math.sin(p.pitch), cy = Math.cos(p.yaw), sy = Math.sin(p.yaw);
    return { eye: [p.t[0] + p.dist * sy * cp, p.t[1] + p.dist * sp, p.t[2] + p.dist * cy * cp], up: [-sy * sp, cp, -cy * sp] };
  }

  class ResearchScene {
    constructor() {
      this.cv = document.getElementById('gl');
      this.gl = this.cv && K.context(this.cv);
      if (!this.gl) throw new Error('WebGL 2 is not available');
      this.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
      this.ready = false; this.lost = false; this.onready = null; this.labels = [];
      this.cv.addEventListener('webglcontextlost', e => { e.preventDefault(); this.lost = true; });
      this.cv.addEventListener('webglcontextrestored', () => {
        try { this.build(); this.lost = false; if (this.onready) this.onready(); }
        catch (e) { console.error('[scene] could not rebuild after a lost context:', e); }
      });
      this.load();
    }

    async load() {
      try {
        const get = (url, as) => fetch(url, { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r[as](); });
        const [film, bin] = await Promise.all([get('film/film.json', 'json'), get('film/learn.bin', 'arrayBuffer')]);
        if (film.format !== 1) throw new Error(`film.json has format ${film.format}; this page reads format 1`);
        this.prepare(film, bin);
        this.build();
        this.ready = true;
        if (this.onready) this.onready();
      } catch (e) { console.error('[scene] no film data; the words stay over still water:', e); }
    }

    /* ------------------------------------------------------------------ the records, laid out in the world (CPU, once) */
    prepare(film, bin) {
      this.film = film;
      const L = film.learn, n = L.n;
      if (bin.byteLength !== n * L.bytes_per_point) throw new Error('learn.bin does not match film.json');
      const I = new Int16Array(bin), U = new Uint16Array(bin), f = film.listen.index;
      // learn.bin is scaled by its largest coordinate, so a few outliers would squeeze the bulk into a dot: scale the
      // world so that 98 % of the whistles lie within CLOUD of the middle instead (the outliers simply sit further out)
      const rad = new Float32Array(n);
      for (let i = 0; i < n; i++) rad[i] = Math.hypot(I[i * 4], I[i * 4 + 1], I[i * 4 + 2]) / 32767;
      rad.sort();
      this.scale = CLOUD / Math.max(1e-6, rad[Math.floor(0.98 * (n - 1))]);
      const q = v => v / 32767 * this.scale;
      this.off = [-q(I[f * 4]), -q(I[f * 4 + 1]), -q(I[f * 4 + 2])];   // the Listen whistle's own point sits at the origin
      const sel = new Uint8Array(n).fill(255), used = L.codebook_components, of = new Map(used.map((k, s) => [k, s]));
      const sum = used.map(() => [0, 0, 0, 0]);
      let cx = 0, cy = 0, cz = 0, rmax = 0;
      for (let i = 0; i < n; i++) {
        const x = q(I[i * 4]) + this.off[0], y = q(I[i * 4 + 1]) + this.off[1], z = q(I[i * 4 + 2]) + this.off[2];
        cx += x; cy += y; cz += z; rmax = Math.max(rmax, Math.hypot(x, y, z));
        const s = of.get(U[i * 4 + 3]);
        if (s !== undefined) { sel[i] = s; const a = sum[s]; a[0] += x; a[1] += y; a[2] += z; a[3]++; }
      }
      this.n = n; this.bin = bin; this.sel = sel; this.revealR = rmax;
      this.C = [cx / n, cy / n, cz / n];
      this.cent = sum.map(a => (a[3] ? [a[0] / a[3], a[1] / a[3], a[2] / a[3]] : this.C));
      this.Lc = add(this.C, [0, 0.1, 1.5]);                 // Speak: the lattice, in front of the cloud
      this.R0 = add(this.Lc, [0, -1.3, 0.8]);               // Hide: where the river starts

      this.prepareListen(film.listen);
      // Speak: each shape's points, centred, in scene units (time across, pitch up, on the lattice's pitch scale)
      const sp = film.speak, p = sp.pitches_hz, hz = HS / (p[3] - p[0]);
      this.pitchY = p.map(v => (v - p[0]) * hz - HS / 2);
      this.shapes = sp.shapes.slice(0, 16).map(s => {
        const dur = s.f.length * sp.hop_s;
        return s.f.map((v, k) => [(k * sp.hop_s - dur / 2) * TS, v * hz]);
      });
      this.followed = [sp.followed_shape, sp.band];
      this.prepareRiver(film.hide, film.hear);
    }

    prepareListen(l) {
      const lv = Uint8Array.from(atob(l.levels_b64), c => c.charCodeAt(0));
      const rowOf = f => l.zero_row - (f - l.center_hz) / l.hz_per_row, hzOf = r => l.center_hz + (l.zero_row - r) * l.hz_per_row;
      const rows = l.contour_hz.map(rowOf), rc = Math.round(rows.reduce((a, b) => a + b, 0) / rows.length);
      const c0 = Math.max(0, l.col0 - CROP_T), c1 = Math.min(l.cols - 1, l.col0 + l.contour_hz.length - 1 + CROP_T);
      const r0 = Math.max(0, rc - CROP_F), r1 = Math.min(l.rows - 1, rc + CROP_F);
      const X = c => lerp(-1.3, 1.3, (c - c0) / (c1 - c0)), Z = r => lerp(-1, 1, (r - r0) / (r1 - r0));
      // the image's level between pixels (bicubic)
      const px = (r, c) => lv[clamp(r, 0, l.rows - 1) * l.cols + clamp(c, 0, l.cols - 1)] / 255;
      const cub = (p0, p1, p2, p3, t) => p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0)));
      const S = (r, c) => {
        const ri = Math.floor(r), ci = Math.floor(c), tr = r - ri, row = k => cub(px(k, ci - 1), px(k, ci), px(k, ci + 1), px(k, ci + 2), c - ci);
        return clamp(cub(row(ri - 1), row(ri), row(ri + 1), row(ri + 2), tr));
      };
      // a hairline at every frame of the contour, as tall as the image's level there: the highest within a row of the
      // contour, averaged over five frames (the contour falls between pixel rows, so the level read at it alternates from
      // frame to frame by up to 15 %; the drawing smooths that, the image keeps every pixel)
      const crest = l.contour_hz.map((f, k) => Math.max(...[-1, -0.5, 0, 0.5, 1].map(d => S(rowOf(f) + d, l.col0 + k))));
      const avg = crest.map((_, k) => { const w = crest.slice(Math.max(0, k - 2), k + 3); return w.reduce((a, b) => a + b, 0) / w.length; });
      this.hairs = l.contour_hz.map((f, k) => [X(l.col0 + k), avg[k] * HMAX, Z(rowOf(f))]);
      // the amber line along their tops, and its trace on the floor: the contour through a Catmull-Rom curve
      const n = this.hairs.length, per = 6, curve = [];
      for (let k = 0; k < n - 1; k++) for (let j = 0; j < per; j++) {
        const t = j / per, P = i => this.hairs[clamp(i, 0, n - 1)], p0 = P(k - 1), p1 = P(k), p2 = P(k + 1), p3 = P(k + 2);
        curve.push([0, 1, 2].map(d => p1[d] + 0.5 * t * (p2[d] - p0[d] + t * (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d] + t * (3 * (p1[d] - p2[d]) + p3[d] - p0[d])))));
      }
      curve.push(this.hairs[n - 1].slice());
      this.ridge = curve;                                       // u along the contour: index / (length - 1)
      // the floor: one dot per DOT x DOT pixels of the crop, fading out over the outer fifth of each side
      const dots = [];
      for (let r = r0; r <= r1; r += DOT) for (let c = c0; c <= c1; c += DOT) {
        const ex = Math.min(c - c0, c1 - c) / ((c1 - c0) * 0.2), ez = Math.min(r - r0, r1 - r) / ((r1 - r0) * 0.2);
        dots.push(X(c), 0, Z(r), sm(0, 1, ex) * sm(0, 1, ez));
      }
      this.dotData = new Float32Array(dots); this.nDots = dots.length / 4;
      this.floor = { dur: (c1 - c0) * l.s_per_col, fLo: hzOf(r1), fHi: hzOf(r0), time: [0.15, 0, 0.92], pitch: [-1.18, 0, -0.1] };
    }

    prepareRiver(hide, hear) {
      const R0 = this.R0, yR = f => R0[1] + (f - RIVER_HZ[0]) / (RIVER_HZ[1] - RIVER_HZ[0]) * RIVER_H, zR = t => R0[2] - t * KT;
      this.yR = yR; this.zR = zR; this.dur = hide.duration_s;
      const read = new Map(hear.slots.map(s => [s.i, s]));
      const letters = hide.letters, nL = letters.length, zMid = zR(hide.duration_s / 2), yText = R0[1] + RIVER_H + 0.75, zText = zMid - 0.85;
      this.letters = letters.map((l, j) => ({ c: l.c, at: [R0[0], yText, zText + ((nL - 1) / 2 - j) * 0.36], whistles: [] }));
      this.sounds = hide.sounds.map((s, k) => {
        const x = R0[0] + (hash(k + 17) - 0.5) * 0.6;
        const o = { kind: s.kind, part: s.part, i: s.i, t0: s.t0 };
        // a click: a short tick on the riverbed at its time (clicks are broadband; a full-height line would read as rain)
        if (s.kind === 'click') { o.pts = [[x, R0[1] - 0.06, zR(s.t0)], [x, R0[1] + 0.16, zR(s.t0)]]; return o; }
        const n = s.f.length;
        o.pts = s.f.map((v, j) => [x, yR(s.fc + v), zR(s.t0 + j / (n - 1) * (s.t1 - s.t0))]);
        o.mid = o.pts[n >> 1];
        if (s.kind === 'data') {
          const r = read.get(s.i);
          o.misread = !!(r && r.symbol != null && r.symbol !== s.symbol);
          if (s.chars) {
            o.chars = s.chars;
            o.to = lerp3(this.letters[s.chars[0]].at, this.letters[s.chars[1]].at, 0.5);
            for (let j = s.chars[0]; j <= s.chars[1]; j++) this.letters[j].whistles.push(o);
          }
        }
        return o;
      });
      // the order the key's whistles light up: start signal, header, message; each part in time order
      const parts = ['start', 'header', 'message'];
      for (const part of parts) {
        const ws = this.sounds.filter(s => s.kind === 'data' && s.part === part);
        ws.forEach((s, j) => { s.order = j / Math.max(1, ws.length - 1); });
      }
      const flyers = this.sounds.filter(s => s.to);
      flyers.forEach((s, j) => { s.flyOrder = j / Math.max(1, flyers.length - 1); });
      this.zMid = zMid;
    }

    /* ------------------------------------------------------------------ GPU objects (again after a lost context) */
    build() {
      const gl = this.gl;
      this.segProg = K.program(gl, K.SEG_VS, K.SEG_FS);
      this.ptProg = K.program(gl, POINT_VS, POINT_FS);
      this.dotProg = K.program(gl, DOT_VS, DOT_FS);
      this.lines = new K.Lines(gl, 4000);
      this.timer = new K.GpuTimer(gl);
      this.dyn = new K.Segments(gl, 12000, this.segProg);
      this.dots = gl.createVertexArray();
      gl.bindVertexArray(this.dots);
      gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer()); gl.bufferData(gl.ARRAY_BUFFER, this.dotData, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 4, gl.FLOAT, false, 16, 0);
      this.cloud = gl.createVertexArray();
      gl.bindVertexArray(this.cloud);
      gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
      gl.bufferData(gl.ARRAY_BUFFER, this.bin, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 3, gl.SHORT, true, 8, 0);
      gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 1, gl.UNSIGNED_SHORT, false, 8, 6);
      gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
      gl.bufferData(gl.ARRAY_BUFFER, this.sel, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(2); gl.vertexAttribPointer(2, 1, gl.UNSIGNED_BYTE, false, 1, 0);
      gl.bindVertexArray(null);
      this.warm();
    }

    /* Drivers finish compiling a shader on its first draw (13 ms for the lines on the Radeon 610M), which would stall the
       frame where the scene first appears. One invisible draw of each, now, while the film's opening frame holds still */
    warm() {
      const gl = this.gl, id = new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]), keep = this.mvp;
      const shade = this.shadeU || [new Float32Array([0, 0, 1, 1]), 0];
      gl.viewport(0, 0, 1, 1); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
      this.dyn.clear(); this.dyn.add([0, 0, 0], [0.1, 0, 0], INK, 0.01, 1); this.dyn.upload();
      this.dyn.draw(id, [1, 1], shade, { passes: [[1, 0]] }); this.dyn.clear();
      this.lines.clear(); this.lines.line([[0, 0, 0], [0.1, 0, 0]], INK, 0.01, 1); this.lines.draw(id, [1, 1], shade); this.lines.clear();
      this.mvp = id; this.shadeU = shade;
      this.drawDots(0.001);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
      this.drawCloud(0, { learn: 1, pick: 0, lattice: 0 });
      this.mvp = keep;
      gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    }

    resize(W, H, box, text) {
      this.W = W; this.H = H; this.box = box; this.text = text;
      const d = this.d = Math.min(2, devicePixelRatio || 1);
      this.cv.width = Math.round(W * d); this.cv.height = Math.round(H * d);
      const S = Math.min((box.x1 - box.x0) / 2.9, (box.y1 - box.y0) / 1.5);
      this.fov = 2 * Math.atan(H / 2 / (2.55 * S));
      const ox = box.x0 + (box.x1 - box.x0) * 0.58, oy = box.y0 + (box.y1 - box.y0) * 0.52;
      this.dx = ox / W * 2 - 1; this.dy = 1 - oy / H * 2;
      this.shadeU = text
        ? [new Float32Array([(text.x0 + (text.x1 - text.x0) * 0.42) * d, (H - (text.y0 + (text.y1 - text.y0) * 0.45)) * d,
                             (text.x1 - text.x0) * 1.05 * d, (text.y1 - text.y0) * 1.05 * d]), 0.8]
        : [new Float32Array([0, 0, 1, 1]), 0];
      this.fs = Math.round(clamp(W * 0.0084, 13, 19));
      this.u = clamp(S / 300, 1, 2.4);
    }

    /* ------------------------------------------------------------------ one camera for the whole scene */
    camera(P) {
      // Listen: the camera comes round from low on the side as the whistle rises, then tips over it
      const A0s = pose([0, 0.12, 0.05], -0.82, 0.24, 3.15), A0 = pose([0, 0.14, 0], -0.5, 0.4, 2.8);
      const A1 = pose([0, 0, 0], 0, Math.PI / 2 - 1e-3, 2.85);
      const B = pose(this.C, 0.9, 0.32, 3.7), S = pose(this.Lc, 0, 0.05, 6.2);
      // Hide: the river seen from its side at an angle, time running across and into the distance; the camera drifts along it
      const river = tc => pose([this.R0[0], this.R0[1] + 0.7, this.zR(tc)], 0.95, 0.24, 4.4);
      const E = pose([this.R0[0], this.R0[1] + 1.75, this.zMid - 0.4], 1.42, 0.2, 6.8);
      if (P.learn <= 0) return mixPose(mixPose(A0s, A0, smoother(clamp(0.2 + 0.8 * P.rise))), A1, smoother(P.tip));
      if (P.pick <= 0) { const b = mixPose(A1, B, smoother(sm(0.08, 1, P.learn))); b.yaw += 0.25 * P.learn; return b; }
      const B1 = { ...B, yaw: B.yaw + 0.25 };
      if (P.hide <= 0) return mixPose(B1, S, smoother(clamp(0.35 * P.pick + 0.65 * P.lattice)));
      const tc = lerp(8, 24, sm(0.3, 1, P.hide));
      if (P.hear <= 0) return mixPose(S, river(tc), smoother(sm(0, 0.45, P.hide)));
      return mixPose(river(24), E, smoother(sm(0, 0.35, P.hear)));
    }

    /* reduced motion: the settled pose of the beat on screen, no camera moves */
    snap(pos) {
      const V = window.VIZ, beats = [[-1, V.rise[1]], [V.learn[0], V.learn[1]], [V.pick[0], V.lattice[1]], [V.hide[0], V.hide[1]], [V.hear[0], V.hear[1]]];
      let out = beats[0][1];
      for (const [a, b] of beats) if (pos >= a) out = b;
      return out;
    }

    /* a label: text, or [word, detail] with the detail fainter after it */
    label(text, p, alpha, align = 'left', dx = 0, dy = 0) {
      if (alpha < 0.02) return;
      const s = M.screen(this.mvp, p, this.W, this.H);
      if (s[2] > 0) this.labels.push([text, s[0] + dx, s[1] + dy, alpha, align]);
    }
    flushLabels(cx) {
      const t = this.text;
      cx.font = `400 ${this.fs}px "IBM Plex Mono", monospace`;
      if ('letterSpacing' in cx) cx.letterSpacing = '0.16em';
      cx.textBaseline = 'middle'; cx.textAlign = 'left';
      cx.shadowColor = 'rgba(2,10,20,0.5)'; cx.shadowBlur = 10; cx.shadowOffsetY = 1;
      for (const [text, x, y, alpha, align] of this.labels) {
        const [word, more] = Array.isArray(text) ? text : [text, ''];
        const w1 = cx.measureText(word.toUpperCase()).width, gap = more ? this.fs : 0, w = w1 + gap + (more ? cx.measureText(more).width : 0);
        const l = align === 'right' ? x - w : align === 'center' ? x - w / 2 : x;
        if (t && y > t.y0 - 12 && y < t.y1 + this.fs + 12 && l < t.x1 + 16 && l + w > t.x0) continue;    // never over the words
        cx.fillStyle = `rgba(${S_INK},${0.92 * alpha})`; cx.fillText(word.toUpperCase(), l, y);
        if (more) { cx.fillStyle = `rgba(${S_INK},${0.6 * alpha})`; cx.fillText(more, l + w1 + gap, y); }
      }
      cx.shadowColor = 'transparent'; cx.shadowBlur = 0; cx.shadowOffsetY = 0; cx.textBaseline = 'alphabetic';
      this.labels.length = 0;
    }
    /* a point marked on the 2D layer: a small filled dot and, if ring > 0, a thin ring of that radius */
    mark(cx, p, r, ring, alpha, color) {
      if (alpha < 0.01) return;
      const s = M.screen(this.mvp, p, this.W, this.H);
      if (!(s[2] > 0)) return;
      cx.fillStyle = `rgba(${color},${alpha})`; cx.beginPath(); cx.arc(s[0], s[1], r, 0, 2 * Math.PI); cx.fill();
      if (ring > 0) { cx.strokeStyle = `rgba(${color},${0.6 * alpha})`; cx.lineWidth = 1; cx.beginPath(); cx.arc(s[0], s[1], ring, 0, 2 * Math.PI); cx.stroke(); }
    }
    glow(cx, p, r, alpha, color = S_INK) {
      if (alpha < 0.01) return;
      const s = M.screen(this.mvp, p, this.W, this.H);
      if (!(s[2] > 0)) return;
      const R = r * this.u, g = cx.createRadialGradient(s[0], s[1], 0, s[0], s[1], R);
      g.addColorStop(0, `rgba(${color},${alpha})`); g.addColorStop(0.22, `rgba(${color},${0.55 * alpha})`); g.addColorStop(1, `rgba(${color},0)`);
      cx.fillStyle = g; cx.fillRect(s[0] - R, s[1] - R, 2 * R, 2 * R);
    }

    /** draw everything for scroll position `pos`; A = overall visibility; playT = 0..1 while "Hear it" plays */
    draw(cx, pos, A, playT) {
      if (!this.ready || this.lost) return;
      if (this.reduced) pos = this.snap(pos);
      const V = window.VIZ, gl = this.gl;
      const P = { rise: ph(V.rise, pos), tip: ph(V.tip, pos), learn: ph(V.learn, pos), pick: ph(V.pick, pos),
                  lattice: ph(V.lattice, pos), hide: ph(V.hide, pos), hear: ph(V.hear, pos) };
      const cam = this.camera(P), { eye, up } = eyeOf(cam);
      const proj = M.shift(M.perspective(this.fov, this.W / this.H, 0.05, 80), this.dx, this.dy);
      this.mvp = M.mul(proj, M.lookAt(eye, cam.t, up));
      const res = [this.cv.width, this.cv.height], D = this.dyn;
      this.timer.begin();
      gl.viewport(0, 0, res[0], res[1]); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      D.clear();

      /* ---- 01 Listen: the floor, the trace, the hairlines and the amber line; seen from above, one line, which then
         shrinks into its own point ---- */
      const gone = sm(0, 0.35, P.learn), shrink = 1 - sm(0.05, 0.4, P.learn);
      const floorA = A * sm(0, 0.45, P.rise) * (1 - gone);
      if (floorA > 0.004) this.drawDots(floorA);
      const lineA = A * (1 - sm(0.3, 0.45, P.learn));
      if (lineA > 0.004 && P.rise > 0) this.drawListen(lineA, P, shrink);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);

      /* ---- 02 Learn and 03 Speak: every whistle as a point; the codebook's families light up ---- */
      const cloudA = A * sm(0.12, 0.45, P.learn) * (1 - sm(0.1, 0.5, P.hide)) * (1 - 0.85 * sm(0.2, 0.8, P.lattice));
      if (cloudA > 0.004) this.drawCloud(cloudA, P);

      /* ---- 03 Speak: the lattice of 64 whistles ---- */
      const latA = A * sm(0, 0.15, P.lattice) * (1 - sm(0.05, 0.35, P.hide));
      let playAt = null;
      if (latA > 0.004) {
        this.lines.clear(); playAt = this.drawLattice(this.lines, latA, P.lattice, playT);
        this.lines.draw(this.mvp, res, this.shadeU, [8, 0.3]);
        gl.blendFunc(gl.ONE, gl.ONE);
      }

      /* ---- 04 Hide and 05 Hear: the river of one real send ---- */
      const riverA = A * sm(0.1, 0.45, P.hide);
      if (riverA > 0.004) this.drawRiver(cx, D, riverA, P.hear);

      D.upload();
      D.draw(this.mvp, res, this.shadeU, { passes: [[5, 0.09], [1, 1]] });

      /* ---- the 2D layer: glows, labels, letters ---- */
      const pointA = A * sm(0.3, 0.42, P.learn) * (1 - sm(0, 0.4, P.pick));
      this.mark(cx, [0, 0, 0], 3.5, 3.5 + 10 * sm(0.3, 0.6, P.learn), pointA, S_SUN);
      if (playAt) this.mark(cx, playAt, 4, 10, A, S_SUN);
      const fl = this.floor, kHz = v => (v / 1000).toFixed(1), axisA = A * sm(0.55, 1, P.rise) * (1 - sm(0, 0.2, P.learn));
      const topA = A * sm(0.7, 1, P.tip) * (1 - sm(0, 0.15, P.learn));
      this.label(['time', `${fl.dur.toFixed(2)} s`], fl.time, axisA, 'center', 0, 0);
      this.label(['pitch', `${kHz(fl.fLo)}–${kHz(fl.fHi)} kHz`], fl.pitch, axisA, 'right', 0, 0);
      this.label('its shape', this.ridge[this.ridge.length - 1], topA, 'left', 16, 0);
      const learnA = A * sm(0.55, 0.85, P.learn) * (1 - sm(0, 0.4, P.pick));
      this.label(`${this.n.toLocaleString('en-GB')} whistles, one point each`, add(this.C, [0, -CLOUD * 1.0, 0]), learnA, 'center');
      const lat = A * sm(0.6, 1, P.lattice) * (1 - sm(0, 0.2, P.hide)), Lc = this.Lc;
      this.label('16 shapes', add(Lc, [GAP * 8, -HS / 2 - 0.3, 0]), lat, 'right');
      this.label('4 pitches', add(Lc, [-GAP * 8 - 0.1, -HS / 2, 0]), lat, 'right');
      const tLabel = lerp(8, 24, sm(0.3, 1, P.hide)) + 3;                 // just ahead of where the camera looks
      this.label('time →', [this.R0[0], this.R0[1] - 0.12, this.zR(tLabel)], riverA * (1 - sm(0, 0.2, P.hear)), 'left', 8, 20);
      if (P.hear > 0) this.drawLetters(cx, A, P.hear);
      this.flushLabels(cx);
      this.timer.end();
    }

    drawDots(alpha) {
      const gl = this.gl, { p, u } = this.dotProg;
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(p); gl.bindVertexArray(this.dots);
      gl.uniformMatrix4fv(u.uM, false, this.mvp); gl.uniform1f(u.uPx, 1.9 * (this.d || 1)); gl.uniform1f(u.uA, 0.6 * alpha);
      gl.uniform2f(u.uFog, 3, 0.35); gl.uniform3fv(u.uInk, INK);
      K.setShade(gl, u, this.shadeU);
      gl.drawArrays(gl.POINTS, 0, this.nDots);
      gl.bindVertexArray(null);
    }

    /* the trace draws itself along time; then the hairlines rise, one frame after another, and the amber line rides
       their tops; as the camera tips over, the hairlines sink into points and the amber line comes down onto its trace */
    drawListen(alpha, P, shrink) {
      const L = this.lines, n = this.hairs.length, m = this.ridge.length, flat = 1 - P.tip, d = this.d;
      const up = u => smoother(clamp(P.rise * 1.7 - 0.5 - 0.6 * u)) * flat;     // how far the hairline at u (0-1) has risen
      const at = q => lerp3([0, 0, 0], q, shrink);
      L.clear();
      // the trace on the floor, drawn along time
      const drawn = sm(0, 0.45, P.rise) * (m - 1), k1 = Math.floor(drawn), trace = [];
      for (let j = 0; j <= Math.min(k1 + 1, m - 1); j++) {
        const q = [this.ridge[j][0], 0, this.ridge[j][2]];
        trace.push(at(j <= k1 ? q : lerp3(trace[j - 1], q, drawn - k1)));
      }
      L.line(trace, INK, 0.55 * alpha * (1 - 0.7 * P.tip), 1 * d);
      // the hairlines, fainter at their feet
      const hairA = 0.6 * alpha * (1 - sm(0.25, 0.75, P.tip));
      for (let k = 0; k < n; k++) {
        const h = this.hairs[k], e = up(k / (n - 1));
        if (e <= 0.002) continue;
        L.line([at([h[0], 0, h[2]]), at([h[0], h[1] * e, h[2]])], INK, hairA, 1 * d, j => (j ? 1 : 0.15));
      }
      // the amber line along their tops
      const top = this.ridge.map((q, j) => at([q[0], q[1] * up(j / (m - 1)), q[2]]));
      const crestA = alpha * sm(0.25, 0.6, P.rise);
      L.line(top, SUN, crestA, 2 * d);
      L.draw(this.mvp, [this.cv.width, this.cv.height], this.shadeU, [3.2, 0.4]);
    }

    drawCloud(alpha, P) {
      const gl = this.gl, { p, u } = this.ptProg;
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(p); gl.bindVertexArray(this.cloud);
      gl.uniformMatrix4fv(u.uM, false, this.mvp);
      gl.uniform3fv(u.uO, this.off); gl.uniform3fv(u.uFocus, [0, 0, 0]);
      gl.uniform3fv(u.uHue, new Float32Array(HUES.flat()));
      gl.uniform1f(u.uScale, this.scale); gl.uniform1f(u.uPx, 2.4 * (this.d || 1)); gl.uniform1f(u.uBase, 0.5);
      gl.uniform1f(u.uReveal, sm(0.15, 0.8, P.learn)); gl.uniform1f(u.uRevealR, this.revealR + 0.3);
      // the families light up, then dim again as their shapes fly out of them into the lattice
      gl.uniform1f(u.uPick, P.pick * (1 - 0.65 * P.lattice)); gl.uniform1f(u.uDim, 0.78 * P.pick); gl.uniform1f(u.uFollow, this.followed[0]);
      gl.uniform1f(u.uA, alpha);
      gl.uniform4fv(u.uShade, this.shadeU[0]); gl.uniform1f(u.uShadeK, this.shadeU[1]);
      gl.drawArrays(gl.POINTS, 0, this.n);
      gl.bindVertexArray(null);
      gl.blendFunc(gl.ONE, gl.ONE);
    }

    /* each family's shape flies from its family in the cloud to its column, once at each of the four pitches */
    drawLattice(L, alpha, t, playT) {
      const [fs, fb] = this.followed, Lc = this.Lc;
      let playAt = null;
      for (let i = 0; i < 16; i++) for (let b = 0; b < 4; b++) {
        const e = smoother(clamp((t - 0.025 * i - 0.05 * b) / 0.45));
        if (e <= 0) continue;
        const slot = [Lc[0] + (i - 7.5) * GAP, Lc[1] + this.pitchY[b], Lc[2]], c = lerp3(this.cent[i], slot, e), k = lerp(0.12, 1, e);
        const pts = this.shapes[i].map(([x, y]) => [c[0] + x * k, c[1] + y * k, c[2]]);
        const mine = i === fs && b === fb;
        L.line(pts, mine ? SUN : INK, alpha * (mine ? 1 : 0.92) * sm(0, 0.2, e), (mine ? 3.6 : 2.6) * this.d);
        if (mine && playT != null && e > 0.9) playAt = pts[Math.round(clamp(playT) * (pts.length - 1))];
      }
      return playAt;
    }

    /* every sound of the send, all alike; then the key's whistles rise, the misread one is repaired, and the message
       whistles fly to their letters */
    drawRiver(cx, D, alpha, h) {
      const quiet = 1 - 0.7 * sm(0, 0.2, h);
      D.add([this.R0[0], this.R0[1] - 0.06, this.zR(0)], [this.R0[0], this.R0[1] - 0.06, this.zR(this.dur)], PALE, 0.14 * alpha, 1 * this.d);
      const at = { start: 0.04, header: 0.12, message: 0.2 };
      for (const s of this.sounds) {
        if (s.kind === 'click') { D.add(s.pts[0], s.pts[1], PALE, 0.2 * alpha * quiet, 1 * this.d); continue; }
        if (s.kind === 'cover' || h <= 0) { D.line(s.pts, INK, 0.62 * alpha * (s.kind === 'cover' ? quiet : 1), 1.5 * this.d); continue; }
        const up = smoother(clamp((h - at[s.part] - 0.06 * s.order) / 0.12));
        const fixed = sm(0.34, 0.44, h);
        const color = s.misread && fixed < 1 ? lerp3(CORAL, SUN, fixed) : (up > 0 ? lerp3(INK, SUN, up) : INK);
        let pts = s.pts.map(p => [p[0], p[1] + 0.55 * up, p[2]]);
        if (s.to) {
          const e = smoother(clamp((h - 0.44 - 0.16 * s.flyOrder) / 0.16));
          if (e > 0) {
            const mid = [s.mid[0], s.mid[1] + 0.55, s.mid[2]], c = lerp3(mid, s.to, e), k = lerp(1, 0.35, e);
            pts = pts.map(p => [c[0] + (p[0] - mid[0]) * k, c[1] + (p[1] - mid[1]) * k, c[2] + (p[2] - mid[2]) * k]);
            s.arrived = e;
          } else s.arrived = 0;
        }
        const fade = s.to ? 1 - sm(0.9, 1, s.arrived || 0) * 0.6 : 1 - 0.35 * sm(0.7, 0.9, h);
        const wrong = s.misread && fixed < 1;                         // the misread whistle stands out until it is repaired
        D.line(pts, color, alpha * lerp(0.62, 1, up) * fade, lerp(1.5, 2.2, up) * (wrong ? 1.6 : 1) * this.d);
        if (s.misread && h > 0.3 && h < 0.56) {                     // the repair: a ring opens where the misread whistle sits
          const r = sm(0.34, 0.5, h);
          this.glow(cx, [s.mid[0], s.mid[1] + 0.55, s.mid[2]], 18 + 44 * r, 0.65 * alpha * (1 - r), r < 0.35 ? S_CORAL : S_SUN);
        }
      }
    }

    drawLetters(cx, A, h) {
      const size = Math.round(clamp(this.H * 0.06, 34, 80));
      cx.font = `300 ${size}px "Cormorant Garamond", Garamond, serif`; cx.textAlign = 'center'; cx.textBaseline = 'middle';
      if ('letterSpacing' in cx) cx.letterSpacing = '0px';
      for (const l of this.letters) {
        if (l.c === ' ' || !l.whistles.length) continue;
        const a = A * Math.min(...l.whistles.map(w => sm(0.75, 1, w.arrived || 0)));
        if (a < 0.01) continue;
        const s = M.screen(this.mvp, l.at, this.W, this.H);
        if (!(s[2] > 0)) continue;
        cx.shadowColor = `rgba(${S_SUN},${0.6 * a})`; cx.shadowBlur = 18;
        cx.fillStyle = `rgba(${S_INK},${a})`; cx.fillText(l.c, s[0], s[1]);
      }
      cx.shadowBlur = 0; cx.textBaseline = 'alphabetic';
      const key = this.film.provenance.example.key, last = this.letters[this.letters.length - 1].at;
      // the key as a detail: labels set their first word in capitals, and a key is case-sensitive
      this.label(['read with the key', `“${key}”`], [last[0], last[1] - 0.42, lerp(this.letters[0].at[2], last[2], 0.5)], A * sm(0.8, 0.9, h), 'center');
    }
  }
  window.ResearchScene = ResearchScene;
})();
