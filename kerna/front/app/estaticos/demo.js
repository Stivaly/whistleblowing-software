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
  const contar = () => { cuenta.textContent = ta.value.length; };
  ta.addEventListener('input', contar); contar();
  const aviso = (m) => { err.hidden = !m; err.textContent = m || ''; };
  async function anonimizar(texto) {
    aviso(''); boton.disabled = true;
    try {
      const r = await fetch(f.action, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' },
        body: new URLSearchParams({ csrf: raiz.dataset.csrf, texto }) });
      const d = await r.json().catch(() => ({ estado: 'error' }));
      if (d.estado !== 'ok') { aviso(MSG[d.estado] || MSG.error); return; }
      salida.innerHTML = d.html;  // HTML ya escapado por el servidor
      salida.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } catch (_) { aviso(MSG.error); } finally { boton.disabled = false; }
  }
  f.addEventListener('submit', (e) => {
    e.preventDefault();
    const p = e.submitter && e.submitter.dataset.texto;
    if (p) { ta.value = p; contar(); }
    anonimizar(ta.value);
  });
})();
