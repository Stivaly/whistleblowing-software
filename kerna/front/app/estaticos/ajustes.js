/* Ajustes: estado en memoria, texto «Así queda», aviso de cambios y envío del formulario (la escritura la hace el servidor con CSRF). */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  let D; try { D = JSON.parse($('#ajustes-datos').textContent); } catch (_) { return; }
  const clon = (x) => JSON.parse(JSON.stringify(x));
  const rec = D.recomendado, base = clon(D.valores), M = D.modelos;
  let s = clon(D.valores);
  const items = {}; D.grupos.forEach((g) => g.items.forEach((it) => { items[it.k] = it; }));
  const fh = (v) => v >= 3600 ? v / 3600 + ' h' : v >= 60 ? v / 60 + ' min' : v + ' s';
  const fmt = (it, v) => {
    if (it.t === 'sw') return v ? 'Encendido' : 'Apagado';
    if (it.t === 'rg') return v === 0 && it.cero ? it.cero : v + ' ' + (v === 1 ? it.u[0] : it.u[1]);
    if (it.t === 'sg') return (it.o.find((o) => o.v === v) || {}).t;
    if (it.t === 'ch') return v.length ? v.map((x) => it.o.find((o) => o.v === x).t).join(', ') : 'Nadie';
    return v.filter((m) => m.on).map((m) => M[m.v][0]).join(' → ') || 'Ninguno';
  };
  const aviso = (k, v) => k === 'envios' && v > 7 ? 'Con tantos casos juntos puede superarse el límite del proveedor de IA.' : k === 'reintentos' && v === 0 ? 'Los casos fallidos quedarán en revisión manual sin nuevo intento.' : '';
  const vivo = (id) => {
    if (id === 'proc') return 'Cada ronda envía ' + s.envios + (s.envios === 1 ? ' caso' : ' casos') + ' a Kerna. ' + (s.reintentos === 0 ? 'Los casos que fallen no se reintentan.' : 'Un caso que falla se reintenta hasta ' + s.reintentos + (s.reintentos === 1 ? ' vez' : ' veces') + ', cada ' + s.espera + ' h.') + ' Veridy se revisa cada ' + fh(s.revision) + '.' + (s.reprocesar ? ' Al guardar, los casos en revisión manual vuelven a la fila.' : '');
    if (id === 'ia') return (s.evaluador ? 'El revisor está encendido y compara ' + s.candidatos + ' artículos por caso.' : 'El revisor está apagado: más rápido y barato, con menos control de citas.') + ' Orden de modelos: ' + fmt(items.cadena, s.cadena) + '.';
    if (id === 'comp') return s.compartir.length ? 'Cada caso se comparte con: ' + fmt(items.compartir, s.compartir) + '.' : 'Los casos no se comparten con ningún equipo.';
    return 'Un caso se marca como lento pasados ' + s.maxresp + ' segundos y se destaca si sigue sin sugerencia tras ' + s.alerta + (s.alerta === 1 ? ' hora' : ' horas') + '.';
  };
  const sats = { proc: () => s.envios, ia: () => s.evaluador ? Math.min(s.candidatos, 12) : 0, comp: () => s.compartir.length, plazos: () => Math.round(s.maxresp / 5) };
  const NS = 'http://www.w3.org/2000/svg';
  function pintarSats(id, n) {
    const svg = $('[data-sats="' + id + '"]'); if (!svg || svg.__n === n) return; svg.__n = n; svg.textContent = '';
    for (let i = 0; i < n; i++) { const a = i * 2 * Math.PI / Math.max(1, n), c = document.createElementNS(NS, 'circle'); c.setAttribute('class', 'as'); c.setAttribute('r', 10); c.setAttribute('cx', 150 + 120 * Math.cos(a)); c.setAttribute('cy', 150 + 120 * Math.sin(a)); svg.appendChild(c); }
  }
  const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  function pintar() {
    $$('.ctl').forEach((c) => {
      const k = c.dataset.k, it = items[k], v = s[k], dep = it.dep && !s[it.dep];
      c.classList.toggle('opacity-60', !!dep);
      $('[data-cambiado]', c).hidden = igual(v, rec[k]);
      if (it.t === 'sw') { $('.sw', c).setAttribute('aria-checked', v); $('[data-swt]', c).textContent = fmt(it, v); }
      if (it.t === 'rg') {
        const r = $('.range', c); r.value = v; r.disabled = !!dep; r.style.setProperty('--p', ((v - it.min) / (it.max - it.min) * 100) + '%'); r.setAttribute('aria-valuetext', fmt(it, v));
        $('[data-v]', c).textContent = fmt(it, v); $('[data-min]', c).textContent = fmt(it, it.min); $('[data-max]', c).textContent = fmt(it, it.max); $('[data-rec]', c).textContent = 'Recomendado: ' + fmt(it, rec[k]);
        const a = aviso(k, v), p = $('[data-av]', c); p.hidden = !a; $('span', p).textContent = a;
      }
      if (it.t === 'sg') $$('button', c).forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.v) === v)));
      if (it.t === 'ch') $$('button', c).forEach((b) => { const on = v.includes(b.dataset.v); b.setAttribute('aria-pressed', on); b.classList.toggle('brand', on); b.classList.toggle('na', !on); });
      if (it.t === 'cd') {
        const host = $('[data-cadena]', c); host.textContent = '';
        v.forEach((m, i) => {
          const row = document.createElement('div'); row.className = 'cn-row'; row.style.opacity = m.on ? '' : '.65';
          row.innerHTML = '<span class="cn-n">' + (i + 1) + '</span><div class="flex-1 min-w-0"><b class="block text-[14px]"></b><span class="text-xs muted"></span></div><div class="flex items-center gap-1.5"></div>';
          $('b', row).textContent = M[m.v][0]; $('.muted', row).textContent = M[m.v][1];
          const bt = $('.flex.items-center', row);
          [[-1, 'arrow-up', 'Subir: '], [1, 'arrow-down', 'Bajar: ']].forEach(([d, ic, t]) => {
            const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-sec !min-h-[40px] !w-10 !px-0'; b.setAttribute('aria-label', t + M[m.v][0]); b.disabled = i + d < 0 || i + d >= v.length;
            b.innerHTML = '<k-ic n="' + ic + '" aria-hidden="true"><svg aria-hidden="true" focusable="false"><use href="/estaticos/iconos.svg#' + ic + '"/></svg></k-ic>'; b.onclick = () => { const a = [...s.cadena]; [a[i], a[i + d]] = [a[i + d], a[i]]; s.cadena = a; pintar(); }; bt.appendChild(b);
          });
          const sw = document.createElement('button'); sw.type = 'button'; sw.setAttribute('role', 'switch'); sw.className = 'sw ml-1'; sw.setAttribute('aria-checked', m.on); sw.setAttribute('aria-label', 'Usar ' + M[m.v][0]); sw.onclick = () => { m.on = !m.on; pintar(); }; bt.appendChild(sw);
          host.appendChild(row);
        });
      }
    });
    $$('[data-vivo]').forEach((n) => { n.textContent = vivo(n.dataset.vivo); });
    Object.keys(sats).forEach((id) => pintarSats(id, sats[id]()));
    const n = Object.keys(rec).filter((k) => !igual(s[k], base[k])).length, f = $('[data-barra]');
    f.hidden = !n; $('[data-ncambios]', f).textContent = n + (n === 1 ? ' cambio sin guardar' : ' cambios sin guardar');
    $('input[name=valores]', f).value = JSON.stringify(s);
  }
  $$('.ctl').forEach((c) => {
    const k = c.dataset.k, it = items[k];
    if (it.t === 'sw') $('.sw', c).onclick = () => { s[k] = !s[k]; pintar(); };
    if (it.t === 'rg') $('.range', c).oninput = (e) => { s[k] = Number(e.target.value); pintar(); };
    if (it.t === 'sg') $$('button', c).forEach((b) => { b.onclick = () => { s[k] = Number(b.dataset.v); pintar(); }; });
    if (it.t === 'ch') $$('button', c).forEach((b) => { b.onclick = () => { const v = b.dataset.v; s[k] = s[k].includes(v) ? s[k].filter((x) => x !== v) : [...s[k], v]; pintar(); }; });
  });
  $('[data-restaurar]').onclick = () => { s = clon(rec); pintar(); };
  $('[data-descartar]').onclick = () => { s = clon(base); pintar(); };
  pintar();
})();
