"""Ingesta idempotente del corpus desde LeyChile."""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime

from . import bcn, db

# Cuerpos nucleares; ampliable sin tocar codigo.
NORMAS = [6369, 207436, 172986, 1974, 1984, 242302, 141599, 127917, 61438]


def una(con, id_norma: int, forzar: bool = False) -> str:
    crudo = bcn.xml_norma(id_norma)
    sha = hashlib.sha256(crudo).hexdigest()
    if not forzar and db.sha_de(con, id_norma) == sha:
        return "sin cambios"
    datos = bcn.parsear(crudo)
    db.guardar(con, datos["meta"], datos["partes"], sha,
               datetime.now().isoformat(timespec="seconds"))
    try:
        n = db.guardar_versiones(con, id_norma, bcn.versiones(id_norma))
    except bcn.BCNError:
        n = 0
    con.commit()
    return f"{datos['meta']['tipo']} {datos['meta']['numero']}: {len(datos['partes'])} partes, {n} versiones"


def todo(ruta: str, forzar: bool = False) -> int:
    con = db.conectar(ruta)
    for id_norma in NORMAS:
        try:
            print(f"  {id_norma}: {una(con, id_norma, forzar)}", flush=True)
        except bcn.BCNError as exc:
            print(f"  {id_norma}: ERROR {exc}", file=sys.stderr, flush=True)
            return 1
    c = db.cobertura(con)
    print(f"OK {c['normas']} normas, {c['articulos']} articulos, {c['versiones']} versiones")
    return 0 if c["articulos"] >= 700 and c["versiones"] >= 4 else 1
