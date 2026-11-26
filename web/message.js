/**
 * Encode and Decode — WhistleCode on the project page, right after the film (Encode opens the lab).
 *
 * Encode: as you type, /api/wc/frame returns every step from letters to whistles with the real values (no audio is made).
 * "Hide it" makes the sound the sender would play, which is silent between the animals' sounds; "Hear it in the sea" mixes that
 * file into a real sea recording. Decode: a recording and a key go to the receiver, and nothing else. Only when the recording was
 * made by Encode on this page does the page afterwards ask the server to compare each whistle with the sender's record
 * (/api/wc/check), and it says so.
 *
 * Talks to `python whistlecode/whistlecode.py serve` (same origin; whistlecode/wcode/web.py). Without it both places say how to
 * start it and stay still. Every value that came from a file or from the visitor is inserted as text, never as markup.
 */
(() => {
  const $ = s => document.querySelector(s);
  const h = (tag, props = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (v == null || v === false) continue;
      if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  };
  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs = {}) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const rnd = n => Math.floor(Math.random() * n);
  const s1 = v => (+v).toFixed(1);
  const plural = (n, w, ws = w + 's') => `${n} ${n === 1 ? w : ws}`;
  const WORDS = ['tide', 'reef', 'kelp', 'coral', 'shoal', 'swell', 'drift', 'brine', 'surf', 'pearl', 'squid', 'krill'];
  const newKey = not => { let k; do k = `${WORDS[rnd(WORDS.length)]}-${10 + rnd(90)}`; while (k === not); return k; };
  const post = (url, body) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const fileUrl = (id, name) => `api/wc/files/${id}/${name}`;
  const detail = b => typeof b.detail === 'string' ? b.detail : Array.isArray(b.detail) ? b.detail.map(d => d.msg).join('; ') : '';

  /* SHALLOWS, the palette of Try it (lab.js, infer.py): quiet = pale sea foam, loud = deep water */
  const SHALLOWS = [[0, [238, 247, 248]], [0.18, [200, 226, 233]], [0.4, [127, 182, 201]], [0.65, [42, 110, 150]], [0.85, [13, 58, 92]], [1, [4, 26, 46]]];
  const LUT = (() => {
    const t = new Uint8ClampedArray(256 * 3);
    for (let i = 0; i < 256; i++) {
      const v = i / 255; let k = 1;
      while (k < SHALLOWS.length - 1 && v > SHALLOWS[k][0]) k++;
      const [a, ca] = SHALLOWS[k - 1], [b, cb] = SHALLOWS[k], w = (v - a) / (b - a);
      for (let c = 0; c < 3; c++) t[i * 3 + c] = ca[c] + (cb[c] - ca[c]) * w;
    }
    return t;
  })();

  const S = { ready: false, status: null, shapes: [], maxMs: 1, maxF: 1, nonce: rnd(256), nextNonce: rnd(256), frame: null, seq: 0,
              sent: null, sea: null, texts: {}, src: null, dec: null, encPic: null, seaPic: null, decPic: null };

  /* ------------------------------------------------------------------ jobs */
  function jobLine(el, text, err) {
    el.hidden = false; el.classList.toggle('err', !!err); el.classList.toggle('busy', !err);
    el.querySelector('span').textContent = text; el.querySelector('i').style.width = '';
  }
  async function runJob(req, el) {
    jobLine(el, 'Starting…');
    const r = await req;
    let body = {};
    try { body = await r.json(); } catch (_) { /* not JSON */ }
    if (!r.ok) throw new Error(detail(body) || r.statusText);
    for (;;) {
      await sleep(350);
      const j = await (await fetch(`api/wc/jobs/${body.job}`)).json();
      if (j.state === 'error') throw new Error(j.error);
      if (j.state === 'done') { el.hidden = true; return { id: body.job, ...(await (await fetch(j.result.replace(/^\//, ''))).json()) }; }
      jobLine(el, j.state === 'queued' ? 'Waiting for the previous job…' : j.stage ? j.stage[0].toUpperCase() + j.stage.slice(1) + '…' : 'Working…');
    }
  }

  /* ------------------------------------------------------------------ sound: one player for the whole page section */
  const player = new Audio();
  player.preload = 'auto';
  let active = null;                    // { pic, btn, until }
  function stopSound() {
    player.pause();
    if (active) { if (active.btn) active.btn.setAttribute('aria-pressed', 'false'); active.pic.playhead(null); active = null; }
  }
  function playFrom(pic, url, t0, t1 = Infinity, btn = null) {
    stopSound();
    const abs = new URL(url, location.href).href;
    if (player.src !== abs) player.src = abs;
    active = { pic, btn, until: t1 };
    if (btn) btn.setAttribute('aria-pressed', 'true');
    const go = () => { player.currentTime = Math.max(0, t0); player.play().catch(stopSound); };
    if (player.readyState >= 1) go(); else player.addEventListener('loadedmetadata', go, { once: true });
    const tick = () => {
      if (!active || active.pic !== pic) return;
      const t = player.currentTime;
      if (t >= active.until || player.ended) { stopSound(); return; }
      if (!player.paused) pic.playhead(t, true);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  player.addEventListener('ended', stopSound);
  function playButton(label, pic, url) {
    const b = h('button', { class: 'play', type: 'button', 'aria-pressed': 'false' }, h('span', { class: 'ic', 'aria-hidden': 'true' }), label);
    b.addEventListener('click', () => { if (active && active.btn === b) stopSound(); else playFrom(pic, url, pic.win0, Infinity, b); });
    return b;
  }
  const download = (label, url, name) => h('a', { class: 'play', href: url, download: name }, '↓ ', label);

  /* ------------------------------------------------------------------ a recording: close-up above, the whole of it below */
  class Picture {
    constructor(host) {
      this.fAx = h('div', { class: 'ov-f', 'aria-hidden': 'true' });
      this.lensCv = h('canvas'); this.lensSvg = svgEl('svg', { preserveAspectRatio: 'none' }); this.lensPh = h('i', { class: 'wc-ph' });
      this.lens = h('div', { class: 'ov wc-lens' }, this.lensCv, this.lensSvg, this.lensPh);
      this.tAx = h('div', { class: 'ov-t', 'aria-hidden': 'true' });
      this.overCv = h('canvas'); this.overSvg = svgEl('svg', { preserveAspectRatio: 'none' });
      this.win = h('i', { class: 'wc-win' }); this.overPh = h('i', { class: 'wc-ph' });
      this.over = h('div', { class: 'ov wc-over', tabindex: 0, role: 'slider', 'aria-label': 'Part of the recording shown in the close-up' },
                    this.overCv, this.overSvg, this.win, this.overPh);
      host.replaceChildren(h('div', { class: 'ov-card wc-card' }, this.fAx, this.lens, this.tAx, this.over));
      this.src = null; this.info = null; this.boxes = []; this.win0 = 0; this.span = 8; this.dur = 1; this.sel = -1; this.onBox = null;
      const move = e => { const r = this.over.getBoundingClientRect(); this.centre((e.clientX - r.left) / r.width * this.dur); };
      this.over.addEventListener('pointerdown', e => { this.over.setPointerCapture(e.pointerId); this.drag = true; move(e); });
      this.over.addEventListener('pointermove', e => { if (this.drag) move(e); });
      this.over.addEventListener('pointerup', () => { this.drag = false; });
      this.over.addEventListener('keydown', e => {
        const d = { ArrowLeft: -0.5, ArrowRight: 0.5, PageUp: -1, PageDown: 1 }[e.key];
        if (d) { e.preventDefault(); this.show(this.win0 + d * this.span); }
      });
      this.lensSvg.addEventListener('click', e => {
        const r = e.target.closest('rect');
        if (r && r.dataset.k != null && this.onBox) this.onBox(+r.dataset.k);
      });
      new ResizeObserver(() => this.layout()).observe(this.lens);
    }
    async load(url, info) {
      this.info = info; this.dur = info.t1_s; this.span = Math.min(8, this.dur); this.win0 = 0; this.sel = -1; this.boxes = [];
      const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('the picture could not be loaded')); i.src = url; });
      const c = document.createElement('canvas');
      c.width = img.naturalWidth; c.height = img.naturalHeight;
      const x = c.getContext('2d');
      x.drawImage(img, 0, 0);
      const d = x.getImageData(0, 0, c.width, c.height), p = d.data;
      for (let i = 0; i < p.length; i += 4) { const v = p[i] * 3; p[i] = LUT[v]; p[i + 1] = LUT[v + 1]; p[i + 2] = LUT[v + 2]; p[i + 3] = 255; }
      x.putImageData(d, 0, 0);
      this.src = c;
      this.fAx.replaceChildren();
      const { f_lo, f_hi } = info;
      for (let f = Math.ceil(f_lo / 5000) * 5000; f <= f_hi; f += 5000) this.fAx.append(h('span', { style: `bottom:${(f - f_lo) / (f_hi - f_lo) * 100}%` }, `${f / 1000} kHz`));
      this.layout();
    }
    layout() {
      if (!this.src) return;
      const dpr = Math.min(2, devicePixelRatio || 1);
      for (const [cv, el] of [[this.lensCv, this.lens], [this.overCv, this.over]]) {
        cv.width = Math.max(1, Math.round(el.clientWidth * dpr)); cv.height = Math.max(1, Math.round(el.clientHeight * dpr));
      }
      const o = this.overCv.getContext('2d');
      o.imageSmoothingQuality = 'high';
      o.drawImage(this.src, 0, 0, this.overCv.width, this.overCv.height);
      this.drawOver(); this.show(this.win0);
    }
    centre(t) { this.show(t - this.span / 2); }
    show(t0) {
      if (!this.src) return;
      this.win0 = Math.max(0, Math.min(this.dur - this.span, t0));
      const cps = this.src.width / this.dur, l = this.lensCv.getContext('2d');
      l.drawImage(this.src, this.win0 * cps, 0, Math.max(1, this.span * cps), this.src.height, 0, 0, this.lensCv.width, this.lensCv.height);
      Object.assign(this.win.style, { left: `${this.win0 / this.dur * 100}%`, width: `${this.span / this.dur * 100}%` });
      this.over.setAttribute('aria-valuemin', 0); this.over.setAttribute('aria-valuemax', Math.round(this.dur));
      this.over.setAttribute('aria-valuenow', Math.round(this.win0));
      this.over.setAttribute('aria-valuetext', `${s1(this.win0)} to ${s1(this.win0 + this.span)} s`);
      this.tAx.replaceChildren();
      const step = this.span <= 3 ? 0.5 : 1;
      for (let t = Math.ceil(this.win0 / step) * step; t <= this.win0 + this.span + 1e-6; t += step)
        this.tAx.append(h('span', { style: `left:${(t - this.win0) / this.span * 100}%` }, `${+t.toFixed(1)} s`));
      this.drawLens();
    }
    setBoxes(list) { this.boxes = list; this.sel = -1; this.drawOver(); this.drawLens(); }
    drawLens() {
      const W = this.lens.clientWidth, H = this.lens.clientHeight, svg = this.lensSvg;
      svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
      svg.replaceChildren();
      if (!this.info) return;
      const k = W / this.span, { f_lo, f_hi } = this.info, fy = f => (f_hi - f) / (f_hi - f_lo) * H;
      this.boxes.forEach((b, i) => {
        if (b.t1 < this.win0 || b.t0 > this.win0 + this.span) return;
        const x = (b.t0 - this.win0) * k, y = fy(b.f1 + 300), y1 = fy(b.f0 - 300);
        const r = svgEl('rect', { x, y, width: Math.max(3, (b.t1 - b.t0) * k), height: Math.max(3, y1 - y),
                                  class: `w ${b.cls || ''}${i === this.sel ? ' hl' : ''}`, 'data-k': i });
        if (b.title) { const t = svgEl('title'); t.textContent = b.title; r.append(t); }
        svg.append(r);
        if (b.label) { const t = svgEl('text', { x: x + 1, y: Math.max(11, y - 4) }); t.textContent = b.label; svg.append(t); }
      });
    }
    drawOver() {
      const svg = this.overSvg;
      svg.setAttribute('viewBox', `0 0 ${this.dur} 1`);
      svg.replaceChildren(...this.boxes.map(b => svgEl('rect', { x: b.t0, y: 0.2, width: Math.max(this.dur / 900, b.t1 - b.t0), height: 0.6, class: b.cls || '' })));
    }
    select(i, reveal) {
      this.sel = i;
      const b = this.boxes[i];
      if (reveal && b && (b.t0 < this.win0 || b.t1 > this.win0 + this.span)) this.centre((b.t0 + b.t1) / 2); else this.drawLens();
    }
    playhead(t, follow) {
      if (t == null) { this.lensPh.style.display = this.overPh.style.display = 'none'; return; }
      if (follow && (t < this.win0 || t > this.win0 + this.span * 0.92)) this.show(t - this.span * 0.08);
      this.overPh.style.display = 'block'; this.overPh.style.left = `${t / this.dur * 100}%`;
      const inLens = t >= this.win0 && t <= this.win0 + this.span;
      this.lensPh.style.display = inLens ? 'block' : 'none';
      if (inLens) this.lensPh.style.left = `${(t - this.win0) / this.span * 100}%`;
    }
  }
  /* play one boxed whistle with a little sound either side */
  const playBox = (pic, url, k) => { const b = pic.boxes[k]; pic.select(k, true); playFrom(pic, url, b.t0 - 0.25, b.t1 + 0.3); };

  /* ------------------------------------------------------------------ whistle tiles */
  function chipSvg(shape, band) {
    const svg = svgEl('svg', { viewBox: '0 0 24 32', 'aria-hidden': 'true' }), s = S.shapes[shape];
    if (!s) return svg;
    const len = 5 + 14 * s.ms / S.maxMs, x0 = (24 - len) / 2, yc = 26.5 - band * 7;        // pitch 1 at the bottom, 4 at the top
    svg.append(svgEl('polyline', { points: s.f.map((f, k) => `${(x0 + len * k / (s.f.length - 1)).toFixed(1)},${(yc - f / S.maxF * 4.5).toFixed(1)}`).join(' ') }));
    return svg;
  }
  const GROUPS = [['start', 'Start signal'], ['header', 'Header'], ['message', 'Message']];
  function chipGroups(host, items, make) {
    host.replaceChildren();
    for (const [g, title] of GROUPS) {
      const its = items.filter(it => it.part === g);
      if (its.length) host.append(h('div', { class: 'chip-g' }, h('h5', {}, `${title} · ${its.length}`), h('div', { class: 'chip-row' }, its.map(make))));
    }
  }
  function chip(cls, svg, label, on, pick) {
    const b = h('button', { class: `chip ${cls}`, type: 'button', 'aria-label': label }, svg);
    b.addEventListener('mouseenter', () => on(true)); b.addEventListener('focus', () => on(true));
    b.addEventListener('mouseleave', () => on(false)); b.addEventListener('blur', () => on(false));
    b.addEventListener('click', pick);
    return b;
  }
  function setStation(ol, k, v) {
    const li = ol.children[k];
    li.classList.toggle('on', !!(v && v.on)); li.classList.toggle('bad', !!(v && v.bad)); li.classList.remove('hi');
    li.querySelector('b').textContent = v ? v.b : '–';
    li.querySelector('p').replaceChildren(...(v && v.p != null ? [].concat(v.p) : []));
    const old = li.querySelector('.letters');
    if (old) old.remove();
    if (v && v.extra) li.append(v.extra);
  }
  const setStations = (ol, list) => [...ol.children].forEach((_, k) => setStation(ol, k, list[k]));

  /* ================================================================== Encode */
  const two = a => a.slice(0, 6).map(v => String(v).padStart(2, '0')).join(' ') + (a.length > 6 ? ' …' : '');
  const sentMatches = () => S.sent && S.sent.text === $('#enc-text').value && S.sent.key === $('#enc-key').value;

  function rhythmStation(f) {
    if (sentMatches() && S.sent.nonce === f.nonce) {
      const r = S.sent.r;
      return { on: true, b: `${s1(r.duration_s)} s`, p: `${r.n_data} of ${r.n_data + r.n_cover} whistles carry the message${r.n_clicks ? ` · ${r.n_clicks} recorded clicks` : ''} · each at a moment a real animal called` };
    }
    return { b: `≈ ${Math.round(f.duration_s)} s`, p: `among ${f.n_cover} real whistles, at the moments real animals called · press Hide it to make the sound` };
  }

  function showFrame(f) {
    S.frame = f;
    const total = f.n_start + f.n_header + f.n_payload, unit = f.mode === 'compact' ? 'letter' : 'byte';
    const count = $('#enc-count');
    count.replaceChildren([`${f.length} ${f.unit}`, f.mode === 'compact' ? 'compact alphabet, 5 bits a letter' : null,
                           `${f.n_start} start + ${f.n_header} header + ${f.n_payload} message whistles = ${total}`,
                           `about ${Math.round(f.duration_s)} s among ${f.n_cover} cover whistles`].filter(Boolean).join(' · '));
    if (f.mode === 'raw') {
      const up = $('#enc-text').value.toUpperCase();
      count.append(h('span', { class: 'warn' }, ' · sent as raw UTF-8, 8 bits a byte: only A–Z, space and . , ? ! - fit the 5-bit alphabet'));
      if ([...up].every(c => S.status.alphabet.includes(c)))
        count.append(' ', h('button', { class: 'wc-link', type: 'button', onclick: () => { $('#enc-text').value = up; onType(); } }, 'Use capitals'));
    }
    const letters = h('div', { class: 'letters' }, f.letters.map((l, i) => h('span', { title: `${l.c}: ${l.bits}`, 'data-i': i }, l.c)));
    const blocks = f.blocks.length > 1 ? ` in ${f.blocks.length} blocks` : '';
    setStations($('#enc-stations'), [
      { on: true, b: `${f.message_bits} bits`, p: `${f.length} ${unit}${f.length === 1 ? '' : 's'} × ${f.char_bits} bits`, extra: letters },
      { on: true, b: `+ ${f.crc_bits} bits`, p: `CRC-16 ${f.crc}${f.pad_bits ? ` · ${f.pad_bits} zero bits fill the last group` : ''} · ${f.plain.length} groups of 6 bits` },
      { on: true, b: `${f.plain.length} mixed`, p: [`before ${two(f.plain)}`, h('br'), `after ${two(f.scrambled)}`, h('br'), `scrambled by the key and nonce ${f.nonce}`] },
      { on: true, b: `+ ${f.parity}`, p: `Reed–Solomon${blocks}: rebuilds up to ${f.parity} lost whistles, or half as many wrong ones · header ${f.header.data} + ${f.header.parity} spare` },
      { on: true, b: `${total}`, p: `header and message: 6 bits each, shape 1 of 16 × pitch 1 of 4 · the ${f.n_start} start whistles carry none` },
      rhythmStation(f),
    ]);
    chipGroups($('#enc-chips'), f.whistles, w => chip(
      { start: 'start', header: 'head', 'header-spare': 'head spare', spare: 'spare' }[w.role] || '', chipSvg(w.shape, w.band), encInfo(w),
      on => encHover(w, on), () => encPick(w)));
    $('#enc-chip-info').textContent = 'Each tile is one whistle: the line is its shape (one of 16, at its own length), its height its pitch (one of 4). Point at one to see what it carries.';
  }

  function encInfo(w) {
    const n = `Whistle ${w.i + 1}`, sp = `shape ${w.shape + 1} of 16, pitch ${w.band + 1} of 4 (symbol ${w.symbol})`;
    if (w.role === 'start') return `${n} · start signal: the same signature whistle three times, at moments only the key knows`;
    if (w.role === 'header') return `${n} · header · ${sp} · carries the ${w.about}`;
    if (w.role === 'header-spare') return `${n} · header spare · ${sp} · lets the decoder rebuild a lost or wrong header whistle`;
    if (w.role === 'spare') return `${n} · message spare · ${sp} · Reed–Solomon parity: lets the decoder rebuild lost or wrong whistles`;
    const f = S.frame, what = [];
    if (w.chars) {
      const cs = f.letters.slice(w.chars[0], w.chars[1] + 1).map(l => `‘${l.c}’`), u = f.mode === 'compact' ? 'letter' : 'byte';
      what.push(`${cs.length > 1 ? `${u}s` : u} ${cs.join(' ')}`);
    }
    if (w.crc) what.push('the checksum');
    return `${n} · message · ${sp} · carries bits ${w.bits[0]}–${w.bits[1] - 1}: ${what.join(' and ') || 'padding'}, scrambled by the key`;
  }
  function encHover(w, on) {
    const st = $('#enc-stations').children;
    st[0].querySelectorAll('.letters span').forEach(s => s.classList.toggle('hi', on && !!w.chars && +s.dataset.i >= w.chars[0] && +s.dataset.i <= w.chars[1]));
    st[1].classList.toggle('hi', on && !!w.crc);
    st[3].classList.toggle('hi', on && (w.role === 'spare' || w.role === 'header-spare'));
    if (on) $('#enc-chip-info').textContent = encInfo(w);
    if (S.encPic && sentMatches()) {
      const k = S.encPic.boxes.findIndex(b => b.i === w.i);
      if (on && k >= 0) S.encPic.select(k, false);
    }
  }
  function encPick(w) {
    if (!S.encPic || !sentMatches()) return;
    const k = S.encPic.boxes.findIndex(b => b.i === w.i);
    if (k >= 0) playBox(S.encPic, fileUrl(S.sent.id, S.sent.r.audio.play), k);
  }

  let typeTimer = 0;
  function onType() {
    clearTimeout(typeTimer);
    const text = $('#enc-text').value, key = $('#enc-key').value;
    if (S.sent) {
      const same = sentMatches();
      $('#enc-out').classList.toggle('stale', !same);
      S.nonce = same ? S.sent.nonce : S.nextNonce;               // a new message never reuses the nonce of the last one
    }
    S.frame = null; updateEnc();
    typeTimer = setTimeout(() => frame(text, key), 180);
  }
  async function frame(text, key) {
    const seq = ++S.seq;
    const clear = msg => {
      $('#enc-count').replaceChildren(msg); setStations($('#enc-stations'), []);
      $('#enc-chips').replaceChildren(); $('#enc-chip-info').textContent = ''; S.frame = null; updateEnc();
    };
    if (!text) return clear('Write a message first.');
    if (!key) return clear('Choose a key: the decoder will need the same one.');
    try {
      const r = await post('api/wc/frame', { text, key, nonce: S.nonce }), b = await r.json();
      if (seq !== S.seq) return;
      if (!r.ok) return clear(h('span', { class: 'warn' }, detail(b) || r.statusText));
      showFrame(b);
    } catch (_) { if (seq === S.seq) clear(h('span', { class: 'warn' }, 'The message server did not answer.')); }
    updateEnc();
  }
  const updateEnc = () => { $('#enc-run').disabled = !(S.ready && S.frame && !S.busyEnc); $('#sea-run').disabled = !(S.ready && S.sent && !S.busySea); };

  async function hide() {
    const text = $('#enc-text').value, key = $('#enc-key').value, nonce = S.nonce;
    S.busyEnc = true; updateEnc(); stopSound();
    try {
      const r = await runJob(post('api/wc/send', { text, key, nonce }), $('#enc-job'));
      S.sent = { id: r.id, text, key, nonce, r }; S.texts[r.id] = text; S.sea = null;
      do S.nextNonce = rnd(256); while (S.nextNonce === nonce);
      await showSent(r);
    } catch (e) { jobLine($('#enc-job'), String(e.message || e), true); }
    S.busyEnc = false; updateEnc();
  }
  async function showSent(r) {
    const out = $('#enc-out');
    out.hidden = false; out.classList.remove('stale');
    $('#enc-sum').replaceChildren(h('b', {}, plural(r.n_data, 'message whistle')), ' among ', h('b', {}, plural(r.n_cover, 'cover whistle')),
      r.n_clicks ? ` and ${r.n_clicks} recorded clicks` : '', ' · ', h('b', {}, `${s1(r.duration_s)} s`), ` · nonce ${r.nonce}. `,
      'The file holds only the animals’ sounds and is silent between them: the sea brings its own noise.');
    if (S.frame) setStation($('#enc-stations'), 5, rhythmStation(S.frame));
    S.encPic = S.encPic || new Picture($('#enc-pic'));
    const pic = S.encPic, play = fileUrl(r.id, r.audio.play);
    await pic.load(fileUrl(r.id, r.picture.png), r.picture);
    pic.setBoxes(r.whistles.map(w => ({ i: w.i, t0: w.t0, t1: w.t1, f0: w.f0, f1: w.f1, cls: w.part === 'start' ? 'p' : '',
                                        label: `${w.i + 1}`, title: `whistle ${w.i + 1} · ${w.part}` })));
    pic.onBox = k => playBox(pic, play, k);
    pic.show(r.whistles[0].t0 - 0.5);
    $('#enc-plays').replaceChildren(playButton('Play', pic, play), download('Download WAV · 96 kHz', fileUrl(r.id, r.audio.file), 'whistlecode_sent.wav'),
      h('button', { class: 'play', type: 'button', onclick: () => useInDecoder({ kind: 'job', job: r.id, which: 'sent', label: 'the file you just made', sendId: r.id }) }, 'Open in decoder ↓'));
    $('#sea-out').hidden = true; $('#sea-job').hidden = true;
    $('#dec-src').hidden = false; $('#dec-use-heard').hidden = true;
    out.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'nearest' });
  }

  async function sea() {
    if (!S.sent) return;
    const sent = S.sent, snr = +$('#sea-snr').value, encounter = +$('#sea-noise').value;
    S.busySea = true; updateEnc(); stopSound();
    try {
      const r = await runJob(post('api/wc/sea', { job: sent.id, snr_db: snr, encounter, seed: rnd(2 ** 31) }), $('#sea-job'));
      S.sea = { id: r.id, r, sendId: sent.id };
      $('#sea-sum').replaceChildren('Mixed at ', h('b', {}, `${snr} dB`), ` above the noise of encounter ${r.encounter}, `,
        r.encounter === 276 ? 'a recording the decoder was never tuned on' : 'the recording the decoder was tuned on',
        ` · the message starts ${s1(r.offset_s)} s in · `, h('b', {}, `${s1(r.duration_s)} s`), '. The animals in that recording are still there.');
      $('#sea-out').hidden = false;
      S.seaPic = S.seaPic || new Picture($('#sea-pic'));
      const pic = S.seaPic, play = fileUrl(r.id, r.audio.play);
      await pic.load(fileUrl(r.id, r.picture.png), r.picture);
      const boxes = sent.r.whistles.map(w => ({ i: w.i, t0: w.t0 + r.offset_s, t1: w.t1 + r.offset_s, f0: w.f0, f1: w.f1, cls: w.part === 'start' ? 'p' : '',
                                                label: `${w.i + 1}`, title: `whistle ${w.i + 1} · ${w.part} (from the sender’s record)` }));
      const show = h('input', { type: 'checkbox' });
      show.addEventListener('change', () => pic.setBoxes(show.checked ? boxes : []));
      pic.onBox = k => playBox(pic, play, k);
      pic.show(r.offset_s + sent.r.whistles[0].t0 - 0.5);
      $('#sea-plays').replaceChildren(playButton('Play', pic, play), download('Download WAV · 96 kHz', fileUrl(r.id, r.audio.file), 'whistlecode_heard.wav'),
        h('button', { class: 'play', type: 'button', onclick: () => useInDecoder({ kind: 'job', job: r.id, which: 'heard', label: 'the file as heard in the sea', sendId: sent.id }) }, 'Open in decoder ↓'),
        h('label', { class: 'wc-show' }, show, 'Show where the message is (from the sender’s record)'));
      $('#dec-use-heard').hidden = false;
    } catch (e) { jobLine($('#sea-job'), String(e.message || e), true); }
    S.busySea = false; updateEnc();
  }

  /* ================================================================== Decode */
  const srcName = src => src.rec ? `${src.label} · ${s1(src.rec)} s`
    : src.kind === 'file' ? `${src.file.name} · ${(src.file.size / 1048576).toFixed(1)} MB` : `${src.label}, made above`;
  function setSource(src) {
    S.src = src;
    // the drop zone itself names the recording it holds, so a chosen file never looks ignored
    $('#dec-drop-t').replaceChildren('Ready: ', h('b', {}, src.label || src.file.name), ' · drop another, or ', h('u', {}, 'choose a file'));
    $('#dec-drop').classList.add('has');
    updateDec();
  }
  const updateDec = () => {
    const ok = S.ready && !!S.src && !S.busyDec && !REC.on && !REC.busy, key = $('#dec-key').value;
    $('#dec-run').disabled = !(ok && key); $('#dec-wrong').disabled = !ok;
    // the next step, in words: a greyed-out button alone does not say what it waits for
    const line = $('#dec-chosen');
    line.classList.toggle('next', !!S.src && !key);
    line.textContent = !S.src ? 'No recording chosen yet.'
      : `Chosen: ${srcName(S.src)} · ${key ? 'press Read it.' : 'now type the key it was hidden with, then press Read it.'}`;
  };
  function useInDecoder(src) {
    setSource(src);
    $('#dec-key').value = S.sent ? S.sent.key : $('#dec-key').value;        // a file made above comes with its key
    updateDec();
    const d = $('#decode');
    d.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
    d.focus({ preventScroll: true });
  }

  async function decode(key, label) {
    const src = S.src;
    if (!src || !key) return;
    S.busyDec = true; updateDec(); stopSound();
    let req;
    if (src.kind === 'file') {
      const fd = new FormData(); fd.append('file', src.file); fd.append('key', key);
      req = fetch('api/wc/decode', { method: 'POST', body: fd });
    } else req = post('api/wc/decode-job', { job: src.job, file: src.which, key });
    try {
      const r = await runJob(req, $('#dec-job'));
      await showDecoded(r, key, label, src);
    } catch (e) { jobLine($('#dec-job'), String(e.message || e), true); }
    S.busyDec = false; updateDec();
  }

  function decStations(r) {
    const out = [{ on: true, b: `${r.n_tracks}`, p: `whistle tracks in ${s1(r.duration_s)} s of sound` }];
    if (r.offset_s == null) return [...out, { bad: true, b: 'none', p: 'no whistles line up with the timing this key gives' }];
    out.push({ on: true, b: `${s1(r.offset_s)} s`, p: `where the key’s timing lines up with the recording · agreement ${r.sync_votes}` });
    const hd = r.header, sp = r.repair.spare;
    if (r.stage === 'header' || !r.payload) {
      return [...out, { bad: true, b: hd ? `${hd.read} / ${hd.n}` : '–',
                        p: hd ? `${hd.missed} missed · ${hd.doubtful} unclear: no valid header within the ${sp ? sp.header : 4} spare header whistles` : 'no header found' }];
    }
    out.push({ on: true, b: `${hd.read} / ${hd.n}`, p: `read · ${r.length} ${r.mode === 'compact' ? 'characters' : 'bytes'}, nonce ${r.nonce}` });
    const pl = r.payload, total = sp && sp.payload != null ? sp.header + sp.payload : null;
    out.push({ on: true, b: `${pl.read} / ${pl.n}`, p: `read · ${pl.missed} missed · ${pl.doubtful} unclear` });
    if (r.ok) {
      const used = 2 * r.repair.wrong + r.repair.lost;
      out.push({ on: true, b: total ? `${used} / ${total}` : `${used}`, p: `spare used: ${r.repair.wrong} wrong (each costs 2) + ${r.repair.lost} lost` });
      out.push({ on: true, b: 'passed', p: 'CRC-16 matches: this is the message' });
    } else if (/^crc/.test(r.detail)) {
      out.push({ on: true, b: 'tried', p: `every repair within the ${total ?? ''} spare whistles was tried` });
      out.push({ bad: true, b: 'failed', p: 'no repair passes the checksum, so nothing is shown' });
    } else out.push({ bad: true, b: 'too much', p: `more lost and wrong whistles than the ${total ?? ''} spare whistles can rebuild` });
    return out;
  }

  const STATE_CLS = { start: 'start', read: '', missed: 'lost', doubtful: 'unclear', unread: 'lost' };
  const BOX_CLS = { start: 'p', read: '', missed: 'miss', doubtful: 'doubt', unread: 'miss' };
  function decInfo(s, v, ok) {
    const n = `Whistle ${s.i + 1}`;
    if (s.state === 'start') return `${n} · start signal, where the key said it would be`;
    const fix = ok ? ', then rebuilt by the spare whistles' : '';
    let t = s.state === 'read' ? `${n} · ${s.part} · read as shape ${s.shape + 1}, pitch ${s.band + 1} (symbol ${s.symbol})`
          : s.state === 'doubtful' ? `${n} · ${s.part} · a whistle was there, but its shape was too unclear to trust: treated as lost${fix}`
          : `${n} · ${s.part} · no whistle found where the key pointed${fix}`;
    if (v && v.verdict === 'right') t += ' · the same as sent';
    if (v && v.verdict === 'wrong') t += ` · sent as symbol ${v.sent}: read wrong${fix}`;
    return t;
  }

  async function showDecoded(r, key, label, src) {
    S.dec = { r, src, verdicts: {} };
    const ol = $('#dec-stations'), st = decStations(r);
    ol.hidden = false; setStations(ol, []);
    $('#dec-result').hidden = true; $('#dec-chips').replaceChildren(); $('#dec-chip-info').textContent = '';
    // the values are the receiver's own; the stations only light up one after another, so the order can be followed
    for (let k = 0; k < st.length; k++) { if (!reduced) await sleep(260); setStation(ol, k, st[k]); }

    const res = $('#dec-result'), txt = $('#dec-text'), badge = $('#dec-badge');
    $('#dec-label').textContent = label || `Read with the key “${key}”`;
    txt.classList.toggle('none', !r.ok);
    badge.className = 'wc-badge';
    if (r.ok) {
      // the server holds a decoded message in memory only (never on disk), so a restart forgets it
      const shown = r.text != null ? r.text : r.hex != null ? `binary: ${r.hex}` : 'No longer held by the server';
      txt.replaceChildren(...[...shown].map(c => h('span', {}, c)));
      res.hidden = false;
      [...txt.children].forEach((sp, i) => reduced ? sp.classList.add('in') : setTimeout(() => sp.classList.add('in'), 40 * i));
      badge.textContent = 'CRC passed'; badge.classList.add('ok');
    } else {
      txt.textContent = 'No message found'; res.hidden = false;
      badge.textContent = 'No message'; badge.classList.add('err');
    }

    // the receiver's own view: where the key told it to look, and what it read there
    $('#dec-out').hidden = false;
    S.decPic = S.decPic || new Picture($('#dec-pic'));
    const pic = S.decPic, play = fileUrl(r.id, r.audio.play);
    await pic.load(fileUrl(r.id, r.picture.png), r.picture);
    const boxes = () => r.slots.map(s => {
      const v = S.dec.verdicts[s.i];
      const cls = v ? { right: 'ok', wrong: 'bad', lost: 'miss' }[v.verdict] : BOX_CLS[s.state];
      return { i: s.i, t0: s.t0, t1: s.t1, f0: s.f0, f1: s.f1, cls, label: `${s.i + 1}`, title: decInfo(s, v, r.ok) };
    });
    pic.setBoxes(boxes());
    pic.onBox = k => { playBox(pic, play, k); $('#dec-chip-info').textContent = pic.boxes[k].title; };
    if (r.slots.length) pic.show(r.slots[0].t0 - 0.5);
    $('#dec-plays').replaceChildren(playButton('Play', pic, play));
    const legend = ['Boxes: where the key told the decoder to look, drawn with the shape it read there.',
                    'Dashed grey: no whistle found · dashed amber: too unclear to trust.'];
    $('#dec-hint').textContent = r.slots.length ? legend.join(' ') : 'No start signal lined up with this key, so the decoder had nowhere to look.';
    const chips = () => chipGroups($('#dec-chips'), r.slots, s => {
      const v = S.dec.verdicts[s.i], cls = v ? { right: 'right', wrong: 'wrong', lost: 'lost' }[v.verdict] : STATE_CLS[s.state];
      const svg = s.shape != null ? chipSvg(s.shape, s.band) : chipSvg(-1, 0);
      return chip(cls, svg, decInfo(s, v, r.ok), on => {
        if (on) $('#dec-chip-info').textContent = decInfo(s, v, r.ok);
        const k = pic.boxes.findIndex(b => b.i === s.i);
        if (on && k >= 0) pic.select(k, false);
      }, () => { const k = pic.boxes.findIndex(b => b.i === s.i); if (k >= 0) playBox(pic, play, k); });
    });
    chips();
    if (!r.ok && r.detail) $('#dec-chip-info').textContent = `The decoder’s own words: ${r.detail}.`;

    // a file made above can be checked against the sender's record, after decoding and only then
    if (src.kind === 'job' && src.sendId && r.slots.length) {
      try {
        const c = await (await post('api/wc/check', { send: src.sendId, decode: r.id })).json();
        if (c.comparable) {
          c.whistles.forEach(w => { S.dec.verdicts[w.i] = w; });
          pic.setBoxes(boxes()); chips();
          const n = c.counts, sent = S.texts[src.sendId];
          $('#dec-hint').textContent = `${legend[0]} Checked afterwards against the sender’s record, which the decoder never saw: `
            + `${n.right} read right (green), ${n.wrong} read wrong (amber), ${n.lost} lost (grey)${r.ok && (n.wrong || n.lost) ? ', and every one of them repaired' : ''}.`;
          if (r.ok && sent != null) {
            const same = r.text === sent;
            badge.textContent = same ? 'Exact match' : 'Differs from what was sent';
            badge.className = `wc-badge ${same ? 'ok' : 'warn'}`;
          }
        } else $('#dec-hint').textContent = `${$('#dec-hint').textContent} No check against the sender’s record: ${c.why}.`;
      } catch (_) { /* the reading stands without the check */ }
    }
  }

  /* ------------------------------------------------------------------ or listen: record with the microphone
     The microphone's own sound, untouched: no echo cancelling, noise suppression or automatic gain, which would take the
     whistles for noise. An AudioWorklet collects the samples as they arrive; Stop writes them as a 32-bit float WAV at the
     microphone's own rate, and the recording goes to the decoder exactly like a dropped file. */
  const TAP = `class Tap extends AudioWorkletProcessor {
    constructor() { super(); this.buf = new Float32Array(16384); this.n = 0;
      this.port.onmessage = () => { this.flush(); this.port.postMessage('end'); }; }
    flush() { if (this.n) { this.port.postMessage(this.buf.slice(0, this.n)); this.n = 0; } }
    process(inputs) {
      const ch = inputs[0] && inputs[0][0];
      if (ch) { if (this.n + ch.length > this.buf.length) this.flush(); this.buf.set(ch, this.n); this.n += ch.length; }
      return true;
    }
  }
  registerProcessor('wc-tap', Tap);`;
  const REC = { on: false, busy: false, ctx: null, stream: null, tap: null, an: null, chunks: [], n: 0, fs: 0, t0: 0, peak: 0, dev: '', ended: null };
  const canRecord = () => !!(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

  function wavFloat32(chunks, n, fs) {
    const b = new ArrayBuffer(44 + 4 * n), v = new DataView(b), str = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
    str(0, 'RIFF'); v.setUint32(4, 36 + 4 * n, true); str(8, 'WAVE'); str(12, 'fmt '); v.setUint32(16, 16, true);
    v.setUint16(20, 3, true); v.setUint16(22, 1, true); v.setUint32(24, fs, true); v.setUint32(28, 4 * fs, true);   // 3 = IEEE float, mono
    v.setUint16(32, 4, true); v.setUint16(34, 32, true); str(36, 'data'); v.setUint32(40, 4 * n, true);
    const out = new Float32Array(b, 44, n);
    let o = 0;
    for (const c of chunks) { out.set(c, o); o += c.length; }
    return new Blob([b], { type: 'audio/wav' });
  }
  function recNote(parts, warn) {
    const el = $('#rec-note');
    el.replaceChildren(...[].concat(parts));
    el.classList.toggle('warn', !!warn);
  }
  function recUi() {
    const b = $('#rec-run');
    b.disabled = !S.ready || REC.busy || !canRecord();
    b.setAttribute('aria-pressed', REC.on ? 'true' : 'false');
    $('#rec-run-t').textContent = REC.on ? ($('#dec-key').value ? 'Stop and read' : 'Stop') : REC.busy ? 'Starting…' : 'Record';
    updateDec();
  }
  async function listDevices() {
    try {
      const ins = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audioinput' && d.deviceId);
      if (ins.length < 2) return;
      const cur = REC.dev || (REC.stream && REC.stream.getAudioTracks()[0].getSettings().deviceId) || '';
      $('#rec-dev').replaceChildren(...ins.map((d, i) => h('option', { value: d.deviceId, selected: d.deviceId === cur }, d.label || `Microphone ${i + 1}`)));
      $('#rec-dev-l').hidden = false;
    } catch (_) { /* the choice is optional */ }
  }

  async function startRec() {
    if (!canRecord()) return;
    stopSound();
    REC.busy = true; recUi();
    let stream = null, ctx = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: REC.dev ? { exact: REC.dev } : undefined, channelCount: 1,
                                                                    echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      ctx = new AudioContext();
      const min = S.status.limits.min_rate_hz;
      if (ctx.sampleRate < min) throw new Error(`this computer records at ${ctx.sampleRate / 1000} kHz; the decoder needs ${min / 1000} kHz or more`);
      await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([TAP], { type: 'text/javascript' })));
      const src = ctx.createMediaStreamSource(stream), tap = new AudioWorkletNode(ctx, 'wc-tap'), mute = ctx.createGain(), an = ctx.createAnalyser();
      mute.gain.value = 0;                                  // keeps the tap running; nothing is played back
      an.fftSize = 2048; an.smoothingTimeConstant = 0; an.minDecibels = -100; an.maxDecibels = -30;
      src.connect(tap); tap.connect(mute); mute.connect(ctx.destination); src.connect(an);
      tap.port.onmessage = e => {
        if (e.data === 'end') { if (REC.ended) REC.ended(); return; }
        const c = e.data;
        REC.chunks.push(c); REC.n += c.length;
        for (let i = 0; i < c.length; i++) { const a = Math.abs(c[i]); if (a > REC.peak) REC.peak = a; }
      };
      Object.assign(REC, { on: true, busy: false, ctx, stream, tap, an, chunks: [], n: 0, fs: ctx.sampleRate, peak: 0, t0: performance.now() });
      await ctx.resume();
    } catch (e) {
      if (stream) stream.getTracks().forEach(t => t.stop());
      if (ctx) ctx.close();
      Object.assign(REC, { on: false, busy: false });
      recUi();
      return recNote(e && e.name === 'NotAllowedError' ? 'The browser was not allowed to use the microphone. Allow it from the icon in the address bar, then press Record again.'
                                                       : `The microphone could not start: ${(e && e.message) || e}`, true);
    }
    recUi(); listDevices();
    recNote('Recording. Play the message now, near this computer, at a comfortable loudness. Press Stop when it has finished.');
    $('#rec-live').hidden = false;
    live();
  }

  function live() {
    const cv = $('#rec-cv'), dpr = Math.min(2, devicePixelRatio || 1);
    cv.width = Math.max(1, Math.round(cv.clientWidth * dpr)); cv.height = Math.max(1, Math.round(cv.clientHeight * dpr));
    const g = cv.getContext('2d'), W = cv.width, H = cv.height, an = REC.an;
    g.fillStyle = `rgb(${LUT[0]},${LUT[1]},${LUT[2]})`; g.fillRect(0, 0, W, H);
    const bins = new Uint8Array(an.frequencyBinCount), wave = new Float32Array(an.fftSize), binHz = REC.fs / an.fftSize;
    const rows = Array.from({ length: H }, (_, y) => Math.min(bins.length - 1, Math.round((20000 - 19000 * y / Math.max(1, H - 1)) / binHz)));
    const col = g.createImageData(1, H), pxPerS = W / 10, max = S.status.limits.max_seconds - 1;      // the last 10 seconds
    let last = performance.now(), acc = 0;
    const step = now => {
      if (!REC.on) return;
      acc += (now - last) / 1000 * pxPerS; last = now;
      const dx = Math.floor(acc);
      if (dx > 0) {
        acc -= dx;
        an.getByteFrequencyData(bins);
        for (let y = 0; y < H; y++) { const v = bins[rows[y]] * 3, o = 4 * y; col.data[o] = LUT[v]; col.data[o + 1] = LUT[v + 1]; col.data[o + 2] = LUT[v + 2]; col.data[o + 3] = 255; }
        g.drawImage(cv, -dx, 0);
        for (let i = 0; i < dx; i++) g.putImageData(col, W - dx + i, 0);
      }
      an.getFloatTimeDomainData(wave);
      let e = 0;
      for (let i = 0; i < wave.length; i++) e += wave[i] * wave[i];
      const db = 10 * Math.log10(e / wave.length + 1e-12), lvl = $('#rec-level');
      lvl.style.width = `${Math.max(0, Math.min(1, (db + 70) / 70)) * 100}%`;
      lvl.classList.toggle('loud', REC.peak >= 0.99);
      const t = (now - REC.t0) / 1000;
      $('#rec-time').replaceChildren(`${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')} · ${REC.fs / 1000} kHz · level ${Math.round(db)} dB`,
        REC.peak >= 0.99 ? h('span', { class: 'warn' }, ' · too loud: it clipped; turn the sound down or move away') : '');
      if (t >= max) { stopRec(); return; }
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  async function stopRec() {
    if (!REC.on) return;
    REC.on = false; REC.busy = true; recUi();
    await new Promise(res => { REC.ended = res; REC.tap.port.postMessage('flush'); setTimeout(res, 600); });   // the last samples
    REC.ended = null;
    REC.stream.getTracks().forEach(t => t.stop());
    REC.ctx.close();
    const secs = REC.n / REC.fs;
    const file = secs >= 1 ? new File([wavFloat32(REC.chunks, REC.n, REC.fs)], 'microphone.wav', { type: 'audio/wav' }) : null;
    REC.chunks = []; REC.busy = false; recUi();
    if (!file) return recNote('That was too short to hold a message. Press Record and play the whole message.', true);
    setSource({ kind: 'file', file, rec: secs, label: 'the microphone recording' });
    const key = $('#dec-key').value;
    recNote(`Recorded ${s1(secs)} s.${key ? ' Reading it now.' : ' Type the key it was hidden with, then press Read it.'}`);
    if (key) decode(key, `Read from the microphone recording with the key “${key}”`);
    else $('#dec-key').focus();
  }

  /* ================================================================== status, wiring, index */
  function offline(...parts) {
    const st = $('#wc-status');
    st.classList.remove('ok');
    st.querySelector('.txt').replaceChildren(...parts.map((p, i) => i === 1 && parts.length === 3 ? h('code', {}, p) : p));
    $('#enc-count').textContent = '';
  }
  async function init() {
    let s = null;
    try { const r = await fetch('api/wc/status'); if (r.ok) s = await r.json(); } catch (_) { /* no server */ }
    if (!s) return offline('Encoding and decoding need the message server. Start it with ', 'python whistlecode/whistlecode.py serve', ', then open http://127.0.0.1:8000.');
    S.status = s;
    if (!s.shapes) return offline(`The message server is running but WhistleCode is not ready: ${s.message}`);
    S.shapes = s.shapes; S.maxMs = Math.max(...s.shapes.map(x => x.ms)); S.maxF = Math.max(1, ...s.shapes.flatMap(x => x.f.map(Math.abs)));
    $('#sea-snr').replaceChildren(...s.snr_choices_db.map(v => h('option', { value: v, selected: v === 15 }, `${v} dB`)));
    $('#sea-noise').replaceChildren(...s.noise_choices.map(v => h('option', { value: v }, `Encounter ${v}${v === 276 ? ' · never used to tune the decoder' : ' · used to tune the decoder'}`)));
    const L = s.limits;
    $('#enc-text').maxLength = L.max_chars; $('#enc-key').maxLength = $('#dec-key').maxLength = L.max_key_chars;
    $('#dec-drop-n').textContent = `${L.formats.map(f => f.slice(1).toUpperCase()).join(', ')} · ${L.min_rate_hz / 1000} kHz or more · up to ${Math.round(L.max_seconds)} s`;
    $('#enc-key').value = newKey();
    for (const id of ['#enc-text', '#enc-key', '#dec-key', '#dec-file']) $(id).disabled = false;
    $('#dec-drop').classList.remove('off');
    const m = s.model || {};
    $('#wc-foot').textContent = `WhistleCode runs on this computer: VAE-GMM ${String(m.checkpoint || '').split('/').pop()} (${m.sha256}…), codebook ${s.codebook_sha256}…. `
      + 'Not in this demonstration yet: echoes, absorption and Doppler. The key hides where the message is; it is not encryption.';
    const showStatus = st => {
      const el = $('#wc-status');
      el.classList.toggle('ok', !!st.ready && !st.loading);
      el.querySelector('.txt').textContent = st.loading ? 'Loading the sender and the receiver…'
        : st.ready ? 'Ready. The sender and the receiver run here, on the trained model; nothing leaves this computer.'
        : `WhistleCode could not load: ${st.message}`;
    };
    S.ready = !!s.ready;
    showStatus(s);
    if (s.loading) (async () => {                    // jobs can start already; they wait for the loading to finish
      for (;;) { await sleep(1500); try { const t = await (await fetch('api/wc/status')).json(); showStatus(t); if (!t.loading) { S.ready = t.ready; break; } } catch (_) { break; } }
      updateEnc(); recUi();
    })();
    onType(); recUi();
    if (!canRecord()) recNote(['Recording needs this page over https, or opened on the computer that runs the server. Start it with ',
                               h('code', {}, 'python whistlecode/whistlecode.py serve --lan'), ' and open the https address it prints.'], true);
  }

  function bind() {
    $('#enc-text').addEventListener('input', onType);
    $('#enc-key').addEventListener('input', onType);
    $('#enc-text').addEventListener('keydown', e => { if (e.key === 'Enter' && !$('#enc-run').disabled) hide(); });
    $('#enc-run').addEventListener('click', hide);
    $('#sea-run').addEventListener('click', sea);
    const drop = $('#dec-drop'), file = $('#dec-file');
    file.addEventListener('change', () => {
      if (!file.files[0]) return;
      setSource({ kind: 'file', file: file.files[0] });
      file.value = '';                                  // so choosing the same file again still counts
      if (!$('#dec-key').value) $('#dec-key').focus();
    });
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, () => { if (!file.disabled) drop.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, () => drop.classList.remove('over')));
    $('#dec-use-sent').addEventListener('click', () => S.sent && useInDecoder({ kind: 'job', job: S.sent.id, which: 'sent', label: 'the file you just made', sendId: S.sent.id }));
    $('#dec-use-heard').addEventListener('click', () => S.sea && useInDecoder({ kind: 'job', job: S.sea.id, which: 'heard', label: 'the file as heard in the sea', sendId: S.sea.sendId }));
    $('#dec-key').addEventListener('input', recUi);                  // recUi updates the decoder's buttons too
    $('#rec-run').addEventListener('click', () => (REC.on ? stopRec() : startRec()));
    $('#rec-dev').addEventListener('change', e => { REC.dev = e.target.value; });
    $('#dec-key').addEventListener('keydown', e => { if (e.key === 'Enter' && !$('#dec-run').disabled) decode($('#dec-key').value); });
    $('#dec-run').addEventListener('click', () => decode($('#dec-key').value));
    $('#dec-wrong').addEventListener('click', () => { const k = newKey($('#dec-key').value); decode(k, `Read with a wrong key, “${k}”`); });
  }

  /* the index: app.js marks the film's beats; below the film, these two places mark their own links */
  function setupIndex() {
    const links = { encode: $('a[href="#encode"]'), decode: $('a[href="#decode"]') };
    let raf = 0;
    const mark = () => {
      raf = 0;
      let cur = null;
      for (const id of ['encode', 'decode']) if ($(`#${id}`).getBoundingClientRect().top <= innerHeight * 0.5) cur = id;
      for (const [id, a] of Object.entries(links)) if (a) id === cur ? a.setAttribute('aria-current', 'step') : a.removeAttribute('aria-current');
    };
    addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(mark); }, { passive: true });
    addEventListener('scrollend', mark);
    for (const [id, a] of Object.entries(links)) if (a) a.addEventListener('click', e => {
      e.preventDefault();
      const el = $(`#${id}`);
      el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
      el.focus({ preventScroll: true });
    });
  }

  addEventListener('DOMContentLoaded', () => {
    if (!$('#encode')) return;
    bind(); setupIndex(); init();
  });
})();
