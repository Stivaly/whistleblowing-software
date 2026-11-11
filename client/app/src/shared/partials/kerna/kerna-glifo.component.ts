import {ChangeDetectionStrategy, Component, Input} from "@angular/core";
import {EstadoId} from "./kerna-estados";

/** Silueta secundaria de cada estado (el color nunca es la única señal). Usa `currentColor`; las marcas internas, blanco. */
@Component({
  selector: "src-kerna-glifo",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg class="kerna-glifo-svg" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
    @switch (estado) {
      @case ("sin-info") { <circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-dasharray="2.2 1.8"/> }
      @case ("generando") { <circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="23 8.4" stroke-linecap="round"/> }
      @case ("lista") { <circle cx="7" cy="7" r="6.2" fill="currentColor"/><path d="M4 7.2 6.2 9.3 10 5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/> }
      @case ("contingencia") { <path d="M7 .6 13.4 7 7 13.4.6 7z" fill="currentColor"/><path d="M4.4 7h5.2" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/> }
      @case ("revision-tiempo") { <path d="M3 1.2h8M3 12.8h8M3.8 1.2c0 3 2.4 4 3.2 5.8-.8 1.8-3.2 2.8-3.2 5.8M10.2 1.2c0 3-2.4 4-3.2 5.8.8 1.8 3.2 2.8 3.2 5.8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><path d="M4.6 11.8c.6-1.2 1.4-1.8 2.4-1.8s1.8.6 2.4 1.8z" fill="currentColor"/> }
      @case ("revision-citas") { <rect x=".8" y=".8" width="12.4" height="12.4" rx="2.4" fill="currentColor"/><path d="M5.2 5.4c0-1.1.8-1.8 1.9-1.8s1.8.7 1.8 1.6c0 1.5-1.8 1.5-1.8 3" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/><circle cx="7.1" cy="10.6" r=".95" fill="#fff"/> }
      @case ("sin-normativa") { <circle cx="6" cy="6" r="4.4" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M9.3 9.3 13 13" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M4 6h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/> }
      @case ("cadena-agotada") { <path d="M4.2.8h5.6l3.4 3.4v5.6l-3.4 3.4H4.2L.8 9.8V4.2z" fill="currentColor"/><path d="M4 7h6" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/> }
      @case ("nucleo-no-disponible") { <path d="M7 .8 13.4 12.6H.6z" fill="currentColor" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="M7 5.2v3.4" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/><circle cx="7" cy="10.5" r=".9" fill="#fff"/> }
      @case ("conector-inactivo") { <path d="M3.9.8h6.2l3.1 6.2-3.1 6.2H3.9L.8 7z" fill="currentColor"/><circle cx="4.3" cy="7" r="1" fill="#fff"/><circle cx="7" cy="7" r="1" fill="#fff"/><circle cx="9.7" cy="7" r="1" fill="#fff"/> }
      @case ("sin-conexion") { <circle cx="7" cy="7" r="5.6" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M3 11 11 3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/> }
      @case ("valorada") { <path d="M3 13V1.2M3 1.8h8l-2 3 2 3H3" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/> }
    }
  </svg>`
})
export class KernaGlifoComponent {
  @Input() estado!: EstadoId;
}
