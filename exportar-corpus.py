#!/usr/bin/env python3
"""Exporta el corpus de skill/data/corpus.jsonl conservando la jerarquia del XML de BCN.

Uso:  python exportar-corpus.py [salida.jsonl]
Necesita red (descarga el XML desde LeyChile) y las dependencias del repo.

El DFL 1 (idNorma 172986) es un compendio: el Codigo Civil vive bajo su
"Articulo 2" y las leyes anexas bajo otros articulos. Sin jerarquia, un
"articulo 31" se atribuiria al Codigo Civil aunque sea de la Ley 4.808.
"""
import json
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from mcp_leyes import bcn  # noqa: E402
from lxml import etree  # noqa: E402

NORMAS = [6369, 207436, 172986, 1974, 1984, 242302, 141599, 127917, 61438]
CORTO = {
    172986: "Código Civil", 207436: "Código del Trabajo", 1974: "Código de Comercio",
    1984: "Código Penal", 6369: "DL 825 (IVA)", 61438: "Ley 19.496 (consumidor)",
    141599: "Ley 19.628 (datos personales)", 242302: "Constitución",
    127917: "Decreto 587 (arancel notarios)",
}


def ln(e):
    return etree.QName(e).localname


def sin_tildes(valor):
    s = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def metas(e):
    m = {}
    for met in e:
        if ln(met) == "Metadatos":
            for x in met:
                m[ln(x)] = (x.text or "").strip()
    return m


def exportar(idn):
    parser = etree.XMLParser(recover=True, huge_tree=True)
    raiz = etree.fromstring(bcn.xml_norma(idn), parser=parser)
    filas = []

    def walk(e, pila):
        for ch in e:
            if not isinstance(ch.tag, str):
                continue
            if ln(ch) != "EstructuraFuncional":
                walk(ch, pila)
                continue
            m = metas(ch)
            nivel = {"tipo": ch.get("tipoParte") or "", "nombre": m.get("NombreParte", ""),
                     "titulo": m.get("TituloParte", "")}
            nueva = pila + [nivel]
            texto = ""
            for h in ch:
                if ln(h) == "Texto":
                    texto = (h.text or "").strip()
            if texto:
                cuerpo = ""
                for n in nueva:
                    if n["titulo"]:
                        cuerpo = n["titulo"]
                        break
                if not cuerpo:
                    cuerpo = nueva[0]["nombre"]
                seccion = ""
                for n in reversed(nueva):
                    if n["titulo"] and n["titulo"] != cuerpo:
                        seccion = n["titulo"]
                        break
                filas.append({
                    "id_norma": idn, "norma": CORTO.get(idn, cuerpo),
                    "cuerpo": cuerpo, "seccion": seccion,
                    "id_parte": ch.get("idParte"), "nombre": m.get("NombreParte", ""),
                    "titulo": m.get("TituloParte", ""), "texto": texto,
                    "derogado": ch.get("derogado") or "",
                    "transitorio": ch.get("transitorio") or "",
                    "fecha_version": ch.get("fechaVersion") or "",
                    "url": "https://www.leychile.cl/N?i=%s" % idn,
                })
            walk(ch, nueva)

    walk(raiz, [])
    return filas


def main():
    salida = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "skill" / "data" / "corpus.jsonl")
    salida.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with salida.open("w", encoding="utf-8") as fh:
        for idn in NORMAS:
            filas = exportar(idn)
            if idn == 172986:
                antes = len(filas)
                filas = [f for f in filas if "codigo civil" in sin_tildes(f["cuerpo"])]
                print("  172986: %d partes, %d del Codigo Civil" % (antes, len(filas)), flush=True)
            for f in filas:
                fh.write(json.dumps(f, ensure_ascii=False, separators=(",", ":")) + "\n")
            total += len(filas)
            print("  %s: %d" % (idn, len(filas)), flush=True)
    print("OK %d filas -> %s (%.1f MB)" % (total, salida, salida.stat().st_size / 1048576))


if __name__ == "__main__":
    main()
