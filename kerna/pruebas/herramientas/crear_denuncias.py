#!/usr/bin/python3
"""Crea denuncias de prueba en Veridy como lo haría un denunciante (API pública, sin navegador).

Flujo (réplica del cliente Angular):
  1. GET /api/public                      -> contexto y cuestionario.
  2. POST /api/auth/token + prueba de trabajo -> cabecera x-token "<id>:<c>".
  3. POST /api/auth/receiptauth {receipt:""}  -> sesión de envío (X-Session).
  4. POST /api/whistleblower/submission   -> crea la denuncia.
El recibo son 16 dígitos aleatorios; si la instancia es de tipo "key" se envía su
argon2id(recibo, sal, 16 pasadas, 128 MiB) en base64 (44 caracteres).
"""
import argparse
import base64
import json
import os
import random
import secrets
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DATASET = RAIZ / "evaluacion" / "datos" / "denuncias_publicas.json"
REGISTRO = RAIZ / "evaluacion" / "datos" / "denuncias_veridy.json"
SEMILLA = 20261110
MAX_RELATO = 2000


# ---------------------------------------------------------------- relato y selección

def armar_relato(caso):
    """Relato corto: marca visible + título, resumen parafraseado y submateria (nunca texto_original)."""
    resumen = (caso.get("resumen_parafraseado") or "").replace("[Resumen parafraseado]", "").strip()
    partes = [
        "[PRUEBA SINTÉTICA %s]" % caso["id"],
        "Título: %s" % (caso.get("titulo") or "").strip(),
        "Relato: %s" % resumen,
        "Materia: %s" % (caso.get("submateria") or "").strip(),
    ]
    return "\n".join(partes)[:MAX_RELATO]


def seleccionar_lote(casos, n, semilla=SEMILLA):
    """N casos variados por ley_principal, determinista: turnos rotativos entre leyes."""
    grupos = defaultdict(list)
    for c in sorted(casos, key=lambda c: c["id"]):
        grupos[c.get("ley_principal") or ""].append(c["id"])
    rng = random.Random(semilla)
    leyes = sorted(grupos)
    rng.shuffle(leyes)
    for ley in leyes:
        rng.shuffle(grupos[ley])
    elegidos = []
    while len(elegidos) < n and any(grupos.values()):
        for ley in leyes:
            if grupos[ley] and len(elegidos) < n:
                elegidos.append(grupos[ley].pop())
    return elegidos


# ---------------------------------------------------------------- cuerpo del envío

def _opcion(campo, preferida=None):
    ops = sorted(campo.get("options", []), key=lambda o: o.get("order", 0))
    if preferida:
        for o in ops:
            if preferida(o["label"]):
                return o["id"]
    return ops[0]["id"] if ops else ""


def _activo(campo, respuestas):
    trig = campo.get("triggered_by_options") or []
    if not trig:
        return True
    for t in trig:
        r = respuestas.get(t["field"])
        if r and r[0].get("value") == t["option"]:
            return True
    return False


def armar_respuestas(cuestionario, relato, ley_principal=""):
    """answers = {id_campo: [{"value": ...}]}; campos no activados van como [{}] (como el cliente)."""
    respuestas = {}
    ms = str(int(datetime(2024, 1, 15, tzinfo=timezone.utc).timestamp() * 1000))
    for paso in cuestionario["steps"]:
        for c in paso["children"]:
            if not _activo(c, respuestas):
                respuestas[c["id"]] = [{}]
                continue
            t = c["type"]
            if t == "textarea":
                v = relato
            elif t == "inputbox":
                v = "Prueba sintética"
            elif t == "selectbox":
                if "Tipo de denuncia" in c["label"]:
                    v = _opcion(c, (lambda l: "Maltrato" in l) if ley_principal.startswith("21.643") else None)
                else:
                    v = _opcion(c, lambda l: l.strip().lower().startswith("no"))
            elif t == "daterange":
                v = "%s:%s" % (ms, ms)
            elif t == "date":
                v = datetime(2024, 1, 15, tzinfo=timezone.utc).isoformat().replace("+00:00", ".000Z")
            elif t == "checkbox":
                respuestas[c["id"]] = [{_opcion(c): True}]
                continue
            else:
                respuestas[c["id"]] = [{}]
                continue
            respuestas[c["id"]] = [{"value": v}]
    return respuestas


def validar_cuerpo(cuestionario, respuestas):
    """Devuelve lista de errores: obligatorios activos sin valor, tipos o ids desconocidos."""
    errores = []
    ids = set()
    for paso in cuestionario["steps"]:
        parciales = {}
        for c in paso["children"]:
            ids.add(c["id"])
            r = respuestas.get(c["id"])
            if r is None:
                errores.append("falta %s" % c["id"])
                continue
            parciales[c["id"]] = r
            if c.get("required") and c["type"] != "fileupload" and r != [{}] and not r[0].get("value"):
                errores.append("obligatorio vacío %s" % c["id"])
    for k in respuestas:
        if k not in ids:
            errores.append("campo desconocido %s" % k)
    # obligatorios activos no vacíos
    acum = {}
    for paso in cuestionario["steps"]:
        for c in paso["children"]:
            acum[c["id"]] = respuestas.get(c["id"], [{}])
            if c.get("required") and c["type"] != "fileupload" and _activo(c, acum) and not acum[c["id"]][0]:
                errores.append("obligatorio activo sin respuesta %s" % c["id"])
    return errores


def generar_recibo():
    return "".join(secrets.choice("0123456789") for _ in range(16))


def armar_cuerpo(contexto, answers, recibo_enviado):
    return {
        "context_id": contexto["id"],
        "receivers": list(contexto["receivers"]),
        "identity_provided": False,
        "answers": answers,
        "score": 0,
        "receipt": recibo_enviado,
    }


# ---------------------------------------------------------------- registro local

class Registro:
    def __init__(self, ruta=REGISTRO):
        self.ruta = Path(ruta)
        self.datos = {}
        if self.ruta.exists():
            self.datos = json.loads(self.ruta.read_text(encoding="utf-8"))

    def __contains__(self, caso_id):
        return caso_id in self.datos

    def __len__(self):
        return len(self.datos)

    def anotar(self, caso_id, recibo, denuncia_id=None):
        """Guarda de inmediato; no pisa un caso ya registrado."""
        if caso_id in self.datos:
            return False
        self.datos[caso_id] = {
            "denuncia_id": denuncia_id,
            "recibo": recibo,
            "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.guardar()
        return True

    def descartar(self, caso_id):
        """Quita una anotación cuyo envío falló (solo el registro local; nada en Veridy)."""
        if self.datos.pop(caso_id, None) is not None:
            self.guardar()

    def actualizar_id(self, caso_id, denuncia_id):
        if self.datos[caso_id].get("denuncia_id") != denuncia_id:
            self.datos[caso_id]["denuncia_id"] = denuncia_id
            self.guardar()

    def guardar(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.datos, ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.ruta)


# ---------------------------------------------------------------- red

class ErrorVeridy(RuntimeError):
    pass


class LimiteDeEnvios(ErrorVeridy):
    """Veridy limita los envíos por hora y por IP (HTTP 403, error_code 8)."""


def _argon2(texto, sal_b64, ops, mem):
    from nacl.pwhash import argon2id
    sal = base64.b64decode(sal_b64)[:16]
    return argon2id.kdf(32, texto.encode(), sal, opslimit=ops, memlimit=mem)


def peticion(url, ruta, datos=None, sesion=None, token=None, metodo=None, timeout=60):
    cab = {"Content-Type": "application/json"}
    if sesion:
        cab["X-Session"] = sesion
    if token:
        cab["x-token"] = token
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    req = urllib.request.Request(url.rstrip("/") + ruta, data=cuerpo, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError) as e:
        raise ErrorVeridy("sin conexión con Veridy: %s" % type(e).__name__)


def obtener_token(url):
    """Token con prueba de trabajo: argon2id(id+c, sal, 1, 2^20) con el byte 31 en 0."""
    st, t = peticion(url, "/api/auth/token", {})
    if st not in (200, 201):
        raise ErrorVeridy("token: HTTP %s" % st)
    c = 0
    while _argon2(t["id"] + str(c), t["salt"], 1, 1 << 20)[31] != 0:
        c += 1
    return "%s:%s" % (t["id"], c)


def _recibo_para_enviar(url, recibo):
    st, tipo = peticion(url, "/api/auth/type", {"username": ""})
    if st not in (200, 201):
        raise ErrorVeridy("auth/type: HTTP %s" % st)
    if tipo.get("type") == "key":
        return base64.b64encode(_argon2(recibo, tipo["salt"], 16, 1 << 27)).decode()
    return recibo


def iniciar_sesion_denunciante(url, recibo):
    """Inicia sesión como denunciante con el recibo (16 dígitos). Devuelve el id de sesión."""
    recibo = "".join(ch for ch in recibo if ch.isdigit())
    enviado = _recibo_para_enviar(url, recibo)
    st, s = peticion(url, "/api/auth/receiptauth", {"receipt": enviado}, token=obtener_token(url))
    if st not in (200, 201) or "id" not in s:
        raise ErrorVeridy("inicio de sesión denunciante: HTTP %s %s" % (st, s.get("error_code", "")))
    return s["id"]


def cerrar_sesion(url, sesion):
    try:
        peticion(url, "/api/auth/session", sesion=sesion, metodo="DELETE")
    except ErrorVeridy:
        pass


def leer_denuncia_como_denunciante(url, recibo, sesion=None):
    """Lee la denuncia con la sesión del denunciante.

    Devuelve {"id", "progresivo", "comentarios": [textos visibles para el denunciante], "denuncia": dict completo}.
    El servidor solo entrega comentarios de visibilidad pública; las notas internas no aparecen.
    """
    propia = sesion is None
    sesion = sesion or iniciar_sesion_denunciante(url, recibo)
    try:
        st, tip = peticion(url, "/api/whistleblower/wbtip", sesion=sesion)
        if st != 200:
            raise ErrorVeridy("wbtip: HTTP %s" % st)
        return {
            "id": tip.get("id"),
            "progresivo": tip.get("progressive"),
            "comentarios": [c.get("content") for c in tip.get("comments", [])],
            "denuncia": tip,
        }
    finally:
        if propia:
            cerrar_sesion(url, sesion)


def obtener_publico(url):
    st, pub = peticion(url, "/api/public")
    if st != 200:
        raise ErrorVeridy("api/public: HTTP %s" % st)
    ctx = pub["contexts"][0]
    cuest = next(q for q in pub["questionnaires"] if q["id"] == ctx["questionnaire_id"])
    return ctx, cuest


def enviar_denuncia(url, contexto, answers, recibo):
    enviado = _recibo_para_enviar(url, recibo)
    st, s = peticion(url, "/api/auth/receiptauth", {"receipt": ""}, token=obtener_token(url))
    if st not in (200, 201):
        raise ErrorVeridy("sesión de envío: HTTP %s" % st)
    cuerpo = armar_cuerpo(contexto, answers, enviado)
    st, r = peticion(url, "/api/whistleblower/submission", cuerpo, sesion=s["id"])
    if st == 403 and r.get("error_code") == 8:
        raise LimiteDeEnvios("límite de envíos por hora alcanzado")
    if st not in (200, 201):
        raise ErrorVeridy("envío: HTTP %s %s" % (st, r.get("error_code", "")))
    return r


# ---------------------------------------------------------------- CLI

def cargar_casos(ruta=DATASET):
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return {c["id"]: c for c in d["casos"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--casos", nargs="+", metavar="DEN-0001")
    g.add_argument("--lote", type=int, metavar="N")
    g.add_argument("--verificar", action="store_true")
    ap.add_argument("--url", default=os.environ.get("VERIDY_URL"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not (a.casos or a.lote or a.verificar):
        ap.error("indica --casos, --lote o --verificar")
    if not a.url:
        ap.error("falta --url o la variable VERIDY_URL")

    reg = Registro()
    try:
        if a.verificar:
            return verificar(a.url, reg)
        casos = cargar_casos()
        ids = a.casos if a.casos else seleccionar_lote(list(casos.values()), a.lote)
        desconocidos = [i for i in ids if i not in casos]
        if desconocidos:
            print("casos inexistentes:", ", ".join(desconocidos))
            return 2
        ctx, cuest = obtener_publico(a.url)
        creados = omitidos = errores = 0
        limite = False
        for i in ids:
            if i in reg:
                omitidos += 1
                continue
            ans = armar_respuestas(cuest, armar_relato(casos[i]), casos[i].get("ley_principal") or "")
            fallos = validar_cuerpo(cuest, ans)
            if fallos:
                print("%s: cuerpo inválido (%d)" % (i, len(fallos)))
                errores += 1
                continue
            if a.dry_run:
                print("%s: cuerpo válido (dry-run)" % i)
                continue
            recibo = generar_recibo()
            reg.anotar(i, recibo)  # antes de enviar: no se pierde el recibo si algo falla
            try:
                enviar_denuncia(a.url, ctx, ans, recibo)
            except ErrorVeridy as e:
                reg.descartar(i)
                if isinstance(e, LimiteDeEnvios):
                    print("%s: %s; se detiene (reintentar más tarde, el registro evita duplicados)" % (i, e))
                    limite = True
                    break
                errores += 1
                print("%s: error de envío %s" % (i, e))
                continue
            try:
                info = leer_denuncia_como_denunciante(a.url, recibo)
                reg.actualizar_id(i, info["id"])
                creados += 1
                print("%s: creada, denuncia %s" % (i, info["id"]))
            except ErrorVeridy as e:
                errores += 1
                print("%s: error %s (enviada pero sin confirmar; revisar con --verificar)" % (i, e))
        print("creadas=%d omitidas(ya existían)=%d errores=%d" % (creados, omitidos, errores))
        return 3 if limite else (1 if errores else 0)
    except ErrorVeridy as e:
        print("error:", e)
        return 1


def verificar(url, reg):
    ok = faltan = 0
    for caso, d in sorted(reg.datos.items()):
        try:
            info = leer_denuncia_como_denunciante(url, d["recibo"])
            reg.actualizar_id(caso, info["id"])
            ok += 1
        except ErrorVeridy:
            faltan += 1
            print("%s: no verificable" % caso)
    print("registradas=%d verificadas=%d no_verificadas=%d" % (len(reg), ok, faltan))
    return 1 if faltan else 0


if __name__ == "__main__":
    sys.exit(main())
