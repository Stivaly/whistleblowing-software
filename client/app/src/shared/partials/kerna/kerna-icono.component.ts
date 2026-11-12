import {ChangeDetectionStrategy, Component, Input} from "@angular/core";

/**
 * Símbolo de Kerna AI ("guilloché", kerna/diseno/logo/kerna-logo.html): anillo y roseta de elipses punteadas, una órbita
 * trazada con el satélite lima y el núcleo. Es la marca y también el indicador de estado. El SVG va en línea (las animaciones
 * CSS no cruzan <use>) y sin atributos style (CSP de Veridy): colores y tiempos van por clases en kerna.css.
 *  - marca: satélite en su órbita, quieto.   - lista: satélite en su órbita, girando.   - busca: gira rápido, sin satélite.
 *  - vacio: roseta quieta, sin órbita trazada.   - apagado: roseta quieta con opacidad baja.
 * `pequeno` (<= 24 px): 6 elipses continuas.
 */
export type FormaSimbolo = "marca" | "lista" | "busca" | "vacio" | "apagado";

@Component({
  selector: "src-kerna-icono",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg [class]="clase" viewBox="-1 -1 66 66" aria-hidden="true" focusable="false">
    @if (!pequeno) { <circle class="k-orb k-anillo" cx="32" cy="32" r="30.5"/> }
    <g class="k-roseta">
      @for (a of angulos; track a) {
        <ellipse [class]="pequeno ? 'k-orb k-cont' : 'k-orb k-ros'" cx="32" cy="32" rx="27" ry="8" [attr.transform]="'rotate(' + a + ' 32 32)'"/>
      }
    </g>
    @if (conOrbita) {
      <g class="k-camino">
        <ellipse class="k-orb k-guia" cx="32" cy="32" rx="27" ry="8"/>
        @if (conSatelite) { <circle class="k-sat" cx="59" cy="32" r="3.8"/> }
      </g>
    }
    <g class="k-latido"><circle class="k-nuc" cx="32" cy="32" r="5.4"/><circle class="k-nuc-l" cx="32" cy="32" r="2"/></g>
  </svg>`
})
export class KernaIconoComponent {
  protected clase = "kerna-icono kerna-sim";
  protected angulos: number[] = [15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165];
  protected conOrbita = true;
  protected conSatelite = true;
  protected pequeno = false;
  private f: FormaSimbolo = "marca";

  @Input() set forma(f: FormaSimbolo) {
    this.f = f;
    this.calcular();
  }

  @Input() set chico(v: boolean) {
    this.pequeno = v;
    this.calcular();
  }

  private calcular(): void {
    this.angulos = this.pequeno ? [30, 60, 90, 120, 150] : [15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165];
    this.conOrbita = this.f !== "vacio" && this.f !== "apagado";
    this.conSatelite = this.f !== "busca";
    this.clase = `kerna-icono kerna-sim k-${this.f}`;
  }
}
