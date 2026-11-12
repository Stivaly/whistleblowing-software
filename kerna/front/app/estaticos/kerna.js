/* Kerna AI · interacciones del front. JavaScript sin dependencias (salvo ECharts, servido desde /estaticos), compatible con una CSP sin 'unsafe-eval'. */
(function () {
  'use strict';
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const NS = 'http://www.w3.org/2000/svg';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const leerJSON = (id) => { try { const e = document.getElementById(id); return e ? JSON.parse(e.textContent) : null; } catch (_) { return null; } };
  const G = leerJSON('glosario') || {};
  const DATOS = leerJSON('datos') || {};

  /* ---------- logo vivo: cada svg[data-logo] se reemplaza por capas que anima el compositor ---------- */
  const el = (t, a, p) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); if (p) p.appendChild(e); return e; };
  const vio = new IntersectionObserver((es) => es.forEach((e) => e.target.classList.toggle('vis', e.isIntersecting)), { rootMargin: '120px' });
  const watch = (n) => { if (!n.__w) { n.__w = 1; vio.observe(n); } };
  const layer = (host, cls, vb, st) => { const s = el('svg', { class: 'ly ' + cls + (st ? ' st' : ''), viewBox: vb, 'aria-hidden': 'true', focusable: 'false' }); host.appendChild(s); return s; };
  function buildLogo(svg) {
    const hero = svg.dataset.logo === 'hero', vb = svg.getAttribute('viewBox');
    const host = document.createElement('span');
    host.className = svg.getAttribute('class'); host.dataset.logo = svg.dataset.logo; host.dataset.ok = '1';
    ['role', 'aria-label', 'aria-hidden'].forEach((k) => { if (svg.hasAttribute(k)) host.setAttribute(k, svg.getAttribute(k)); });
    const w = svg.getAttribute('width'), h = svg.getAttribute('height'); if (w) host.style.width = w + 'px'; if (h) host.style.height = h + 'px';
    if (hero) {
      const x1 = layer(host, 'xr1', vb);
      el('circle', { class: 'orb anillo', cx: 32, cy: 32, r: 42 }, x1); el('circle', { class: 'sat-s', cx: 74, cy: 32, r: 2.4 }, x1);
      const x2 = layer(host, 'xr2', vb);
      el('circle', { class: 'orb anillo', cx: 32, cy: 32, r: 37 }, x2); el('circle', { class: 'nuc', cx: 69, cy: 32, r: 1.3 }, x2);
    }
    el('circle', { class: 'orb anillo', cx: 32, cy: 32, r: 30.5 }, layer(host, 'base', vb, 1));
    const ros = layer(host, 'lg-a roseta', vb);
    if (hero) { for (let j = 1; j < 12; j++) el('ellipse', { class: 'orb ros', cx: 32, cy: 32, rx: 27, ry: 8, transform: 'rotate(' + (j * 180 / 12) + ' 32 32)' }, ros); }
    else { for (let j = 1; j < 6; j++) el('ellipse', { class: 'orb rc', cx: 32, cy: 32, rx: 27, ry: 8, transform: 'rotate(' + (j * 30) + ' 32 32)' }, ros); }
    const cam = layer(host, 'lg-b camino', vb);
    el('ellipse', { class: 'orb guia', cx: 32, cy: 32, rx: 27, ry: 8 }, cam); el('circle', { class: 'sat', cx: 59, cy: 32, r: 3.8 }, cam);
    const n = layer(host, 'lg-c latido', vb);
    el('circle', { class: 'nuc', cx: 32, cy: 32, r: 5.4 }, n); el('circle', { class: 'nuc-l', cx: 32, cy: 32, r: 2 }, n);
    if (hero) el('circle', { class: 'ping', cx: 32, cy: 32, r: 6 }, layer(host, 'ping', vb, 1));
    svg.replaceWith(host); watch(host);
  }
  $$('svg[data-logo]').forEach((s) => { s.setAttribute('data-ok', '1'); buildLogo(s); });

  /* logo de la portada: la órbita apunta al cursor y la roseta gira con el scroll */
  const hs = $('[data-logo=hero]');
  if (hs && !RM) {
    const wrap = hs.parentElement, A = $('.lg-a', hs), B = $('.lg-b', hs), C = $('.lg-c', hs), ping = $('.ly.ping', hs), U = 100 / 92;
    let tx = 0, ty = 0, cx = 0, cy = 0, ta = 0, ca = 0, ts = 0, cs = 0, vis = true, raf = 0;
    new IntersectionObserver((e) => { vis = e[0].isIntersecting; if (vis) kick(); }).observe(wrap);
    const tick = () => {
      cx += (tx - cx) * .09; cy += (ty - cy) * .09; cs += (ts - cs) * .1;
      const d = ((ta - ca + 540) % 360) - 180; ca += d * .07;
      A.style.translate = (-cx * 2 * U) + '% ' + (-cy * 2 * U) + '%'; A.style.rotate = cs + 'deg';
      B.style.translate = (cx * 3.5 * U) + '% ' + (cy * 3.5 * U) + '%'; B.style.rotate = ca + 'deg';
      C.style.translate = (cx * 6 * U) + '% ' + (cy * 6 * U) + '%';
      raf = (Math.abs(tx - cx) + Math.abs(ty - cy) + Math.abs(d) + Math.abs(ts - cs) > .02 && vis) ? requestAnimationFrame(tick) : 0;
    };
    const kick = () => { if (!raf && vis) raf = requestAnimationFrame(tick); };
    addEventListener('pointermove', (e) => {
      if (!vis) return; const r = wrap.getBoundingClientRect(), x = e.clientX - (r.left + r.width / 2), y = e.clientY - (r.top + r.height / 2);
      tx = Math.max(-1, Math.min(1, x / (innerWidth / 2))); ty = Math.max(-1, Math.min(1, y / (innerHeight / 2))); ta = Math.atan2(y, x) * 180 / Math.PI; kick();
    }, { passive: true });
    addEventListener('scroll', () => { ts = scrollY * .18; kick(); }, { passive: true });
    wrap.addEventListener('click', () => { ping.classList.remove('go'); void ping.getBoundingClientRect(); ping.classList.add('go'); });
  }

  /* todas las animaciones infinitas comparten reloj (los cuadros coinciden y el compositor recompone una vez por cuadro) */
  (() => {
    const hechas = new WeakSet();
    const scan = () => {
      if (!document.getAnimations) return;
      document.getAnimations().forEach((a) => {
        if (hechas.has(a) || !a.effect || !a.animationName) return;
        if (a.effect.getTiming().iterations === Infinity) { hechas.add(a); a.startTime = 0; }
      });
    };
    let q = 0;
    new MutationObserver(() => { if (!q) q = requestAnimationFrame(() => { q = 0; scan(); }); }).observe(document.body, { childList: true, subtree: true });
    scan();
  })();

  /* ---------- aparición al entrar en pantalla (nunca parte de opacidad 0 en reposo) ---------- */
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (!e.isIntersecting) return; const t = e.target; io.unobserve(t);
    if (t.hasAttribute('data-rvs')) { let i = 0; for (const c of t.children) c.style.setProperty('--i', i++); }
    t.classList.add('rv-go');
  }), { rootMargin: '0px 0px -6% 0px', threshold: .04 });
  $$('main>div>*').forEach((t) => {
    if (t.classList.contains('fixed')) return;
    if (t.classList.contains('grid') && Array.from(t.children).some((c) => c.classList && c.classList.contains('card'))) t.setAttribute('data-rvs', '');
    else if (!t.hasAttribute('data-rvs')) t.setAttribute('data-rv', '');
  });
  $$('[data-rv],[data-rvs]').forEach((t) => { if (!RM) io.observe(t); });

  /* ---------- tooltips «?» ---------- */
  const tt = $('#tt'); let ttFor = null, pinned = false;
  const hace = (s) => (s < 5 ? 'ahora mismo' : s < 60 ? 'hace ' + s + ' s' : 'hace ' + Math.floor(s / 60) + ' min');
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let ultimo = Date.now(), fallo = false;
  function showTip(b) {
    if (!tt) return;
    const hh = b.closest('k-tip') || b, key = hh.getAttribute('g') || hh.getAttribute('data-tip'), g = G[key]; if (!g) return;
    ttFor = b;
    let xt = hh.getAttribute('x');
    if (key === 'envivo') {
      const q = Math.round((Date.now() - ultimo) / 1000);
      xt = fallo ? 'No se pudo actualizar la última vez; se vuelve a intentar en un minuto. Último dato bueno: ' + hace(q) + '.'
        : 'Último dato: ' + hace(q) + '. Próxima actualización en unos ' + Math.max(1, 60 - q) + ' s.';
    }
    tt.innerHTML = '<b>' + esc(g.t) + '</b>' + esc(g.q) + '<span class="l">' + esc(g.l) + '</span>' + esc(g.c) + (xt ? '<span class="l">En este caso</span>' + esc(xt) : '');
    b.setAttribute('aria-describedby', 'tt'); tt.classList.add('on');
    const r = b.getBoundingClientRect(), w = tt.offsetWidth, h = tt.offsetHeight;
    const x = Math.min(Math.max(12, r.left + r.width / 2 - w / 2), innerWidth - w - 12); let y = r.bottom + 8; if (y + h > innerHeight - 8) y = r.top - h - 8;
    tt.style.left = x + 'px'; tt.style.top = Math.max(8, y) + 'px';
  }
  function hideTip() { if (!tt) return; tt.classList.remove('on'); if (ttFor) ttFor.removeAttribute('aria-describedby'); ttFor = null; pinned = false; }
  const selTip = 'k-tip button,[data-tip]';
  const tipDe = (e) => e.target.closest && e.target.closest(selTip);
  document.addEventListener('pointerover', (e) => { const b = tipDe(e); if (b && e.pointerType === 'mouse' && !pinned) showTip(b); });
  document.addEventListener('pointerout', (e) => { if (tipDe(e) && !pinned && e.pointerType === 'mouse') hideTip(); });
  document.addEventListener('focusin', (e) => { const b = tipDe(e); if (b) showTip(b); });
  document.addEventListener('focusout', (e) => { if (tipDe(e) && !pinned) hideTip(); });
  document.addEventListener('click', (e) => { const b = tipDe(e); if (b) { if (pinned && ttFor === b) hideTip(); else { showTip(b); pinned = true; } } else if (pinned) hideTip(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideTip(); });
  addEventListener('scroll', () => { if (!pinned) hideTip(); }, { passive: true });

  /* desplazamiento suave a anclas de la misma página */
  document.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('a[href^="#"]'); if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey) return;
    const id = a.getAttribute('href').slice(1), t = id && document.getElementById(id); if (t) { e.preventDefault(); t.scrollIntoView({ behavior: RM ? 'auto' : 'smooth', block: 'start' }); }
  });

  /* ---------- contadores ---------- */
  const parse = (s) => { s = String(s).trim(); if (!/^[−-]?[\d.,]+$/.test(s)) return null; const neg = /^[−-]/.test(s); const t = s.replace(/^[−-]/, ''); return { n: (neg ? -1 : 1) * parseFloat(t.replace(/\./g, '').replace(',', '.')), d: (t.split(',')[1] || '').length }; };
  const fmtN = (n, d) => n.toLocaleString('es-CL', { minimumFractionDigits: d, maximumFractionDigits: d }).replace('-', '−');
  const animar = (nodo, desde, p) => {
    cancelAnimationFrame(nodo.__raf);
    if (RM) { nodo.textContent = fmtN(p.n, p.d); return; }
    const t0 = performance.now(), dur = 1100;
    const paso = (t) => { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); nodo.textContent = fmtN(desde + (p.n - desde) * e, p.d); if (k < 1) nodo.__raf = requestAnimationFrame(paso); };
    nodo.__raf = requestAnimationFrame(paso);
  };
  const cont = new IntersectionObserver((es) => es.forEach((e) => {
    if (!e.isIntersecting) return; const n = e.target; cont.unobserve(n); const p = parse(n.dataset.final || n.textContent);
    if (p && !n.__listo) { n.__listo = 1; animar(n, 0, p); }
  }));
  $$('.kv[data-count]').forEach((n) => { n.dataset.final = n.textContent; cont.observe(n); });
  function poner(nodo, txt) {
    if (nodo.textContent === txt) return;
    if (nodo.hasAttribute('data-count')) {
      const antes = parse(nodo.textContent), ahora = parse(txt); nodo.dataset.final = txt;
      if (ahora && antes) { animar(nodo, antes.n, ahora); return; }
    }
    nodo.textContent = txt;
  }

  /* ---------- gráficos (ECharts, SVG) ---------- */
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const redim = [];
  function mk(id, opt, vacio) {
    const c0 = document.getElementById(id); if (!c0 || !window.echarts) return;
    let c = echarts.getInstanceByDom(c0);
    if (vacio) { if (c) { c.dispose(); } c0.innerHTML = '<div class="chart-vacio">' + vacio + '</div>'; return; }
    if (!c) { c0.innerHTML = ''; c = echarts.init(c0, null, { renderer: 'svg' }); const ro = new ResizeObserver(() => c.resize()); ro.observe(c0); redim.push(c); }
    c.setOption(opt, true); c.resize();
  }
  const base = () => ({ textStyle: { fontFamily: 'Inter' }, aria: { enabled: true }, animation: !RM, animationDuration: 450, animationDurationUpdate: 200, animationEasing: 'cubicOut' });
  const fmtUF = (v) => v.toLocaleString('es-CL', { maximumFractionDigits: 0 });
  function graficos(g) {
    if (!g) return;
    const ok = css('--ok-bar'), ba = css('--bad-bar'), ink = css('--ink'), mu = css('--muted'), ln = '#DDE2EF';
    if (g.casos) {
      const c = g.casos, hay = c.con.some((v) => v) || c.sin.some((v) => v), intervalo = c.labels.length <= 8 ? 0 : Math.ceil(c.labels.length / 7) - 1;
      mk('ch-casos', {
        ...base(), grid: { left: 30, right: 4, top: 12, bottom: 22 }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { show: false },
        xAxis: { type: 'category', data: c.labels, axisLabel: { color: mu, fontSize: 10.5, interval: intervalo }, axisLine: { lineStyle: { color: ln } }, axisTick: { show: false } },
        yAxis: { type: 'value', minInterval: 1, axisLabel: { color: mu, fontSize: 10.5 }, splitLine: { lineStyle: { color: '#EEF1F8' } } },
        series: [{ name: 'Con sugerencia', type: 'bar', stack: 'a', data: c.con, itemStyle: { color: ok }, barMaxWidth: 18 },
          { name: 'Sin sugerencia', type: 'bar', stack: 'a', data: c.sin, itemStyle: { color: ba, borderRadius: [3, 3, 0, 0] } }],
      }, hay ? '' : 'Sin denuncias en el período');
    }
    if (g.lat) {
      const l = g.lat, intervalo = l.labels.length <= 8 ? 0 : Math.ceil(l.labels.length / 7) - 1, top = Math.max(l.meta * 1.4, ...l.p95, 1);
      mk('ch-lat', {
        ...base(), grid: { left: 32, right: 6, top: 24, bottom: 22 }, tooltip: { trigger: 'axis', valueFormatter: (v) => String(v).replace('.', ',') + ' s' }, legend: { top: 0, right: 0, textStyle: { color: ink, fontSize: 11 }, itemWidth: 12, itemHeight: 4 },
        xAxis: { type: 'category', data: l.labels, boundaryGap: false, axisLabel: { color: mu, fontSize: 10.5, interval: intervalo }, axisLine: { lineStyle: { color: ln } }, axisTick: { show: false } },
        yAxis: { type: 'value', axisLabel: { color: mu, fontSize: 10.5 }, splitLine: { lineStyle: { color: '#EEF1F8' } }, max: Math.ceil(top / 5) * 5 },
        series: [{ name: '9 de cada 10 casos', type: 'line', data: l.p95, smooth: true, symbol: 'none', lineStyle: { color: '#7C88B8', width: 2 }, areaStyle: { color: 'rgba(124,136,184,.18)' } },
          { name: 'Caso típico', type: 'line', data: l.p50, smooth: true, symbol: 'none', lineStyle: { color: '#3B4FB4', width: 3 }, areaStyle: { color: 'rgba(59,79,180,.22)' },
            markLine: { symbol: 'none', silent: true, data: [{ yAxis: l.meta, label: { formatter: 'Meta ' + String(l.meta).replace('.', ',') + ' s', color: ok, fontWeight: 700, fontSize: 10.5, position: 'insideEndTop' }, lineStyle: { color: ok, type: 'dashed', width: 2 } }] } }],
      }, l.labels.length ? '' : 'Sin mediciones de tiempo en el período');
    }
    if (g.heat !== undefined) {
      const h = g.heat;
      mk('ch-heat', h && {
        ...base(), grid: { left: 30, right: 4, top: 4, bottom: 46 }, tooltip: { formatter: (p) => h.dias[p.value[1]] + ' ' + h.franjas[p.value[0]] + ': ' + p.value[2] + (p.value[2] === 1 ? ' denuncia' : ' denuncias') },
        xAxis: { type: 'category', data: h.franjas, splitArea: { show: false }, axisLabel: { color: mu, fontSize: 10, interval: 0, formatter: (v) => parseInt(v) + ' h' }, axisLine: { show: false }, axisTick: { show: false } },
        yAxis: { type: 'category', data: h.dias, inverse: true, axisLabel: { color: mu, fontSize: 10.5 }, axisLine: { show: false }, axisTick: { show: false } },
        visualMap: { min: 0, max: h.max, orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 10, itemHeight: 80, text: ['Más', 'Menos'], textStyle: { color: mu, fontSize: 10.5 }, inRange: { color: ['#EEF1FB', '#9AA8E0', '#3B4FB4', '#1C2A6B'] } },
        series: [{ type: 'heatmap', data: h.datos, itemStyle: { borderColor: '#fff', borderWidth: 1.5, borderRadius: 2 }, label: { show: true, fontSize: 10, formatter: (p) => (p.value[2] >= h.max * .4 ? (p.value[2] >= h.max * .65 ? '{w|' + p.value[2] + '}' : '{d|' + p.value[2] + '}') : ''), rich: { w: { color: '#fff', fontSize: 10 }, d: { color: '#0F1736', fontSize: 10 } } } }],
      }, h ? '' : 'Sin denuncias en el período');
    }
    if (g.clientes) {
      const cs = ['#1C2A6B', '#6E7FD0', '#B7C0E8', '#3B4FB4', '#8E9AD0', '#DCE1F5'], c = g.clientes, hay = c.series.some((s) => s.d.some((v) => v));
      mk('ch-cli', {
        ...base(), grid: { left: 28, right: 6, top: 40, bottom: 22 }, tooltip: { trigger: 'axis' }, legend: { top: 0, left: 0, textStyle: { color: ink, fontSize: 11 }, itemWidth: 10, itemHeight: 10 },
        xAxis: { type: 'category', boundaryGap: false, data: c.labels, axisLabel: { color: mu, fontSize: 10.5, interval: Math.ceil(c.labels.length / 7) - 1 }, axisTick: { show: false }, axisLine: { lineStyle: { color: ln } } },
        yAxis: { type: 'value', minInterval: 1, axisLabel: { color: mu, fontSize: 10.5 }, splitLine: { lineStyle: { color: '#EEF1F8' } } },
        series: c.series.map((s, i) => ({ name: s.n, type: 'line', stack: 't', smooth: true, symbol: 'none', data: s.d, itemStyle: { color: cs[i % cs.length] }, lineStyle: { width: 1.5, color: cs[i % cs.length] }, areaStyle: { color: cs[i % cs.length], opacity: .9 } })),
      }, hay ? '' : 'Sin denuncias en el período');
    }
    if (g.proy) {
      const p = g.proy;
      mk('ch-proy', {
        ...base(), grid: { left: 56, right: 6, top: 28, bottom: 22 }, tooltip: { trigger: 'axis', valueFormatter: (v) => fmtUF(v) + ' UF' }, legend: { top: 0, left: 0, textStyle: { color: ink, fontSize: 11 }, itemWidth: 10, itemHeight: 10 },
        xAxis: { type: 'category', data: p.labels, axisLabel: { color: mu, fontSize: 10.5 }, axisTick: { show: false } },
        yAxis: { type: 'value', axisLabel: { color: mu, fontSize: 10.5, formatter: (v) => fmtUF(v) + ' UF' }, splitLine: { lineStyle: { color: '#EEF1F8' } } },
        series: [{ name: 'Ventas', type: 'bar', data: p.ventas, itemStyle: { color: '#3B4FB4', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 26 },
          { name: 'Costos', type: 'bar', data: p.costos, itemStyle: { color: '#A8B1CC', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 26 },
          { name: 'Utilidad', type: 'bar', data: p.utilidad, itemStyle: { color: ok, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 26 }],
      });
    }
  }
  graficos(DATOS.graficos);
  addEventListener('resize', () => redim.forEach((c) => c.resize()));

  /* ---------- En vivo: el Resumen consulta /api/metricas y /api/proveedores cada 60 s si la pestaña está visible ---------- */
  const PROV_E = { operativo: 'ok', degradado: 'warn', caido: 'bad', sin_informacion: 'na' };
  const PROV_T = { operativo: 'Operativo', degradado: 'Degradado', caido: 'Caído', sin_informacion: 'Sin información' };
  const ICO = { ok: 'circle-check', warn: 'triangle-alert', bad: 'octagon-alert', na: 'circle-minus' };
  const setCls = (n, e) => { n.className = n.className.replace(/\bs-(ok|warn|bad|na)\b/g, '').trim() + ' s-' + e; };
  function aplicar(m) {
    $$('[data-t]').forEach((n) => { const k = n.dataset.t; if (k in m.t) poner(n, m.t[k]); });
    $$('[data-s]').forEach((n) => { const k = n.dataset.s; if (k in m.s) setCls(n, m.s[k]); });
    $$('[data-w]').forEach((n) => { const k = n.dataset.w; if (k in m.w) n.style.width = m.w[k] + '%'; });
    $$('[data-l]').forEach((n) => { const k = n.dataset.l; if (k in m.l) n.style.left = m.l[k] + '%'; });
    $$('[data-rot]').forEach((n) => { const k = n.dataset.rot; if (k in m.rot) n.style.transform = 'rotate(' + m.rot[k] + 'deg)'; });
    $$('[data-d]').forEach((n) => { const k = n.dataset.d; if (k in m.d) n.setAttribute('d', m.d[k]); });
    $$('[data-i]').forEach((n) => { const k = n.dataset.i; if (k in m.ico) n.setAttribute('href', '/estaticos/iconos.svg#' + m.ico[k]); });
    $$('[data-xk]').forEach((n) => { const k = n.dataset.xk; if (k in m.x) n.setAttribute('x', m.x[k]); });
    $$('.kt').forEach((n) => { n.classList.add('upd'); setTimeout(() => n.classList.remove('upd'), 900); });
  }
  function proveedores(p) {
    (p.proveedores || []).forEach((x) => {
      const e = PROV_E[x.estado] || 'na', li = document.getElementById('pv-' + x.id); if (!li) return;
      setCls(li, e); const u = $('use', li); if (u) u.setAttribute('href', '/estaticos/iconos.svg#' + ICO[e]);
      const t = $('[data-pt]', li); if (t) t.textContent = PROV_T[x.estado] || 'Sin información';
      const k = $('k-tip', li); if (k) k.setAttribute('x', x.mensaje);
    });
  }
  const vd = $('.vd'); let pulso = 0, cargando = false;
  async function refrescar() {
    if (cargando || document.hidden) return;
    cargando = true;
    try {
      const dias = (DATOS.graficos && DATOS.graficos.dias) || 7, o = { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } };
      const [rm, rp] = await Promise.all([fetch('/api/metricas?dias=' + dias, o), fetch('/api/proveedores', o)]);
      if (rm.status === 401 || rp.status === 401) { location.href = '/acceso'; return; }
      if (!rm.ok) throw new Error('metricas');
      const m = await rm.json(); if (rp.ok) proveedores(await rp.json());
      if (m.vista) { aplicar(m.vista.mapas); graficos(m.vista.graficos); }
      ultimo = Date.now(); fallo = false;
      if (vd) { vd.classList.remove('b1', 'b2'); void vd.offsetWidth; vd.classList.add(++pulso % 2 ? 'b1' : 'b2'); vd.style.background = ''; }
    } catch (_) { fallo = true; if (vd) vd.style.background = css('--warn-bar'); }
    cargando = false;
  }
  if ($('[data-vivo]')) {
    setInterval(refrescar, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden && Date.now() - ultimo > 60000) refrescar(); });
    if (vd && !RM) vd.classList.add('b1');
  }
})();
