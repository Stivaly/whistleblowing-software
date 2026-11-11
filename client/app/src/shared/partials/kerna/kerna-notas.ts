/**
 * Lectura y validación de las notas internas de Kerna (contrato: kerna/docs/contratos.md, version 1).
 * Módulo puro: no importa Angular, para poder probarlo con Node (ver kerna-pruebas.ts).
 */

/** Los destinatarios cuyo nombre empieza así son la cuenta de servicio de Kerna (único lugar donde se define). */
export const PREFIJO_CUENTA_KERNA = "Kerna AI";

export const VERSION_NOTAS = 1;
export const MAX_OBSERVACION = 500;

export interface ComentarioEntrada {
  id?: string;
  creation_date: string;
  content: string;
  author_id?: string;
  visibility: string;
  type?: string;
}

export interface DestinatarioEntrada {
  id: string;
  name: string;
}

export interface KernaArticulo {
  id_sugerencia: string;
  id_articulo: string;
  norma: string;
  articulo: string;
  explicacion: string;
  cita: string;
  enlace_fuente: string;
  confianza: number;
}

export interface KernaSugerencia {
  tipo: "kerna_sugerencia";
  version: number;
  id_solicitud: string;
  version_corpus: number;
  estado: "completada" | "revision_manual";
  motivo_revision: string | null;
  modo: "oficial" | "respaldo" | "local" | "manual";
  recuperacion: "nube" | "local";
  contingencia: boolean;
  generado_en: string;
  articulos: KernaArticulo[];
}

export interface KernaEstadoNota {
  tipo: "kerna_estado";
  version: number;
  estado: "en_proceso" | "nucleo_no_disponible";
  fecha: string;
  id_seguimiento: string;
}

export interface KernaFeedback {
  tipo: "kerna_feedback";
  version: number;
  id_sugerencia: string;
  valoracion: "arriba" | "abajo";
  observacion?: string;
}

export interface KernaArticuloClasificado {
  id_articulo: string;
  origen: "sugerido" | "agregado_por_auditor";
}

export interface KernaClasificacion {
  tipo: "kerna_clasificacion";
  version: number;
  articulos: KernaArticuloClasificado[];
  observacion?: string;
}

export type NotaKerna = KernaSugerencia | KernaEstadoNota | KernaFeedback | KernaClasificacion;

export interface NotasKerna {
  /** Id del destinatario que es la cuenta de Kerna; null si el caso no la tiene (no se muestra nada). */
  cuentaId: string | null;
  sugerencia: KernaSugerencia | null;
  estado: KernaEstadoNota | null;
  clasificacion: KernaClasificacion | null;
  /** Última valoración por id_sugerencia (de un artículo). */
  feedback: Record<string, KernaFeedback>;
}

const esTexto = (v: unknown): v is string => typeof v === "string";
const esObjeto = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const esFecha = (v: unknown): v is string => esTexto(v) && !isNaN(Date.parse(v));

function leerJson(contenido: string): Record<string, unknown> | null {
  if (!esTexto(contenido)) {
    return null;
  }
  const texto = contenido.trim();
  if (!texto.startsWith("{")) {
    return null;
  }
  try {
    const v = JSON.parse(texto);
    return esObjeto(v) ? v : null;
  } catch {
    return null;
  }
}

/** Un comentario es una nota de Kerna (aunque esté mal formada) si su contenido es un JSON con `tipo` "kerna_*". */
export function esNotaKerna(contenido: string): boolean {
  const o = leerJson(contenido);
  return o !== null && esTexto(o["tipo"]) && (o["tipo"] as string).startsWith("kerna_");
}

function leerArticulo(a: unknown): KernaArticulo | null {
  if (!esObjeto(a)) {
    return null;
  }
  const claves = ["id_sugerencia", "id_articulo", "norma", "articulo", "explicacion", "cita", "enlace_fuente"];
  for (const c of claves) {
    if (!esTexto(a[c])) {
      return null;
    }
  }
  const confianza = typeof a["confianza"] === "number" ? (a["confianza"] as number) : 0;
  return {
    id_sugerencia: a["id_sugerencia"] as string, id_articulo: a["id_articulo"] as string, norma: a["norma"] as string,
    articulo: a["articulo"] as string, explicacion: a["explicacion"] as string, cita: a["cita"] as string,
    enlace_fuente: a["enlace_fuente"] as string, confianza
  };
}

/** Valida una nota contra el contrato. Devuelve null si no es una nota de Kerna válida de la versión 1. */
export function parsearNota(contenido: string): NotaKerna | null {
  const o = leerJson(contenido);
  if (!o || o["version"] !== VERSION_NOTAS) {
    return null;
  }
  switch (o["tipo"]) {
    case "kerna_sugerencia": {
      if (!esTexto(o["id_solicitud"]) || !esFecha(o["generado_en"]) || !Array.isArray(o["articulos"])) {
        return null;
      }
      if (o["estado"] !== "completada" && o["estado"] !== "revision_manual") {
        return null;
      }
      const articulos: KernaArticulo[] = [];
      for (const a of o["articulos"] as unknown[]) {
        const x = leerArticulo(a);
        if (!x) {
          return null;
        }
        articulos.push(x);
      }
      return {
        tipo: "kerna_sugerencia", version: 1, id_solicitud: o["id_solicitud"] as string,
        version_corpus: typeof o["version_corpus"] === "number" ? (o["version_corpus"] as number) : 0,
        estado: o["estado"], motivo_revision: esTexto(o["motivo_revision"]) ? (o["motivo_revision"] as string) : null,
        modo: o["modo"] === "respaldo" || o["modo"] === "local" || o["modo"] === "manual" ? o["modo"] : "oficial",
        recuperacion: o["recuperacion"] === "local" ? "local" : "nube",
        contingencia: o["contingencia"] === true, generado_en: o["generado_en"] as string, articulos
      };
    }
    case "kerna_estado": {
      if ((o["estado"] !== "en_proceso" && o["estado"] !== "nucleo_no_disponible") || !esFecha(o["fecha"])) {
        return null;
      }
      return {
        tipo: "kerna_estado", version: 1, estado: o["estado"], fecha: o["fecha"] as string,
        id_seguimiento: esTexto(o["id_seguimiento"]) ? (o["id_seguimiento"] as string) : ""
      };
    }
    case "kerna_feedback": {
      if (!esTexto(o["id_sugerencia"]) || (o["valoracion"] !== "arriba" && o["valoracion"] !== "abajo")) {
        return null;
      }
      const obs = o["observacion"];
      if (obs !== undefined && obs !== null && (!esTexto(obs) || (obs as string).length > MAX_OBSERVACION)) {
        return null;
      }
      return {
        tipo: "kerna_feedback", version: 1, id_sugerencia: o["id_sugerencia"] as string,
        valoracion: o["valoracion"], observacion: esTexto(obs) ? (obs as string) : undefined
      };
    }
    case "kerna_clasificacion": {
      if (!Array.isArray(o["articulos"])) {
        return null;
      }
      const articulos: KernaArticuloClasificado[] = [];
      for (const a of o["articulos"] as unknown[]) {
        if (!esObjeto(a) || !esTexto(a["id_articulo"]) || (a["origen"] !== "sugerido" && a["origen"] !== "agregado_por_auditor")) {
          return null;
        }
        articulos.push({id_articulo: a["id_articulo"] as string, origen: a["origen"]});
      }
      const obs = o["observacion"];
      if (obs !== undefined && obs !== null && (!esTexto(obs) || (obs as string).length > MAX_OBSERVACION)) {
        return null;
      }
      return {tipo: "kerna_clasificacion", version: 1, articulos, observacion: esTexto(obs) ? (obs as string) : undefined};
    }
    default:
      return null;
  }
}

/** Id de la cuenta de servicio: el destinatario del caso cuyo nombre empieza con PREFIJO_CUENTA_KERNA. */
export function idCuentaKerna(destinatarios: DestinatarioEntrada[] | undefined | null): string | null {
  for (const d of destinatarios || []) {
    if (d && esTexto(d.name) && d.name.trim().toLowerCase().startsWith(PREFIJO_CUENTA_KERNA.toLowerCase())) {
      return d.id;
    }
  }
  return null;
}

const ms = (fecha: string): number => Date.parse(fecha);

/**
 * Extrae las notas válidas de los comentarios del caso aplicando las reglas del contrato:
 * - `kerna_sugerencia` y `kerna_estado` valen solo si el autor es la cuenta de Kerna;
 * - `kerna_feedback` y `kerna_clasificacion` valen solo si el autor es otro destinatario del caso;
 * - todas deben ser notas internas comunes (sin `type` de registro de auditoría);
 * - si hay varias, vale la última.
 */
export function extraerNotas(comentarios: ComentarioEntrada[] | undefined | null, destinatarios: DestinatarioEntrada[] | undefined | null): NotasKerna {
  const cuentaId = idCuentaKerna(destinatarios);
  const vacio: NotasKerna = {cuentaId, sugerencia: null, estado: null, clasificacion: null, feedback: {}};
  if (!cuentaId) {
    return vacio;
  }
  const ids = new Set((destinatarios || []).map(d => d.id));
  const ordenados = [...(comentarios || [])]
    .filter(c => c && c.visibility === "internal" && !c.type && !!c.author_id && esFecha(c.creation_date))
    .sort((a, b) => ms(a.creation_date) - ms(b.creation_date));
  const res = vacio;
  const fechaDe = (n: NotaKerna, c: ComentarioEntrada): number => {
    if (n.tipo === "kerna_sugerencia") { return ms(n.generado_en); }
    if (n.tipo === "kerna_estado") { return ms(n.fecha); }
    return ms(c.creation_date);
  };
  let fechaSug = -Infinity, fechaEst = -Infinity;
  for (const c of ordenados) {
    const n = parsearNota(c.content);
    if (!n) {
      continue;
    }
    const esCuenta = c.author_id === cuentaId;
    if (n.tipo === "kerna_sugerencia" || n.tipo === "kerna_estado") {
      if (!esCuenta) {
        continue;
      }
      const f = fechaDe(n, c);
      if (n.tipo === "kerna_sugerencia" && f >= fechaSug) {
        res.sugerencia = n; fechaSug = f;
      } else if (n.tipo === "kerna_estado" && f >= fechaEst) {
        res.estado = n; fechaEst = f;
      }
    } else {
      if (esCuenta || !ids.has(c.author_id as string)) {
        continue;
      }
      if (n.tipo === "kerna_feedback") {
        res.feedback[n.id_sugerencia] = n;
      } else {
        res.clasificacion = n;
      }
    }
  }
  return res;
}
