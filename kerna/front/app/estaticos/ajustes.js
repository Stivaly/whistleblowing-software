/* Ajustes: estado en memoria, previsualización orbital viva, estados de guardado y teclado.
   Paneles azules: elementos persistentes (se crean una vez). Un control solo cambia `transform` (ángulo del satélite) y `opacity`
   con transición; las órbitas giran lento en capas aparte (compositor, sin repintar). El arco de «Meta de respuesta» anima su trazo. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  let D; try { D = JSON.parse($('#ajustes-datos').textContent); } catch (_) { return; }
  const clon = (x) => JSON.parse(JSON.stringify(x));
  const rec = D.recomendado, M = D.modelos;
  let base = clon(D.valores), s = clon(D.valores);
  const items = {}; D.grupos.forEach((g) => g.items.forEach((it) => { items[it.k] = it; }));
  const fmt = (it, v) => {
    if (it.t === 'sw') return v ? 'Encendido' : 'Apagado';
    if (it.t === 'rg') return v === 0 && it.cero ? it.cero : v + ' ' + (v === 1 ? it.u[0] : it.u[1]);
    if (it.t === 'sg') return (it.o.find((o) => o.v === v) || {}).t;
    if (it.t === 'ch') return v.length ? v.map((x) => it.o.find((o) => o.v === x).t).join(', ') : 'Nadie';
    return v.filter((m) => m.on).map((m) => M[m.v][0]).join(' → ') || 'Ninguno';
  };
  const aviso = (k, v) => k === 'envios' && v > 7 ? 'Con tantos casos juntos puede superarse el límite del proveedor de IA.' : k === 'reintentos' && v === 0 ? 'Los casos fallidos quedarán en revisión manual sin nuevo intento.' : '';
  const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- paneles azules ---------- */
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, at, padre) => { const n = document.createElementNS(NS, tag); Object.keys(at || {}).forEach((k) => n.setAttribute(k, at[k])); if (padre) padre.appendChild(n); return n; };
  const capa = (host, cl, vb, origen) => { const v = el('svg', { viewBox: vb, class: 'ap-l ' + cl, 'aria-hidden': 'true', focusable: 'false' }); if (origen) v.style.transformOrigin = origen; host.appendChild(v); return v; };
  /* satélite: grupo que gira alrededor del centro; su ángulo y opacidad se animan con CSS */
  const sat = (padre, cl, k, cx, cy, r, ox, oy) => { const g = el('g', { class: 'sg' }, padre); g.style.transformOrigin = ox + 'px ' + oy + 'px'; el('circle', { class: cl + ' hk', 'data-k': k, cx, cy, r }, g); return g; };
  const poner = (g, grados, on) => { g.style.transform = 'rotate(' + grados + 'deg)'; g.style.opacity = on ? '1' : '0'; };
  const N = (n) => Array.from({ length: n }, (_, i) => i);
  const nucleo = (p, cx, cy, r) => { el('circle', { class: 'acore', cx, cy, r }, p); el('circle', { class: 'acore-l', cx, cy, r: r * 0.35 }, p); };

  const ESC = {
    proc(h) {
      const l1 = capa(h, 'ap-l1', '0 0 300 300'), l2 = capa(h, 'ap-l2', '0 0 300 300'), st = capa(h, 'ap-s', '0 0 300 300');
      el('circle', { class: 'ao', cx: 150, cy: 150, r: 120 }, l1); el('circle', { class: 'ao', cx: 150, cy: 150, r: 72 }, l2);
      const E = N(10).map(() => sat(l1, 'as', 'envios', 270, 150, 10, 150, 150)), R = N(5).map(() => sat(l2, 'as2', 'reintentos', 222, 150, 6, 150, 150));
      const pu = el('circle', { class: 'pulse-ring hk', 'data-k': 'reprocesar', cx: 150, cy: 150, r: 46 }, st); nucleo(st, 150, 150, 26);
      return (v) => { E.forEach((g, i) => poner(g, i * 360 / Math.max(1, v.envios), i < v.envios)); R.forEach((g, i) => poner(g, i * 360 / Math.max(1, v.reintentos) + 20, i < v.reintentos));
        pu.style.opacity = v.reprocesar ? '' : '0'; pu.classList.toggle('on', !!v.reprocesar); };
    },
    ia(h) {
      const l1 = capa(h, 'ap-l1', '0 0 300 300'), l2 = capa(h, 'ap-l2', '0 0 300 300'), st = capa(h, 'ap-s', '0 0 300 300');
      const rE = el('circle', { class: 'ao hk', 'data-k': 'evaluador', cx: 150, cy: 150, r: 132 }, l1), C = N(20).map(() => sat(l1, 'cd', 'candidatos', 282, 150, 4, 150, 150)), sE = sat(l1, 'as', 'evaluador', 282, 150, 9, 150, 150);
      const rA = el('circle', { class: 'ao hk', 'data-k': 'cadena', cx: 150, cy: 150, r: 62 }, l2), rB = el('circle', { class: 'ao hk', 'data-k': 'cadena', cx: 150, cy: 150, r: 96 }, l2);
      const sA = sat(l2, 'as', 'cadena', 212, 150, 11, 150, 150), sB = sat(l2, 'as', 'cadena', 246, 150, 8, 150, 150); nucleo(st, 150, 150, 20);
      return (v) => { const a = v.cadena[0] && v.cadena[0].on, b = v.cadena[1] && v.cadena[1].on, nc = Math.max(3, v.candidatos);
        rE.setAttribute('class', 'ao hk ' + (v.evaluador ? 'solid' : 'dim')); rA.setAttribute('class', 'ao hk ' + (a ? 'solid' : 'dim')); rB.setAttribute('class', 'ao hk ' + (b ? 'solid' : 'dim'));
        C.forEach((g, i) => poner(g, i * 360 / nc + 9, v.evaluador && i < v.candidatos)); poner(sE, 40, v.evaluador); poner(sA, 200, a); poner(sB, 120, b); };
    },
    comp(h) {
      const W = 280, CY = 28, l1 = capa(h, 'ap-l1', '0 0 280 78', '50% 36%'), l2 = capa(h, 'ap-l2', '0 0 280 78', '50% 36%'), st = capa(h, 'ap-s', '0 0 280 78');
      el('circle', { class: 'ao', cx: 140, cy: CY, r: 22 }, l1); el('circle', { class: 'ao', cx: 140, cy: CY, r: 32, style: 'opacity:.55' }, l2);
      const eq = [['analista', 'Analistas', 30], ['comite', 'Comité', 82], ['auditoria', 'Auditoría', 198], ['legal', 'Fiscalía', 250]];
      const eqh = document.createElement('div'); eqh.className = 'ap-eq'; eqh.setAttribute('aria-hidden', 'true'); h.appendChild(eqh);
      const T = eq.map(([k, t, x]) => { const ln = el('line', { class: 'alink', x1: 140, y1: CY, x2: x, y2: CY }, st); el('circle', { class: 'team', cx: x, cy: CY, r: 17 }, st);
        const c1 = el('circle', { class: 'team-on hk', 'data-k': 'compartir', cx: x, cy: CY, r: 17 }, st), tx = document.createElement('span'); tx.style.left = (x / W * 100) + '%'; tx.textContent = t; eqh.appendChild(tx); return { k, ln, c1, tx }; });
      nucleo(st, 140, CY, 12);
      return (v) => T.forEach((o) => { const on = v.compartir.includes(o.k); o.ln.style.opacity = on ? '1' : '0'; o.c1.style.opacity = on ? '1' : '0'; o.c1.style.transform = on ? 'scale(1)' : 'scale(.4)'; o.tx.classList.toggle('on', on); });
    },
    plazos(h) {
      const l1 = capa(h, 'ap-l1', '0 0 300 300'), st = capa(h, 'ap-s', '0 0 300 300');
      el('circle', { class: 'ao', cx: 150, cy: 150, r: 140, style: 'opacity:.5' }, l1);
      el('circle', { class: 'ao', cx: 150, cy: 150, r: 115 }, st); const arc = el('circle', { class: 'arc hk', 'data-k': 'maxresp', cx: 150, cy: 150, r: 115, pathLength: 100, transform: 'rotate(-90 150 150)' }, st); arc.style.strokeDasharray = '0 100';
      el('circle', { class: 'ao', cx: 150, cy: 150, r: 88, style: 'opacity:.5' }, st); const arc2 = el('circle', { class: 'arc2 hk', 'data-k': 'alerta', cx: 150, cy: 150, r: 88, pathLength: 100, transform: 'rotate(-90 150 150)' }, st); arc2.style.strokeDasharray = '0 100';
      const sg = sat(st, 'as', 'maxresp', 265, 150, 11, 150, 150), t1 = el('text', { class: 'bigtxt', x: 150, y: 156 }, st), t2 = el('text', { class: 'subtxt', x: 150, y: 196 }, st); t2.textContent = 'objetivo';
      const sp = el('tspan', { 'font-size': 28, dx: 4 }); sp.textContent = 's';
      return (v) => { arc.style.strokeDasharray = (v.maxresp / 60 * 100) + ' 100'; arc2.style.strokeDasharray = (v.alerta / 24 * 100) + ' 100'; poner(sg, v.maxresp / 60 * 360 - 90, true);
        t1.textContent = v.maxresp; t1.appendChild(sp); };
    },
  };
  const VIVO = { proc: (v) => v.envios + ' casos por ronda, ' + v.reintentos + ' reintentos', ia: (v) => (v.evaluador ? 'Revisor encendido' : 'Revisor apagado') + ', ' + v.candidatos + ' artículos por caso', comp: (v) => 'Compartido con ' + (v.compartir.length || 'nadie') + ' equipos', plazos: (v) => v.maxresp + ' segundos para responder' };
  const CAP = { proc: (v) => v.envios + (v.envios === 1 ? ' caso' : ' casos') + ' por ronda · ' + (v.reintentos ? v.reintentos + (v.reintentos === 1 ? ' reintento' : ' reintentos') : 'sin reintentos'),
    ia: (v) => (v.evaluador ? 'Revisor activo · ' + v.candidatos + ' artículos' : 'Revisor apagado') + (v.cadena.filter((m) => m.on).length < 2 ? ' · ' + v.cadena.filter((m) => m.on).length + ' modelo' : ''),
    comp: () => '', plazos: (v) => 'Lento desde ' + v.maxresp + ' s · aviso tras ' + v.alerta + ' h' };
  const escenas = {};
  $$('[data-orb]').forEach((h) => { const g = h.dataset.orb; if (ESC[g]) escenas[g] = { host: h, up: ESC[g](h), cap: $('[data-cap]', h.parentNode) }; });
  function orbitas() { Object.keys(escenas).forEach((g) => { const e = escenas[g]; e.up(s); e.host.setAttribute('aria-label', VIVO[g](s)); if (e.cap) e.cap.textContent = CAP[g](s); }); }
  /* resalta en el panel lo que el control en foco o bajo el cursor modifica (solo opacity) */
  const calor = (k, on) => { const g = $('.ctl[data-k="' + k + '"]').closest('[data-g]'), h = $('[data-orb]', g); if (on && $('.hk[data-k="' + k + '"]', h)) h.dataset.hot = k; else delete h.dataset.hot; };

  /* ---------- estados: todo guardado / sin guardar / guardando / guardado / error ---------- */
  const chip = $('[data-estado]'), fch = $('[data-guardado]'), barra = $('[data-barra]'), form = barra;
  const MINI = (e) => '<k-st data-e="' + e + '" class="sm" style="--s:18px" aria-hidden="true"><svg aria-hidden="true" focusable="false"><use href="/estaticos/identidad.svg#m-' + e + '"/></svg></k-st>';
  const hora = (iso) => { const d = new Date(iso); return isNaN(d) ? '' : d.toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }); };
  let estado = 'ok', tFin = 0;
  function estadoVista(e, txt) {
    estado = e; if (!chip) return;
    const M2 = { ok: ['ok', 'lista', 'Todo guardado'], sucio: ['warn', 'contingencia-modelo', 'Cambios sin guardar'], guardando: ['brand', 'conector-en-proceso', 'Guardando…'], guardado: ['ok', 'lista', 'Guardado'], error: ['bad', 'cadena-agotada', 'No se pudo guardar'] }[e];
    chip.className = 'chip ' + M2[0] + (e === 'guardando' ? ' gir' : ''); chip.innerHTML = MINI(M2[1]) + '<span></span>'; $('span', chip).textContent = txt || M2[2];
  }
  const barraTxt = $('[data-ncambios]'), btnG = $('[data-guardar]'), btnD = $('[data-descartar]');
  const MSG = { origen: 'Recarga la página e inténtalo otra vez', token: 'Recarga la página e inténtalo otra vez', invalido: 'Algún valor no es válido. Revisa los ajustes', sesion: 'La sesión terminó. Vuelve a entrar', error: 'Inténtalo en un momento' };

  function pintar() {
    $$('.ctl').forEach((c) => {
      const k = c.dataset.k, it = items[k], v = s[k], dep = it.dep && !s[it.dep];
      c.classList.toggle('opacity-60', !!dep); c.classList.toggle('dirty', !igual(v, base[k]));
      const rs = $('[data-cambiado]', c); if (rs) rs.hidden = igual(v, rec[k]);
      if (it.t === 'sw') { const b = $('.sw', c); b.setAttribute('aria-checked', v); $('[data-swt]', c).textContent = fmt(it, v); }
      if (it.t === 'rg') {
        const r = $('.range', c); r.value = v; r.disabled = !!dep; r.style.setProperty('--p', ((v - it.min) / (it.max - it.min) * 100) + '%'); r.setAttribute('aria-valuetext', fmt(it, v));
        $('[data-v]', c).textContent = fmt(it, v); r.title = 'De ' + fmt(it, it.min) + ' a ' + fmt(it, it.max) + ' · recomendado: ' + fmt(it, rec[k]); const fr = (rec[k] - it.min) / (it.max - it.min); $('[data-rc]', c).style.left = 'calc(' + fr * 100 + '% + ' + (8 - fr * 16) + 'px)';
        const a = aviso(k, v), p = $('[data-av]', c); p.hidden = !a; $('span', p).textContent = a;
      }
      if (it.t === 'sg') $$('button', c).forEach((b) => { const on = Number(b.dataset.v) === v; b.setAttribute('aria-checked', String(on)); b.tabIndex = on ? 0 : -1; });
      if (it.t === 'ch') $$('button.chip', c).forEach((b) => { const on = v.includes(b.dataset.v); b.setAttribute('aria-pressed', on); b.classList.toggle('brand', on); b.classList.toggle('na', !on); });
      if (it.t === 'cd') cadena(c, v);
    });
    const n = Object.keys(rec).filter((k) => !igual(s[k], base[k])).length;
    $('input[name=valores]', form).value = JSON.stringify(s);
    if (estado !== 'guardando') {
      clearTimeout(tFin);
      if (n) { barra.hidden = false; barra.classList.remove('ok', 'bad'); barraTxt.textContent = n + (n === 1 ? ' cambio sin guardar' : ' cambios sin guardar'); btnD.hidden = false; btnG.disabled = false; estadoVista('sucio', n + (n === 1 ? ' cambio sin guardar' : ' cambios sin guardar')); }
      else if (estado === 'sucio' || estado === 'error') { barra.hidden = true; estadoVista('ok'); }
    }
    orbitas();
  }
  /* orden de los modelos: se redibuja, pero el foco vuelve al botón que se acaba de usar (teclado) */
  function cadena(c, v) {
    const host = $('[data-cadena]', c), act = document.activeElement, memo = act && host.contains(act) ? act.dataset.id : null; host.textContent = '';
    v.forEach((m, i) => {
      const row = document.createElement('div'); row.className = 'cn-row'; row.style.opacity = m.on ? '' : '.65';
      row.innerHTML = '<span class="cn-n">' + (i + 1) + '</span><div class="flex-1 min-w-0"><b class="block text-[14px]"></b><span class="text-xs muted"></span></div><div class="flex items-center gap-1.5"></div>';
      $('b', row).textContent = M[m.v][0]; $('.muted', row).textContent = i === 0 ? 'Principal' : 'Respaldo';
      const bt = $('.flex.items-center', row);
      [[-1, 'arrow-up', 'Subir: ', 'u'], [1, 'arrow-down', 'Bajar: ', 'd']].forEach(([d, ic, t, id]) => {
        const b = document.createElement('button'); b.type = 'button'; b.className = 'cn-b'; b.dataset.id = m.v + id; b.setAttribute('aria-label', t + M[m.v][0]); b.disabled = i + d < 0 || i + d >= v.length;
        b.innerHTML = '<k-ic n="' + ic + '" aria-hidden="true"><svg aria-hidden="true" focusable="false"><use href="/estaticos/iconos.svg#' + ic + '"/></svg></k-ic>';
        b.onclick = () => { const a = [...s.cadena]; [a[i], a[i + d]] = [a[i + d], a[i]]; s.cadena = a; c.dataset.foco = m.v + (b.disabled ? (id === 'u' ? 'd' : 'u') : id); pintar(); const f = $('[data-id="' + c.dataset.foco + '"]:not(:disabled)', c) || $('[data-id="' + m.v + (id === 'u' ? 'd' : 'u') + '"]', c); if (f) f.focus(); }; bt.appendChild(b);
      });
      const sw = document.createElement('button'); sw.type = 'button'; sw.setAttribute('role', 'switch'); sw.className = 'sw ml-1'; sw.dataset.id = m.v + 's'; sw.setAttribute('aria-checked', m.on); sw.setAttribute('aria-label', 'Usar ' + M[m.v][0]);
      sw.onclick = () => { m.on = !m.on; pintar(); const f = $('[data-id="' + m.v + 's"]', c); if (f) f.focus(); }; bt.appendChild(sw);
      host.appendChild(row);
    });
    if (memo) { const f = $('[data-id="' + memo + '"]:not(:disabled)', host); if (f) f.focus(); }
  }

  /* ---------- entradas ---------- */
  $$('.ctl').forEach((c) => {
    const k = c.dataset.k, it = items[k];
    c.addEventListener('pointerenter', () => calor(k, true)); c.addEventListener('pointerleave', () => calor(k, false));
    c.addEventListener('focusin', () => calor(k, true)); c.addEventListener('focusout', () => calor(k, false));
    const rs = $('[data-rst]', c); if (rs) rs.onclick = () => { s[k] = clon(rec[k]); pintar(); };
    if (it.t === 'sw') $('.sw', c).onclick = () => { s[k] = !s[k]; pintar(); };
    if (it.t === 'rg') $('.range', c).oninput = (e) => { s[k] = Number(e.target.value); pintar(); };
    if (it.t === 'sg') {
      const g = $('.seg', c); g.setAttribute('role', 'radiogroup');
      $$('button', c).forEach((b, i, all) => {
        b.setAttribute('role', 'radio'); b.removeAttribute('aria-pressed');
        b.onclick = () => { s[k] = Number(b.dataset.v); pintar(); };
        b.onkeydown = (e) => { const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key]; if (!d) return; e.preventDefault(); const nb = all[(i + d + all.length) % all.length]; s[k] = Number(nb.dataset.v); pintar(); nb.focus(); };
      });
    }
    if (it.t === 'ch') $$('button.chip', c).forEach((b) => { b.onclick = () => { const v = b.dataset.v; s[k] = s[k].includes(v) ? s[k].filter((x) => x !== v) : [...s[k], v]; pintar(); }; });
  });
  $('[data-restaurar]').onclick = () => { s = clon(rec); pintar(); };
  btnD.onclick = () => { s = clon(base); pintar(); };

  /* guardar sin recargar: guardando → guardado | error (con motivo y reintento) */
  form.addEventListener('submit', async (e) => {
    e.preventDefault(); if (estado === 'guardando') return;
    estadoVista('guardando'); barra.classList.remove('bad'); barraTxt.textContent = 'Guardando…'; btnG.disabled = true; btnD.hidden = true;
    let r = { estado: 'error' };
    try {
      const resp = await fetch(form.action, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body: new URLSearchParams({ csrf: $('input[name=csrf]', form).value, valores: JSON.stringify(s) }) });
      r = await resp.json().catch(() => ({ estado: 'error' }));
    } catch (_) { r = { estado: 'error' }; }
    btnG.disabled = false;
    if (r.estado === 'sesion') { location.href = '/acceso'; return; }
    if (r.estado === 'ok') {
      base = clon(s); estado = 'guardado'; barra.classList.add('ok'); barraTxt.textContent = 'Guardado'; estadoVista('guardado', 'Guardado'); fch.textContent = hora(r.guardado_en || new Date().toISOString());
      $$('.ctl').forEach((c) => c.classList.remove('dirty')); pintarSoloMarcas();
      tFin = setTimeout(() => { if (estado === 'guardado') { barra.hidden = true; barra.classList.remove('ok'); estadoVista('ok'); } }, 2600);
    } else {
      estado = 'error'; barra.classList.add('bad'); barra.hidden = false; btnD.hidden = false; barraTxt.textContent = 'No se pudo guardar. ' + (MSG[r.estado] || MSG.error); estadoVista('error'); btnG.querySelector('span').textContent = 'Reintentar';
    }
  });
  function pintarSoloMarcas() { btnG.querySelector('span').textContent = 'Guardar'; }
  const antes = pintar; pintar = function () { if (estado === 'error' || estado === 'guardado') { if (estado === 'guardado') { clearTimeout(tFin); } estado = 'ok'; btnG.querySelector('span').textContent = 'Guardar'; barra.classList.remove('bad', 'ok'); } antes(); };
  pintar();
  /* entrada del panel: los satélites parten de cero y se despliegan (transición) */
  if (!RM) { Object.keys(escenas).forEach((g) => { const e = escenas[g]; e.host.classList.add('ini'); });
    requestAnimationFrame(() => requestAnimationFrame(() => Object.keys(escenas).forEach((g) => escenas[g].host.classList.remove('ini')))); }
})();
