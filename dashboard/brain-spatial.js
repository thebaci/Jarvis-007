/* Jarvis 007: local perspective brain, real vault memories and no external assets. */
(function () {
  'use strict';
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  const end = n => n && typeof n === 'object' ? n.id : n;
  function hash(s) { let n = 2166136261; for (const c of String(s)) n = Math.imul(n ^ c.charCodeAt(0), 16777619); return n >>> 0; }
  // Jarvis 007: two hemispheres with a central fissure and restrained cortical folds.
  function cortex(u, v, side) {
    const fold = 1 + .035 * Math.sin(13 * u + 3 * Math.sin(v * 5)) * Math.sin(v * 11);
    let y = 142 * Math.cos(v) * fold + 25 + 14 * Math.sin(u) * Math.sin(v);
    if (y < -30) y = -30 + (y + 30) * .65;
    return [208 * Math.cos(u) * Math.sin(v) * fold,
      y,
      side * (7 + 102 * Math.sin(u) * Math.sin(v) * fold)];
  }
  function memoryPosition(id) {
    const a = hash(id), b = hash('latitude:' + id);
    const u = .08 + (a % 100003) / 100003 * (Math.PI - .16);
    const v = .16 + (b % 100019) / 100019 * (Math.PI - .32);
    const p = cortex(u, v, a & 1 ? 1 : -1);
    const depth = .76 + (hash('depth:' + id) % 1000) / 1000 * .24;
    return p.map(n => n * depth);
  }
  function project(p, yaw, pitch, zoom, width, height, pan) {
    const x = p[0] * Math.cos(yaw) + p[2] * Math.sin(yaw);
    const z = -p[0] * Math.sin(yaw) + p[2] * Math.cos(yaw);
    const y = p[1] * Math.cos(pitch) - z * Math.sin(pitch);
    const depth = p[1] * Math.sin(pitch) + z * Math.cos(pitch);
    const scale = Math.min(width / 520, height / 480) * zoom * 820 / (820 - depth);
    return { x: width / 2 + x * scale + pan[0], y: height / 2 - y * scale + pan[1], z: depth, scale };
  }
  class BrainSpatial extends window.JavisGraph {
    constructor(container) {
      super(container);
      this._data = { nodes: [], links: [] }; this._yaw = .34; this._pitch = -.12; this._zoom = 1;
      this._pan = [0, 0]; this._pointers = new Map(); this._points = [];
      this._paused = false; this._last = 0; this._interactUntil = 0;
      this._motion = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
      this._orbit = !(this._motion && this._motion.matches);
      this.canvas = document.createElement('canvas'); this.canvas.tabIndex = 0;
      this.canvas.className = 'brain-spatial-canvas';
      this.canvas.setAttribute('aria-label', '3D memory brain. Drag to rotate, pinch or use plus and minus to zoom. Arrow keys rotate. Page Up and Page Down browse memories. Enter opens the selected memory.');
      container.replaceChildren(this.canvas); container.classList.add('brain-spatial');
      this.ctx = this.canvas.getContext('2d');
      this.toolbar = document.createElement('div'); this.toolbar.className = 'brain-spatial-toolbar';
      this._button('−', 'Zoom out', () => this.zoomBy(.8)); this._button('+', 'Zoom in', () => this.zoomBy(1.25));
      this._button('Reset', 'Reset brain view', () => this.refit());
      this.orbitButton = this._button('Slow spin', 'Toggle slow rotation', () => {
        this._orbit = !this._orbit; this._syncSpin(); this._invalidate();
      }); this._syncSpin(); container.append(this.toolbar);
      this.detail = document.createElement('div'); this.detail.className = 'brain-memory-detail'; this.detail.hidden = true;
      this.title = document.createElement('strong'); this.path = document.createElement('span');
      this.openButton = document.createElement('button'); this.openButton.type = 'button'; this.openButton.textContent = 'Open memory';
      this.openButton.onclick = () => { if (this._selected && window.onGraphNodeClick) window.onGraphNodeClick(this._selected); };
      this.detail.append(this.title, this.path, this.openButton); container.append(this.detail);
      this.status = document.createElement('div'); this.status.className = 'brain-spatial-status'; this.status.setAttribute('role', 'status');
      container.append(this.status);
      const self = this;
      // Jarvis 007: preserve category filters, realtime updates and timelapse graphData contract.
      this.graph = {
        graphData(data) {
          if (data === undefined) return self._data;
          self._data = data;
          data.nodes.forEach(n => { n.__brainPosition = memoryPosition(n.id); });
          if (self._selected && !data.nodes.some(n => n.id === self._selected.id)) self._select(null);
          self.status.textContent = `${data.nodes.length} memories · ${data.links.length} links${data.nodes.length ? ' · Drag to explore' : ' · No memories in this view'}`;
          self._invalidate(); return this;
        },
        warmupTicks() { return this; }, linkColor() { self._invalidate(); return this; },
        pauseAnimation() { self.pause(); return this; }, resumeAnimation() { self.wake(); return this; }
      };
      this._shell = [];
      for (const side of [-1, 1]) {
        for (let row = 1; row < 19; row++) {
          const line = []; for (let i = 0; i <= 55; i++) line.push(cortex(i / 55 * Math.PI, row / 19 * Math.PI + .045 * Math.sin(i / 55 * Math.PI * 14 + row * 1.7) + .025 * Math.sin(i / 55 * Math.PI * 23 - row * .4), side)); this._shell.push(line);
        }
        for (let col = 1; col < 16; col++) {
          const line = []; for (let i = 0; i <= 40; i++) line.push(cortex(col / 16 * Math.PI + .035 * Math.sin(i / 40 * Math.PI * 15 + col), i / 40 * Math.PI, side)); this._shell.push(line);
        }
      }
      // Jarvis 007: cerebellum and brainstem are visual scaffolding, never represented as memory records.
      for (let row = 0; row < 10; row++) {
        const line = []; for (let i = 0; i <= 60; i++) { const a = i / 60 * Math.PI * 2, v = (row + .5) / 10 * Math.PI; line.push([-88 + 77 * Math.sin(v) * Math.cos(a), -105 + 47 * Math.cos(v), 64 * Math.sin(v) * Math.sin(a)]); } this._shell.push(line);
      }
      for (let row = 0; row < 10; row++) {
        const line = []; for (let i = 0; i <= 32; i++) { const a = i / 32 * Math.PI * 2; line.push([-20 + row * 3 + (23 - row) * Math.cos(a), -126 - row * 8, (22 - row) * Math.sin(a)]); } this._shell.push(line);
      }
      for (let col = 0; col < 14; col++) {
        const a = col / 14 * Math.PI * 2, line = [];
        for (let i = 0; i <= 40; i++) { const v = i / 40 * Math.PI; line.push([-88 + 77 * Math.sin(v) * Math.cos(a), -105 + 47 * Math.cos(v), 64 * Math.sin(v) * Math.sin(a)]); }
        this._shell.push(line);
      }
      for (let col = 0; col < 8; col++) {
        const a = col / 8 * Math.PI * 2, line = [];
        for (let i = 0; i <= 9; i++) line.push([-20 + i * 3 + (23 - i) * Math.cos(a), -126 - i * 8, (22 - i) * Math.sin(a)]);
        this._shell.push(line);
      }
      this._bind();
      this._resizeObserver = new ResizeObserver(() => this.resize()); this._resizeObserver.observe(container);
      this._visibility = () => { if (document.hidden) this._cancel(); else this._invalidate(); };
      document.addEventListener('visibilitychange', this._visibility);
      this._motionChange = () => { if (this._motion.matches) { this._orbit = false; this._syncSpin(); this._invalidate(); } };
      if (this._motion && this._motion.addEventListener) this._motion.addEventListener('change', this._motionChange);
      this.resize();
    }
    _button(text, label, action) {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = text; b.setAttribute('aria-label', label); b.title = label; b.onclick = action; this.toolbar.append(b); return b;
    }
    _syncSpin() { this.orbitButton.setAttribute('aria-pressed', String(this._orbit)); }
    async load(query = 'source=all') {
      const generation = this._generation = (this._generation || 0) + 1;
      const res = await fetch(`/graph?${query}&orphans=1`); const data = await res.json();
      if (generation !== this._generation) return data;
      if (!res.ok) throw new Error(data.error || 'Could not load memories');
      const nodes = Array.isArray(data.nodes) ? data.nodes : []; this._catMap = null; this._prep(nodes);
      window.__javisCatIdx = this._catMap; window.__javisCatMap = _mapFromIdx(this._catMap);
      const ids = new Set(nodes.map(n => n.id));
      const links = (data.edges || []).filter(e => ids.has(end(e.source)) && ids.has(end(e.target))).map(e => ({ source: end(e.source), target: end(e.target) }));
      this.graph.graphData({ nodes, links }); this.resize(); return data;
    }
    _bind() {
      const c = this.canvas;
      c.addEventListener('wheel', e => { e.preventDefault(); this.zoomBy(Math.exp(-clamp(e.deltaY, -200, 200) * .0025)); }, { passive: false });
      c.addEventListener('pointerdown', e => {
        c.focus(); this._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY }); c.setPointerCapture(e.pointerId);
        this._gesture = { x: e.clientX, y: e.clientY, moved: 0 }; this._pinch = this._distance(); this._interactUntil = performance.now() + 2500;
      });
      c.addEventListener('pointermove', e => {
        if (this._pointers.has(e.pointerId)) {
          const prev = this._pointers.get(e.pointerId); this._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
          const dx = e.clientX - prev.x, dy = e.clientY - prev.y; if (this._gesture) this._gesture.moved += Math.abs(dx) + Math.abs(dy);
          if (this._pointers.size === 2) { const d = this._distance(); if (d && this._pinch) this.zoomBy(d / this._pinch); this._pinch = d; }
          else if (e.shiftKey) { this._pan[0] += dx; this._pan[1] += dy; }
          else { this._yaw += dx * .006; this._pitch = clamp(this._pitch + dy * .006, -1.25, 1.25); }
          this._interactUntil = performance.now() + 2500; this._invalidate();
        } else {
          const n = this._hit(e.clientX, e.clientY); this._hoverId = n ? n.id : null; c.title = n ? String(n.label || n.id) : 'Drag to rotate · Scroll to zoom · Shift-drag to pan'; c.style.cursor = n ? 'pointer' : 'grab'; this._invalidate();
        }
      });
      c.addEventListener('pointerup', e => {
        if (this._gesture && this._gesture.moved < 7 && this._pointers.size === 1) this._select(this._hit(e.clientX, e.clientY));
        this._pointers.delete(e.pointerId); this._pinch = this._distance(); this._gesture = null; this._invalidate();
      });
      for (const event of ['pointercancel', 'lostpointercapture']) c.addEventListener(event, e => { this._pointers.delete(e.pointerId); this._gesture = null; this._pinch = 0; });
      c.addEventListener('pointerleave', () => { this._hoverId = null; this._invalidate(); });
      c.addEventListener('keydown', e => {
        if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','0',' ','Enter','Escape','Tab','PageDown','PageUp'].includes(e.key)) return;
        if (e.key === 'Tab') return;
        e.preventDefault(); this._interactUntil = performance.now() + 2500;
        if (e.key === 'ArrowLeft') this._yaw -= .12; if (e.key === 'ArrowRight') this._yaw += .12;
        if (e.key === 'ArrowUp') this._pitch = clamp(this._pitch - .1, -1.25, 1.25); if (e.key === 'ArrowDown') this._pitch = clamp(this._pitch + .1, -1.25, 1.25);
        if (e.key === '+' || e.key === '=') this.zoomBy(1.2); if (e.key === '-') this.zoomBy(1 / 1.2); if (e.key === '0') this.refit();
        if (e.key === ' ') { this._orbit = !this._orbit; this._syncSpin(); }
        if (e.key === 'Escape') this._select(null);
        if (e.key === 'PageDown' || e.key === 'PageUp') {
          const list = this._data.nodes.filter(n => !this._catFilter || n.__cat === this._catFilter);
          const index = list.findIndex(n => n.id === this._selected?.id);
          this._select(list[(index + (e.key === 'PageDown' ? 1 : list.length - 1)) % list.length] || null);
        }
        if (e.key === 'Enter') { if (!this._selected) this._select(this._data.nodes[0] || null); else this.openButton.click(); }
        this._invalidate();
      });
    }
    _distance() { const p = [...this._pointers.values()]; return p.length === 2 ? Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y) : 0; }
    _hit(x, y) {
      const r = this.canvas.getBoundingClientRect(); x -= r.left; y -= r.top;
      return [...this._points].reverse().find(p => (!this._catFilter || p.node.__cat === this._catFilter) && Math.hypot(p.x - x, p.y - y) < clamp(p.radius + 5, 9, 22))?.node || null;
    }
    _select(n) {
      this._selected = n; this.detail.hidden = !n;
      if (n) { this.title.textContent = String(n.label || n.id); this.path.textContent = String(n.path || n.id); }
      this._interactUntil = n ? Infinity : performance.now() + 1200; this._invalidate();
    }
    zoomBy(factor) { this._zoom = clamp(this._zoom * factor, .45, 5); this._interactUntil = performance.now() + 2500; this._invalidate(); }
    refit() { this._yaw = .34; this._pitch = -.12; this._zoom = 1; this._pan = [0, 0]; this._select(null); this.resize(); }
    resize() {
      const w = this.container.clientWidth || 800, h = this.container.clientHeight || 600, dpr = Math.min(window.devicePixelRatio || 1, 2);
      this._width = w; this._height = h; this.canvas.width = Math.round(w * dpr); this.canvas.height = Math.round(h * dpr); this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0); this._invalidate();
    }
    _project(p) { return project(p, this._yaw, this._pitch, this._zoom, this._width, this._height, this._pan); }
    _draw() {
      const c = this.ctx, w = this._width, h = this._height, light = document.documentElement.getAttribute('data-theme') === 'light';
      c.clearRect(0, 0, w, h);
      const gold = light ? '123,86,26' : '231,182,94', blue = light ? '27,116,151' : '77,184,225';
      const halo = c.createRadialGradient(w/2,h/2,10,w/2,h/2,Math.max(1,Math.min(w,h)*.48));
      halo.addColorStop(0,`rgba(${blue},.085)`);halo.addColorStop(1,`rgba(${blue},0)`);c.fillStyle=halo;c.fillRect(0,0,w,h);
      // Jarvis 007: restrained holographic stage; it conveys depth without fake statistics.
      for (let ring=0;ring<3;ring++) { c.strokeStyle=`rgba(${ring===1?gold:blue},${light?.14:.22})`; c.lineWidth=.7; c.beginPath(); c.ellipse(w/2+this._pan[0],h*.87+this._pan[1],Math.min(w*.36,h*.36)*(1-ring*.12),h*.045*(1-ring*.12),0,0,Math.PI*2); c.stroke(); }
      for (const line of this._shell) {
        c.beginPath(); let avg=0;
        line.forEach((p,i)=>{const q=this._project(p);avg+=q.z;if(i)c.lineTo(q.x,q.y);else c.moveTo(q.x,q.y);});
        c.strokeStyle=`rgba(${gold},${clamp(.36+avg/line.length/600,.07,.60)})`;c.lineWidth=.8;c.stroke();
      }
      this._points = this._data.nodes.map(node=>{const p=this._project(node.__brainPosition);return {...p,node,radius:clamp((2+Math.sqrt(Math.min(40,node.links||0))*.25)*p.scale,1.7,7)};}).sort((a,b)=>a.z-b.z);
      const map=new Map(this._points.map(p=>[p.node.id,p])); const active=this._selected?.id||this._hoverId;
      for (const l of this._data.links) { const a=map.get(end(l.source)),b=map.get(end(l.target));if(!a||!b)continue;const on=active&&(a.node.id===active||b.node.id===active); c.strokeStyle=`rgba(${on?blue:gold},${on?.65:active?.035:.13})`;c.lineWidth=on?1.2:.6;c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.stroke(); }
      for (const p of this._points) {
        const dim=this._catFilter&&p.node.__cat!==this._catFilter, on=p.node.id===active;
        c.globalAlpha=dim?.1:clamp(.55+p.z/500,.25,1); const radius=p.radius*(on?1.65:1);
        c.fillStyle=on?`rgb(${blue})`:`rgb(${gold})`;c.shadowColor=on?`rgb(${blue})`:`rgb(${gold})`;c.shadowBlur=on?18:8;
        c.beginPath();c.arc(p.x,p.y,radius,0,Math.PI*2);c.fill();c.shadowBlur=0;
        c.strokeStyle=p.node.__c||`rgb(${blue})`;c.lineWidth=1;c.stroke();
        c.fillStyle=light?'#5c4217':'#fff3d2';c.beginPath();c.arc(p.x,p.y,Math.max(.7,radius*.38),0,Math.PI*2);c.fill();
        if(on||this._zoom>2.3&&!dim&&p.z>25) { c.font='11px system-ui';c.fillStyle=light?'#26323d':'#e5edf2'; c.fillText(String(p.node.label||p.node.id).slice(0,42),p.x+radius+6,p.y-5); }
      }
      c.globalAlpha=1;
    }
    _cancel() { if(this._raf!=null)cancelAnimationFrame(this._raf);this._raf=null;this._last=0; }
    _invalidate() {
      if(this._paused||document.hidden||this._raf!=null)return;
      this._raf=requestAnimationFrame(time=>{this._raf=null;if(this._paused||document.hidden)return;
        if(!this._orbit||!this._last||time-this._last>=32){const dt=this._last?Math.min((time-this._last)/1000,.1):0;this._last=time;if(this._orbit&&time>this._interactUntil&&!this._pointers.size&&!this._selected&&!this._hoverId)this._yaw+=dt*.055;this._draw();}
        if(this._orbit||this._pointers.size)this._invalidate();
      });
    }
    pause(){this._paused=true;this._cancel();} wake(){this._paused=false;this._invalidate();} resume(){this.wake();}
    _nhipVe(){this._invalidate();} _recolor(){super._recolor();this._invalidate();}
    spotlightCategory(cat){const r=super.spotlightCategory(cat);this._invalidate();return r;}
    destroy(){this.pause();this.stopTimelapse();this._resizeObserver.disconnect();document.removeEventListener('visibilitychange',this._visibility);if(this._motion?.removeEventListener)this._motion.removeEventListener('change',this._motionChange);}
  }
  window.JarvisBrainGeometry = { cortex, memoryPosition, project };
  // Jarvis 007: graph.js declares a global lexical class; app.js uses that binding.
  if (typeof JavisGraph !== 'undefined') JavisGraph = BrainSpatial;
  window.JavisGraph = BrainSpatial;
})();
