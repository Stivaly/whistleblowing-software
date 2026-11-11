"""Carga contra la API del núcleo (kerna/docs/contratos.md): token OAuth, POST /v1/casos y sondeo de la sugerencia.

Variables: KERNA_API_URL (host), KERNA_CLIENT_ID, KERNA_CLIENT_SECRET, KERNA_ID_EMPRESA (por defecto "empresa-prueba"),
KERNA_SONDEO_MAX_S (tope de espera por sugerencia, 60), KERNA_SONDEO_PAUSA_S (2). Usa denuncias sintéticas.
Ejemplo: locust -f kerna/pruebas/carga/locustfile.py --headless -u 3 -r 1 -t 60s --csv reportes/carga
"""
import json
import os
import pathlib
import random
import time
import uuid

from locust import HttpUser, between, events, task

DATOS = pathlib.Path(__file__).resolve().parents[1] / "datos" / "denuncias_sinteticas.json"
DENUNCIAS = json.loads(DATOS.read_text(encoding="utf-8"))["denuncias"]


@events.init.add_listener
def _verificar(environment, **kw):
    faltan = [v for v in ("KERNA_API_URL", "KERNA_CLIENT_ID", "KERNA_CLIENT_SECRET") if not os.environ.get(v)]
    if faltan:
        raise SystemExit("Carga: faltan variables " + ", ".join(faltan))


class UsuarioNucleo(HttpUser):
    host = os.environ.get("KERNA_API_URL", "http://localhost:8000")
    wait_time = between(1, 3)

    def on_start(self):
        self.rng = random.Random(20260101)
        self.token = None
        self.vence = 0.0
        self._autenticar()

    def _autenticar(self):
        r = self.client.post("/oauth/token", name="/oauth/token", data={
            "grant_type": "client_credentials",
            "client_id": os.environ["KERNA_CLIENT_ID"],
            "client_secret": os.environ["KERNA_CLIENT_SECRET"]})
        if r.status_code == 200:
            self.token = r.json()["access_token"]
            self.vence = time.time() + r.json().get("expires_in", 600) - 30

    def _cabeceras(self):
        if time.time() >= self.vence:
            self._autenticar()
        return {"Authorization": f"Bearer {self.token}"}

    @task
    def caso_y_sugerencia(self):
        ref = str(uuid.uuid4())
        texto = self.rng.choice(DENUNCIAS)["texto"]
        with self.client.post("/v1/casos", name="/v1/casos", headers=self._cabeceras(), json={
                "ref_opaca": ref, "id_empresa": os.environ.get("KERNA_ID_EMPRESA", "empresa-prueba"),
                "texto": texto}, catch_response=True) as r:
            if r.status_code != 202:
                r.failure(f"POST /v1/casos devolvió {r.status_code}")
                return
        inicio = time.time()
        tope = float(os.environ.get("KERNA_SONDEO_MAX_S", "60"))
        pausa = float(os.environ.get("KERNA_SONDEO_PAUSA_S", "2"))
        while time.time() - inicio < tope:
            with self.client.get(f"/v1/casos/{ref}/sugerencia", name="/v1/casos/[ref]/sugerencia",
                                 headers=self._cabeceras(), catch_response=True) as r:
                if r.status_code == 200 and r.json().get("estado") in ("completada", "revision_manual"):
                    r.success()
                    self.environment.events.request.fire(
                        request_type="E2E", name="caso -> sugerencia lista", response_time=(time.time() - inicio) * 1000,
                        response_length=0, exception=None, context={})
                    return
                if r.status_code in (200, 404):
                    r.success()  # aún pendiente
                else:
                    r.failure(f"GET sugerencia devolvió {r.status_code}")
                    return
            time.sleep(pausa)
        self.environment.events.request.fire(
            request_type="E2E", name="caso -> sugerencia lista", response_time=tope * 1000, response_length=0,
            exception=TimeoutError("sugerencia no lista dentro del tope"), context={})
