/**
 * The film's research beats as one WebGL 2 scene, drawn only from real records: web/film/, written by
 * `python whistlecode/whistlecode.py export-film` (web/PLAN.md, WEB-5). As in the rest of the film, every frame is a pure
 * function of the scroll position (timings: shots.js VIZ) and one camera moves through all of it: nothing cuts.
 *
 *   01 Listen  one encounter-191 training image as a landscape (time across, pitch into the distance, loudness up), cropped
 *              around its whistle; the contour it was made from is the glowing ridge. The camera tips over until the
 *              ridge is a line: the whistle's shape
 *   02 Learn   the line shrinks into a point: that same whistle's place among all 63,490 whistles the model learned from
 *              (latent means on three principal axes). The others appear around it, coloured by mixture component
 *   03 Speak   the codebook's 16 families light up and unfold into their mean shapes; at the four pitches of a slot, a
 *              lattice of the 64 whistles a message is written with. "Hear it" plays one of them, cut from a real send
 *   04 Hide    the lattice dissolves into a river of time: every sound of one real send of the example message (data
 *              whistles, cover whistles as played, recorded clicks), all alike
 *   05 Hear    the key's whistles rise out of the river; the one the receiver misread in the sea shows, then is repaired;
 *              the message whistles become the letters (the receiver's own record of that send)
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
  const GAP = 0.22, TS = 0.42; // Speak: column spacing; units per second of a shape
  const HS = 1.3;              //         height spanned by the four pitches
  const KT = 0.13;             // Hide: units per second along the river
  const RIVER_HZ = [3000, 17000], RIVER_H = 1.5;

  const POINT_VS = `#version 300 es
layout(location = 0) in vec3 aP;
layout(location = 1) in float aK;
layout(location = 2) in float aSel;
uniform mat4 uM; uniform vec3 uO, uFocus; uniform vec3 uHue[5];
uniform float uScale, uPx, uReveal, uRevealR, uPick, uDim, uFollow, uA;
out vec4 vCol;
void main() {
  vec3 w = aP * uScale + uO;
  gl_Position = uM * vec4(w, 1.0);
  float shown = 1.0 - smoothstep(uReveal * uRevealR - 0.3, uReveal * uRevealR, distance(w, uFocus));
  vec3 c = uHue[int(mod(aK * 7.0 + floor(aK / 5.0), 5.0))];
  float a = 0.24 * shown, pick = 0.0;
  if (aSel < 16.5) {
    pick = uPick;
    vec3 hi = abs(aSel - uFollow) < 0.5 ? vec3(0.949, 0.816, 0.588) : vec3(0.918, 0.965, 0.984);
    c = mix(c, hi, pick); a = mix(a, 0.9 * shown, pick);
  } else a *= 1.0 - uDim;
  gl_PointSize = max(1.0, uPx * (1.0 + 1.4 * pick) * clamp(3.2 / gl_Position.w, 0.9, 2.2));
  vCol = vec4(c * a, a) * uA;
}`;
  const POINT_FS = `#version 300 es
precision mediump float;
in vec4 vCol; out vec4 o;
${K.SHADE}
void main() {
  vec2 q = gl_PointCoord - 0.5; float r = dot(q, q) * 4.0;
  if (r > 1.0) discard;
  o = vCol * exp(-r * 2.6) * shade();
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
      const rowOf = f => l.zero_row - (f - l.center_hz) / l.hz_per_row;
      const rows = l.contour_hz.map(rowOf), rc = Math.round(rows.reduce((a, b) => a + b, 0) / rows.length);
      const c0 = Math.max(0, l.col0 - CROP_T), c1 = Math.min(l.cols - 1, l.col0 + l.contour_hz.length - 1 + CROP_T);
      const r0 = Math.max(0, rc - CROP_F), r1 = Math.min(l.rows - 1, rc + CROP_F);
      const X = c => lerp(-1.3, 1.3, (c - c0) / (c1 - c0)), Z = r => lerp(-1, 1, (r - r0) / (r1 - r0));
      const H = (r, c) => lv[Math.round(clamp(r, 0, l.rows - 1)) * l.cols + Math.round(clamp(c, 0, l.cols - 1))] / 255 * 0.55;
      // the landscape as line segments; a flat stretch is one long segment
      const segs = [];
      const run = (pts, alpha) => {
        let a = 0;
        for (let k = 1; k < pts.length; k++) {
          const flat = pts[k][1] === 0 && pts[a][1] === 0 && pts[k - 1][1] === 0;
          if (flat && k < pts.length - 1) continue;
          if (flat) { segs.push([pts[a], pts[k], alpha]); a = k; continue; }
          if (k - 1 > a) segs.push([pts[a], pts[k - 1], alpha]);
          const h = Math.max(pts[k - 1][1], pts[k][1]);
          segs.push([pts[k - 1], pts[k], alpha * (1 + 2.2 * h)]);
          a = k;
        }
      };
      for (let r = r0; r <= r1; r++) {
        const pts = []; for (let c = c0; c <= c1; c++) pts.push([X(c), H(r, c), Z(r)]);
        run(pts, 0.1 + 0.3 * (r - r0) / (r1 - r0));                 // near rows (low pitch) brighter: the floor recedes
      }
      for (let c = c0; c <= c1; c += 5) {
        const pts = []; for (let r = r0; r <= r1; r++) pts.push([X(c), H(r, c), Z(r)]);
        run(pts, 0.14);
      }
      this.terrainSegs = segs;
      // the glowing ridge: the contour, at the image's crest (the highest level within two rows of it). The contour falls
      // between pixel rows, so the crest alternates by about 15 % from frame to frame; the line takes a five-frame average
      // (the landscape itself keeps every pixel)
      const crest = l.contour_hz.map((f, k) => Math.max(...[-2, -1, 0, 1, 2].map(d => H(rowOf(f) + d, l.col0 + k))));
      const avg = crest.map((_, k) => { const w = crest.slice(Math.max(0, k - 2), k + 3); return w.reduce((a, b) => a + b, 0) / w.length; });
      this.ridge = l.contour_hz.map((f, k) => [X(l.col0 + k), avg[k] + 0.012, Z(rowOf(f))]);
      const a = this.ridge[0], e = this.ridge[this.ridge.length - 1];
      this.axes = { t: [e[0] + 0.3, 0, Math.max(a[2], e[2]) + 0.5], f: [a[0] - 0.3, 0, Math.min(a[2], e[2]) - 0.6],
                    tl: [e[0], 0, Math.max(a[2], e[2]) + 0.22], fl: [a[0] - 0.12, 0, Math.min(a[2], e[2]) - 0.1] };
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
      this.terrain = new K.Segments(gl, this.terrainSegs.length, this.segProg);
      for (const [a, b, al] of this.terrainSegs) this.terrain.add(a, b, PALE, Math.min(1, al), 1);
      this.terrain.upload();
      this.dyn = new K.Segments(gl, 12000, this.segProg);
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
      this.terrain.draw(id, [1, 1], shade, { passes: [[1, 0]] });
      this.mvp = id; this.shadeU = shade;
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
      const A0 = pose([0, 0.05, 0], -0.34, 0.44, 3.25), A1 = pose([0, 0, 0], 0, Math.PI / 2 - 1e-3, 2.85);
      const B = pose(this.C, 0.9, 0.32, 3.7), S = pose(this.Lc, 0, 0.05, 6.2);
      // Hide: the river seen from its side at an angle, time running across and into the distance; the camera drifts along it
      const river = tc => pose([this.R0[0], this.R0[1] + 0.7, this.zR(tc)], 0.95, 0.24, 4.4);
      const E = pose([this.R0[0], this.R0[1] + 1.75, this.zMid - 0.4], 1.42, 0.2, 6.8);
      if (P.learn <= 0) return mixPose(A0, A1, smoother(P.tip));
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

    label(text, p, alpha, align = 'left', dx = 0, dy = 0) {
      if (alpha < 0.02) return;
      const s = M.screen(this.mvp, p, this.W, this.H);
      if (s[2] > 0) this.labels.push([text, s[0] + dx, s[1] + dy, alpha, align]);
    }
    flushLabels(cx) {
      const t = this.text;
      cx.font = `400 ${this.fs}px "IBM Plex Mono", monospace`;
      if ('letterSpacing' in cx) cx.letterSpacing = '0.06em';
      for (let [text, x, y, alpha, align] of this.labels) {
        const w = cx.measureText(text).width, l = align === 'right' ? x - w : align === 'center' ? x - w / 2 : x;
        // a label that would sit on the words moves out to their right
        if (t && y > t.y0 - 12 && y < t.y1 + this.fs + 12 && l < t.x1 + 16 && l + w > t.x0) { x = t.x1 + 28; align = 'left'; }
        cx.textAlign = align; cx.lineWidth = 4; cx.strokeStyle = `rgba(4,22,40,${0.55 * alpha})`; cx.strokeText(text, x, y);
        cx.fillStyle = `rgba(226,242,248,${0.95 * alpha})`; cx.fillText(text, x, y);
      }
      this.labels.length = 0;
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
      gl.viewport(0, 0, res[0], res[1]); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
      D.clear();

      /* ---- 01 Listen: the landscape and its ridge, then the ridge shrinks into a point ---- */
      const flat = 1 - P.tip, gone = sm(0, 0.35, P.learn);
      const landA = A * P.rise * (1 - gone) * lerp(1, 0.35, P.tip);
      if (landA > 0.004) this.terrain.draw(this.mvp, res, this.shadeU, { s: [1, P.rise * flat, 1], passes: [[1, landA]] });
      const shrink = 1 - sm(0.05, 0.4, P.learn), ridgeA = A * P.rise * (1 - sm(0.3, 0.45, P.learn));
      if (ridgeA > 0.004) {
        const pts = this.ridge.map(p => lerp3([0, 0, 0], [p[0], p[1] * P.rise * flat, p[2]], shrink));
        D.line(pts, INK, ridgeA, 2.2 * this.d);
      }

      /* ---- 02 Learn and 03 Speak: every whistle as a point; the codebook's families light up ---- */
      const cloudA = A * sm(0.12, 0.45, P.learn) * (1 - sm(0.1, 0.5, P.hide));
      if (cloudA > 0.004) this.drawCloud(cloudA, P);

      /* ---- 03 Speak: the lattice of 64 whistles ---- */
      const latA = A * sm(0, 0.15, P.lattice) * (1 - sm(0.05, 0.35, P.hide));
      let playAt = null;
      if (latA > 0.004) playAt = this.drawLattice(D, latA, P.lattice, playT);

      /* ---- 04 Hide and 05 Hear: the river of one real send ---- */
      const riverA = A * sm(0.1, 0.45, P.hide);
      if (riverA > 0.004) this.drawRiver(cx, D, riverA, P.hear);

      D.upload();
      D.draw(this.mvp, res, this.shadeU, { passes: [[5, 0.09], [1, 1]] });

      /* ---- the 2D layer: glows, labels, letters ---- */
      this.glow(cx, [0, 0, 0], 26, A * sm(0.25, 0.4, P.learn) * (1 - sm(0.7, 1, P.learn)), S_INK);
      if (playAt) this.glow(cx, playAt, 18, A, S_SUN);
      const listenA = A * P.rise * (1 - sm(0.05, 0.4, P.tip)), topA = A * sm(0.65, 1, P.tip) * (1 - sm(0, 0.15, P.learn));
      const ax = this.axes, peak = this.ridge[this.ridge.length >> 1];
      this.label('time →', ax.t, listenA, 'right', 0, 18);
      this.label('pitch', ax.f, listenA, 'right', -10, 0);
      this.label('loudness ↑', [peak[0], peak[1] * P.rise, peak[2]], listenA * sm(0.5, 1, P.rise), 'right', -18, -28);
      this.label('time →', ax.tl, topA, 'right', 0, 22);
      this.label('pitch ↑', ax.fl, topA, 'right', -8, 0);
      this.label('its shape', this.ridge[this.ridge.length - 1], topA, 'left', 16, 5);
      const learnA = A * sm(0.55, 0.85, P.learn) * (1 - sm(0, 0.4, P.pick));
      this.label(`${this.n.toLocaleString('en-GB')} whistles, one point each`, add(this.C, [0, -CLOUD * 0.95, 0]), learnA, 'center');
      const lat = A * sm(0.6, 1, P.lattice) * (1 - sm(0, 0.2, P.hide)), Lc = this.Lc;
      this.label('16 shapes →', add(Lc, [GAP * 8, -HS / 2 - 0.3, 0]), lat, 'right');
      this.label('4 pitches ↑', add(Lc, [-GAP * 8 - 0.1, -HS / 2, 0]), lat, 'right');
      const tLabel = lerp(8, 24, sm(0.3, 1, P.hide)) + 3;                 // just ahead of where the camera looks
      this.label('time →', [this.R0[0], this.R0[1] - 0.12, this.zR(tLabel)], riverA * (1 - sm(0, 0.2, P.hear)), 'left', 8, 20);
      if (P.hear > 0) this.drawLetters(cx, A, P.hear);
      this.flushLabels(cx);
    }

    drawCloud(alpha, P) {
      const gl = this.gl, { p, u } = this.ptProg;
      gl.useProgram(p); gl.bindVertexArray(this.cloud);
      gl.uniformMatrix4fv(u.uM, false, this.mvp);
      gl.uniform3fv(u.uO, this.off); gl.uniform3fv(u.uFocus, [0, 0, 0]);
      gl.uniform3fv(u.uHue, new Float32Array(HUES.flat()));
      gl.uniform1f(u.uScale, this.scale); gl.uniform1f(u.uPx, 2.3 * this.d);
      gl.uniform1f(u.uReveal, sm(0.15, 0.8, P.learn)); gl.uniform1f(u.uRevealR, this.revealR + 0.3);
      // the families light up, then dim again as their shapes fly out of them into the lattice
      gl.uniform1f(u.uPick, P.pick * (1 - 0.65 * P.lattice)); gl.uniform1f(u.uDim, 0.78 * P.pick); gl.uniform1f(u.uFollow, this.followed[0]);
      gl.uniform1f(u.uA, alpha);
      gl.uniform4fv(u.uShade, this.shadeU[0]); gl.uniform1f(u.uShadeK, this.shadeU[1]);
      gl.drawArrays(gl.POINTS, 0, this.n);
      gl.bindVertexArray(null);
    }

    /* each family's shape flies from its family in the cloud to its column, once at each of the four pitches */
    drawLattice(D, alpha, t, playT) {
      const [fs, fb] = this.followed, Lc = this.Lc;
      let playAt = null;
      for (let i = 0; i < 16; i++) for (let b = 0; b < 4; b++) {
        const e = smoother(clamp((t - 0.025 * i - 0.05 * b) / 0.45));
        if (e <= 0) continue;
        const slot = [Lc[0] + (i - 7.5) * GAP, Lc[1] + this.pitchY[b], Lc[2]], c = lerp3(this.cent[i], slot, e), k = lerp(0.12, 1, e);
        const pts = this.shapes[i].map(([x, y]) => [c[0] + x * k, c[1] + y * k, c[2]]);
        const mine = i === fs && b === fb;
        D.line(pts, mine ? SUN : INK, alpha * (mine ? 1 : 0.72) * sm(0, 0.2, e), (mine ? 2.4 : 1.3) * this.d);
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
      this.label(`read with the key “${key}”`, [last[0], last[1] - 0.42, lerp(this.letters[0].at[2], last[2], 0.5)], A * sm(0.8, 0.9, h), 'center');
    }
  }
  window.ResearchScene = ResearchScene;
})();
