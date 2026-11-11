/**
 * Pruebas de la lógica pura de Kerna (kerna-notas.ts y kerna-estados.ts). El cliente no tiene un corredor de
 * pruebas unitarias configurado, así que esto es un script autocontenido de Node. Desde client/:
 *
 *   npx esbuild app/src/shared/partials/kerna/kerna-pruebas.ts --bundle --platform=node --outfile=/tmp/kerna-pruebas.cjs && node /tmp/kerna-pruebas.cjs
 *
 * Sale con código distinto de 0 si algo falla. Este archivo no forma parte de la aplicación (no lo importa nadie).
 */
import * as assert from "assert";
import {extraerNotas, esNotaKerna, idCuentaKerna, parsearNota, ComentarioEntrada, DestinatarioEntrada} from "./kerna-notas";
import {
  ESTADOS, EstadoId, UMBRAL_CONECTOR_MS, UMBRAL_ESPERA_MS, VENTANA_CASO_NUEVO_MS, ResultadoEstado,
  claveModo, claveTexto, codigoSeguimiento, deducirEstado, esProvisional, resumen, tieneArticulos
} from "./kerna-estados";

const KERNA = "u-kerna";
const AUDITOR = "u-auditor";
const OTRA = "u-otra";
const DEST: DestinatarioEntrada[] = [
  {id: AUDITOR, name: "Auditora"}, {id: KERNA, name: "Kerna AI (cuenta de servicio)"}, {id: OTRA, name: "Otro auditor"}
];
const CREACION = Date.parse("2026-11-10T12:00:00Z");
const MIN = 60 * 1000;

let n = 0;
const casos: string[] = [];
function caso(nombre: string, f: () => void): void {
  try {
    f();
    n++;
  } catch (e) {
    casos.push(`FALLA ${nombre}: ${(e as Error).message}`);
  }
}

let idc = 0;
function comentario(autor: string | undefined, nota: unknown, extra: Partial<ComentarioEntrada> = {}): ComentarioEntrada {
  return {
    id: `c${++idc}`, creation_date: new Date(CREACION + idc * 1000).toISOString(), author_id: autor,
    visibility: "internal", content: typeof nota === "string" ? nota : JSON.stringify(nota), ...extra
  };
}

const art = (i: number, norma = "Ley N.° 21.643", confianza = 0.8) => ({
  id_sugerencia: `s-${i}`, id_articulo: `a-${i}`, norma, articulo: `Artículo ${i}`, explicacion: "e", cita: "c",
  enlace_fuente: "https://www.bcn.cl/leychile/navegar?idNorma=1", confianza
});
const sugerencia = (o: Record<string, unknown> = {}) => ({
  tipo: "kerna_sugerencia", version: 1, id_solicitud: "sol-123", version_corpus: 3, estado: "completada", motivo_revision: null,
  modo: "oficial", recuperacion: "nube", contingencia: false, generado_en: new Date(CREACION + 60 * 1000).toISOString(),
  articulos: [art(1), art(2), art(3, "Ley N.° 20.393", 0.5)], ...o
});
const revision = (motivo: string) => sugerencia({estado: "revision_manual", motivo_revision: motivo, modo: "manual", articulos: []});
const estadoNota = (estado: string, minutosAntes: number, ahora: number) => ({
  tipo: "kerna_estado", version: 1, estado, fecha: new Date(ahora - minutosAntes * MIN).toISOString(), id_seguimiento: "seg-9"
});
const clasificacion = (o: Record<string, unknown> = {}) => ({
  tipo: "kerna_clasificacion", version: 1, articulos: [{id_articulo: "a-1", origen: "sugerido"}], ...o
});

function estadoDe(comentarios: ComentarioEntrada[], ahora = CREACION + MIN, fallaDeRed = false, dest = DEST): ResultadoEstado | null {
  return deducirEstado({notas: extraerNotas(comentarios, dest), creacion: CREACION, ahora, fallaDeRed});
}
function id(r: ResultadoEstado | null): string {
  return r ? r.id + (r.variante ? ":" + r.variante : "") : "null";
}

// ---- Los 12 estados y sus variantes ----
caso("sin-info: sin notas y caso recién creado", () => assert.equal(id(estadoDe([], CREACION + MIN)), "sin-info"));
caso("sin-info: sin notas y caso anterior a Kerna (más de 24 h)", () =>
  assert.equal(id(estadoDe([], CREACION + VENTANA_CASO_NUEVO_MS + MIN)), "sin-info"));
caso("generando: en_proceso reciente", () => {
  const ahora = CREACION + 3 * MIN;
  assert.equal(id(estadoDe([comentario(KERNA, estadoNota("en_proceso", 1, ahora))], ahora)), "generando");
});
caso("lista: completada en modo oficial", () => assert.equal(id(estadoDe([comentario(KERNA, sugerencia())])), "lista"));
caso("contingencia: modo respaldo", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia({modo: "respaldo", contingencia: true}))])), "contingencia:modo"));
caso("contingencia: modo local", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia({modo: "local", contingencia: true}))])), "contingencia:modo"));
caso("contingencia: recuperación local con modo oficial", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia({recuperacion: "local", contingencia: true}))])), "contingencia:busqueda"));
caso("contingencia: el modo no oficial manda sobre la recuperación local", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia({modo: "respaldo", recuperacion: "local", contingencia: true}))])), "contingencia:modo"));
caso("revision-tiempo", () => assert.equal(id(estadoDe([comentario(KERNA, revision("tiempo_agotado"))])), "revision-tiempo"));
caso("revision-citas", () => assert.equal(id(estadoDe([comentario(KERNA, revision("validacion_fallida"))])), "revision-citas"));
caso("sin-normativa: motivo sin_normativa_aplicable", () =>
  assert.equal(id(estadoDe([comentario(KERNA, revision("sin_normativa_aplicable"))])), "sin-normativa"));
caso("sin-normativa: completada sin artículos (defensivo)", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia({articulos: []}))])), "sin-normativa"));
caso("cadena-agotada: motivo cadena_agotada", () => assert.equal(id(estadoDe([comentario(KERNA, revision("cadena_agotada"))])), "cadena-agotada"));
caso("cadena-agotada: motivo desconocido", () => assert.equal(id(estadoDe([comentario(KERNA, revision("otra_cosa"))])), "cadena-agotada"));
caso("nucleo-no-disponible", () => {
  const ahora = CREACION + 2 * MIN;
  assert.equal(id(estadoDe([comentario(KERNA, estadoNota("nucleo_no_disponible", 1, ahora))], ahora)), "nucleo-no-disponible");
});
caso("nucleo-no-disponible: la última nota de estado manda", () => {
  const ahora = CREACION + 2 * MIN;
  const c = [comentario(KERNA, estadoNota("nucleo_no_disponible", 1.5, ahora)), comentario(KERNA, estadoNota("en_proceso", 0.5, ahora))];
  assert.equal(id(estadoDe(c, ahora)), "generando");
});
caso("conector-inactivo (sin nota): entre 5 min y 24 h", () => {
  assert.equal(id(estadoDe([], CREACION + UMBRAL_CONECTOR_MS)), "conector-inactivo:sin-nota");
  assert.equal(id(estadoDe([], CREACION + UMBRAL_CONECTOR_MS - 1)), "sin-info");
  assert.equal(id(estadoDe([], CREACION + VENTANA_CASO_NUEVO_MS)), "conector-inactivo:sin-nota");
});
caso("conector-inactivo (en proceso hace demasiado)", () => {
  const ahora = CREACION + 20 * MIN;
  const e = (min: number) => estadoDe([comentario(KERNA, estadoNota("en_proceso", min, ahora))], ahora);
  assert.equal(id(e(UMBRAL_ESPERA_MS / MIN + 0.1)), "conector-inactivo:en-proceso");
  assert.equal(id(e(UMBRAL_ESPERA_MS / MIN - 0.1)), "generando");
});
caso("sin-conexion: manda sobre el resto y recuerda el estado previo", () => {
  const r = estadoDe([comentario(KERNA, sugerencia())], CREACION + MIN, true);
  assert.equal(r?.id, "sin-conexion");
  assert.equal(r?.previo?.id, "lista");
  assert.equal(resumen(r as ResultadoEstado).clave, "kerna.resumen.articulos");
  assert.equal(claveModo(r as ResultadoEstado), "kerna.modo.habitual");
});
caso("valorada: clasificación de otro destinatario", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia()), comentario(AUDITOR, clasificacion())])), "valorada"));
caso("valorada: vale la última clasificación", () => {
  const r = estadoDe([comentario(KERNA, sugerencia()), comentario(AUDITOR, clasificacion()), comentario(OTRA, clasificacion({articulos: []}))]);
  assert.equal(r?.id, "valorada");
  assert.equal(r?.clasificacion?.articulos.length, 0);
});
caso("los 12 estados están cubiertos", () => {
  const vistos = new Set<EstadoId>();
  const ahora = CREACION + 20 * MIN;
  const lotes: ResultadoEstado[] = [
    estadoDe([], CREACION + MIN), estadoDe([comentario(KERNA, estadoNota("en_proceso", 1, ahora))], ahora),
    estadoDe([comentario(KERNA, sugerencia())]), estadoDe([comentario(KERNA, sugerencia({contingencia: true, modo: "local"}))]),
    estadoDe([comentario(KERNA, revision("tiempo_agotado"))]), estadoDe([comentario(KERNA, revision("validacion_fallida"))]),
    estadoDe([comentario(KERNA, revision("sin_normativa_aplicable"))]), estadoDe([comentario(KERNA, revision("cadena_agotada"))]),
    estadoDe([comentario(KERNA, estadoNota("nucleo_no_disponible", 1, ahora))], ahora), estadoDe([], CREACION + UMBRAL_CONECTOR_MS),
    estadoDe([], CREACION + MIN, true), estadoDe([comentario(KERNA, sugerencia()), comentario(AUDITOR, clasificacion())])
  ].filter((x): x is ResultadoEstado => x !== null);
  lotes.forEach(r => vistos.add(r.id));
  assert.deepEqual([...vistos].sort(), [...ESTADOS].sort());
});

// ---- Textos, resumen, modo y código ----
caso("claves de texto con variante", () => {
  assert.equal(claveTexto(estadoDe([comentario(KERNA, sugerencia({recuperacion: "local", contingencia: true}))]) as ResultadoEstado, "mensaje"),
    "kerna.estado.contingencia.busqueda.mensaje");
  assert.equal(claveTexto(estadoDe([], CREACION + MIN) as ResultadoEstado, "etiqueta"), "kerna.estado.sin-info.etiqueta");
});
caso("resumen: norma principal = la de más artículos; modo; código", () => {
  const r = estadoDe([comentario(KERNA, sugerencia())]) as ResultadoEstado;
  assert.deepEqual(resumen(r), {clave: "kerna.resumen.articulos", params: {norma: "Ley N.° 21.643", n: 3}});
  assert.equal(claveModo(r), "kerna.modo.habitual");
  assert.equal(codigoSeguimiento(r), "sol-123");
  assert.ok(tieneArticulos(r));
});
caso("resumen: un solo artículo y revisión manual", () => {
  const uno = estadoDe([comentario(KERNA, sugerencia({articulos: [art(1)]}))]) as ResultadoEstado;
  assert.equal(resumen(uno).clave, "kerna.resumen.articulo");
  const rev = estadoDe([comentario(KERNA, revision("tiempo_agotado"))]) as ResultadoEstado;
  assert.equal(resumen(rev).clave, "kerna.resumen.sin-sugerencia");
  assert.equal(claveModo(rev), "kerna.modo.manual");
  assert.equal(codigoSeguimiento(rev), "sol-123");
  assert.ok(!tieneArticulos(rev));
});
caso("modo en contingencia", () => {
  assert.equal(claveModo(estadoDe([comentario(KERNA, sugerencia({modo: "respaldo", contingencia: true}))]) as ResultadoEstado), "kerna.modo.alternativo");
  assert.equal(claveModo(estadoDe([comentario(KERNA, sugerencia({recuperacion: "local", contingencia: true}))]) as ResultadoEstado), "kerna.modo.busqueda");
});
caso("código de seguimiento desde kerna_estado", () => {
  const ahora = CREACION + 2 * MIN;
  assert.equal(codigoSeguimiento(estadoDe([comentario(KERNA, estadoNota("en_proceso", 1, ahora))], ahora) as ResultadoEstado), "seg-9");
  assert.equal(codigoSeguimiento(estadoDe([], CREACION + MIN) as ResultadoEstado), null);
});
caso("estados provisionales", () => {
  assert.ok(esProvisional("generando") && esProvisional("sin-conexion") && !esProvisional("lista") && !esProvisional("valorada"));
});

// ---- Notas falsificadas y mal formadas: deben ignorarse ----
caso("sugerencia de otro destinatario: se ignora", () => assert.equal(id(estadoDe([comentario(AUDITOR, sugerencia())])), "sin-info"));
caso("estado de otro destinatario: se ignora", () => {
  const ahora = CREACION + 2 * MIN;
  assert.equal(id(estadoDe([comentario(AUDITOR, estadoNota("en_proceso", 1, ahora))], ahora)), "sin-info");
});
caso("sugerencia sin autor (como la del denunciante): se ignora", () => assert.equal(id(estadoDe([comentario(undefined, sugerencia())])), "sin-info"));
caso("sugerencia pública: se ignora", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia(), {visibility: "public"})])), "sin-info"));
caso("sugerencia con tipo de registro de auditoría: se ignora", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia(), {type: "auditlog_update_report_status"})])), "sin-info"));
caso("clasificación de la cuenta de Kerna: se ignora", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia()), comentario(KERNA, clasificacion())])), "lista"));
caso("clasificación de un autor que no es destinatario del caso: se ignora", () =>
  assert.equal(id(estadoDe([comentario(KERNA, sugerencia()), comentario("u-desconocido", clasificacion())])), "lista"));
caso("valoración de la cuenta de Kerna: se ignora; la de un destinatario vale (última)", () => {
  const fb = (v: string, obs?: string) => ({tipo: "kerna_feedback", version: 1, id_sugerencia: "s-1", valoracion: v, observacion: obs});
  const sin = extraerNotas([comentario(KERNA, sugerencia()), comentario(KERNA, fb("arriba"))], DEST);
  assert.equal(Object.keys(sin.feedback).length, 0);
  const con = extraerNotas([comentario(KERNA, sugerencia()), comentario(AUDITOR, fb("arriba")), comentario(AUDITOR, fb("abajo", "no aplica"))], DEST);
  assert.equal(con.feedback["s-1"].valoracion, "abajo");
  assert.equal(con.feedback["s-1"].observacion, "no aplica");
});
caso("versión desconocida, JSON roto y campos inválidos: se ignoran", () => {
  assert.equal(parsearNota(JSON.stringify(sugerencia({version: 2}))), null);
  assert.equal(parsearNota("{no es json"), null);
  assert.equal(parsearNota(JSON.stringify(sugerencia({articulos: [{id_articulo: "x"}]}))), null);
  assert.equal(parsearNota(JSON.stringify({tipo: "kerna_feedback", version: 1, id_sugerencia: "s", valoracion: "meh"})), null);
  assert.equal(parsearNota(JSON.stringify({tipo: "kerna_feedback", version: 1, id_sugerencia: "s", valoracion: "arriba", observacion: "x".repeat(501)})), null);
  assert.equal(parsearNota(JSON.stringify({tipo: "otra_cosa", version: 1})), null);
});
caso("un comentario común no es nota de Kerna; una nota mal formada sí se oculta", () => {
  assert.equal(esNotaKerna("Revisar el contrato con legal"), false);
  assert.equal(esNotaKerna('{"clave": 1}'), false);
  assert.equal(esNotaKerna(JSON.stringify(sugerencia())), true);
  assert.equal(esNotaKerna('{"tipo":"kerna_sugerencia","version":9}'), true);
  assert.equal(esNotaKerna("[1,2]"), false);
});
caso("sin cuenta de Kerna entre los destinatarios: no hay indicador", () => {
  const sinCuenta = DEST.filter(d => d.id !== KERNA);
  assert.equal(estadoDe([comentario(KERNA, sugerencia())], CREACION + MIN, false, sinCuenta), null);
  assert.equal(idCuentaKerna(sinCuenta), null);
  assert.equal(idCuentaKerna(DEST), KERNA);
  assert.equal(idCuentaKerna([{id: "x", name: "Auditor de Kerna AI"}]), null);
});
caso("si hay dos sugerencias vale la de generado_en más reciente", () => {
  const vieja = sugerencia({generado_en: new Date(CREACION + 10 * 1000).toISOString(), id_solicitud: "vieja"});
  const nueva = sugerencia({generado_en: new Date(CREACION + 20 * 1000).toISOString(), id_solicitud: "nueva"});
  assert.equal(extraerNotas([comentario(KERNA, nueva), comentario(KERNA, vieja)], DEST).sugerencia?.id_solicitud, "nueva");
});

if (casos.length) {
  console.error(casos.join("\n"));
  console.error(`\n${casos.length} fallas, ${n} correctos`);
  process.exit(1);
}
console.log(`kerna-pruebas: ${n} casos correctos`);
