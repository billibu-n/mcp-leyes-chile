"""Fichas notariales curadas: cada campo declara su estado y su fuente."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import db as db_mod

DIR = Path(__file__).resolve().parent.parent / "notaria"
ESTADOS = {"verificado", "parcial", "sin_fuente"}


def cargar() -> dict[str, dict]:
    fichas = {}
    for ruta in sorted(DIR.glob("*.yaml")):
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        datos["_ruta"] = ruta.name
        fichas[datos["id"]] = datos
    return fichas


def validar() -> list[str]:
    fallos = []
    for ident, f in cargar().items():
        if f.get("estado") not in ESTADOS:
            fallos.append(f"{ident}: estado invalido")
        if not f.get("fuente"):
            fallos.append(f"{ident}: sin fuente")
        if not f.get("revisado"):
            fallos.append(f"{ident}: sin fecha de revision")
        for campo in ("requisitos", "documentos"):
            for item in f.get(campo) or []:
                if item.get("estado") not in ESTADOS:
                    fallos.append(f"{ident}.{campo}: item sin estado")
        if (f.get("arancel") or {}).get("advertencia") in (None, ""):
            fallos.append(f"{ident}: arancel sin advertencia")
    return fallos


def buscar(q: str = "", ficha: str = "") -> list[dict]:
    fichas = cargar()
    if ficha:
        f = fichas.get(ficha)
        return [f] if f else []
    q = (q or "").lower().strip()
    if not q:
        return list(fichas.values())
    return [f for f in fichas.values()
            if q in f["id"] or q in f.get("tramite", "").lower()
            or q in (f.get("para_que") or "").lower()]


def numerales_arancel(texto: str) -> list[tuple[int, str]]:
    """Parte el articulo 1 del arancel en (numeral, texto)."""
    trozos = re.split(r"(?<![\d.$])(\d{1,2})\)\s+", texto)
    salida = []
    for i in range(1, len(trozos) - 1, 2):
        try:
            salida.append((int(trozos[i]), trozos[i + 1].strip()))
        except ValueError:
            continue
    return salida


def _titulo(texto: str, tope: int = 90) -> str:
    frase = re.split(r"(?<=[.;])\s", texto, maxsplit=1)[0]
    frase = re.sub(r"\s+", " ", frase).strip()
    return (frase[:tope].rstrip() + "…") if len(frase) > tope else frase


def generar_desde_arancel(con, escribir: bool = True, destino: Path | None = None) -> list[str]:
    """Crea fichas a partir de los numerales del Decreto 587/1998.

    Cada ficha lleva el texto del numeral y su fuente; los requisitos quedan
    declarados como sin fuente porque no existe catalogo publico estructurado.
    """
    partes = db_mod.traer_articulo(con, 127917, "1")
    if not partes:
        raise RuntimeError("falta la norma 127917 en el indice (corre la ingesta)")
    creadas = []
    for numero, texto in numerales_arancel(partes[0]["texto"]):
        ident = f"arancel-{numero:02d}"
        if ident in cargar():
            continue
        ficha = {
            "id": ident,
            "tramite": _titulo(texto),
            "para_que": "Acto notarial con derecho maximo fijado por el arancel.",
            "requisitos": [],
            "documentos": [],
            "arancel": {
                "norma": "Decreto 587 Exento, 1998 (idNorma 127917)",
                "numeral": str(numero),
                "texto_nominal": texto[:600],
                "advertencia": "Monto nominal de 1998. NO es el precio actual: el decreto no trae "
                               "clausula de reajuste en su texto. Confirmar en la notaria.",
            },
            "competencia": {"regla": None, "estado": "sin_fuente"},
            "fuente": [{"url": "https://www.leychile.cl/N?i=127917",
                        "consultado": "2026-11-06",
                        "que": f"Arancel, numeral {numero}"}],
            "revisado": "2026-11-06",
            "estado": "parcial",
        }
        if escribir:
            ruta = (destino or DIR) / f"{ident}.yaml"
            ruta.write_text(yaml.safe_dump(ficha, allow_unicode=True, sort_keys=False),
                            encoding="utf-8")
        creadas.append(ident)
    return creadas
