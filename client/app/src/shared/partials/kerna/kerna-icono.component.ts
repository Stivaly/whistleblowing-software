import {ChangeDetectionStrategy, Component} from "@angular/core";

/**
 * Marca de Kerna (concepto "Núcleo"): órbitas con un satélite unido al núcleo. Es el ÚNICO lugar donde vive el dibujo.
 * Usa las variables --pi (trazo) y --acc (acento) del bloque; sin recursos externos (la CSP de Veridy no los permite).
 */
@Component({
  selector: "src-kerna-icono",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg class="kerna-icono kerna-svg" viewBox="0 0 48 48" width="24" height="24" aria-hidden="true" focusable="false">
    <circle class="o2" cx="24" cy="24" r="20"/><circle class="o2" cx="24" cy="24" r="12"/>
    <circle class="fa" cx="24" cy="24" r="5"/><circle class="fa" cx="38" cy="10" r="3.5"/><path class="th2" d="M24,24 L38,10"/>
  </svg>`
})
export class KernaIconoComponent {}
