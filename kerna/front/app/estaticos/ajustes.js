/* Ajustes: estado en memoria, aviso de cambios y envío del formulario (la escritura la hace el servidor con CSRF). */
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
  const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);

  /* Panel azul de cada sección: órbitas fijas y satélites que cambian con los controles (SVG chico, sin animación continua) */
  const N = (n) => Array.from({ length: n }, (_, i) => i);
  const sat = (cl, cx, r, i, n, off = 0) => '<circle class="' + cl + '" cx="' + cx + '" cy="150" r="' + r + '" transform="rotate(' + (i * 360 / Math.max(1, n) + off) + ' 150 150)"/>';
  const ORB = {
    proc: (v) => '<circle class="ao" cx="150" cy="150" r="120"/><circle class="ao" cx="150" cy="150" r="72"/>' + N(v.envios).map((i) => sat('as', 270, 10, i, v.envios)).join('') + N(v.reintentos).map((i) => sat('as2', 222, 6, i, v.reintentos)).join('')
      + '<circle class="acore" cx="150" cy="150" r="26"/><circle class="acore-l" cx="150" cy="150" r="9"/>' + (v.reprocesar ? '<circle class="pulse-ring" cx="150" cy="150" r="44"/>' : ''),
    ia: (v) => { const a = v.cadena[0] && v.cadena[0].on, b = v.cadena[1] && v.cadena[1].on, nc = Math.max(3, v.candidatos);
      return '<circle class="ao ' + (v.evaluador ? 'solid' : 'dim') + '" cx="150" cy="150" r="132"/>' + (v.evaluador ? N(v.candidatos).map((i) => sat('cd', 282, 4, i, nc, 9)).join('') + sat('as', 282, 9, 0, 1, 40) : '')
        + '<circle class="ao ' + (a ? 'solid' : 'dim') + '" cx="150" cy="150" r="62"/><circle class="ao ' + (b ? 'solid' : 'dim') + '" cx="150" cy="150" r="96"/>'
        + (a ? sat('as', 212, 11, 0, 1, 200) : '') + (b ? sat('as', 246, 8, 0, 1, 120) : '') + '<circle class="acore" cx="150" cy="150" r="20"/><circle class="acore-l" cx="150" cy="150" r="7"/>'; },
    comp: (v) => { const eq = [['analista', 'AN', 79.3, 79.3], ['comite', 'CE', 220.7, 79.3], ['auditoria', 'AU', 79.3, 220.7], ['legal', 'FL', 220.7, 220.7]];
      return '<circle class="ao" cx="150" cy="150" r="100"/>' + eq.map(([k, t, x, y]) => { const on = v.compartir.includes(k);
        return '<line class="alink' + (on ? '' : ' off') + '" x1="150" y1="150" x2="' + x + '" y2="' + y + '"/><circle class="team' + (on ? ' on' : '') + '" cx="' + x + '" cy="' + y + '" r="32"/><text class="team-t' + (on ? ' on' : '') + '" x="' + x + '" y="' + (y + 10) + '">' + t + '</text>'; }).join('')
        + sat('as', 250, 7, 0, 1, 20) + '<circle class="acore" cx="150" cy="150" r="22"/><circle class="acore-l" cx="150" cy="150" r="8"/>'; },
    plazos: (v) => '<circle class="ao" cx="150" cy="150" r="115"/><circle class="arc" cx="150" cy="150" r="115" pathLength="100" transform="rotate(-90 150 150)" style="stroke-dasharray:' + (v.maxresp / 60 * 100) + ' 100"/>'
      + sat('as', 265, 11, 0, 1, v.maxresp / 60 * 360 - 90) + '<circle class="ao" cx="150" cy="150" r="88" style="opacity:.5"/><circle class="arc2" cx="150" cy="150" r="88" pathLength="100" transform="rotate(-90 150 150)" style="stroke-dasharray:' + (v.alerta / 24 * 100) + ' 100"/>'
      + '<text class="bigtxt" x="150" y="156">' + v.maxresp + '<tspan font-size="28" dx="4">s</tspan></text><text class="subtxt" x="150" y="196">objetivo</text>',
  };
  const VIVO = { proc: (v) => v.envios + ' casos por ronda, ' + v.reintentos + ' reintentos', ia: (v) => (v.evaluador ? 'Revisor encendido' : 'Revisor apagado') + ', ' + v.candidatos + ' artículos por caso', comp: (v) => 'Compartido con ' + (v.compartir.length || 'nadie') + ' equipos', plazos: (v) => v.maxresp + ' segundos para responder' };
  function orbitas() { $$('[data-orb]').forEach((n) => { const g = n.dataset.orb; n.innerHTML = ORB[g](s); n.setAttribute('aria-label', VIVO[g](s)); }); }
  function pintar() {
    $$('.ctl').forEach((c) => {
      const k = c.dataset.k, it = items[k], v = s[k], dep = it.dep && !s[it.dep];
      c.classList.toggle('opacity-60', !!dep);
      $('[data-cambiado]', c).hidden = igual(v, rec[k]);
      if (it.t === 'sw') { $('.sw', c).setAttribute('aria-checked', v); $('[data-swt]', c).textContent = fmt(it, v); }
      if (it.t === 'rg') {
        const r = $('.range', c); r.value = v; r.disabled = !!dep; r.style.setProperty('--p', ((v - it.min) / (it.max - it.min) * 100) + '%'); r.setAttribute('aria-valuetext', fmt(it, v));
        $('[data-v]', c).textContent = fmt(it, v); r.title = 'De ' + fmt(it, it.min) + ' a ' + fmt(it, it.max) + ' · recomendado: ' + fmt(it, rec[k]); const fr = (rec[k] - it.min) / (it.max - it.min); $('[data-rc]', c).style.left = 'calc(' + fr * 100 + '% + ' + (8 - fr * 16) + 'px)';
        const a = aviso(k, v), p = $('[data-av]', c); p.hidden = !a; $('span', p).textContent = a;
      }
      if (it.t === 'sg') $$('button', c).forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.v) === v)));
      if (it.t === 'ch') $$('button', c).forEach((b) => { const on = v.includes(b.dataset.v); b.setAttribute('aria-pressed', on); b.classList.toggle('brand', on); b.classList.toggle('na', !on); });
      if (it.t === 'cd') {
        const host = $('[data-cadena]', c); host.textContent = '';
        v.forEach((m, i) => {
          const row = document.createElement('div'); row.className = 'cn-row'; row.style.opacity = m.on ? '' : '.65';
          row.innerHTML = '<span class="cn-n">' + (i + 1) + '</span><div class="flex-1 min-w-0"><b class="block text-[14px]"></b><span class="text-xs muted"></span></div><div class="flex items-center gap-1.5"></div>';
          $('b', row).textContent = M[m.v][0]; $('.muted', row).textContent = i === 0 ? 'Principal' : 'Respaldo';
          const bt = $('.flex.items-center', row);
          [[-1, 'arrow-up', 'Subir: '], [1, 'arrow-down', 'Bajar: ']].forEach(([d, ic, t]) => {
            const b = document.createElement('button'); b.type = 'button'; b.className = 'cn-b'; b.setAttribute('aria-label', t + M[m.v][0]); b.disabled = i + d < 0 || i + d >= v.length;
            b.innerHTML = '<k-ic n="' + ic + '" aria-hidden="true"><svg aria-hidden="true" focusable="false"><use href="/estaticos/iconos.svg#' + ic + '"/></svg></k-ic>'; b.onclick = () => { const a = [...s.cadena]; [a[i], a[i + d]] = [a[i + d], a[i]]; s.cadena = a; pintar(); }; bt.appendChild(b);
          });
          const sw = document.createElement('button'); sw.type = 'button'; sw.setAttribute('role', 'switch'); sw.className = 'sw ml-1'; sw.setAttribute('aria-checked', m.on); sw.setAttribute('aria-label', 'Usar ' + M[m.v][0]); sw.onclick = () => { m.on = !m.on; pintar(); }; bt.appendChild(sw);
          host.appendChild(row);
        });
      }
    });
    const n = Object.keys(rec).filter((k) => !igual(s[k], base[k])).length, f = $('[data-barra]');
    f.hidden = !n; $('[data-ncambios]', f).textContent = n + (n === 1 ? ' cambio sin guardar' : ' cambios sin guardar');
    $('input[name=valores]', f).value = JSON.stringify(s);
    orbitas();
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
