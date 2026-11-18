/* Clientes: agregar, dar de baja, reactivar y borrar por ley. Todo va por fetch con el token de la sesión; al terminar se recarga la lista. */
(() => {
  'use strict';
  const raiz = document.querySelector('.cli'); if (!raiz) return;
  const $ = (s, r = document) => r.querySelector(s);
  const csrf = raiz.dataset.csrf;
  const MSG = {
    invalido: 'Revisa los datos: el identificador usa minúsculas, números y guiones', existe: 'Ya existe un cliente con ese identificador',
    protegido: 'Esa cuenta sostiene la plataforma y no se puede quitar', no_existe: 'Ese cliente ya no existe', estado: 'El cliente cambió de estado. Recarga la página',
    confirmacion: 'El identificador escrito no coincide', token: 'Recarga la página e inténtalo otra vez', origen: 'Recarga la página e inténtalo otra vez',
    sesion: 'La sesión terminó. Vuelve a entrar', error: 'No se pudo completar. Inténtalo en un momento'
  };
  async function pedir(ruta, datos, metodo) {
    try {
      const r = metodo === 'GET' ? await fetch(ruta + '?' + new URLSearchParams(datos), { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        : await fetch(ruta, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body: new URLSearchParams({ csrf, ...datos }) });
      return await r.json().catch(() => ({ estado: 'error' }));
    } catch (_) { return { estado: 'error' }; }
  }
  const error = (d, e) => { const p = $('[data-error]', d); if (!p) return; p.hidden = !e; p.textContent = e || ''; };
  const abrir = (d) => { error(d, ''); d.showModal(); };
  document.addEventListener('click', (e) => {
    const t = e.target;
    if (t.matches('dialog.dlg')) { t.close(); return; }
    const a = t.closest('[data-abrir]'); if (a) { const f = $('form', $('#' + a.dataset.abrir)); if (f) f.reset(); abrir($('#' + a.dataset.abrir)); return; }
    const c = t.closest('[data-cerrar]'); if (c) { c.closest('dialog').close(); return; }
    const fila = t.closest('tr[data-id]');
    if (fila && t.closest('[data-baja]')) { const d = $('#dlg-baja'); d.dataset.id = fila.dataset.id; $('[data-n]', d).textContent = fila.dataset.nombre; abrir(d); return; }
    if (fila && t.closest('[data-reactivar]')) { pedir('/panel/clientes/reactivar', { id: fila.dataset.id }).then((r) => r.estado === 'ok' ? location.reload() : aviso(MSG[r.estado] || MSG.error)); return; }
    if (fila && t.closest('[data-ley]')) {
      const d = $('#dlg-ley'), f = $('form', d); f.reset(); d.dataset.id = fila.dataset.id; $('[data-n]', d).textContent = fila.dataset.nombre; $('[data-idl]', d).textContent = fila.dataset.id;
      $('[data-sol]', d).textContent = '…'; $('[data-dias]', d).textContent = '…'; $('[data-ok]', d).disabled = true; abrir(d);
      pedir('/panel/clientes/previa', { id: fila.dataset.id }, 'GET').then((r) => { if (r.estado === 'ok') { $('[data-sol]', d).textContent = r.solicitudes; $('[data-dias]', d).textContent = r.dias_de_uso; } else error(d, MSG[r.estado] || MSG.error); });
      return;
    }
    if (t.closest('[data-copiar]')) { const i = $('[data-v=secreto]'); i.select(); (navigator.clipboard ? navigator.clipboard.writeText(i.value) : Promise.resolve(document.execCommand('copy'))).catch(() => {}); t.closest('[data-copiar]').textContent = 'Copiada'; return; }
    if (t.closest('[data-listo]')) { location.reload(); }
  });
  function aviso(m) { const p = $('[data-aviso]', raiz); p.hidden = false; p.className = 'cola-av s-bad'; p.textContent = m; }
  // el botón peligroso solo se habilita al escribir el identificador exacto
  const ley = $('#dlg-ley');
  $('[name=confirmar]', ley).addEventListener('input', (e) => { $('[data-ok]', ley).disabled = e.target.value.trim().toLowerCase() !== ley.dataset.id; });
  document.addEventListener('submit', async (e) => {
    const f = e.target.closest('form[data-form]'); if (!f) return; e.preventDefault();
    const d = f.closest('dialog'), b = $('button[type=submit]', f), k = f.dataset.form, v = Object.fromEntries(new FormData(f));
    b.disabled = true; error(d, '');
    const r = k === 'crear' ? await pedir('/panel/clientes/crear', v) : k === 'baja' ? await pedir('/panel/clientes/baja', { id: d.dataset.id })
      : await pedir('/panel/clientes/borrar-por-ley', { id: d.dataset.id, confirmar: v.confirmar, referencia: v.referencia || '' });
    if (r.estado !== 'ok') { error(d, MSG[r.estado] || MSG.error); b.disabled = k === 'ley' && $('[name=confirmar]', f).value.trim().toLowerCase() !== d.dataset.id; return; }
    d.close();
    if (k === 'crear') { const c = $('#dlg-clave'); $('[data-v=id]', c).value = r.id; $('[data-v=secreto]', c).value = r.secreto; c.showModal(); } else location.reload();
  });
})();
