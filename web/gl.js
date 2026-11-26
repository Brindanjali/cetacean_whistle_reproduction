/**
 * Small WebGL 2 helpers for the film's scene (scene.js): no library (web/PLAN.md, "The 3D scene"; web/PLAN-SCENE.md).
 *
 *   context(canvas)          a WebGL 2 context, or null (the film then shows its words over still water)
 *   program(gl, vs, fs)      a linked program and its uniform locations (throws with the log if a shader fails)
 *   Mat                      column-major 4x4 matrices: perspective, lookAt, multiply, and a point's screen position
 *   Lines                    fine lines: each polyline one strip with mitred joins, its opacity per point (a line can fade
 *                            along its length), fading with distance into the water. Drawn over the water, not added to it
 *   Segments                 a batch of thick line segments drawn as instanced quads, added to the water (Hide and Hear)
 *   GpuTimer                 GPU time per frame from the browser's timer query, where it has one (for measuring)
 *
 * Shared by every fragment shader: SHADE, the soft oval behind the research words where the scene thins out.
 */
(() => {
  function context(canvas) {
    // high-performance: browsers that can choose the graphics chip take the faster one. Chrome on Windows does not (it
    // gives every page the browser's own chip, measured 2026-11-26); there the chip is set per browser in Windows
    // no multisampling: every line and point smooths its own edge in its shader, and multisampling would only add the
    // cost of four samples a pixel (the Learn cloud: 7 ms a frame with it on the Radeon 610M at 2560 x 1600)
    const gl = canvas.getContext('webgl2', { alpha: true, premultipliedAlpha: true, antialias: false, depth: false,
                                             preserveDrawingBuffer: false, powerPreference: 'high-performance' });
    return gl || null;
  }

  function program(gl, vs, fs) {
    const sh = (type, src) => {
      const o = gl.createShader(type);
      gl.shaderSource(o, src); gl.compileShader(o);
      if (!gl.getShaderParameter(o, gl.COMPILE_STATUS) && !gl.isContextLost()) throw new Error(gl.getShaderInfoLog(o));
      return o;
    };
    const p = gl.createProgram();
    gl.attachShader(p, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS) && !gl.isContextLost()) throw new Error(gl.getProgramInfoLog(p));
    const u = {};
    const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS) || 0;
    for (let i = 0; i < n; i++) { const name = gl.getActiveUniform(p, i).name.replace(/\[0\]$/, ''); u[name] = gl.getUniformLocation(p, name); }
    return { p, u };
  }

  /* ------------------------------------------------------------------ matrices (column-major, as WebGL reads them) */
  const Mat = {
    perspective(fovy, aspect, near, far) {
      const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
      return new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0]);
    },
    /* a projection whose centre sits at NDC (dx, dy) instead of the screen's middle: the scene stays right of the words */
    shift(P, dx, dy) {
      const M = P.slice();
      for (let c = 0; c < 4; c++) { M[c * 4] += dx * P[c * 4 + 3]; M[c * 4 + 1] += dy * P[c * 4 + 3]; }
      return M;
    },
    lookAt(e, t, up) {
      let zx = e[0] - t[0], zy = e[1] - t[1], zz = e[2] - t[2];
      let l = Math.hypot(zx, zy, zz) || 1; zx /= l; zy /= l; zz /= l;
      let xx = up[1] * zz - up[2] * zy, xy = up[2] * zx - up[0] * zz, xz = up[0] * zy - up[1] * zx;
      l = Math.hypot(xx, xy, xz) || 1; xx /= l; xy /= l; xz /= l;
      const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
      return new Float32Array([xx, yx, zx, 0, xy, yy, zy, 0, xz, yz, zz, 0,
                               -(xx * e[0] + xy * e[1] + xz * e[2]), -(yx * e[0] + yy * e[1] + yz * e[2]), -(zx * e[0] + zy * e[1] + zz * e[2]), 1]);
    },
    mul(a, b) {
      const o = new Float32Array(16);
      for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
        o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
      }
      return o;
    },
    /* [x px, y px, w] of a world point (y down, as the 2D canvas draws); w <= 0 means behind the camera */
    screen(M, p, W, H) {
      const x = M[0] * p[0] + M[4] * p[1] + M[8] * p[2] + M[12], y = M[1] * p[0] + M[5] * p[1] + M[9] * p[2] + M[13];
      const w = M[3] * p[0] + M[7] * p[1] + M[11] * p[2] + M[15];
      return w <= 1e-4 ? [NaN, NaN, w] : [(x / w + 1) / 2 * W, (1 - y / w) / 2 * H, w];
    }
  };

  /* the soft oval behind the research words: the scene thins out there (uniform uShade: centre x, y and radii, device px,
     y up; uShadeK: how much is taken away at its centre) */
  const SHADE = `
uniform vec4 uShade; uniform float uShadeK;
float shade() {
  if (uShadeK <= 0.0) return 1.0;
  float d = length((gl_FragCoord.xy - uShade.xy) / uShade.zw);
  return 1.0 - uShadeK * (1.0 - smoothstep(0.55, 1.0, d));
}`;
  function setShade(gl, u, sh) { gl.uniform4fv(u.uShade, sh[0]); gl.uniform1f(u.uShadeK, sh[1]); }

  /* ------------------------------------------------------------------ fine lines */
  const LINE_VS = `#version 300 es
layout(location = 0) in vec3 aP;
layout(location = 1) in vec3 aPrev;
layout(location = 2) in vec3 aNext;
layout(location = 3) in float aSide;
layout(location = 4) in float aW;
layout(location = 5) in vec4 aCol;
uniform mat4 uM; uniform vec2 uRes; uniform float uFogD, uFogK;
out vec4 vCol; out float vD; out float vHalf;
vec2 scr(vec4 c) { return c.xy / max(c.w, 0.05) * uRes * 0.5; }
void main() {
  vec4 c = uM * vec4(aP, 1.0);
  if (c.w < 0.05) { gl_Position = vec4(0.0, 0.0, 2.0, 1.0); vCol = vec4(0.0); vD = 0.0; vHalf = 1.0; return; }
  vec2 s = scr(c), d1 = s - scr(uM * vec4(aPrev, 1.0)), d2 = scr(uM * vec4(aNext, 1.0)) - s;
  if (dot(d1, d1) < 1e-6) d1 = d2;
  if (dot(d2, d2) < 1e-6) d2 = d1;
  if (dot(d1, d1) < 1e-6) { d1 = vec2(1.0, 0.0); d2 = d1; }
  d1 = normalize(d1); d2 = normalize(d2);
  vec2 t = d1 + d2; t = dot(t, t) < 1e-6 ? d1 : normalize(t);
  vec2 n = vec2(-t.y, t.x);
  float miter = 1.0 / max(dot(n, vec2(-d1.y, d1.x)), 0.4), half_ = 0.5 * aW;
  vec2 p = s + n * aSide * (half_ + 1.0) * miter;
  gl_Position = vec4(p / (uRes * 0.5) * c.w, c.z, c.w);
  vCol = aCol * exp(-max(0.0, c.w - uFogD) * uFogK);        // farther into the water, fainter
  vD = aSide * (half_ + 1.0); vHalf = half_;
}`;
  const LINE_FS = `#version 300 es
precision highp float;
in vec4 vCol; in float vD; in float vHalf;
out vec4 o;
${SHADE}
void main() { o = vCol * (clamp(vHalf + 0.5 - abs(vD), 0.0, 1.0) * shade()); }`;

  const LF = 15;          // p (3), prev (3), next (3), side, width, rgba premultiplied (4)
  class Lines {
    constructor(gl, capacity) {
      this.gl = gl; this.cap = capacity; this.nv = 0; this.ni = 0;
      this.prog = program(gl, LINE_VS, LINE_FS);
      this.data = new Float32Array(capacity * 2 * LF); this.idx = new Uint32Array(capacity * 6);
      this.vao = gl.createVertexArray(); this.buf = gl.createBuffer(); this.ibuf = gl.createBuffer();
      gl.bindVertexArray(this.vao); gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
      gl.bufferData(gl.ARRAY_BUFFER, this.data.byteLength, gl.DYNAMIC_DRAW);
      [[0, 3, 0], [1, 3, 12], [2, 3, 24], [3, 1, 36], [4, 1, 40], [5, 4, 44]].forEach(([loc, k, off]) => {
        gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, k, gl.FLOAT, false, LF * 4, off);
      });
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.ibuf);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, this.idx.byteLength, gl.DYNAMIC_DRAW);
      gl.bindVertexArray(null);
    }
    clear() { this.nv = 0; this.ni = 0; }
    /* a polyline through pts: colour rgb (0-1), opacity a, width w px; at(k) optional, a multiplier of point k's opacity */
    line(pts, rgb, a, w, at = null) {
      const n = pts.length;
      if (n < 2 || a <= 0.002 || this.nv + 2 * n > this.cap * 2) return;
      const d = this.data, x = this.idx, v0 = this.nv;
      for (let k = 0; k < n; k++) {
        const p = pts[k], q = pts[Math.max(0, k - 1)], r = pts[Math.min(n - 1, k + 1)], m = a * (at ? at(k) : 1);
        for (let s = -1; s <= 1; s += 2) {
          const i = this.nv++ * LF;
          d[i] = p[0]; d[i + 1] = p[1]; d[i + 2] = p[2]; d[i + 3] = q[0]; d[i + 4] = q[1]; d[i + 5] = q[2];
          d[i + 6] = r[0]; d[i + 7] = r[1]; d[i + 8] = r[2]; d[i + 9] = s; d[i + 10] = w;
          d[i + 11] = rgb[0] * m; d[i + 12] = rgb[1] * m; d[i + 13] = rgb[2] * m; d[i + 14] = m;
        }
      }
      for (let k = 0; k < n - 1; k++) {
        const b = v0 + 2 * k;
        x[this.ni++] = b; x[this.ni++] = b + 1; x[this.ni++] = b + 2;
        x[this.ni++] = b + 1; x[this.ni++] = b + 3; x[this.ni++] = b + 2;
      }
    }
    /* draw over what is there (premultiplied); fog [start, rate] in view depth */
    draw(M, res, shadeU, fog = [1e3, 0]) {
      if (!this.ni) return;
      const gl = this.gl, { p, u } = this.prog;
      gl.bindVertexArray(this.vao);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buf); gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.data, 0, this.nv * LF);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.ibuf); gl.bufferSubData(gl.ELEMENT_ARRAY_BUFFER, 0, this.idx, 0, this.ni);
      gl.useProgram(p);
      gl.uniformMatrix4fv(u.uM, false, M); gl.uniform2f(u.uRes, res[0], res[1]);
      gl.uniform1f(u.uFogD, fog[0]); gl.uniform1f(u.uFogK, fog[1]);
      setShade(gl, u, shadeU);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.drawElements(gl.TRIANGLES, this.ni, gl.UNSIGNED_INT, 0);
      gl.bindVertexArray(null);
    }
  }

  /* ------------------------------------------------------------------ segments (Hide and Hear, as in WEB-5) */
  const SEG_VS = `#version 300 es
layout(location = 0) in vec3 aA;
layout(location = 1) in vec3 aB;
layout(location = 2) in vec4 aCol;
layout(location = 3) in float aW;
uniform mat4 uM; uniform vec2 uRes; uniform vec3 uS, uO; uniform float uWMul;
out vec4 vCol; out float vPx; out float vHalf;
void main() {
  vec4 ca = uM * vec4(aA * uS + uO, 1.0), cb = uM * vec4(aB * uS + uO, 1.0);
  if (ca.w < 0.05 || cb.w < 0.05) { gl_Position = vec4(0.0, 0.0, 2.0, 1.0); vCol = vec4(0.0); vPx = 0.0; vHalf = 1.0; return; }
  vec2 sa = ca.xy / ca.w * uRes * 0.5, sb = cb.xy / cb.w * uRes * 0.5;
  vec2 d = sb - sa; float len = length(d);
  vec2 dir = len > 1e-4 ? d / len : vec2(1.0, 0.0), n = vec2(-dir.y, dir.x);
  int id = gl_VertexID;
  float side = (id == 0 || id == 2) ? -1.0 : 1.0;
  bool end = id >= 2;
  float half_ = 0.5 * aW * uWMul;
  vec2 p = (end ? sb : sa) + n * side * (half_ + 1.0) + dir * (end ? 1.0 : -1.0) * half_;
  vec4 c = end ? cb : ca;
  gl_Position = vec4(p / (uRes * 0.5) * c.w, c.z, c.w);
  vCol = aCol; vPx = side * (half_ + 1.0); vHalf = half_;
}`;
  const SEG_FS = `#version 300 es
precision mediump float;
in vec4 vCol; in float vPx; in float vHalf;
uniform float uAMul;
out vec4 o;
${SHADE}
void main() {
  float a = clamp(vHalf + 0.5 - abs(vPx), 0.0, 1.0);
  if (vHalf > 2.0) a *= 1.0 - smoothstep(0.0, vHalf + 0.5, abs(vPx)) * 0.85;     // wide strokes are glows: soft to the edge
  o = vCol * (a * uAMul * shade());
}`;

  const FLOATS = 11;      // a (3), b (3), rgba (4), width (1)
  class Segments {
    constructor(gl, capacity, prog) {
      this.gl = gl; this.prog = prog; this.cap = capacity; this.n = 0;
      this.data = new Float32Array(capacity * FLOATS);
      this.vao = gl.createVertexArray(); this.buf = gl.createBuffer();
      gl.bindVertexArray(this.vao); gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
      gl.bufferData(gl.ARRAY_BUFFER, this.data.byteLength, gl.DYNAMIC_DRAW);
      const s = FLOATS * 4;
      [[0, 3, 0], [1, 3, 12], [2, 4, 24], [3, 1, 40]].forEach(([loc, k, off]) => {
        gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, k, gl.FLOAT, false, s, off); gl.vertexAttribDivisor(loc, 1);
      });
      gl.bindVertexArray(null);
    }
    clear() { this.n = 0; }
    /* one segment: ends a and b, colour rgb (0-1) at alpha a, width w px */
    add(a, b, rgb, alpha, w) {
      if (this.n >= this.cap || alpha < 0.003) return;
      const d = this.data, i = this.n++ * FLOATS;
      d[i] = a[0]; d[i + 1] = a[1]; d[i + 2] = a[2]; d[i + 3] = b[0]; d[i + 4] = b[1]; d[i + 5] = b[2];
      d[i + 6] = rgb[0] * alpha; d[i + 7] = rgb[1] * alpha; d[i + 8] = rgb[2] * alpha; d[i + 9] = alpha; d[i + 10] = w;
    }
    /* a polyline through pts (world points) */
    line(pts, rgb, alpha, w) { for (let k = 1; k < pts.length; k++) this.add(pts[k - 1], pts[k], rgb, alpha, w); }
    upload() {
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.data, 0, this.n * FLOATS);
    }
    /* draw with transform M; uS/uO scale and offset every end; a glow pass is the same batch, wider and fainter */
    draw(M, res, shadeU, opt = {}) {
      if (!this.n) return;
      const gl = this.gl, { p, u } = this.prog;
      gl.useProgram(p); gl.bindVertexArray(this.vao);
      gl.uniformMatrix4fv(u.uM, false, M); gl.uniform2f(u.uRes, res[0], res[1]);
      gl.uniform3fv(u.uS, opt.s || [1, 1, 1]); gl.uniform3fv(u.uO, opt.o || [0, 0, 0]);
      setShade(gl, u, shadeU);
      for (const [wm, am] of opt.passes || [[1, 1]]) {
        gl.uniform1f(u.uWMul, wm); gl.uniform1f(u.uAMul, am);
        gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.n);
      }
      gl.bindVertexArray(null);
    }
  }

  /* ------------------------------------------------------------------ GPU time per frame (ms, newest last, at most 600) */
  class GpuTimer {
    constructor(gl) { this.gl = gl; this.ext = gl.getExtension('EXT_disjoint_timer_query_webgl2'); this.open = null; this.queue = []; this.ms = []; }
    begin() {
      if (!this.ext || this.open) return;
      this.open = this.gl.createQuery(); this.gl.beginQuery(this.ext.TIME_ELAPSED_EXT, this.open);
    }
    end() {
      const gl = this.gl;
      if (!this.open) return;
      gl.endQuery(this.ext.TIME_ELAPSED_EXT); this.queue.push(this.open); this.open = null;
      const disjoint = gl.getParameter(this.ext.GPU_DISJOINT_EXT);
      while (this.queue.length && gl.getQueryParameter(this.queue[0], gl.QUERY_RESULT_AVAILABLE)) {
        const q = this.queue.shift();
        if (!disjoint) this.ms.push(gl.getQueryParameter(q, gl.QUERY_RESULT) / 1e6);
        gl.deleteQuery(q);
      }
      if (this.ms.length > 600) this.ms.splice(0, this.ms.length - 600);
    }
  }

  window.GLKit = { context, program, Mat, Lines, Segments, GpuTimer, SHADE, SEG_VS, SEG_FS, setShade };
})();
