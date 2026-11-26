/**
 * The page's water, below the film: the tide the film ends under (index.html only), and the sea itself (both pages).
 * Moved unchanged from lab.js (WEB-5, web/PLAN.md), so the film's page no longer needs Try it's code.
 *
 *   setupTide   four swells roll in over the film as #lab comes up, back ones first; the front swell is the page's own water,
 *               and its crest is a whistle that draws itself. Then the first heading rises (CSS .lab.anim / .in).
 *   setupSea    light rays, the surface's shimmer and marine snow in one fragment shader, dimming as you go deeper.
 *
 * Decoration only: each part fails on its own, and a failure never stops the page.
 */
(() => {
  const $ = s => document.querySelector(s);

  /* The film ends under a tide: four swells roll in over it, back ones first, each rising as the page comes up and
     rolling sideways with time and with the scroll. The front swell is the page's own water; its crest is a whistle
     that draws itself as it arrives. Runs only while the tide is on screen. */
  const SWELLS = [   // rest height (fraction of the space above the page edge), amplitude, wavelengths, speeds, lead, colour
    { y: 0.18, a: 0.055, k: [1.1, 2.3], v: [0.018, -0.011], ph: 0.4, lead: 0.0, c: [52, 124, 166, 0.2], hl: 0.26 },
    { y: 0.36, a: 0.06, k: [0.8, 1.9], v: [-0.014, 0.02], ph: 2.1, lead: 0.12, c: [34, 98, 140, 0.32], hl: 0.26 },
    { y: 0.55, a: 0.05, k: [1.3, 2.7], v: [0.022, -0.016], ph: 4.0, lead: 0.24, c: [20, 78, 118, 0.55], hl: 0.32 },
    { y: 0.74, a: 0.0, k: [1.6, 3.1], v: [0.012, -0.02], ph: 1.3, lead: 0.36, c: [12, 63, 102, 1], hl: 0 }  // front: the whistle; the page's --sea0
  ];
  function setupTide() {
    const lab = $('#lab'), svg = $('#tide'), cv = $('#tide-c'), cx = cv.getContext('2d');
    const crest = svg.querySelectorAll('.crest');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches, TAU = Math.PI * 2, n = 160;
    const sm = (a, b, v) => { const t = Math.min(1, Math.max(0, (v - a) / (b - a))); return t * t * (3 - 2 * t); };
    let W = 0, H = 0, E = 0, on = false, raf = 0, last = -1e9, paint = [];
    // the swells are soft-edged colour: one canvas pixel per CSS pixel is plenty, and it keeps the fill cost low on an
    // integrated GPU; only the whistle crest (svg) stays sharp
    const measure = () => {
      // a box with no size yet (hidden or minimised window, a background tab): keep the old gradients, wait for a resize
      const r = svg.getBoundingClientRect();
      if (!(r.width > 0 && r.height > 0)) return false;
      W = Math.round(r.width); H = Math.round(r.height); E = H * 70 / 98;     // E: the page's top edge inside the box
      svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
      cv.width = W; cv.height = H;
      // each swell fades out below the page's edge, into the page's own water
      const fade = (rgb, a) => { const g = cx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, `rgba(${rgb},${a})`);
                                 g.addColorStop(E / H, `rgba(${rgb},${a})`); g.addColorStop(1, `rgba(${rgb},0)`); return g; };
      paint = SWELLS.map(w => ({ fill: fade(w.c.slice(0, 3).join(), w.c[3]), line: w.hl && fade('196,230,244', w.hl) }));
      return true;
    };
    const draw = now => {
      if (!paint.length && !measure()) return;
      const t = reduced ? 0 : now / 1000, r = lab.getBoundingClientRect(), vh = innerHeight;
      const s = Math.min(1.2, Math.max(0, (vh - r.top) / vh));        // 0: the page edge at the bottom of the screen, 1: at the top
      cx.clearRect(0, 0, W, H); cx.lineWidth = 1.2;
      SWELLS.forEach((w, i) => {
        const rise = sm(w.lead, w.lead + 0.62, s), base = E * (1 - rise * (1 - w.y)) + 4, front = i === 3;
        const amp = E * (front ? 0.11 : w.a) * (0.3 + 0.7 * rise), slide = s * 0.35 * (i % 2 ? -1 : 1);
        const y0 = front ? Math.min(base, E - amp * 1.32) : base;    // the front swell never dips below the page's edge
        const pts = [];
        for (let j = 0; j <= n; j++) {
          const u = j / n;
          let y;
          if (front) {    // the whistle: rising loops, gently breathing
            y = -Math.sin(3.3 * Math.PI * u + 0.4 + 0.25 * Math.sin(t * 0.21)) * (1 - 0.2 * u) * 0.9 + 0.55 * (u - 0.5)
                + 0.12 * Math.sin(TAU * (w.k[1] * u + w.v[1] * t * 4) + w.ph);
          } else {
            y = 0.62 * Math.sin(TAU * (w.k[0] * u + w.v[0] * t * 4 + slide) + w.ph) + 0.38 * Math.sin(TAU * (w.k[1] * u + w.v[1] * t * 4 - slide) + 2 * w.ph);
          }
          pts.push(u * W, y0 + amp * y);
        }
        cx.beginPath(); cx.moveTo(pts[0], pts[1]);
        for (let j = 2; j < pts.length; j += 2) cx.lineTo(pts[j], pts[j + 1]);
        if (paint[i].line) { cx.strokeStyle = paint[i].line; cx.stroke(); }
        cx.lineTo(W, H); cx.lineTo(0, H); cx.closePath(); cx.fillStyle = paint[i].fill; cx.fill();
        if (front) {
          let d = '';
          for (let j = 0; j < pts.length; j += 2) d += `${j ? 'L' : 'M'}${pts[j].toFixed(1)} ${pts[j + 1].toFixed(1)}`;
          crest.forEach(p => p.setAttribute('d', d));
        }
      });
    };
    // the swells drift slowly: 60 redraws a second are enough even on a 240 Hz screen (the scroll itself stays native)
    const loop = now => { if (now - last > 15) { last = now; draw(now); } raf = on && !reduced ? requestAnimationFrame(loop) : 0; };
    measure(); draw(performance.now());
    addEventListener('resize', () => { measure(); draw(performance.now()); });
    addEventListener('scroll', () => { if (!raf) requestAnimationFrame(draw); }, { passive: true });
    new IntersectionObserver(es => {
      on = es[es.length - 1].isIntersecting;
      if (on && !raf && !reduced) raf = requestAnimationFrame(loop);
    }).observe(svg);
    // the arrival: a whistle line draws itself across, then the first heading rises
    lab.classList.add('anim');
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { lab.classList.add('in'); io.disconnect(); } },
                                        { rootMargin: '0px 0px -35% 0px' });
    io.observe(lab);
  }

  /* The water of the page: light rays fanning down from the surface, the surface's shimmer near the top and marine snow
     at two depths, all in one fragment shader. It renders at about 1000 px across, 30 times a second, and is stretched
     to the screen: soft light needs no more, and the GPU composites one layer. Dims as you go deeper; pauses off screen. */
  const SEA_FS = `precision mediump float;
uniform vec2 R; uniform float T, D;
float h1(float n) { return fract(sin(n * 127.1) * 43758.5453); }
vec2 h2(vec2 p) { return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
float n1(float x) { float i = floor(x), f = fract(x); return mix(h1(i), h1(i + 1.0), f * f * (3.0 - 2.0 * f)); }
float snow(vec2 p, float cells, float speed, float r, float t) {
  vec2 q = p * cells + vec2(0.3 * sin(t * 0.13 + p.y * 3.0), -t * speed);   // sinking, with a slow sideways sway
  vec2 c = floor(q), f = fract(q), h = h2(c);
  if (h.x > 0.42) return 0.0;                                                // most cells are empty water
  float d = length(f - (0.2 + 0.6 * h2(c + 7.0)));
  return smoothstep(r, r * 0.25, d) * (0.35 + 0.65 * h.y);
}
void main() {
  vec2 uv = gl_FragCoord.xy / R; uv.y = 1.0 - uv.y;                        // y down from the top of the view
  float a = R.x / R.y; vec2 p = vec2(uv.x * a, uv.y); float t = T;
  // rays: brightness varying with the angle from a light source above the view, drifting and breathing
  vec2 d = p - vec2(0.52 * a + 0.08 * sin(t * 0.05), -0.55);
  float ang = atan(d.x, d.y);
  float rays = pow(n1(ang * 11.0 + t * 0.045), 3.0) * 0.65 + pow(n1(ang * 23.0 - t * 0.07 + 5.0), 4.0) * 0.45;
  rays *= smoothstep(-0.02, 0.2, uv.y) * (1.0 - smoothstep(0.2, 0.95, uv.y)) * (0.8 + 0.2 * sin(t * 0.3 + ang * 7.0));
  // the surface's shimmer: interfering ripples, bright where they cancel, strongest at the top
  vec2 w = p * 7.0 + vec2(sin(p.y * 4.0 + t * 0.4), cos(p.x * 3.0 - t * 0.3)) * 0.35;
  float v = sin(w.x + t * 0.5) + sin(0.6 * w.x + 0.8 * w.y - t * 0.37) + sin(-0.5 * w.x + 0.9 * w.y + t * 0.29);
  float shimmer = pow(1.0 - smoothstep(0.0, 0.55, abs(v)), 3.0) * (1.0 - smoothstep(0.0, 0.45, uv.y));
  float s = snow(p, 26.0, 0.012, 0.09, t) * 0.55 + snow(p + 3.7, 11.0, 0.022, 0.07, t) * 0.8;
  float L = rays * 0.19 * (1.0 - 0.75 * D) + shimmer * 0.05 * (1.0 - 0.8 * D) + s * 0.3 * (1.0 - 0.4 * D);
  gl_FragColor = vec4(vec3(0.81, 0.93, 0.97) * L, L);
}`;
  function setupSea() {
    const lab = $('#lab'), view = $('#sea-view'), cv = $('#sea-gl');
    const gl = cv.getContext('webgl', { alpha: true, antialias: false, depth: false, powerPreference: 'low-power' });
    const sh = (type, src) => { const o = gl.createShader(type); gl.shaderSource(o, src); gl.compileShader(o); return o; };
    let prog = null;
    if (gl) {
      prog = gl.createProgram();
      gl.attachShader(prog, sh(gl.VERTEX_SHADER, 'attribute vec2 v; void main() { gl_Position = vec4(v, 0.0, 1.0); }'));
      gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, SEA_FS));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) prog = null;
    }
    if (!prog) { cv.remove(); view.classList.add('static'); return; }
    gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    const uR = gl.getUniformLocation(prog, 'R'), uT = gl.getUniformLocation(prog, 'T'), uD = gl.getUniformLocation(prog, 'D');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const size = () => { const k = Math.min(1, 1000 / view.clientWidth); cv.width = Math.round(view.clientWidth * k); cv.height = Math.round(view.clientHeight * k);
                         gl.viewport(0, 0, cv.width, cv.height); gl.uniform2f(uR, cv.width, cv.height); };
    let on = false, raf = 0, last = -1e9;
    const draw = now => {
      gl.uniform1f(uT, reduced ? 20 : now / 1000);
      gl.uniform1f(uD, Math.min(1, Math.max(0, -lab.getBoundingClientRect().top / (innerHeight * 2.4))));
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };
    const loop = now => { if (now - last > 32) { last = now; draw(now); } raf = on && !reduced ? requestAnimationFrame(loop) : 0; };
    size(); draw(performance.now());
    addEventListener('resize', () => { size(); draw(performance.now()); });
    if (reduced) addEventListener('scroll', () => requestAnimationFrame(draw), { passive: true });
    new IntersectionObserver(es => { on = es[es.length - 1].isIntersecting; if (on && !raf) raf = requestAnimationFrame(loop); }).observe(lab);
  }

  // the water is decoration: each part fails on its own, and never stops the page working
  addEventListener('DOMContentLoaded', () => {
    if ($('#sea-gl')) try { setupSea(); } catch (e) { console.warn('setupSea:', e); }
    if ($('#tide')) try { setupTide(); } catch (e) { console.warn('setupTide:', e); }
  });
})();
