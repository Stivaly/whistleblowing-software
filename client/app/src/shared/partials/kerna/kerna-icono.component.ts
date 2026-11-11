import {ChangeDetectionStrategy, Component} from "@angular/core";

/**
 * Ícono de marca de Kerna: el ÚNICO lugar donde vive el dibujo. Para cambiar de ícono se reemplaza el <svg> de esta
 * plantilla (las otras opciones están en kerna/docs/diseno/opciones-icono/svg/). Debe ser monocromo con
 * `currentColor`, caja 24x24, y sin recursos externos (la CSP de Veridy no los permite).
 * Vigente: "articulo-marcado" (artículo con marcador de cita).
 */
@Component({
  selector: "src-kerna-icono",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg class="kerna-icono" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor"
      stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path d="M6 2.8h8.4L19 7.4v13.8H6z"/>
    <path d="M14.4 2.8v4.6H19"/>
    <path d="M9.6 12.6h5.8M9.6 16.2h5.8"/>
    <path d="M8.6 2.8v6.6l1.9-1.5 1.9 1.5V2.8" fill="currentColor" stroke="none"/>
  </svg>`
})
export class KernaIconoComponent {}
