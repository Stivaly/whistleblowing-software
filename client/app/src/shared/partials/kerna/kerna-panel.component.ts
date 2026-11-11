import {Component, effect, inject, untracked} from "@angular/core";
import {FormsModule} from "@angular/forms";
import {TranslateService} from "@ngx-translate/core";
import {KernaService} from "./kerna.service";
import {KernaIconoComponent} from "./kerna-icono.component";
import {KernaArticulo, KernaArticuloClasificado, MAX_OBSERVACION} from "./kerna-notas";
import {ResultadoEstado, claveTexto, codigoSeguimiento, esProvisional, tieneArticulos} from "./kerna-estados";

interface Valoracion {
  valor: "arriba" | "abajo" | null;
  obs: string;
  enviada: boolean;
}

/**
 * Panel de Kerna: sugerencia por artículo (explicación, cita literal y enlace a la Biblioteca del Congreso Nacional),
 * valoración arriba/abajo con observación opcional, clasificación final y código de seguimiento copiable.
 * Se abre y se cierra desde el indicador. Nunca bloquea la clasificación manual del caso (que sigue siendo el cambio
 * de estado de siempre): es una tarjeta más del caso.
 */
@Component({
  selector: "src-kerna-panel",
  standalone: true,
  imports: [FormsModule, KernaIconoComponent],
  templateUrl: "./kerna-panel.component.html"
})
export class KernaPanelComponent {
  protected k = inject(KernaService);
  private translate = inject(TranslateService);

  protected readonly maxObservacion = MAX_OBSERVACION;
  protected claveTexto = claveTexto;
  protected tieneArticulos = tieneArticulos;

  protected incluidos = new Set<string>();
  protected agregados: string[] = [];
  protected otro = "";
  protected obsClasificacion = "";
  protected valoraciones: Record<string, Valoracion> = {};
  protected codigoCopiado = false;
  private claveSincronizada = "";

  constructor() {
    effect(() => {
      const r = this.k.resultado();
      untracked(() => this.sincronizar(r));
    });
  }

  protected t(clave: string, params?: Record<string, string | number>): string {
    return this.translate.instant(clave, params);
  }

  /** Estado cuyo contenido se muestra (el previo si no hay conexión). */
  protected base(e: ResultadoEstado): ResultadoEstado {
    return e.id === "sin-conexion" && e.previo ? e.previo : e;
  }

  protected articulos(e: ResultadoEstado): KernaArticulo[] {
    const s = this.base(e).sugerencia;
    return s ? [...s.articulos].sort((a, b) => b.confianza - a.confianza) : []; // el orden implica la confianza; no se muestra el número
  }

  protected codigo(e: ResultadoEstado): string | null {
    return codigoSeguimiento(e);
  }

  protected muestraActualizar(e: ResultadoEstado): boolean {
    return esProvisional(e.id) && e.id !== "sin-conexion";
  }

  protected muestraMensaje(e: ResultadoEstado): boolean {
    return e.id !== "lista" && e.id !== "contingencia";
  }

  protected enlaceSeguro(url: string): boolean {
    return /^https:\/\//i.test(url);
  }

  protected deshabilitado(e: ResultadoEstado): boolean {
    return e.id === "sin-conexion" || this.k.enviando();
  }

  /** Reinicia el estado local solo si cambió la sugerencia o la clasificación guardada (no pisa lo que se está escribiendo). */
  private sincronizar(r: ResultadoEstado | null): void {
    const clave = r ? `${r.sugerencia ? r.sugerencia.id_solicitud : ""}|${r.clasificacion ? JSON.stringify(r.clasificacion) : ""}` : "";
    if (clave === this.claveSincronizada) {
      return;
    }
    this.claveSincronizada = clave;
    this.incluidos = new Set<string>();
    this.agregados = [];
    this.obsClasificacion = "";
    this.valoraciones = {};
    const c = r ? r.clasificacion : null;
    if (c) {
      for (const a of c.articulos) {
        if (a.origen === "sugerido") {
          this.incluidos.add(a.id_articulo);
        } else {
          this.agregados.push(a.id_articulo);
        }
      }
      this.obsClasificacion = c.observacion || "";
    }
  }

  protected valoracion(a: KernaArticulo): Valoracion {
    let v = this.valoraciones[a.id_sugerencia];
    if (!v) {
      const previa = this.k.notas()?.feedback[a.id_sugerencia];
      v = {valor: previa ? previa.valoracion : null, obs: previa?.observacion || "", enviada: !!previa};
      this.valoraciones[a.id_sugerencia] = v;
    }
    return v;
  }

  protected elegir(a: KernaArticulo, valor: "arriba" | "abajo"): void {
    const v = this.valoracion(a);
    v.valor = valor;
    v.enviada = false;
  }

  protected async enviarValoracion(a: KernaArticulo): Promise<void> {
    const v = this.valoracion(a);
    if (!v.valor) {
      return;
    }
    v.enviada = await this.k.guardarValoracion(a.id_sugerencia, v.valor, v.obs);
  }

  protected alternarIncluido(id: string, marcado: boolean): void {
    if (marcado) {
      this.incluidos.add(id);
    } else {
      this.incluidos.delete(id);
    }
  }

  protected agregarOtro(): void {
    const t = this.otro.trim();
    if (t && !this.agregados.includes(t)) {
      this.agregados = [...this.agregados, t];
    }
    this.otro = "";
  }

  protected quitar(texto: string): void {
    this.agregados = this.agregados.filter(x => x !== texto);
  }

  protected async guardarClasificacion(e: ResultadoEstado, ninguno = false): Promise<void> {
    this.agregarOtro();
    const articulos: KernaArticuloClasificado[] = [];
    if (!ninguno) {
      for (const a of this.base(e).sugerencia?.articulos || []) {
        if (this.incluidos.has(a.id_articulo)) {
          articulos.push({id_articulo: a.id_articulo, origen: "sugerido"});
        }
      }
      for (const x of this.agregados) {
        articulos.push({id_articulo: x, origen: "agregado_por_auditor"});
      }
    }
    await this.k.guardarClasificacion(articulos, this.obsClasificacion);
  }

  protected async copiarCodigo(codigo: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(codigo);
      this.codigoCopiado = true;
      setTimeout(() => { this.codigoCopiado = false; }, 3000);
    } catch {
      this.codigoCopiado = false;
    }
  }
}
