"""Indice local: SQLite + FTS5. El texto vive aqui, no en el prompt."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS norma (
  id INTEGER PRIMARY KEY,
  tipo TEXT, numero TEXT, titulo TEXT, organismo TEXT,
  fecha_publicacion TEXT, fecha_promulgacion TEXT, fecha_version TEXT,
  derogado TEXT, sha256 TEXT, descargado TEXT, url TEXT
);
CREATE TABLE IF NOT EXISTS parte (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_norma INTEGER NOT NULL REFERENCES norma(id),
  orden INTEGER, id_parte TEXT, tipo TEXT, clase TEXT,
  nombre TEXT, titulo TEXT, texto TEXT,
  derogado TEXT, transitorio TEXT, fecha_version TEXT
);
CREATE TABLE IF NOT EXISTS version (
  id_norma INTEGER NOT NULL, vigente_desde TEXT, vigente_hasta TEXT,
  tipo_version TEXT, url TEXT,
  PRIMARY KEY (id_norma, vigente_desde)
);
CREATE VIRTUAL TABLE IF NOT EXISTS parte_fts USING fts5(
  nombre, titulo, texto, content='parte', content_rowid='id'
);
CREATE INDEX IF NOT EXISTS ix_parte_norma ON parte(id_norma);
CREATE INDEX IF NOT EXISTS ix_parte_nombre ON parte(id_norma, nombre);
"""


def conectar(ruta: str | Path) -> sqlite3.Connection:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(ruta))
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def sha_de(con, id_norma: int) -> str | None:
    fila = con.execute("SELECT sha256 FROM norma WHERE id=?", (id_norma,)).fetchone()
    return fila["sha256"] if fila else None


def guardar(con, meta: dict, partes: list[dict], sha: str, descargado: str) -> None:
    url = f"https://www.leychile.cl/N?i={meta['id_norma']}"
    con.execute("DELETE FROM parte WHERE id_norma=?", (meta["id_norma"],))
    con.execute("DELETE FROM norma WHERE id=?", (meta["id_norma"],))
    con.execute(
        "INSERT INTO norma VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (meta["id_norma"], meta["tipo"], meta["numero"], meta["titulo"],
         meta["organismo"], meta["fecha_publicacion"], meta["fecha_promulgacion"],
         meta["fecha_version"], meta["derogado"], sha, descargado, url),
    )
    con.executemany(
        "INSERT INTO parte (id_norma, orden, id_parte, tipo, clase, nombre, titulo,"
        " texto, derogado, transitorio, fecha_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(meta["id_norma"], p["orden"], p["id_parte"], p["tipo"], p["clase"],
          p["nombre"], p["titulo"], p["texto"], p["derogado"], p["transitorio"],
          p["fecha_version"]) for p in partes],
    )
    con.execute("INSERT INTO parte_fts(parte_fts) VALUES('rebuild')")


def guardar_versiones(con, id_norma: int, versiones: list[dict]) -> int:
    con.execute("DELETE FROM version WHERE id_norma=?", (id_norma,))
    filas = []
    for v in versiones:
        filas.append((id_norma, v.get("@vigenteDesde") or "", v.get("@vigenteHasta") or "",
                      v.get("@tipoVersion") or "",
                      (v.get("UrlVersion") or {}).get("$", "")))
    con.executemany("INSERT OR REPLACE INTO version VALUES (?,?,?,?,?)", filas)
    return len(filas)


MAX_TOKENS = 24
MAX_TOKEN = 64


def _limpiar(q: str) -> str:
    return " ".join(t for t in q.replace('"', " ").split() if t)


def recortar(q: str) -> tuple[str, bool]:
    """Corta la consulta a 24 terminos de 64 chars: 6000 terminos tardaban 44 s."""
    trozos = _limpiar(q).split()
    recortado = len(trozos) > MAX_TOKENS or any(len(t) > MAX_TOKEN for t in trozos)
    tokens = [t[:MAX_TOKEN] for t in trozos[:MAX_TOKENS]]
    return " ".join(tokens), recortado


def buscar(con, q: str, limite: int = 10, solo_vigentes: bool = True) -> list[dict]:
    tokens, _ = recortar(q)
    if not tokens:
        return []
    consulta = " ".join(f'"{t}"*' for t in tokens.split())
    sql = """
      SELECT p.id_norma, p.nombre, p.titulo, p.clase, p.derogado, p.fecha_version,
             n.tipo, n.numero, n.titulo AS titulo_norma,
             snippet(parte_fts, 2, '>>>', '<<<', '…', 18) AS fragmento
      FROM parte_fts JOIN parte p ON p.id = parte_fts.rowid
      JOIN norma n ON n.id = p.id_norma
      WHERE parte_fts MATCH ?
    """
    if solo_vigentes:
        sql += " AND p.derogado != 'derogado'"
    sql += " ORDER BY rank LIMIT ?"
    try:
        filas = con.execute(sql, (consulta, limite)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(f) for f in filas]


def _clave_articulo(nombre: str) -> str:
    """Clave del articulo: numero + bis/ter, ignorando sufijos como '(DEL ART. 2)'.

    Acepta '1545', '1545 bis', 'art. 1545' y 'artículo 1545'.
    """
    import re
    limpio = str(nombre or "").replace("°", "").replace("º", "").strip()
    limpio = re.sub(r"^(?:art[ií]culo|art)\.?\s*", "", limpio, flags=re.I)
    m = re.match(r"(\d+)\s*(bis|ter|quater)?", limpio, re.I)
    if not m:
        return limpio.rstrip(".").lower()
    return f"{m.group(1)}{(m.group(2) or '').lower()}"


def traer_articulo(con, id_norma: int, numero: str) -> list[dict]:
    """Busca por clave. Prefiltra en SQL: cargar 2.800 articulos costaba 180 ms por llamada."""
    objetivo = _clave_articulo(numero)
    digitos = "".join(c for c in objetivo if c.isdigit()) or objetivo
    filas = con.execute(
        "SELECT * FROM parte WHERE id_norma=? AND clase LIKE 'articulo%' AND nombre LIKE ?",
        (id_norma, f"{digitos}%"),
    ).fetchall()
    return [dict(f) for f in filas if _clave_articulo(f["nombre"]) == objetivo]


def norma(con, id_norma: int) -> dict | None:
    f = con.execute("SELECT * FROM norma WHERE id=?", (id_norma,)).fetchone()
    return dict(f) if f else None


def versiones_de(con, id_norma: int) -> list[dict]:
    return [dict(f) for f in con.execute(
        "SELECT * FROM version WHERE id_norma=? ORDER BY vigente_desde DESC", (id_norma,))]


def cobertura(con) -> dict:
    una = con.execute("SELECT COUNT(*) c FROM norma").fetchone()["c"]
    art = con.execute("SELECT COUNT(*) c FROM parte WHERE clase LIKE 'articulo%'").fetchone()["c"]
    ver = con.execute("SELECT COUNT(*) c FROM version").fetchone()["c"]
    ult = con.execute("SELECT MAX(descargado) d FROM norma").fetchone()["d"]
    return {"normas": una, "articulos": art, "versiones": ver, "ultima_ingesta": ult}
