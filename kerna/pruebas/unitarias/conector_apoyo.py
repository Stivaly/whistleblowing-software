"""Apoyos de las pruebas del conector: Veridy y núcleo simulados y constructor de casos sintéticos."""
from __future__ import annotations

import itertools
import json
import uuid

from kerna_comun import notas
from kerna_conector.nucleo import ErrorNucleo, NucleoNoDisponible
from kerna_conector.veridy import CasoNoAccesible, ErrorVeridy

CUENTA = "u-cuenta-kerna"
AUDITOR = "u-auditor"
OTRO_AUDITOR = "u-auditor-2"

ID_RELATO = "q-relato"
ID_LUGAR = "q-lugar"
ID_GRUPO = "q-grupo"
ID_ARCHIVO = "q-archivo"
ID_IDENTIDAD = "q-identidad"
ID_NOMBRE = "q-nombre"
ID_TIPO = "q-tipo"
OPC_ACOSO = "opt-acoso"


def esquema():
    return [{"label": "Paso 1", "children": [
        {"id": ID_RELATO, "type": "textarea", "label": "Describa los hechos"},
        {"id": ID_TIPO, "type": "selectbox", "label": "Tipo de hecho",
         "options": [{"id": OPC_ACOSO, "label": "Acoso laboral"}, {"id": "opt-otro", "label": "Otro"}]},
        {"id": ID_GRUPO, "type": "fieldgroup", "label": "Lugar", "children": [
            {"id": ID_LUGAR, "type": "inputbox", "label": "Dónde ocurrió"}]},
        {"id": ID_ARCHIVO, "type": "fileupload", "label": "Adjunte pruebas"},
        {"id": ID_IDENTIDAD, "type": "fieldgroup", "template_id": "whistleblower_identity", "label": "Identidad",
         "children": [{"id": ID_NOMBRE, "type": "inputbox", "label": "Nombre completo"}]},
    ]}]


def caso_json(id_caso, fecha="2026-11-01T10:00:00Z", relato="Mi jefe me grita todos los días.", lugar="Oficina central",
              comentarios=(), extra_relato=""):
    return {
        "id": id_caso, "creation_date": fecha, "update_date": fecha, "status": "new", "label": "etiqueta secreta",
        "questionnaires": [{"steps": esquema(), "answers": {
            ID_RELATO: [{"value": relato + extra_relato}],
            ID_TIPO: [{"value": OPC_ACOSO}],
            ID_GRUPO: [{ID_LUGAR: [{"value": lugar}]}],
            ID_ARCHIVO: [{"value": "foto-secreta.png"}],
            ID_IDENTIDAD: [{ID_NOMBRE: [{"value": "Camila Rojas Soto"}]}],
        }}],
        "data": {"whistleblower_identity": {"Nombre": "Camila Rojas Soto"}, "whistleblower_identity_provided": True},
        "identity_provided": True,
        "wbfiles": [{"name": "foto-secreta.png"}], "rfiles": [],
        "receivers": [{"id": CUENTA, "name": "Kerna", "active": True}, {"id": AUDITOR, "name": "Ana", "active": True}],
        "comments": list(comentarios),
    }


class VeridyFalso:
    """Veridy en memoria: casos, comentarios y publicación de notas internas de la cuenta de servicio."""

    def __init__(self):
        self.casos: dict[str, dict] = {}
        self.sin_acceso: set[str] = set()
        self.ilegibles: set[str] = set()
        self.publicaciones: list[tuple[str, str]] = []
        self.id_usuario = CUENTA
        self._n = itertools.count(1)
        self.fallar_publicar_estado_tras_guardar = False

    def agregar(self, id_caso, **kw):
        self.casos[id_caso] = caso_json(id_caso, **kw)
        return self.casos[id_caso]

    def comentar(self, id_caso, autor, contenido, visibilidad="internal", fecha=None):
        n = next(self._n)
        c = {"id": "c%03d" % n, "creation_date": fecha or "2026-11-02T10:%02d:00Z" % n, "author_id": autor,
             "visibility": visibilidad, "content": contenido if isinstance(contenido, str) else json.dumps(contenido)}
        self.casos[id_caso]["comments"].append(c)
        return c["id"]

    # ---- interfaz del cliente real
    def listar_casos(self):
        return [{"id": i, "creation_date": c["creation_date"], "accessible": i not in self.sin_acceso}
                for i, c in self.casos.items()]

    def leer_caso(self, id_caso):
        if id_caso in self.sin_acceso:
            raise CasoNoAccesible("403", 403)
        if id_caso in self.ilegibles:
            return {"id": id_caso, "questionnaires": "basura"}
        return json.loads(json.dumps(self.casos[id_caso]))

    def publicar_nota(self, id_caso, contenido):
        id_nota = self.comentar(id_caso, CUENTA, contenido, "internal")
        self.publicaciones.append((id_caso, contenido))
        return {"id": id_nota, "visibility": "internal", "author_id": CUENTA}

    def notas_publicadas(self, tipo=None):
        salida = []
        for _, contenido in self.publicaciones:
            n = notas.leer(contenido)
            if n is not None and (tipo is None or n.tipo == tipo):
                salida.append(n)
        return salida

    def cerrar_sesion(self):
        pass


class NucleoFalso:
    """API del núcleo simulada: idempotente por ref_opaca/id_nota; resultado configurable."""

    def __init__(self):
        self.solicitudes: dict[str, dict] = {}
        self.cuerpos_enviados: list[str] = []   # todo lo que sale hacia el núcleo, serializado
        self.resultados: dict[str, dict] = {}
        self.completar_al_enviar = False
        self.caido = False
        self.decisiones: list[tuple] = []
        self.envios_de_caso = 0
        self.consultas = 0

    def _registrar(self, *cuerpo):
        self.cuerpos_enviados.append(json.dumps(cuerpo, ensure_ascii=False, default=str))

    def enviar_caso(self, ref_opaca, texto):
        self._registrar(ref_opaca, texto)
        if self.caido:
            raise NucleoNoDisponible("caído")
        self.envios_de_caso += 1
        if ref_opaca not in self.solicitudes:
            self.solicitudes[ref_opaca] = {"id_solicitud": "sol-" + ref_opaca[:8], "estado": "pendiente"}
            if self.completar_al_enviar:
                self.completar(ref_opaca)
        return {"id_solicitud": self.solicitudes[ref_opaca]["id_solicitud"], "estado": "pendiente"}

    def completar(self, ref_opaca, **extra):
        s = self.solicitudes[ref_opaca]
        s.update(resultado_completo(s["id_solicitud"], **extra))

    def consultar_sugerencia(self, ref_opaca):
        self.consultas += 1
        if self.caido:
            raise NucleoNoDisponible("caído")
        return self.solicitudes.get(ref_opaca)

    def enviar_feedback(self, ref_opaca, id_nota, id_sugerencia, valoracion, observacion=None):
        self._registrar(ref_opaca, id_nota, id_sugerencia, valoracion, observacion)
        if self.caido:
            raise NucleoNoDisponible("caído")
        self.decisiones.append(("feedback", id_nota, id_sugerencia, valoracion, observacion))
        return True

    def enviar_clasificacion(self, ref_opaca, id_nota, articulos, observacion=None):
        self._registrar(ref_opaca, id_nota, articulos, observacion)
        if self.caido:
            raise NucleoNoDisponible("caído")
        self.decisiones.append(("clasificacion", id_nota, articulos, observacion))
        return True


def resultado_completo(id_solicitud, estado="completada", modo="oficial", recuperacion="nube", contingencia=False,
                       motivo_revision=None, articulos=None):
    if articulos is None:
        articulos = [{"id_sugerencia": str(uuid.uuid4()), "id_articulo": "ley21643-art2", "norma": "Ley N.° 21.643",
                      "articulo": "Artículo 2", "explicacion": "Define el acoso laboral.",
                      "cita": "Es acoso laboral toda conducta que constituya agresión u hostigamiento",
                      "enlace_fuente": "https://www.bcn.cl/leychile/navegar?idNorma=1200096", "confianza": 0.91}]
    return {"id_solicitud": id_solicitud, "estado": estado, "motivo_revision": motivo_revision, "modo": modo,
            "recuperacion": recuperacion, "contingencia": contingencia, "version_corpus": 7,
            "generado_en": "2026-11-10T12:00:00Z", "articulos": articulos}
