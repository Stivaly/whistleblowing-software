"""sha256 de los datos sintéticos versionados (kerna/pruebas/datos), independiente del orden y de la ruta."""
import hashlib
import pathlib


def hash_datos(carpeta: pathlib.Path) -> str:
    h = hashlib.sha256()
    for ruta in sorted(p for p in carpeta.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(ruta.relative_to(carpeta).as_posix().encode())
        h.update(hashlib.sha256(ruta.read_bytes()).digest())
    return h.hexdigest()


if __name__ == "__main__":
    print(hash_datos(pathlib.Path(__file__).resolve().parents[1] / "datos"))
