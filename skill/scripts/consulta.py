#!/usr/bin/env python3
"""consulta.py - busca en el corpus local de LeyChile. Sin red, sin escrituras.

Uso:
    python3 scripts/consulta.py normas
    python3 scripts/consulta.py buscar "responsabilidad solidaria" --limite 5
    python3 scripts/consulta.py buscar "compraventa" --norma 207436
    python3 scripts/consulta.py articulo 1974 23

Devuelve JSON por stdout. El corpus vive en data/corpus.jsonl (texto legible).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CORPUS = BASE / "data" / "corpus.jsonl"
AVISO = "Esto no es asesoría legal. Verifica con un profesional antes de actuar."

# Nombre corto por idNorma: el titulo oficial es larguisimo y no sirve para citar.
NOMBRES = {
    172986: "Código Civil",
    207436: "Código del Trabajo",
    1974: "Código de Comercio",
    1984: "Código Penal",
    6369: "DL 825 (IVA)",
    61438: "Ley 19.496 (consumidor)",
    141599: "Ley 19.628 (datos personales)",
    242302: "Constitución",
    127917: "Decreto 587 (arancel notarios)",
}


def normalizar(valor):
    """Minusculas sin tildes ni espacios de mas; para comparar sin falsos negativos."""
    if not valor:
        return ""
    s = unicodedata.normalize("NFKD", str(valor))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def cargar():
    if not CORPUS.is_file():
        sys.exit("ROJO: falta data/corpus.jsonl")
    filas = []
    with CORPUS.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if linea:
                filas.append(json.loads(linea))
    return filas


def etiqueta(f):
    return (f.get("norma") or NOMBRES.get(f.get("id_norma"))
            or ("%s %s" % (f.get("tipo") or "", f.get("numero") or "")).strip())


def numero_articulo(f):
    bruto = str(f.get("nombre") or "").replace("°", "").replace("º", "").strip()
    m = re.match(r"(\d+)\s*(bis|ter|quater)?", bruto, re.I)
    if m:
        return m.group(1) + (m.group(2) or "").lower()
    return bruto.rstrip(".")


def base_nombre(valor):
    """'1793 (DEL ART. 2)' -> '1793'; el sufijo marca variantes del mismo articulo."""
    return normalizar(re.sub(r"\(.*?\)", "", str(valor or ""))).strip(" .")


def estado(f):
    if f.get("derogado") == "derogado":
        return "derogado"
    if f.get("transitorio") == "transitorio":
        return "transitorio"
    return "vigente"


def cita(f):
    base = "%s, art. %s" % (etiqueta(f), numero_articulo(f))
    fecha = str(f.get("fecha_version") or "")
    if estado(f) == "derogado":
        return base + " (derogado" + (", última versión %s)" % fecha if fecha else ")")
    if fecha and not fecha.startswith("2222"):
        base += ", texto vigente desde %s" % fecha
    return base


def extracto(texto, tope=320):
    limpio = re.sub(r"\s+", " ", texto or "").strip()
    return limpio[:tope] + ("…" if len(limpio) > tope else "")


def buscar(filas, consulta, limite, norma=None):
    objetivo = normalizar(consulta)
    tokens = [t for t in objetivo.split() if len(t) >= 3]
    hallados = []
    for f in filas:
        if norma and str(f.get("id_norma")) != str(norma):
            continue
        if not str(f.get("nombre") or "").strip():
            continue  # encabezados de titulo, no citables
        cuerpo = normalizar((f.get("texto") or "") + " " + (f.get("titulo") or ""))
        if not cuerpo:
            continue
        if objetivo and objetivo in cuerpo:
            pos = cuerpo.find(objetivo)
            # Las definiciones abren el articulo ("La compraventa es un contrato...").
            if 0 <= pos < 60:
                inicio = cuerpo[:240]
                definicion = " es un " in inicio or " es el " in inicio or " se define " in inicio
                bonus = 30 if definicion else 15
            else:
                bonus = 5 if pos < 400 else 0
            puntaje = 100 + bonus + min(cuerpo.count(objetivo), 10)
        else:
            if not tokens:
                continue
            aciertos = sum(1 for t in tokens if t in cuerpo)
            if aciertos < max(1, (len(tokens) + 1) // 2):
                continue
            puntaje = aciertos
        hallados.append((puntaje, f))
    hallados.sort(key=lambda par: (-par[0], par[1].get("id_norma"), str(par[1].get("nombre"))))
    return hallados


def ficha(f, puntaje=None):
    fecha = str(f.get("fecha_version") or "")
    hueco = None
    if fecha.startswith("2222"):
        hueco = "vigencia diferida por evento (centinela 2222-02-02)"
        fecha = ""
    datos = {
        "id_norma": f.get("id_norma"),
        "norma": etiqueta(f),
        "articulo": numero_articulo(f),
        "estado": estado(f),
        "vigente_desde": fecha or None,
        "url": f.get("url") or "https://www.leychile.cl/N?i=%s" % f.get("id_norma"),
        "cita": cita(f),
        "extracto": extracto(f.get("texto")),
    }
    if puntaje is not None:
        datos["score"] = puntaje
    if hueco:
        datos["hueco"] = hueco
    return datos


def main():
    p = argparse.ArgumentParser(description="Consulta local del corpus LeyChile")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("normas", help="lista las normas del corpus")

    b = sub.add_parser("buscar", help="busca texto en los articulos")
    b.add_argument("texto")
    b.add_argument("--limite", type=int, default=5)
    b.add_argument("--norma", default=None, help="idNorma para acotar")

    a = sub.add_parser("articulo", help="texto completo de un articulo")
    a.add_argument("id_norma")
    a.add_argument("nombre")

    args = p.parse_args()
    filas = cargar()

    if args.cmd == "normas":
        resumen = {}
        for f in filas:
            clave = (f.get("id_norma"), etiqueta(f))
            item = resumen.setdefault(clave, {"id_norma": f.get("id_norma"), "norma": etiqueta(f), "partes": 0})
            item["partes"] += 1
        print(json.dumps({"normas": sorted(resumen.values(), key=lambda x: x["id_norma"]),
                          "partes": len(filas), "aviso": AVISO}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "buscar":
        limite = max(1, min(int(args.limite), 20))
        res = buscar(filas, args.texto, limite, args.norma)
        total = len(res)
        res = res[:limite]
        print(json.dumps({"consulta": args.texto, "total": total, "devueltos": len(res),
                          "resultados": [ficha(f, s) for s, f in res],
                          "aviso": AVISO}, ensure_ascii=False, indent=2))
        return 0

    objetivo = normalizar(args.nombre).rstrip(" .")
    exactos, variantes = [], []
    for f in filas:
        if str(f.get("id_norma")) != str(args.id_norma):
            continue
        if base_nombre(f.get("nombre")) == objetivo:
            (variantes if "(" in str(f.get("nombre")) else exactos).append(f)
    elegido = (exactos or variantes)
    if not elegido:
        print(json.dumps({"error": "no_encontrado", "id_norma": args.id_norma,
                          "articulo": args.nombre}, ensure_ascii=False, indent=2))
        return 1
    f = elegido[0]
    datos = ficha(f)
    datos["texto"] = (f.get("texto") or "").strip()
    datos["aviso"] = AVISO
    print(json.dumps(datos, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
