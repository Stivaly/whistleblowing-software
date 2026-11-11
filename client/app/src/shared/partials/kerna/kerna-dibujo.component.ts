import {ChangeDetectionStrategy, Component, Input, inject} from "@angular/core";
import {DomSanitizer, SafeHtml} from "@angular/platform-browser";
import {ESCENAS, MATERIAS, Materia} from "./kerna-ilustraciones";

/**
 * Dibujo SVG del concepto "Núcleo": escena de un estado (viewBox 160x120) o pictograma de materia (48x48).
 * El contenido sale solo de constantes del código (kerna-ilustraciones.ts), nunca de datos del caso, por eso se marca
 * como confiable. Los colores y las animaciones se definen en kerna.css por `data-estado` y respetan prefers-reduced-motion.
 */
@Component({
  selector: "src-kerna-dibujo",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg [attr.viewBox]="caja" [class]="clase" aria-hidden="true" focusable="false" [innerHTML]="html"></svg>`
})
export class KernaDibujoComponent {
  private san = inject(DomSanitizer);
  protected html: SafeHtml = "";
  protected caja = "0 0 160 120";
  protected clase = "kerna-svg";

  @Input() set escena(clave: string | null) {
    if (clave) {
      this.caja = "0 0 160 120";
      this.clase = "kerna-svg kerna-escena";
      this.html = this.san.bypassSecurityTrustHtml(ESCENAS[clave] || "");
    }
  }

  @Input() set materia(m: Materia | null) {
    if (m) {
      this.caja = "0 0 48 48";
      this.clase = "kerna-svg kerna-materia";
      this.html = this.san.bypassSecurityTrustHtml(MATERIAS[m]);
    }
  }
}
