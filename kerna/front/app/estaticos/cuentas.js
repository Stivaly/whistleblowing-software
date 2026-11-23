/* Cuentas: crear, editar, restablecer la clave y eliminar. Todo va por fetch con el token de la sesión; al terminar se recarga la lista. */
(() => {
  'use strict';
  const raiz = document.querySelector('.cue'); if (!raiz) return;
  const $ = (s, r = document) => r.querySelector(s);
  const csrf = raiz.dataset.csrf;
  const MSG = {
    invalido: 'Revisa los datos: nombre, correo, rol y un usuario de 3 a 32 letras minúsculas, números, punto o guion', existe: 'Ya existe una cuenta con ese usuario',
    no_existe: 'Esa cuenta ya no existe. Recarga la página', ultima_direccion: 'Tiene que quedar al menos una cuenta de Dirección activa', propia: 'No puedes hacerlo con tu propia cuenta',
    confirmacion: 'El usuario escrito no coincide', token: 'Recarga la página e inténtalo otra vez', origen: 'Recarga la página e inténtalo otra vez',
    sesion: 'La sesión terminó. Vuelve a entrar', permiso: 'Tu rol no permite hacer esto', cambiar_clave: 'Cambia tu contraseña para seguir', error: 'No se pudo completar. Inténtalo en un momento'
  };
  async function pedir(ruta, datos) {
    try {
      const r = await fetch(ruta, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body: new URLSearchParams({ csrf, ...datos }) });
      return await r.json().catch(() => ({ estado: 'error' }));
    } catch (_) { return { estado: 'error' }; }
  }
  const error = (d, e) => { const p = $('[data-error]', d); if (!p) return; p.hidden = !e; p.textContent = e || ''; };
  const abrir = (d) => { error(d, ''); d.showModal(); };
  document.addEventListener('click', (e) => {
    const t = e.target;
    if (t.matches('dialog.dlg')) { t.close(); return; }
    const a = t.closest('[data-abrir]'); if (a) { const d = $('#' + a.dataset.abrir), f = $('form', d); if (f) f.reset(); abrir(d); return; }
    const c = t.closest('[data-cerrar]'); if (c) { c.closest('dialog').close(); return; }
    const fila = t.closest('tr[data-usuario]');
    if (fila && t.closest('[data-editar]')) {
      const d = $('#dlg-editar'), f = $('form', d); d.dataset.usuario = fila.dataset.usuario; $('[data-n]', d).textContent = fila.dataset.nombre; $('[data-u]', d).textContent = fila.dataset.usuario;
      f.nombre.value = fila.dataset.nombre; f.correo.value = fila.dataset.correo; f.rol.value = fila.dataset.rol; f.activa.value = fila.dataset.activa; abrir(d); return;
    }
    if (fila && t.closest('[data-restablecer]')) { const d = $('#dlg-restablecer'); d.dataset.usuario = fila.dataset.usuario; $('[data-n]', d).textContent = fila.dataset.nombre; abrir(d); return; }
    if (fila && t.closest('[data-eliminar]')) {
      const d = $('#dlg-eliminar'), f = $('form', d); f.reset(); d.dataset.usuario = fila.dataset.usuario; $('[data-n]', d).textContent = fila.dataset.nombre; $('[data-idl]', d).textContent = fila.dataset.usuario;
      $('[data-ok]', d).disabled = true; abrir(d); return;
    }
    if (t.closest('[data-cerrar-limite]')) { location.reload(); return; }
    if (t.closest('[data-copiar]')) { const i = $('[data-v=clave]'); i.select(); (navigator.clipboard ? navigator.clipboard.writeText(i.value) : Promise.resolve(document.execCommand('copy'))).catch(() => {}); t.closest('[data-copiar]').textContent = 'Copiada'; return; }
    if (t.closest('[data-listo]')) location.reload();
  });
  const el = $('#dlg-eliminar');
  if (el) $('[name=confirmar]', el).addEventListener('input', (e) => { $('[data-ok]', el).disabled = e.target.value.trim().toLowerCase() !== el.dataset.usuario; });
  document.addEventListener('submit', async (e) => {
    const f = e.target.closest('form[data-form]'); if (!f) return; e.preventDefault();
    const d = f.closest('dialog'), b = $('button[type=submit]', f), k = f.dataset.form, v = Object.fromEntries(new FormData(f));
    b.disabled = true; error(d, '');
    const r = k === 'crear' ? await pedir('/panel/cuentas/crear', v) : k === 'editar' ? await pedir('/panel/cuentas/editar', { ...v, usuario: d.dataset.usuario })
      : k === 'restablecer' ? await pedir('/panel/cuentas/restablecer', { usuario: d.dataset.usuario }) : await pedir('/panel/cuentas/eliminar', { usuario: d.dataset.usuario, confirmar: v.confirmar });
    if (r.estado !== 'ok') { error(d, MSG[r.estado] || MSG.error); b.disabled = k === 'eliminar' && $('[name=confirmar]', f).value.trim().toLowerCase() !== d.dataset.usuario; return; }
    d.close();
    if (!r.correo_enviado && r.correo_motivo === 'limite') {   // cupo de correos de la demo agotado: solo esperar
      const espera = r.correo_espera_min ? (r.correo_espera_min === 1 ? '1 minuto' : r.correo_espera_min + ' minutos') : 'una hora';
      const c = $('#dlg-limite'); $('[data-v=espera]', c).textContent = espera; c.showModal(); return;
    }
    if (r.clave) {
      const c = $('#dlg-clave'); $('[data-v=usuario]', c).value = r.usuario; $('[data-v=clave]', c).value = r.clave;
      $('[data-v=titulo]', c).textContent = r.correo_enviado ? 'Se envió por correo' : 'No se pudo enviar el correo';
      $('[data-v=nota]', c).textContent = r.correo_enviado ? 'Puede llegar a correo no deseado (spam): pídele que lo revise. Si no le llega, cópiala y envíasela tú por otro medio. No se vuelve a mostrar'
        : 'No le llegará por correo. Copia esta contraseña y envíasela tú por otro medio (chat o en persona). No se vuelve a mostrar';
      c.showModal();
    } else location.reload();
  });
})();
