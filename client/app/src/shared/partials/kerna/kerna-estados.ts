/**
 * Los 12 estados del indicador de Kerna y la deducción del estado a partir de datos reales del caso.
 * Módulo puro (sin Angular): se prueba con Node (ver kerna-pruebas.ts). Textos: claves `kerna.*` de es.json.
 */
import {KernaArticulo, KernaClasificacion, KernaEstadoNota, KernaSugerencia, NotasKerna} from "./kerna-notas";

export type EstadoId =
  | "sin-info" | "generando" | "lista" | "contingencia" | "revision-tiempo" | "revision-citas"
  | "sin-normativa" | "cadena-agotada" | "nucleo-no-disponible" | "conector-inactivo" | "sin-conexion" | "valorada";

export const ESTADOS: EstadoId[] = [
  "sin-info", "generando", "lista", "contingencia", "revision-tiempo", "revision-citas",
  "sin-normativa", "cadena-agotada", "nucleo-no-disponible", "conector-inactivo", "sin-conexion", "valorada"
];

/** Variantes con texto propio: contingencia (modo | busqueda) y conector-inactivo (sin-nota | en-proceso). */
export type Variante = "modo" | "busqueda" | "sin-nota" | "en-proceso" | null;

/** Umbrales (ver propuesta, sección 2.2). Son supuestos derivados de los plazos del contrato. */
export const UMBRAL_CONECTOR_MS = 5 * 60 * 1000;
export const UMBRAL_ESPERA_MS = 6 * 60 * 1000;
export const VENTANA_CASO_NUEVO_MS = 24 * 60 * 60 * 1000;

export interface EntradaEstado {
  notas: NotasKerna;
  /** Fecha de creación del caso (ms desde 1970). */
  creacion: number;
  ahora: number;
  /** La consulta periódica o un envío falló (se calcula en el servicio, con dos fallos seguidos). */
  fallaDeRed: boolean;
}

export interface ResultadoEstado {
  id: EstadoId;
  variante: Variante;
  sugerencia: KernaSugerencia | null;
  estadoNota: KernaEstadoNota | null;
  clasificacion: KernaClasificacion | null;
  /** Solo en `sin-conexion`: el estado que se había deducido sin el fallo. */
  previo: ResultadoEstado | null;
}

function resultado(id: EstadoId, variante: Variante, notas: NotasKerna): ResultadoEstado {
  return {id, variante, sugerencia: notas.sugerencia, estadoNota: notas.estado, clasificacion: notas.clasificacion, previo: null};
}

function esAlternativa(s: KernaSugerencia): boolean {
  return s.contingencia || s.modo !== "oficial" || s.recuperacion === "local";
}

/** Estado sin tener en cuenta el fallo de conexión. */
function deducirBase(e: EntradaEstado): ResultadoEstado {
  const n = e.notas;
  if (n.clasificacion) {
    return resultado("valorada", null, n);
  }
  const s = n.sugerencia;
  if (s) {
    if (s.estado === "completada") {
      if (s.articulos.length === 0) {
        return resultado("sin-normativa", null, n); // defensivo: el contrato no lo prevé
      }
      if (esAlternativa(s)) {
        return resultado("contingencia", s.recuperacion === "local" && s.modo === "oficial" ? "busqueda" : "modo", n);
      }
      return resultado("lista", null, n);
    }
    switch (s.motivo_revision) {
      case "tiempo_agotado": return resultado("revision-tiempo", null, n);
      case "validacion_fallida": return resultado("revision-citas", null, n);
      case "sin_normativa_aplicable": return resultado("sin-normativa", null, n);
      default: return resultado("cadena-agotada", null, n);
    }
  }
  const est = n.estado;
  if (est) {
    if (est.estado === "nucleo_no_disponible") {
      return resultado("nucleo-no-disponible", null, n);
    }
    if (e.ahora - Date.parse(est.fecha) > UMBRAL_ESPERA_MS) {
      return resultado("conector-inactivo", "en-proceso", n);
    }
    return resultado("generando", null, n);
  }
  const edad = e.ahora - e.creacion;
  if (edad >= UMBRAL_CONECTOR_MS && edad <= VENTANA_CASO_NUEVO_MS) {
    return resultado("conector-inactivo", "sin-nota", n);
  }
  return resultado("sin-info", null, n);
}

/** Deduce el estado del indicador. Devuelve null si el caso no tiene la cuenta de Kerna (no se muestra nada). */
export function deducirEstado(e: EntradaEstado): ResultadoEstado | null {
  if (!e.notas.cuentaId) {
    return null;
  }
  const base = deducirBase(e);
  if (e.fallaDeRed) {
    return {id: "sin-conexion", variante: null, sugerencia: base.sugerencia, estadoNota: base.estadoNota, clasificacion: base.clasificacion, previo: base};
  }
  return base;
}

/** Estados que pueden cambiar solos: el servicio sigue consultando el caso mientras estén activos. */
export function esProvisional(id: EstadoId): boolean {
  return id === "sin-info" || id === "generando" || id === "nucleo-no-disponible" || id === "conector-inactivo" || id === "sin-conexion";
}

/** El estado con que se muestra el contenido (el previo si no hay conexión). */
function base(r: ResultadoEstado): ResultadoEstado {
  return r.id === "sin-conexion" && r.previo ? r.previo : r;
}

/** Estados en los que la sugerencia trae artículos que el auditor puede valorar y clasificar. */
export function tieneArticulos(r: ResultadoEstado): boolean {
  const b = base(r);
  return (b.id === "lista" || b.id === "contingencia" || b.id === "valorada") && !!b.sugerencia && b.sugerencia.articulos.length > 0;
}

/** Clave de texto (es.json) de un campo del estado: etiqueta, titulo o mensaje. */
export function claveTexto(r: ResultadoEstado, campo: "etiqueta" | "titulo" | "mensaje"): string {
  return `kerna.estado.${r.id}${r.variante ? "." + r.variante : ""}.${campo}`;
}

function esRevisionManual(id: EstadoId): boolean {
  return id === "revision-tiempo" || id === "revision-citas" || id === "sin-normativa" || id === "cadena-agotada";
}

export function normaPrincipal(articulos: KernaArticulo[]): {norma: string; n: number} {
  const cuenta = new Map<string, {n: number; mejor: number}>();
  for (const a of articulos) {
    const c = cuenta.get(a.norma) || {n: 0, mejor: -1};
    c.n++;
    c.mejor = Math.max(c.mejor, a.confianza);
    cuenta.set(a.norma, c);
  }
  let principal = "";
  let datos = {n: -1, mejor: -1};
  cuenta.forEach((c, norma) => {
    if (c.n > datos.n || (c.n === datos.n && c.mejor > datos.mejor)) {
      principal = norma;
      datos = c;
    }
  });
  return {norma: principal, n: articulos.length};
}

/** Resumen del tooltip: clave y parámetros de interpolación. */
export function resumen(r: ResultadoEstado): {clave: string; params: Record<string, string | number>} {
  const b = base(r);
  if (tieneArticulos(b) && b.sugerencia) {
    const p = normaPrincipal(b.sugerencia.articulos);
    return {clave: p.n === 1 ? "kerna.resumen.articulo" : "kerna.resumen.articulos", params: {norma: p.norma, n: p.n}};
  }
  if (esRevisionManual(b.id)) {
    return {clave: "kerna.resumen.sin-sugerencia", params: {}};
  }
  return {clave: "kerna.resumen.sin-resultados", params: {}};
}

/** Modo de generación del tooltip: clave de texto. */
export function claveModo(r: ResultadoEstado): string {
  const b = base(r);
  if (tieneArticulos(b) && b.sugerencia) {
    const s = b.sugerencia;
    if (!esAlternativa(s)) {
      return "kerna.modo.habitual";
    }
    return s.recuperacion === "local" && s.modo === "oficial" ? "kerna.modo.busqueda" : "kerna.modo.alternativo";
  }
  if (esRevisionManual(b.id)) {
    return "kerna.modo.manual";
  }
  return "kerna.modo.no-disponible";
}

/** Código copiable para reportar un problema: id_solicitud o, si no hay sugerencia, id_seguimiento. */
export function codigoSeguimiento(r: ResultadoEstado): string | null {
  if (r.sugerencia && r.sugerencia.id_solicitud) {
    return r.sugerencia.id_solicitud;
  }
  if (r.estadoNota && r.estadoNota.id_seguimiento) {
    return r.estadoNota.id_seguimiento;
  }
  return null;
}
