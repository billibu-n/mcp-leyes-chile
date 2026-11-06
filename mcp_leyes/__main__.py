"""CLI: servir por stdio, ingerir, generar documentos o levantar el formulario."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from . import db, documentos, ingesta, notaria, server


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mcp_leyes")
    p.add_argument("--selftest", action="store_true", help="lista tools y sale")
    p.add_argument("--ingesta", action="store_true", help="descarga y reindexa el corpus")
    p.add_argument("--forzar", action="store_true", help="reingesta aunque el hash no cambie")
    p.add_argument("--cobertura", action="store_true", help="estado del indice")
    p.add_argument("--notaria", action="store_true", help="valida las fichas notariales")
    p.add_argument("--notaria-generar", action="store_true", help="crea fichas desde el arancel")
    p.add_argument("--eval", type=int, default=0, metavar="N", help="corre el banco de N tareas")
    p.add_argument("--documento", nargs=2, metavar=("PLANTILLA", "DATOS_JSON"))
    p.add_argument("--formulario", type=int, nargs="?", const=8801)
    p.add_argument("--smoke", action="store_true", help="genera un documento de prueba y verifica")
    p.add_argument("--db", default=server.DB)
    a = p.parse_args(argv)

    if a.selftest:
        nombres = [t.name for t in asyncio.run(server.mcp.list_tools())]
        print(json.dumps({"version": server.mcp.version, "tools": nombres}, ensure_ascii=False))
        return 0 if len(nombres) == 7 else 1
    if a.ingesta:
        return ingesta.todo(a.db, forzar=a.forzar)
    if a.cobertura:
        print(json.dumps(db.cobertura(db.conectar(a.db)), ensure_ascii=False, indent=1))
        return 0
    if a.notaria:
        fallos = notaria.validar()
        print(f"{len(notaria.cargar())} fichas, {len(fallos)} fallos")
        for f in fallos:
            print("  -", f)
        return 0 if not fallos else 1
    if a.notaria_generar:
        con = db.conectar(a.db)
        creadas = notaria.generar_desde_arancel(con)
        print(json.dumps({"creadas": creadas, "total": len(notaria.cargar())}, ensure_ascii=False))
        return 0
    if a.eval:
        from eval.correr import correr
        r = correr(a.eval)
        print(json.dumps({k: v for k, v in r.items() if k != "detalles"}, ensure_ascii=False))
        return 0 if r["ok"] else 1
    if a.documento:
        plantilla, ruta = a.documento
        datos = json.loads(open(ruta, encoding="utf-8").read())
        print(json.dumps(documentos.generar(plantilla, datos), ensure_ascii=False, indent=1))
        return 0
    if a.smoke:
        datos = {"OTORGANTE": "Ana Pérez", "RUT": "9.876.543-2", "DOMICILIO": "Av. Siempre Viva 123",
                 "MANDATARIO": "Pedro Soto", "RUT_MANDATARIO": "11.222.333-4",
                 "FACULTADES": "vender el automóvil patente ABCD12", "CIUDAD": "Santiago",
                 "FECHA": "2026-11-06"}
        r = documentos.generar("poder-especial", datos, ("odt", "pdf"))
        pdf = __import__("pathlib").Path(r["archivos"]["pdf"])
        ok = pdf.exists() and pdf.stat().st_size > 1000
        print(json.dumps({**r, "ok": ok, "pdf_bytes": pdf.stat().st_size if pdf.exists() else 0},
                         ensure_ascii=False))
        return 0 if ok else 1
    if a.formulario:
        from . import formulario
        formulario.servir(a.formulario)
        return 0
    server.mcp.run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
