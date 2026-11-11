"""Cliente de la API del núcleo de Kerna (OAuth client credentials, reintentos con espera creciente)."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

import httpx

MARGEN_TOKEN_S = 60


class ErrorNucleo(Exception):
    """Respuesta de error definitiva del núcleo (4xx)."""

    def __init__(self, mensaje: str, codigo: Optional[int] = None):
        super().__init__(mensaje)
        self.codigo = codigo


class NucleoNoDisponible(ErrorNucleo):
    """El núcleo no respondió (red o 5xx) tras los reintentos."""


class ClienteNucleo:
    def __init__(self, api_url: str, client_id: str, client_secret: str, id_empresa: str = "veridy",
                 http: Optional[httpx.Client] = None, dormir: Callable[[float], None] = time.sleep,
                 reloj: Callable[[], float] = time.monotonic, reintentos: int = 3, espera_base_s: float = 1.0):
        self._url = api_url.rstrip("/")
        self._id = client_id
        self._secreto = client_secret
        self.id_empresa = id_empresa
        self._http = http or httpx.Client(timeout=30)
        self._dormir = dormir
        self._reloj = reloj
        self._reintentos = reintentos
        self._espera = espera_base_s
        self._token: Optional[str] = None
        self._vence = 0.0

    # ---- transporte ---------------------------------------------------------------------------------------
    def _con_reintentos(self, accion: Callable[[], httpx.Response]) -> httpx.Response:
        """Repite ante error de red o 5xx con esperas de base, 2*base, 4*base... Devuelve la primera respuesta < 500."""
        for intento in range(self._reintentos + 1):
            try:
                r = accion()
                if r.status_code < 500:
                    return r
            except httpx.HTTPError:
                pass
            if intento < self._reintentos:
                self._dormir(self._espera * (2 ** intento))
        raise NucleoNoDisponible("el núcleo no responde")

    def _obtener_token(self) -> str:
        if self._token and self._reloj() < self._vence - MARGEN_TOKEN_S:
            return self._token
        r = self._con_reintentos(lambda: self._http.post(
            self._url + "/oauth/token",
            data={"grant_type": "client_credentials", "client_id": self._id, "client_secret": self._secreto}))
        if r.status_code != 200:
            raise ErrorNucleo("el núcleo rechazó las credenciales", r.status_code)
        datos = r.json()
        self._token = datos["access_token"]
        self._vence = self._reloj() + float(datos.get("expires_in", 600))
        return self._token

    def _pedir(self, metodo: str, ruta: str, json: Any = None) -> httpx.Response:
        for vuelta in range(2):
            token = self._obtener_token()
            r = self._con_reintentos(lambda: self._http.request(
                metodo, self._url + ruta, json=json, headers={"Authorization": "Bearer " + token}))
            if r.status_code == 401 and vuelta == 0:
                self._token = None  # venció o fue revocado: se pide otro una vez
                continue
            return r
        return r  # pragma: no cover

    # ---- operaciones --------------------------------------------------------------------------------------
    def enviar_caso(self, ref_opaca: str, texto: str) -> dict:
        r = self._pedir("POST", "/v1/casos", {"ref_opaca": ref_opaca, "id_empresa": self.id_empresa, "texto": texto})
        if r.status_code not in (200, 201, 202):
            raise ErrorNucleo("el núcleo rechazó el caso", r.status_code)
        return r.json()

    def consultar_sugerencia(self, ref_opaca: str) -> Optional[dict]:
        """Objeto de resultado, o None si el núcleo no conoce la solicitud (404)."""
        r = self._pedir("GET", "/v1/casos/%s/sugerencia" % ref_opaca)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise ErrorNucleo("respuesta inesperada del núcleo", r.status_code)
        return r.json()

    def enviar_feedback(self, ref_opaca: str, id_nota: str, id_sugerencia: str, valoracion: str,
                        observacion: Optional[str] = None) -> bool:
        cuerpo = {"id_nota": id_nota, "id_sugerencia": id_sugerencia, "valoracion": valoracion}
        if observacion:
            cuerpo["observacion"] = observacion
        return self._enviar_decision("/v1/casos/%s/feedback" % ref_opaca, cuerpo)

    def enviar_clasificacion(self, ref_opaca: str, id_nota: str, articulos: list[dict],
                             observacion: Optional[str] = None) -> bool:
        cuerpo: dict = {"id_nota": id_nota, "articulos": articulos}
        if observacion:
            cuerpo["observacion"] = observacion
        return self._enviar_decision("/v1/casos/%s/clasificacion" % ref_opaca, cuerpo)

    def _enviar_decision(self, ruta: str, cuerpo: dict) -> bool:
        """True si el núcleo la registró; False si no conoce la solicitud (404)."""
        r = self._pedir("POST", ruta, cuerpo)
        if r.status_code in (200, 201):
            return True
        if r.status_code == 404:
            return False
        raise ErrorNucleo("el núcleo rechazó la decisión", r.status_code)
