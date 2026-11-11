"""Estado persistente del conector. Es el único lugar donde conviven el identificador real del caso y la `ref_opaca`.

Nunca guarda el texto del caso. Tablas: `correspondencia_caso`, `objeto_procesado`, `ejecucion_reconciliacion`,
`aviso_recibido` (reservada) y `cerrojo` (exclusión entre pasadas).
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

ESQUEMA = [
    """CREATE TABLE IF NOT EXISTS correspondencia_caso (
        id_caso TEXT PRIMARY KEY,
        ref_opaca TEXT NOT NULL UNIQUE,
        id_solicitud TEXT,
        estado TEXT NOT NULL,
        id_nota_sugerencia TEXT,
        intentos INTEGER NOT NULL DEFAULT 0,
        proximo_intento DOUBLE PRECISION NOT NULL DEFAULT 0,
        ultimo_error TEXT,
        creado_en TEXT NOT NULL,
        actualizado_en TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS objeto_procesado (
        id_caso TEXT NOT NULL,
        tipo TEXT NOT NULL,
        clave TEXT NOT NULL,
        id_nota TEXT,
        procesado_en TEXT NOT NULL,
        PRIMARY KEY (id_caso, tipo, clave))""",
    """CREATE TABLE IF NOT EXISTS ejecucion_reconciliacion (
        id TEXT PRIMARY KEY,
        inicio TEXT NOT NULL,
        fin TEXT,
        casos INTEGER NOT NULL DEFAULT 0,
        enviados INTEGER NOT NULL DEFAULT 0,
        publicadas INTEGER NOT NULL DEFAULT 0,
        decisiones INTEGER NOT NULL DEFAULT 0,
        errores INTEGER NOT NULL DEFAULT 0,
        resultado TEXT)""",
    """CREATE TABLE IF NOT EXISTS aviso_recibido (
        id TEXT PRIMARY KEY,
        id_caso TEXT,
        recibido_en TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS cerrojo (
        nombre TEXT PRIMARY KEY,
        dueno TEXT NOT NULL,
        vence DOUBLE PRECISION NOT NULL)""",
]

# Estados de `correspondencia_caso.estado`
NUEVO, PENDIENTE, COMPLETADO, ERROR = "nuevo", "pendiente", "completado", "error"


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Correspondencia:
    id_caso: str
    ref_opaca: str
    id_solicitud: Optional[str]
    estado: str
    id_nota_sugerencia: Optional[str]
    intentos: int
    proximo_intento: float
    ultimo_error: Optional[str]


_COLUMNAS = "id_caso, ref_opaca, id_solicitud, estado, id_nota_sugerencia, intentos, proximo_intento, ultimo_error"


class Estado(ABC):
    """Interfaz de persistencia. Las implementaciones SQL comparten la lógica en `_EstadoSql`."""

    @abstractmethod
    def crear_esquema(self) -> None: ...
    @abstractmethod
    def obtener(self, id_caso: str) -> Optional[Correspondencia]: ...
    @abstractmethod
    def registrar(self, id_caso: str, ref_opaca: str) -> Correspondencia: ...
    @abstractmethod
    def actualizar(self, id_caso: str, **campos) -> None: ...
    @abstractmethod
    def registrar_fallo(self, id_caso: str, codigo: str, ahora: float, base_s: float = 30, tope_s: float = 3600) -> None: ...
    @abstractmethod
    def listar(self) -> list[Correspondencia]: ...
    @abstractmethod
    def objeto_procesado(self, id_caso: str, tipo: str, clave: str) -> bool: ...
    @abstractmethod
    def id_nota_procesado(self, id_caso: str, tipo: str, clave: str) -> Optional[str]: ...
    @abstractmethod
    def marcar_procesado(self, id_caso: str, tipo: str, clave: str, id_nota: Optional[str] = None) -> None: ...
    @abstractmethod
    def tomar_cerrojo(self, nombre: str, dueno: str, ahora: float, ttl_s: float) -> bool: ...
    @abstractmethod
    def soltar_cerrojo(self, nombre: str, dueno: str) -> None: ...
    @abstractmethod
    def iniciar_ejecucion(self) -> str: ...
    @abstractmethod
    def cerrar_ejecucion(self, id_ejecucion: str, resultado: str, **conteos) -> None: ...
    @abstractmethod
    def ejecuciones(self, limite: int = 10) -> list[dict]: ...
    @abstractmethod
    def cerrar(self) -> None: ...


class _EstadoSql(Estado):
    """Lógica común; las SQL usan `?` y la subclase las adapta a su controlador."""

    @abstractmethod
    def _ejecutar(self, sql: str, params: tuple = (), lectura: bool = False) -> list[tuple]: ...

    def _uno(self, sql: str, params: tuple = ()) -> Optional[tuple]:
        filas = self._ejecutar(sql, params, lectura=True)
        return filas[0] if filas else None

    def crear_esquema(self) -> None:
        for sentencia in ESQUEMA:
            self._ejecutar(sentencia)

    @staticmethod
    def _corr(f: Optional[tuple]) -> Optional[Correspondencia]:
        return None if f is None else Correspondencia(f[0], f[1], f[2], f[3], f[4], int(f[5]), float(f[6]), f[7])

    def obtener(self, id_caso: str) -> Optional[Correspondencia]:
        return self._corr(self._uno("SELECT %s FROM correspondencia_caso WHERE id_caso = ?" % _COLUMNAS, (id_caso,)))

    def registrar(self, id_caso: str, ref_opaca: str) -> Correspondencia:
        """Crea la correspondencia si no existe (la `ref_opaca` queda fija desde el primer registro)."""
        t = _iso()
        self._ejecutar("INSERT INTO correspondencia_caso (id_caso, ref_opaca, estado, creado_en, actualizado_en) "
                       "VALUES (?, ?, ?, ?, ?) ON CONFLICT (id_caso) DO NOTHING", (id_caso, ref_opaca, NUEVO, t, t))
        return self.obtener(id_caso)  # type: ignore[return-value]

    _EDITABLES = {"id_solicitud", "estado", "id_nota_sugerencia", "intentos", "proximo_intento", "ultimo_error"}

    def actualizar(self, id_caso: str, **campos) -> None:
        if not campos or not set(campos) <= self._EDITABLES:
            raise ValueError("campos no editables: %s" % sorted(set(campos) - self._EDITABLES))
        sets = ", ".join("%s = ?" % c for c in campos)
        self._ejecutar("UPDATE correspondencia_caso SET %s, actualizado_en = ? WHERE id_caso = ?" % sets,
                       tuple(campos.values()) + (_iso(), id_caso))

    def registrar_fallo(self, id_caso: str, codigo: str, ahora: float, base_s: float = 30, tope_s: float = 3600) -> None:
        corr = self.obtener(id_caso)
        intentos = (corr.intentos if corr else 0) + 1
        espera = min(base_s * (2 ** (intentos - 1)), tope_s)
        self.actualizar(id_caso, intentos=intentos, proximo_intento=ahora + espera, ultimo_error=codigo)

    def listar(self) -> list[Correspondencia]:
        return [self._corr(f) for f in self._ejecutar(  # type: ignore[misc]
            "SELECT %s FROM correspondencia_caso ORDER BY creado_en, id_caso" % _COLUMNAS, lectura=True)]

    def objeto_procesado(self, id_caso: str, tipo: str, clave: str) -> bool:
        return self._uno("SELECT 1 FROM objeto_procesado WHERE id_caso = ? AND tipo = ? AND clave = ?",
                         (id_caso, tipo, clave)) is not None

    def id_nota_procesado(self, id_caso: str, tipo: str, clave: str) -> Optional[str]:
        fila = self._uno("SELECT id_nota FROM objeto_procesado WHERE id_caso = ? AND tipo = ? AND clave = ?",
                         (id_caso, tipo, clave))
        return fila[0] if fila else None

    def marcar_procesado(self, id_caso: str, tipo: str, clave: str, id_nota: Optional[str] = None) -> None:
        self._ejecutar("INSERT INTO objeto_procesado (id_caso, tipo, clave, id_nota, procesado_en) "
                       "VALUES (?, ?, ?, ?, ?) ON CONFLICT (id_caso, tipo, clave) DO NOTHING",
                       (id_caso, tipo, clave, id_nota, _iso()))

    def tomar_cerrojo(self, nombre: str, dueno: str, ahora: float, ttl_s: float) -> bool:
        self._ejecutar("INSERT INTO cerrojo (nombre, dueno, vence) VALUES (?, ?, ?) "
                       "ON CONFLICT (nombre) DO UPDATE SET dueno = excluded.dueno, vence = excluded.vence "
                       "WHERE cerrojo.vence < ?", (nombre, dueno, ahora + ttl_s, ahora))
        fila = self._uno("SELECT dueno FROM cerrojo WHERE nombre = ?", (nombre,))
        return fila is not None and fila[0] == dueno

    def soltar_cerrojo(self, nombre: str, dueno: str) -> None:
        self._ejecutar("UPDATE cerrojo SET vence = 0 WHERE nombre = ? AND dueno = ?", (nombre, dueno))

    def iniciar_ejecucion(self) -> str:
        id_ej = str(uuid.uuid4())
        self._ejecutar("INSERT INTO ejecucion_reconciliacion (id, inicio) VALUES (?, ?)", (id_ej, _iso()))
        return id_ej

    def cerrar_ejecucion(self, id_ejecucion: str, resultado: str, casos: int = 0, enviados: int = 0,
                         publicadas: int = 0, decisiones: int = 0, errores: int = 0) -> None:
        self._ejecutar("UPDATE ejecucion_reconciliacion SET fin = ?, casos = ?, enviados = ?, publicadas = ?, "
                       "decisiones = ?, errores = ?, resultado = ? WHERE id = ?",
                       (_iso(), casos, enviados, publicadas, decisiones, errores, resultado, id_ejecucion))

    def ejecuciones(self, limite: int = 10) -> list[dict]:
        filas = self._ejecutar("SELECT id, inicio, fin, casos, enviados, publicadas, decisiones, errores, resultado "
                               "FROM ejecucion_reconciliacion ORDER BY inicio DESC, id LIMIT %d" % int(limite),
                               lectura=True)
        claves = ("id", "inicio", "fin", "casos", "enviados", "publicadas", "decisiones", "errores", "resultado")
        return [dict(zip(claves, f)) for f in filas]


class EstadoSqlite(_EstadoSql):
    def __init__(self, ruta: str = ":memory:"):
        self._con = sqlite3.connect(ruta, check_same_thread=False, isolation_level=None, timeout=30)
        self._lock = threading.RLock()
        self.crear_esquema()

    def _ejecutar(self, sql: str, params: tuple = (), lectura: bool = False) -> list[tuple]:
        with self._lock:
            cur = self._con.execute(sql, params)
            return cur.fetchall() if lectura else []

    def cerrar(self) -> None:
        with self._lock:
            self._con.close()


class EstadoPostgres(_EstadoSql):
    def __init__(self, uri: str):
        self._uri = uri
        self._con = None
        self._lock = threading.RLock()
        self.crear_esquema()

    def _conexion(self):
        import psycopg  # import diferido: solo hace falta con PostgreSQL
        if self._con is None or self._con.closed:
            self._con = psycopg.connect(self._uri, autocommit=True, connect_timeout=15)
        return self._con

    def _ejecutar(self, sql: str, params: tuple = (), lectura: bool = False) -> list[tuple]:
        import psycopg
        sql = sql.replace("?", "%s")
        with self._lock:
            for intento in range(2):
                try:
                    with self._conexion().cursor() as cur:
                        cur.execute(sql, params)
                        return cur.fetchall() if lectura else []
                except psycopg.OperationalError:
                    self._con = None
                    if intento:
                        raise
            return []

    def cerrar(self) -> None:
        with self._lock:
            if self._con is not None and not self._con.closed:
                self._con.close()


def abrir_estado(destino: str) -> Estado:
    """`sqlite:///ruta` (o `sqlite://:memory:`) o URI de PostgreSQL (`postgresql://...`)."""
    if destino.startswith("sqlite:///"):
        return EstadoSqlite(destino[len("sqlite:///"):] or ":memory:")
    if destino.startswith(("postgresql://", "postgres://")):
        return EstadoPostgres(destino)
    raise ValueError("CONECTOR_ESTADO debe ser sqlite:///ruta o una URI de PostgreSQL")
