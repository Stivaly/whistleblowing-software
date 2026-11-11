import {Injectable, inject, signal} from "@angular/core";
import {HttpBackend, HttpClient} from "@angular/common/http";
import {Comment} from "@app/models/app/shared-public-model";
import {AuthenticationService} from "@app/services/helper/authentication.service";
import {ReceiverTipService} from "@app/services/helper/receiver-tip.service";
import {
  KernaClasificacion, KernaFeedback, NotasKerna, MAX_OBSERVACION, extraerNotas, VERSION_NOTAS
} from "./kerna-notas";
import {ResultadoEstado, deducirEstado, esProvisional} from "./kerna-estados";

/** Cada cuánto se vuelve a consultar el caso mientras el estado puede cambiar solo (supuesto; ver propuesta 1.3). */
const INTERVALO_CONSULTA_MS = 20 * 1000;
/** Fallos seguidos de la consulta para pasar a "sin conexión" (evita parpadeos por un fallo aislado). */
const FALLOS_PARA_SIN_CONEXION = 2;

/**
 * Estado de Kerna del caso abierto, compartido por el indicador y el panel.
 * - Lee las notas de `tip.comments` (que ya trae `GET api/recipient/rtips/<id>`); no hay endpoints nuevos.
 * - Escribe valoraciones y clasificaciones como comentarios `internal` con el mismo método que usa el hilo de comentarios.
 * - La consulta periódica usa un HttpClient sin interceptores para no activar el panel de carga global de Veridy
 *   (bloquearía la pantalla cada 20 s); agrega por su cuenta la cabecera de sesión.
 */
@Injectable({providedIn: "root"})
export class KernaService {
  private auth = inject(AuthenticationService);
  private rTip = inject(ReceiverTipService);
  private http = new HttpClient(inject(HttpBackend));

  readonly resultado = signal<ResultadoEstado | null>(null);
  readonly notas = signal<NotasKerna | null>(null);
  readonly abierto = signal(false);
  readonly enviando = signal(false);

  private temporizador: ReturnType<typeof setInterval> | null = null;
  private fallos = 0;
  private fallaDeRed = false;
  private escuchando = false;

  private alVolverLaRed = () => { this.actualizar(); };
  private alPerderLaRed = () => { this.fallaDeRed = true; this.recalcular(); };
  private alVolverVisible = () => { if (!document.hidden) { this.actualizar(); } };

  /** Arranca para el caso que tiene abierto `ReceiverTipService`. Solo para destinatarios. */
  iniciar(): void {
    this.detener();
    if (!this.auth.session || this.auth.session.role !== "receiver") {
      return;
    }
    this.recalcular();
    this.temporizador = setInterval(() => this.tic(), INTERVALO_CONSULTA_MS);
    window.addEventListener("online", this.alVolverLaRed);
    window.addEventListener("offline", this.alPerderLaRed);
    document.addEventListener("visibilitychange", this.alVolverVisible);
    this.escuchando = true;
  }

  detener(): void {
    if (this.temporizador) {
      clearInterval(this.temporizador);
      this.temporizador = null;
    }
    if (this.escuchando) {
      window.removeEventListener("online", this.alVolverLaRed);
      window.removeEventListener("offline", this.alPerderLaRed);
      document.removeEventListener("visibilitychange", this.alVolverVisible);
      this.escuchando = false;
    }
    this.fallos = 0;
    this.fallaDeRed = false;
    this.resultado.set(null);
    this.notas.set(null);
    this.abierto.set(false);
  }

  alternar(): void {
    this.abierto.set(!this.abierto());
  }

  private tic(): void {
    if (document.hidden) {
      return;
    }
    this.recalcular(); // los umbrales de tiempo avanzan aunque no haya consulta
    const r = this.resultado();
    if (r && esProvisional(r.id)) {
      this.actualizar();
    }
  }

  /** Vuelve a leer el caso. `manual`: el auditor pidió reintentar, un fallo cuenta como definitivo. */
  actualizar(manual = false): Promise<void> {
    const tip = this.rTip.tip;
    if (!tip || !tip.id) {
      return Promise.resolve();
    }
    return new Promise<void>(resolver => {
      this.http.get<{comments?: Comment[]}>(`api/recipient/rtips/${tip.id}`, {headers: this.auth.getHeader()}).subscribe({
        next: (respuesta) => {
          if (this.rTip.tip === tip) {
            tip.comments = respuesta.comments || [];
          }
          this.fallos = 0;
          this.fallaDeRed = false;
          this.recalcular();
          resolver();
        },
        error: () => {
          this.fallos = manual ? FALLOS_PARA_SIN_CONEXION : this.fallos + 1;
          this.fallaDeRed = this.fallos >= FALLOS_PARA_SIN_CONEXION;
          this.recalcular();
          resolver();
        }
      });
    });
  }

  /** Recalcula las notas y el estado con lo que hay en `tip.comments` y la hora actual. */
  recalcular(): void {
    const tip = this.rTip.tip;
    if (!tip || !tip.id) {
      this.resultado.set(null);
      this.notas.set(null);
      return;
    }
    const notas = extraerNotas(tip.comments, tip.receivers);
    this.notas.set(notas);
    this.resultado.set(deducirEstado({notas, creacion: Date.parse(tip.creation_date), ahora: Date.now(), fallaDeRed: this.fallaDeRed}));
  }

  private recortar(texto: string | undefined): string | undefined {
    const t = (texto || "").trim().slice(0, MAX_OBSERVACION);
    return t ? t : undefined;
  }

  private enviarNota(nota: object): Promise<boolean> {
    this.enviando.set(true);
    return new Promise<boolean>(resolver => {
      this.rTip.newComment(JSON.stringify(nota), "internal").subscribe({
        next: (comentario) => {
          this.rTip.tip.comments = [...(this.rTip.tip.comments || []), comentario];
          this.fallos = 0;
          this.fallaDeRed = false;
          this.recalcular();
          this.enviando.set(false);
          this.actualizar(); // trae el comentario tal como lo guardó el servidor
          resolver(true);
        },
        error: () => {
          this.fallos = FALLOS_PARA_SIN_CONEXION;
          this.fallaDeRed = true;
          this.recalcular();
          this.enviando.set(false);
          resolver(false);
        }
      });
    });
  }

  guardarValoracion(idSugerencia: string, valoracion: "arriba" | "abajo", observacion?: string): Promise<boolean> {
    const nota: KernaFeedback = {tipo: "kerna_feedback", version: VERSION_NOTAS, id_sugerencia: idSugerencia, valoracion};
    const obs = this.recortar(observacion);
    if (obs) {
      nota.observacion = obs;
    }
    return this.enviarNota(nota);
  }

  guardarClasificacion(articulos: KernaClasificacion["articulos"], observacion?: string): Promise<boolean> {
    const nota: KernaClasificacion = {tipo: "kerna_clasificacion", version: VERSION_NOTAS, articulos};
    const obs = this.recortar(observacion);
    if (obs) {
      nota.observacion = obs;
    }
    return this.enviarNota(nota);
  }
}
