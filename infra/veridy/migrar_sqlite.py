"""
Copia una instalación de Veridy en SQLite (globaleaks.db) a su base PostgreSQL.

Las dos bases deben tener el mismo esquema (version_db). Usa los modelos de Veridy, así que se
corre dentro de la imagen de Veridy:

  docker run --rm -e PGPASSFILE=/r/pgpass -e VERIDY_PG_URI=... -v <dir>:/r -v <este dir>:/m:ro \
    --entrypoint python3 <imagen veridy> /m/migrar_sqlite.py /r/globaleaks.db [--aplicar]

Sin --aplicar es un ensayo: hace toda la copia en una transacción, verifica los conteos y la
deshace. Con --aplicar la confirma.

Reemplaza el contenido de la base PostgreSQL por el de SQLite, salvo:
  - las variables de config de CONSERVAR_CONFIG (hostname, HTTPS, ACME, Tor), que son de la
    instalación de destino;
  - los usuarios de destino cuyo nombre no exista en SQLite, que se agregan sin escrow (su
    escrow corresponde a otra clave maestra y no sirve con la de SQLite).

Respaldar antes la base de destino (pg_dump). Veridy debe estar detenido mientras corre.
"""
import os
import sys

from sqlalchemy import create_engine, func, select, text

from globaleaks.models import Base

CONSERVAR_CONFIG = {
    "hostname", "https_enabled", "https_key", "https_cert", "https_chain", "https_csr",
    "https_selfsigned_key", "https_selfsigned_cert", "acme", "acme_accnt_key",
    # Tor y red de la instalación de destino: la dirección .onion publicada no cambia.
    "tor", "onionservice", "tor_onion_key", "anonymize_outgoing_connections",
}
SIN_ESCROW = {"crypto_escrow_prv_key": "", "crypto_escrow_bkp1_key": "", "crypto_escrow_bkp2_key": ""}


def filas(conn, tabla):
    return [dict(r._mapping) for r in conn.execute(select(tabla))]


def main():
    if len(sys.argv) < 2:
        sys.exit("uso: migrar_sqlite.py <globaleaks.db> [--aplicar]")
    aplicar = "--aplicar" in sys.argv[2:]
    origen = create_engine(f"sqlite:///file:{sys.argv[1]}?mode=ro&uri=true")
    destino = create_engine(os.environ["VERIDY_PG_URI"])
    tablas = Base.metadata.sorted_tables  # padres antes que hijos
    por_nombre = {t.name: t for t in tablas}

    with origen.connect() as o:
        version = o.execute(text("select value from config where var_name = 'version_db'")).scalar()
        datos = {t.name: filas(o, t) for t in tablas}

    with destino.connect() as d:
        trans = d.begin()
        version_dest = d.execute(text("select value from config where var_name = 'version_db'")).scalar()
        if str(version) != str(version_dest):
            sys.exit(f"esquemas distintos: SQLite {version}, PostgreSQL {version_dest}")

        config_dest = {(r["tid"], r["var_name"]): r for r in filas(d, por_nombre["config"])
                       if r["var_name"] in CONSERVAR_CONFIG}
        nombres = {(u["tid"], u["username"]) for u in datos["user"]}
        usuarios_dest = [{**u, **SIN_ESCROW} for u in filas(d, por_nombre["user"])
                         if (u["tid"], u["username"]) not in nombres]

        for t in reversed(tablas):
            d.execute(t.delete())

        datos["config"] = [config_dest.get((r["tid"], r["var_name"]), r) for r in datos["config"]]
        datos["user"] += usuarios_dest
        for t in tablas:
            if datos[t.name]:
                d.execute(t.insert(), datos[t.name])

        # Secuencias de las claves enteras autoincrementales (auditlog, tenant...).
        for t in tablas:
            pk = list(t.primary_key.columns)
            if len(pk) == 1 and pk[0].type.python_type is int and datos[t.name]:
                seq = d.execute(text("select pg_get_serial_sequence(:t, :c)"),
                                {"t": t.name, "c": pk[0].name}).scalar()
                if seq:
                    d.execute(text("select setval(:s, (select max(%s) from \"%s\"))" % (pk[0].name, t.name)),
                              {"s": seq})

        resumen = []
        for t in tablas:
            n = d.execute(select(func.count()).select_from(t)).scalar()
            esperado = len(datos[t.name])
            if n != esperado:
                trans.rollback()
                sys.exit(f"{t.name}: {n} filas en destino, se esperaban {esperado}")
            if n:
                resumen.append(f"{t.name}={n}")
        print("filas:", ", ".join(resumen))
        print("config conservada del destino:", sorted(v for _, v in config_dest))
        print("usuarios de destino agregados sin escrow:", [u["username"] for u in usuarios_dest])

        if aplicar:
            trans.commit()
            print("APLICADO")
        else:
            trans.rollback()
            print("ENSAYO: sin cambios (usar --aplicar para confirmar)")


if __name__ == "__main__":
    main()
