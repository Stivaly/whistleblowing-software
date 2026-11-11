import {ChangeDetectionStrategy, Component, Input} from "@angular/core";
import {EstadoId, Variante, claveEscena} from "./kerna-estados";
import {KernaDibujoComponent} from "./kerna-dibujo.component";

/** Miniatura de la escena del estado (el color nunca es la única señal: la forma cambia por estado). Sin animación. */
@Component({
  selector: "src-kerna-glifo",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [KernaDibujoComponent],
  template: `<src-kerna-dibujo class="kerna-glifo-svg" [escena]="clave"></src-kerna-dibujo>`
})
export class KernaGlifoComponent {
  protected clave = "sin-info";
  @Input() set estado(id: EstadoId) {
    this.id = id;
    this.clave = claveEscena(id, this.vari);
  }
  @Input() set variante(v: Variante) {
    this.vari = v;
    this.clave = claveEscena(this.id, v);
  }
  private id: EstadoId = "sin-info";
  private vari: Variante = null;
}
