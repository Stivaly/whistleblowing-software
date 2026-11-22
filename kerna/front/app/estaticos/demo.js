/* Demo: pestañas y anonimizador. Sin JavaScript todo funciona con enlaces y formulario; esto lo hace sin recargar. El texto no se guarda en el navegador. */
(() => {
  'use strict';
  const raiz = document.querySelector('.dmo'); if (!raiz) return;
  const $ = (s, r = raiz) => r.querySelector(s);
  const paneles = [...raiz.querySelectorAll('[data-panel]')], enlaces = [...raiz.querySelectorAll('.seg a[data-pestana]')];
  function mostrar(p) {
    paneles.forEach((x) => { x.hidden = x.dataset.panel !== p; });
    enlaces.forEach((a) => a.setAttribute('aria-current', String(a.dataset.pestana === p)));
    try { history.replaceState(null, '', '?pestana=' + p); } catch (_) { /* sin historial */ }
  }
  enlaces.forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); mostrar(a.dataset.pestana); }));

  const f = $('[data-form]'); if (!f) return;
  const ta = $('textarea', f), cuenta = $('[data-cuenta]', f), salida = $('[data-salida]'), err = $('[data-error]', f), boton = $('[data-enviar]', f);
  const MSG = { vacio: 'Escribe o elige un relato para anonimizar', token: 'Recarga la página e inténtalo otra vez', origen: 'Recarga la página e inténtalo otra vez',
    sesion: 'La sesión terminó. Vuelve a entrar', error: 'No se pudo completar. Inténtalo en un momento' };
  const MAX = parseInt(ta.getAttribute('maxlength'), 10) || 0, cerca = Math.floor(MAX * 0.9);
  const contar = () => {   // el contador avisa cerca del límite: el texto nunca se corta sin que se vea
    const n = ta.value.length; cuenta.textContent = n; const tope = $('.mk-r', f);
    if (tope) { tope.classList.toggle('cerca', MAX > 0 && n >= cerca); tope.dataset.limite = MAX > 0 && n >= MAX ? 'Límite alcanzado' : ''; }
  };
  ta.addEventListener('input', () => { ta.setCustomValidity(''); contar(); }); contar();
  ta.addEventListener('invalid', () => ta.setCustomValidity(MSG.vacio));   // mensaje propio en español, no el del navegador
  ta.addEventListener('paste', (e) => {
    const t = (e.clipboardData && e.clipboardData.getData('text')) || '';
    if (MAX && ta.value.length - (ta.selectionEnd - ta.selectionStart) + t.length > MAX) aviso('El texto pegado supera los ' + MAX.toLocaleString('es-CL') + ' caracteres: se cortó el final');
  });
  const icono = (e) => { const t = document.createElement('template'); t.innerHTML = '<k-st data-e="' + e + '" style="--s:40px" aria-hidden="true"><svg aria-hidden="true" focusable="false"><use href="#e-' + e + '"/></svg></k-st>'; return t.content.firstElementChild; };
  const aviso = (m) => {
    err.hidden = !m; err.replaceChildren(); if (!m) return;
    const sp = document.createElement('span'); sp.textContent = m; err.append(icono('cadena-agotada'), sp);
  };
  async function anonimizar(texto) {
    aviso(''); boton.disabled = true;
    try {
      const r = await fetch(f.action, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' },
        body: new URLSearchParams({ csrf: raiz.dataset.csrf, texto }) });
      const d = await r.json().catch(() => ({ estado: 'error' }));
      if (d.estado !== 'ok') { aviso(MSG[d.estado] || MSG.error); return; }
      salida.innerHTML = d.html;  // HTML ya escapado por el servidor
      const quieto = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
      salida.scrollIntoView({ block: innerWidth < 900 ? 'start' : 'nearest', behavior: quieto ? 'auto' : 'smooth' });
    } catch (_) { aviso(MSG.error); } finally { boton.disabled = false; }
  }
  const borrar = $('[data-borrar]', f);   // sin JS es un enlace que recarga la demo vacía
  if (borrar) borrar.addEventListener('click', (e) => {
    e.preventDefault(); ta.value = ''; ta.setCustomValidity(''); contar(); aviso(''); salida.replaceChildren(); ta.focus();
  });
  f.addEventListener('submit', (e) => {
    e.preventDefault();
    const p = e.submitter && e.submitter.dataset.texto;
    if (p) { ta.value = p; contar(); }
    anonimizar(ta.value);
  });
})();
