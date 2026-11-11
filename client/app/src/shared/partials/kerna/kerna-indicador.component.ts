import {Component, HostListener, OnDestroy, OnInit, inject} from "@angular/core";
import {TranslateService} from "@ngx-translate/core";
import {KernaService} from "./kerna.service";
import {KernaIconoComponent} from "./kerna-icono.component";
import {KernaGlifoComponent} from "./kerna-glifo.component";
import {claveModo, claveTexto, resumen} from "./kerna-estados";

/**
 * Indicador de Kerna: píldora con el ícono de marca, una silueta de estado y la etiqueta, encima de la denuncia.
 * Tooltip accesible (patrón tooltip del APG y WCAG 1.4.13): aparece con el puntero y con el foco del teclado, se
 * descarta con Esc sin mover el foco, no se cierra al pasar el puntero encima y se asocia con `aria-describedby`.
 * Un clic o Enter abre o cierra el panel (`src-kerna-panel`).
 */
@Component({
  selector: "src-kerna-indicador",
  standalone: true,
  imports: [KernaIconoComponent, KernaGlifoComponent],
  templateUrl: "./kerna-indicador.component.html"
})
export class KernaIndicadorComponent implements OnInit, OnDestroy {
  protected k = inject(KernaService);
  private translate = inject(TranslateService);

  readonly idTooltip = "kerna-tooltip";
  readonly idPanel = "kerna-panel";
  protected claveTexto = claveTexto;

  private enPuntero = false;
  private enFoco = false;
  protected descartado = false;
  private retraso: ReturnType<typeof setTimeout> | null = null;
  protected visible = false;

  ngOnInit(): void {
    this.k.iniciar();
  }

  ngOnDestroy(): void {
    this.limpiar();
    this.k.detener();
  }

  protected t(clave: string, params?: Record<string, string | number>): string {
    return this.translate.instant(clave, params);
  }

  protected resumenTexto(): string {
    const r = this.k.resultado();
    if (!r) {
      return "";
    }
    const s = resumen(r);
    return this.t(s.clave, s.params);
  }

  protected modoTexto(): string {
    const r = this.k.resultado();
    return r ? this.t(claveModo(r)) : "";
  }

  private limpiar(): void {
    if (this.retraso) {
      clearTimeout(this.retraso);
      this.retraso = null;
    }
  }

  private actualizarVisible(): void {
    this.visible = (this.enPuntero || this.enFoco) && !this.descartado;
    if (!this.enPuntero && !this.enFoco) {
      this.descartado = false;
    }
  }

  protected alEntrarPuntero(): void {
    this.limpiar();
    this.retraso = setTimeout(() => { this.enPuntero = true; this.actualizarVisible(); }, 200);
  }

  protected alSalirPuntero(): void {
    this.limpiar();
    // Pequeño retraso: permite llevar el puntero desde el botón al tooltip sin que se cierre (WCAG 1.4.13, "sobrevolable")
    this.retraso = setTimeout(() => { this.enPuntero = false; this.actualizarVisible(); }, 200);
  }

  protected alTenerFoco(): void {
    this.enFoco = true;
    this.actualizarVisible();
  }

  protected alPerderFoco(): void {
    this.enFoco = false;
    this.actualizarVisible();
  }

  /** Esc descarta el tooltip sin mover el foco (WCAG 1.4.13, "descartable"). */
  @HostListener("document:keydown.escape")
  protected descartar(): void {
    if (this.visible) {
      this.descartado = true;
      this.actualizarVisible();
    }
  }
}
