/* Demo, sección «Denuncias»: elegir o escribir una denuncia, enviarla al núcleo y comparar lo que sugiere con lo esperado.
   El texto solo viaja en el POST; no se guarda en el navegador (ni en el almacenamiento local ni en la URL). Todo lo que viene del servidor se escribe con textContent. */
(() => {
  'use strict';
  const raiz = document.querySelector('[data-den]'); if (!raiz) return;
  const $ = (s, r = raiz) => r.querySelector(s);
  let datos; try { datos = JSON.parse(document.getElementById('den-datos').textContent); } catch (_) { return; }
  const csrf = raiz.dataset.csrf;
  const ta = $('#den-texto'), btn = $('[data-analizar]'), salida = $('[data-salida]'), cuenta = $('[data-cuenta]'), err = $('[data-error]');
  const LEYES = new Set(['karin', 'datos', 'penal']);
  const ESTADOS = new Set(['lista', 'generando', 'sin-normativa', 'revision-citas', 'revision-tiempo', 'cadena-agotada', 'nucleo-no-disponible', 'sin-info', 'sin-conexion']);
  const MSG = {
    corto: 'Escribe una denuncia más completa: al menos ' + datos.min + ' caracteres', largo: 'La denuncia es demasiado larga para la demo',
    limite: 'Se llegó al límite de denuncias de la demo por ahora. Inténtalo en unos minutos', token: 'Recarga la página e inténtalo otra vez',
    origen: 'Recarga la página e inténtalo otra vez', sesion: 'La sesión terminó. Vuelve a entrar', error: 'No se pudo enviar. Inténtalo en un momento'
  };
  const MOTIVO = {
    sin_normativa_aplicable: ['sin-normativa', 'Kerna no encontró una ley que aplique'], validacion_fallida: ['revision-citas', 'Kerna no pudo verificar las citas'],
    tiempo_agotado: ['revision-tiempo', 'El análisis tardó más de lo permitido'], cadena_agotada: ['cadena-agotada', 'Los modelos no estuvieron disponibles']
  };
  const DETALLE = {
    misma_ley: 'Kerna sugirió la ley correcta, pero con otros artículos.', otra_ley: 'Kerna sugirió artículos de otra ley.',
    sin_sugerencia: 'Se esperaba una sugerencia y Kerna no sugirió ninguna.',
    con_sugerencia: 'Se esperaba que no hubiera sugerencia, porque esa ley no está en el corpus de la demo, y Kerna sugirió artículos de otra ley.'
  };
  let caso = '', sesion = 0;

  /* ---------- construcción segura de nodos ---------- */
  const h = (tag, att, ...hijos) => {
    const e = document.createElement(tag);
    for (const k in att || {}) { if (k === 'class') e.className = att[k]; else if (att[k] !== null && att[k] !== undefined) e.setAttribute(k, att[k]); }
    for (const c of hijos.flat()) if (c !== null && c !== undefined && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
    return e;
  };
  const frag = (html) => { const t = document.createElement('template'); t.innerHTML = html; return t.content.firstElementChild; };   // solo con cadenas fijas de este archivo
  const ley = (t, px) => LEYES.has(t) ? frag('<span class="lx" data-l="' + t + '" style="--s:' + px + 'px" aria-hidden="true"><svg focusable="false"><use href="#l-' + t + '"/></svg></span>') : null;
  const estado = (e, px, mini) => ESTADOS.has(e) ? frag('<k-st data-e="' + e + '" style="--s:' + px + 'px"' + (mini ? ' class="sm"' : '') + ' aria-hidden="true"><svg aria-hidden="true" focusable="false"><use href="#' + (mini ? 'm' : 'e') + '-' + e + '"/></svg></k-st>') : null;
  const ayuda = (txt) => { const b = h('button', { type: 'button', class: 'den-q', 'data-q': txt, 'aria-label': 'Ayuda: ' + txt }); b.append(frag('<k-n style="--s:18px" aria-hidden="true"><svg aria-hidden="true" focusable="false"><use href="#n-ayuda"/></svg></k-n>')); return b; };
  const chip = (cl, txt) => h('span', { class: 'chip ' + cl }, txt);

  /* ---------- «?»: usa el globo de ayuda del panel (#tt) ---------- */
  const tt = document.getElementById('tt'); let fijo = null;
  const mostrar = (b) => {
    const q = b.getAttribute('data-q'); if (!tt || !q) return;
    tt.textContent = q; tt.classList.add('on');
    const r = b.getBoundingClientRect(), w = tt.offsetWidth, al = tt.offsetHeight;
    tt.style.left = Math.min(Math.max(12, r.left + r.width / 2 - w / 2), innerWidth - w - 12) + 'px';
    let y = r.bottom + 8; if (y + al > innerHeight - 8) y = r.top - al - 8; tt.style.top = Math.max(8, y) + 'px';
  };
  const ocultar = () => { if (tt) tt.classList.remove('on'); fijo = null; };
  const tipDe = (e) => e.target.closest && e.target.closest('.den-q');
  document.addEventListener('pointerover', (e) => { const b = tipDe(e); if (b && e.pointerType === 'mouse' && !fijo) mostrar(b); });
  document.addEventListener('pointerout', (e) => { if (tipDe(e) && !fijo && e.pointerType === 'mouse') ocultar(); });
  document.addEventListener('focusin', (e) => { const b = tipDe(e); if (b) mostrar(b); });
  document.addEventListener('focusout', (e) => { if (tipDe(e) && !fijo) ocultar(); });
  document.addEventListener('click', (e) => { const b = tipDe(e); if (b) { if (fijo === b) ocultar(); else { mostrar(b); fijo = b; } } else if (fijo) ocultar(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') ocultar(); });
  addEventListener('scroll', () => { if (!fijo) ocultar(); }, { passive: true });

  /* ---------- selección y texto ---------- */
  const actualizar = () => { cuenta.textContent = ta.value.length; btn.disabled = ta.value.trim().length < datos.min || btn.dataset.ocupado === '1'; };
  const falla = (m) => { err.hidden = !m; err.textContent = m || ''; };
  document.querySelectorAll('.den-caso').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.den-caso').forEach((o) => o.setAttribute('aria-checked', o === b ? 'true' : 'false'));
    caso = b.dataset.caso; falla(''); sesion++; salida.hidden = true; salida.replaceChildren();
    ta.value = caso && datos.casos[caso] ? datos.casos[caso].texto : '';
    actualizar(); if (!caso) ta.focus();
  }));
  ta.addEventListener('input', () => { falla(''); actualizar(); });

  /* ---------- resultado ---------- */
  const cabecera = (ilu, titulo, sub, ...extra) => h('header', { class: 'den-hl' }, estado(ilu, 56), h('div', null, h('h3', { class: 'den-t' }, titulo), sub ? h('p', { class: 'den-s' }, sub) : null), ...extra);
  const comparacion = (r) => {
    if (r.estado === 'sin_nucleo') return r.esperado ? h('span', { class: 'den-cmp' }, chip('na', 'Respuesta esperada guardada'), ayuda('La demo no pudo consultar el núcleo, así que se muestra lo que se esperaba para esta denuncia, no lo que sugirió Kerna.')) : null;
    if (r.comparacion === 'coincide') return h('span', { class: 'den-cmp' }, chip('ok', 'Coincide con lo esperado'), ayuda(r.esperado && r.esperado.tipo === 'fuera' ? 'Se esperaba que no hubiera sugerencia y Kerna no sugirió nada.' : 'Al menos un artículo sugerido está en la lista de artículos esperados.'));
    if (r.comparacion === 'difiere') return h('span', { class: 'den-cmp' }, chip('warn', 'Difiere de lo esperado'), ayuda(DETALLE[r.detalle] || 'Ningún artículo sugerido está en la lista de artículos esperados.'));
    return h('span', { class: 'den-cmp' }, chip('na', 'Denuncia propia: sin respuesta esperada'), ayuda('Solo las denuncias de la lista, sin cambios, tienen una respuesta esperada con la que comparar.'));
  };
  const itemObtenido = (a) => {
    const li = h('li', { class: a.coincide ? 'den-ok' : '' }, ley(a.ley, 28) || estado('sin-info', 28, true),
      h('b', null, a.articulo ? 'Artículo ' + a.articulo : 'Artículo'), h('span', { class: 'den-nm' }, a.norma));
    const f = [];
    if (a.coincide) f.push(chip('ok', 'Esperado'));
    else if (a.confianza) f.push(chip('na', Math.round(a.confianza * 100) + ' % de confianza'));
    li.append(...f);
    if (a.explicacion || a.cita) li.append(h('details', null, h('summary', null, 'Por qué'), a.explicacion ? h('p', null, a.explicacion) : null, a.cita ? h('q', null, a.cita) : null));
    return li;
  };
  const columnaObtenida = (r) => {
    const s = h('section', { 'aria-label': 'Lo que sugirió Kerna' }, h('h4', { class: 'mk' }, 'Lo que sugirió Kerna'));
    if (!r.articulos.length) s.append(h('p', { class: 'den-vac' }, estado('sin-normativa', 24, true), h('b', null, 'Sin sugerencia')));
    else s.append(h('ul', { class: 'den-l' }, r.articulos.map(itemObtenido)));
    if (r.vetados) s.append(h('p', { class: 'den-nota' }, r.vetados === 1 ? 'La revisión jurídica descartó 1 artículo.' : 'La revisión jurídica descartó ' + r.vetados + ' artículos.'));
    return s;
  };
  const columnaEsperada = (r) => {
    const e = r.esperado;
    const t = h('h4', { class: 'mk' }, 'Lo que se esperaba', ayuda('Es la respuesta que corresponde según el criterio jurídico del equipo. Coincide si Kerna sugiere al menos uno de estos artículos.'));
    const s = h('section', { 'aria-label': 'Lo que se esperaba' }, t);
    if (e.tipo === 'fuera') {
      s.append(h('p', { class: 'den-vac' }, estado('sin-normativa', 24, true), h('b', null, 'Sin sugerencia'), h('span', { class: 'den-et' }, chip('na', 'Fuera del corpus'),
        ayuda('Esa ley no está en el corpus de la demo: Kerna solo conoce las leyes 21.643, 19.628 y 21.719, y 20.393. Una denuncia sobre otra ley debe quedar sin sugerencia.'))));
      s.append(h('p', { class: 'den-nota' }, 'Aplica: ' + e.fuera));
    } else s.append(h('ul', { class: 'den-l' }, e.articulos.map((a) => h('li', null, ley(a.ley, 28), h('b', null, a.etiqueta)))));
    return s;
  };
  function pintar(r, seg) {
    salida.hidden = false; salida.replaceChildren();
    let cab, cols = [];
    if (r.estado === 'sin_nucleo') {
      const sinConexion = r.motivo === 'no_configurado';
      cab = cabecera(sinConexion ? 'sin-conexion' : 'nucleo-no-disponible', r.esperado ? (sinConexion ? 'La demo no está conectada al núcleo' : 'El núcleo no respondió') : 'No se pudo analizar la denuncia',
        r.esperado ? 'Se muestra la respuesta esperada guardada' : 'Inténtalo en un momento', comparacion(r));
      if (r.esperado) cols = [columnaEsperada(r)];
    } else if (r.estado === 'listo') {
      cab = cabecera('lista', r.articulos.length === 1 ? 'Kerna sugiere 1 artículo' : 'Kerna sugiere ' + r.articulos.length + ' artículos', 'Analizada en ' + seg + ' s', comparacion(r));
      cols = [columnaObtenida(r)];
    } else {
      const m = MOTIVO[r.motivo] || ['sin-info', 'Kerna no sugiere artículos'];
      cab = cabecera(m[0], m[1], 'Analizada en ' + seg + ' s', comparacion(r));
      cols = [columnaObtenida(r)];
    }
    if (r.esperado && r.estado !== 'sin_nucleo') cols.push(columnaEsperada(r));
    salida.append(cab, cols.length ? h('div', { class: 'den-2' }, cols) : null);
  }
  const procesando = (seg) => {
    salida.hidden = false;
    salida.replaceChildren(h('div', { class: 'den-pro' }, estado('generando', 56), h('div', null, h('h3', { class: 'den-t' }, 'Analizando la denuncia'),
      h('p', { class: 'den-s' }, 'Anonimizando, buscando en la ley y redactando · ' + seg + ' s'))));
  };

  /* ---------- envío y seguimiento ---------- */
  async function json(ruta, opciones) {
    try { const r = await fetch(ruta, { credentials: 'same-origin', headers: { Accept: 'application/json' }, ...opciones }); return await r.json().catch(() => ({ estado: 'error' })); }
    catch (_) { return { estado: 'error' }; }
  }
  const libre = () => { btn.dataset.ocupado = '0'; actualizar(); };
  btn.addEventListener('click', async () => {
    const yo = ++sesion, t0 = Date.now(), seg = () => Math.round((Date.now() - t0) / 1000);
    falla(''); btn.dataset.ocupado = '1'; btn.disabled = true; procesando(0);
    const r = await json('/panel/demo/denuncia', { method: 'POST', body: new URLSearchParams({ csrf, texto: ta.value, caso }) });
    if (yo !== sesion) return;
    if (r.estado === 'sin_nucleo') { pintar(r, seg()); return libre(); }
    if (r.estado !== 'ok' || !r.ref) { salida.hidden = true; salida.replaceChildren(); falla(MSG[r.estado] || MSG.error); return libre(); }
    const vuelta = async () => {
      if (yo !== sesion) return;
      if (seg() > 480) { salida.replaceChildren(); salida.append(cabecera('revision-tiempo', 'El análisis tardó más de lo permitido', 'Vuelve a intentarlo')); return libre(); }
      const d = await json('/panel/demo/denuncia/' + encodeURIComponent(r.ref));
      if (yo !== sesion) return;
      if (d.estado === 'procesando') { procesando(seg()); return setTimeout(vuelta, 3000); }
      if (d.estado === 'desconocida' || d.estado === 'sesion' || d.estado === 'error') { salida.hidden = true; salida.replaceChildren(); falla(d.estado === 'sesion' ? MSG.sesion : 'Se perdió el seguimiento de esta denuncia. Analízala otra vez'); return libre(); }
      pintar(d, seg()); libre();
    };
    setTimeout(vuelta, 2500);
  });
  actualizar();
})();
