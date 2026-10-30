// The live layer over the rendered plant (no WebGL: a 2D canvas, so it runs in the Claude app's pane too).
// Everything is drawn in plate pixels (overlay.json, exported from build_plant.py --overlay with the plate's camera)
// under the page's pan and zoom, and every effect reads the live projections:
// - flows: pulses run along every visible conduit run, coloured by its P&ID kind; intent runs while sessions are live,
//   work in progress while GPU or heavy jobs or lanes run, verified builds faster after a merge, interlocks flash on
//   shields up, the SSH pipe flows only while remote bots report;
// - sections: hover (or the open card) draws the section's own outline with a scan band; busy sections breathe;
// - parts: GPU fins shimmer with GPU use, a capacity arc on the dial, packets on active lanes, envelopes in the fleet
//   tube, one lit pod per live session, the POODO relays' check chase, a radar at the remote site, the deck scan line.
// Loaded after index.html's script: it shares its globals (base, view, S, sum, flatOn, current, reading, SECTIONS).
(() => {
  const KC = {intent: [61, 139, 255], ok: [54, 214, 107], stop: [255, 61, 61], wip: [255, 150, 40], stale: [154, 163, 173]};
  const CYAN = [90, 224, 255], VIOLET = [110, 97, 255];
  const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  const cv = document.getElementById('fx'), ctx = cv.getContext('2d');
  let D = null, idmap = null, idW = 0, idH = 0;
  const masks = {};
  fetch(new URL('overlay.json', base)).then(r => r.json()).then(d => {
    D = d;
    for (const [name, b] of Object.entries(d.boxes || {})) {
      const im = new Image();
      im.onload = () => { masks[name] = {im, b, cache: {}}; };
      im.src = new URL(`section-${name}.png`, base).href;
    }
  }).catch(() => {});
  const idImg = new Image();
  idImg.onload = () => {
    const c = document.createElement('canvas');
    c.width = idW = idImg.width; c.height = idH = idImg.height;
    const x = c.getContext('2d', {willReadFrequently: true});
    x.drawImage(idImg, 0, 0);
    idmap = x.getImageData(0, 0, idW, idH).data;
  };
  idImg.src = new URL('sections-id.png', base).href;

  /** The section under a plate pixel (the ID map is half size), or null. */
  function sectionAt(px, py) {
    if (!idmap || !D) return null;
    const x = Math.floor(px / 2), y = Math.floor(py / 2);
    if (x < 0 || y < 0 || x >= idW || y >= idH) return null;
    const id = Math.round(idmap[(y * idW + x) * 4] / 25);
    return id ? D.sections[id - 1] : null;
  }
  function tinted(name, c) {
    const m = masks[name];
    if (!m) return null;
    const key = c.join();
    if (!m.cache[key]) {
      const t = document.createElement('canvas');
      t.width = m.b[2]; t.height = m.b[3];
      const x = t.getContext('2d');
      x.drawImage(m.im, 0, 0);
      x.globalCompositeOperation = 'source-in';
      x.fillStyle = rgba(c, 1); x.fillRect(0, 0, t.width, t.height);
      m.cache[key] = t;
    }
    return m.cache[key];
  }

  function state() {
    const ses = sum('agent_sessions'), q = sum('gpu_queue'), w = sum('running_work'), h = sum('host_resources');
    const po = sum('poodo_state'), wk = sum('workers'), mt = sum('merge_train'), cap = sum('capacity');
    const g = (h.gpus || [])[0] || {}, L = (S && S.plant.lanes) || {};
    return {live: ses.live || 0, gpuRun: q.running || 0, heavy: (w.heavy_jobs || []).length, util: (g.util || 0) / 100,
      cap: (cap.percent ?? 100) / 100, shields: !!po.shields_up, bots: wk.running || 0, merged: mt.merged || 0,
      lanes: [L.codex > 0, L.claude > 0, L.codex > 1, L.claude > 1]};
  }
  function flowAct(f, st, t) {
    if (f.kind === 'stop') return {speed: 0, glow: st.shields ? (Math.sin(t * 12) > 0 ? 1 : 0.15) : 0.3};
    if (f.dashed) return {speed: 0, glow: 0.3};
    if (f.kind === 'stale') return st.bots ? {speed: 45, glow: 0.7} : {speed: 0, glow: 0.22};
    if (f.kind === 'intent') return st.live ? {speed: 80 + 22 * Math.min(st.live, 6), glow: 1} : {speed: 16, glow: 0.35};
    if (f.kind === 'wip') {
      const on = f.name === 'gpu_to_hall' ? st.gpuRun : st.gpuRun + st.heavy + st.lanes.filter(Boolean).length;
      return on ? {speed: 90 + 30 * Math.min(on, 5), glow: 1} : {speed: 0, glow: 0.25};
    }
    return {speed: st.merged ? 110 : 45, glow: st.merged ? 1 : 0.6};      // ok: verified, shipped, learning
  }
  function path(run) {
    ctx.beginPath();
    ctx.moveTo(run[0][0], run[0][1]);
    for (let i = 1; i < run.length; i++) ctx.lineTo(run[i][0], run[i][1]);
  }
  const lerp = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k];
  // an ellipse point from an exported ring {c, u, v}: angle a from the u axis toward v
  const ring = (r, a, k = 1) => [r.c[0] + ((r.u[0] - r.c[0]) * Math.cos(a) + (r.v[0] - r.c[0]) * Math.sin(a)) * k,
    r.c[1] + ((r.u[1] - r.c[1]) * Math.cos(a) + (r.v[1] - r.c[1]) * Math.sin(a)) * k];
  const glowDot = (p, r, c, a) => {
    const g = ctx.createRadialGradient(p[0], p[1], 0, p[0], p[1], r);
    g.addColorStop(0, rgba([255, 255, 255], a)); g.addColorStop(0.25, rgba(c, a * 0.9)); g.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, 7); ctx.fill();
  };
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;      // one held frame, no motion
  const MOTES = Array.from({length: 80}, (_, i) => [((i * 7919) % 2560), ((i * 104729) % 1440), 0.3 + (i % 7) / 10]);

  function draw(t) {
    const st = state(), P = D.parts;
    ctx.globalCompositeOperation = 'lighter';
    // the deck scan: a violet line sweeping the deck every 8 s
    if (P.deck) {
      const k = (t / 8) % 1, a = lerp(P.deck[0], P.deck[1], k), b = lerp(P.deck[3], P.deck[2], k);
      ctx.lineCap = 'round';
      for (const [w, al] of [[34, 0.05], [12, 0.14], [3, 0.6]]) {
        ctx.strokeStyle = rgba(VIOLET, al); ctx.lineWidth = w;
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      }
    }
    // motes: faint drifting particles over the plant
    ctx.fillStyle = rgba(CYAN, 0.35);
    for (const m of MOTES) {
      const y = (m[1] - t * 9 * m[2]) % 1440, yy = y < 0 ? y + 1440 : y;
      ctx.globalAlpha = 0.25 + 0.25 * Math.sin(t * m[2] * 2 + m[0]);
      ctx.fillRect(m[0] + Math.sin(t * 0.3 + m[1]) * 12, yy, 3, 3);
    }
    ctx.globalAlpha = 1;
    // sections: busy ones breathe in green, the hovered (or open) one gets its outline and a scan band in cyan
    D.sections.forEach((name, i) => {
      const m = masks[name];
      if (!m) return;
      const busy = (reading(name) || [])[1], hov = name === window.PLANT.hover || name === current;
      if (busy) {
        const im = tinted(name, KC.ok);
        ctx.globalAlpha = 0.22 + 0.16 * Math.sin(t * 2.2 + i);
        ctx.drawImage(im, m.b[0], m.b[1]);
      }
      if (hov) {
        const im = tinted(name, CYAN);
        ctx.globalAlpha = 0.9;
        ctx.drawImage(im, m.b[0], m.b[1]);
        const by = m.b[1] + ((t * 0.5) % 1) * m.b[3];
        ctx.save(); ctx.beginPath(); ctx.rect(m.b[0], by - 26, m.b[2], 52); ctx.clip();
        ctx.globalAlpha = 1; ctx.drawImage(im, m.b[0], m.b[1]); ctx.drawImage(im, m.b[0], m.b[1]);
        ctx.restore();
      }
    });
    ctx.globalAlpha = 1;
    // flows
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    for (const f of D.flows) {
      const act = flowAct(f, st, t), c = KC[f.kind] || KC.stale, w = f.width;
      for (const run of f.runs) {
        path(run);
        ctx.setLineDash(f.dashed ? [w * 1.5, w * 2.5] : []);
        ctx.strokeStyle = rgba(c, 0.16 * act.glow); ctx.lineWidth = w * 2.2; ctx.stroke();
        if (act.speed) {
          const period = w * 14;
          ctx.setLineDash([w * 3.5, period - w * 3.5]);
          ctx.lineDashOffset = -((t * act.speed) % period);
          ctx.strokeStyle = rgba(c, 0.85 * act.glow); ctx.lineWidth = w * 1.1; ctx.stroke();
          ctx.strokeStyle = rgba([255, 255, 255], 0.7 * act.glow); ctx.lineWidth = w * 0.35; ctx.stroke();
        }
      }
    }
    ctx.setLineDash([]); ctx.lineDashOffset = 0;
    // GPU: a band of light running along the fins (front arcs), faster and brighter with GPU use
    if (P.gpu_fins) {
      const n = P.gpu_fins.length, head = (t * (0.6 + 5 * st.util)) % n;
      P.gpu_fins.forEach((r, k) => {
        if (!r) return;
        const d = Math.min(Math.abs(k - head), n - Math.abs(k - head)), a = (0.12 + 0.85 * Math.exp(-d * d / 3)) * (0.3 + 0.7 * st.util);
        ctx.beginPath();
        let started = false;
        for (let s = 0; s <= 32; s++) {
          const p = ring(r, s / 32 * Math.PI * 2);
          if (p[1] < r.c[1] - 4) { started = false; continue; }            // the front (lower) arc only
          started ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]); started = true;
        }
        ctx.strokeStyle = rgba(CYAN, a); ctx.lineWidth = 6; ctx.stroke();
      });
      if (st.util > 0.05) glowDot(P.gpu_fins[6].c, 150 + 60 * st.util, [255, 120, 40], 0.18 * st.util);
    }
    // the capacity dial: a lit arc from -120 deg to the fleet capacity
    if (P.dial) {
      const a0 = -2.094, a1 = a0 + 4.189 * st.cap;
      ctx.beginPath();
      for (let s = 0; s <= 40; s++) {
        const a = a0 + (a1 - a0) * s / 40, p = [P.dial.c[0] + (P.dial.u[0] - P.dial.c[0]) * Math.sin(a) + (P.dial.v[0] - P.dial.c[0]) * Math.cos(a),
          P.dial.c[1] + (P.dial.u[1] - P.dial.c[1]) * Math.sin(a) + (P.dial.v[1] - P.dial.c[1]) * Math.cos(a)];
        s ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]);
      }
      ctx.strokeStyle = rgba(st.cap < 0.5 ? KC.wip : KC.ok, 0.85); ctx.lineWidth = 7; ctx.stroke();
    }
    // lanes: packets ride the belts of the active lanes
    (P.lanes || []).forEach((ln, i) => {
      if (!ln[0] || !ln[1]) return;
      const on = st.lanes[i];
      for (let k = 0; k < (on ? 4 : 1); k++) {
        const s = on ? ((t * 0.12 + k / 4) % 1) : 0.08;
        glowDot(lerp(ln[0], ln[1], s), on ? 22 : 10, on ? KC.wip : KC.stale, on ? 0.9 : 0.35);
      }
    });
    // fleet mail: envelopes along the tube, two per live session (up to ten)
    if (P.fleet_tube && P.fleet_tube[0]) {
      const n = Math.min(10, st.live * 2);
      for (let k = 0; k < n; k++) glowDot(lerp(P.fleet_tube[0], P.fleet_tube[1], (t * 0.07 + k / n) % 1), 16, KC.intent, 0.85);
    }
    // pods: one lit pod per live session
    (P.pods || []).forEach((p, i) => {
      if (!p) return;
      const on = i < st.live;
      glowDot(p, on ? 34 + 6 * Math.sin(t * 3 + i) : 12, on ? CYAN : KC.stale, on ? 0.7 : 0.25);
    });
    // POODO: the relays' check chase (authority, evidence, budget, scope, approval)
    (P.relays || []).forEach((p, i) => {
      if (!p) return;
      const on = Math.floor(t * 2.5) % P.relays.length === i;
      glowDot(p, on ? 30 : 12, on ? KC.ok : KC.ok, on ? 0.95 : 0.3);
    });
    // the remote site: a radar sweep round the Grok dish, a ping from Hermes' beacon
    if (P.dish) {
      const r = 190, a = t * 1.4;
      const g = ctx.createConicGradient(a, P.dish[0], P.dish[1]);
      g.addColorStop(0, rgba(CYAN, 0.38)); g.addColorStop(0.12, rgba(CYAN, 0)); g.addColorStop(1, rgba(CYAN, 0));
      ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(P.dish[0], P.dish[1], r, r * 0.6, 0, 0, 7); ctx.fill();
      ctx.strokeStyle = rgba(CYAN, 0.25); ctx.lineWidth = 2; ctx.stroke();
    }
    if (P.beacon) {
      const k = (t / 2.4) % 1;
      ctx.strokeStyle = rgba(KC.wip, 0.7 * (1 - k)); ctx.lineWidth = 4;
      ctx.beginPath(); ctx.ellipse(P.beacon[0], P.beacon[1], 10 + 120 * k, (10 + 120 * k) * 0.6, 0, 0, 7); ctx.stroke();
      glowDot(P.beacon, 26, KC.wip, 0.5 + 0.5 * Math.sin(t * 5));
    }
    // the E-stop: a red halo when shields are up
    if (P.estop) glowDot(P.estop, st.shields ? 90 + 20 * Math.sin(t * 12) : 24, KC.stop, st.shields ? 0.9 : 0.35);
    // the gate lamps and the trucks' underglow
    if (P.gate && P.gate[0]) glowDot(P.gate[0], 26, KC.ok, 0.4 + 0.3 * Math.sin(t * 2));
    (P.trucks || []).forEach((p, i) => p && glowDot(p, 70, [[61, 139, 255], [54, 214, 107], [255, 61, 61], [169, 92, 240]][i], 0.16 + 0.08 * Math.sin(t * 1.5 + i)));
    if (P.hmi) glowDot(P.hmi, 60, VIOLET, 0.12 + 0.05 * Math.sin(t * 3));
    ctx.globalCompositeOperation = 'source-over';
  }

  function frame(now) {
    requestAnimationFrame(frame);
    if (!flatOn || document.hidden || !D) return;
    const dpr = Math.min(devicePixelRatio || 1, 2), W = Math.round(innerWidth * dpr), H = Math.round(innerHeight * dpr);
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.setTransform(dpr * view.s, 0, 0, dpr * view.s, dpr * view.x, dpr * view.y);
    draw(still ? 4 : now / 1000);
  }
  requestAnimationFrame(frame);
  window.FX = {sectionAt};
})();
