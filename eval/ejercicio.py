"""Ejercicio adversarial: 10 tareas por el protocolo MCP real, con puntaje."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from mcp_leyes import db

from .cliente import Cliente

RAIZ = Path(__file__).resolve().parent.parent
DB = os.environ.get("MCP_LEYES_DB") or str(RAIZ / "data" / "corpus.db")


def _txt(r: dict) -> str:
    return json.dumps(r, ensure_ascii=False).lower()


def c_art825(res, ctx):
    return ("dl 825, art. 14" in _txt(res)
            and (res.get("texto") or "").startswith("Artículo 14")
            and "i=6369" in (res.get("fuente") or "")
            and res.get("idNorma") == 6369)


def c_feriado(res, ctx):
    return res.get("total", 0) > 0 and any(x["id_norma"] == 207436 for x in res["resultados"])


def c_prescripcion(res, ctx):
    return res.get("total", 0) > 0 and any(x["id_norma"] in (172986, 1974) for x in res["resultados"])


def c_historico(res, ctx):
    return (res.get("vigente_al") == "2015-01-01"
            and res.get("confianza") in ("alta", "media")
            and (res.get("texto") or "").startswith("Artículo 14")
            and isinstance(res.get("sin_cambios"), bool))


def c_derogado(res, ctx):
    return res.get("estado") == "derogado"


def c_duplicado(res, ctx):
    return res.get("coincidencias", 0) > 1 and "comparten" in (res.get("hueco") or "")


def c_inexistente(res, ctx):
    return str(res.get("error", "")).startswith("[not_found]")


def c_fuera_cobertura(res, ctx):
    return res.get("total", 0) == 0


def c_arancel(res, ctx):
    f = (res.get("fichas") or [{}])[0]
    return bool(f.get("arancel", {}).get("advertencia"))


def c_documento(res, ctx):
    a = res.get("archivos") or {}
    base = res.get("base_legal") or {}
    return (Path(a.get("pdf", "")).exists() and Path(a.get("odt", "")).exists()
            and "BORRADOR" in (res.get("aviso") or "")
            and "172986" in (base.get("fuente") or ""))


def preparar(con) -> list[dict]:
    der = con.execute(
        "SELECT id_norma, nombre FROM parte WHERE clase LIKE 'articulo%' "
        "AND derogado='derogado' LIMIT 1").fetchone()
    dup = con.execute(
        "SELECT id_norma, nombre, COUNT(*) c FROM parte WHERE clase LIKE 'articulo%' "
        "GROUP BY id_norma, nombre HAVING c > 1 ORDER BY c DESC LIMIT 1").fetchone()
    return [
        {"id": "art-825-14", "nivel": 1, "puntos": 1, "check": c_art825,
         "pregunta": "¿Qué dice el artículo 14 del DL 825?",
         "tool": "cl_articulo", "args": {"id_norma": 6369, "articulo": "14"}},
        {"id": "buscar-feriado", "nivel": 2, "puntos": 2, "check": c_feriado,
         "pregunta": "¿Dónde está la norma del feriado anual?",
         "tool": "cl_buscar", "args": {"q": "feriado anual", "limite": 10}},
        {"id": "buscar-prescripcion", "nivel": 2, "puntos": 2, "check": c_prescripcion,
         "pregunta": "Busca la prescripción de las acciones",
         "tool": "cl_buscar", "args": {"q": "prescripción de las acciones", "limite": 10}},
        {"id": "historico-825", "nivel": 3, "puntos": 3, "check": c_historico,
         "pregunta": "¿Qué decía el artículo 14 del DL 825 al 1 de enero de 2015?",
         "tool": "cl_articulo", "args": {"id_norma": 6369, "articulo": "14",
                                         "vigente_al": "2015-01-01"}},
        {"id": "derogado", "nivel": 3, "puntos": 2, "check": c_derogado,
         "pregunta": "Texto de un artículo derogado",
         "tool": "cl_articulo",
         "args": {"id_norma": der["id_norma"], "articulo": der["nombre"]}},
        {"id": "duplicado", "nivel": 3, "puntos": 2, "check": c_duplicado,
         "pregunta": "Artículo con número repetido en una norma refundida",
         "tool": "cl_articulo",
         "args": {"id_norma": dup["id_norma"], "articulo": dup["nombre"]}},
        {"id": "inexistente", "nivel": 3, "puntos": 2, "check": c_inexistente,
         "pregunta": "¿Qué dice el artículo 9999 del DL 825?",
         "tool": "cl_articulo", "args": {"id_norma": 6369, "articulo": "9999"}},
        {"id": "fuera-cobertura", "nivel": 3, "puntos": 3, "check": c_fuera_cobertura,
         "pregunta": "¿Qué ha resuelto la Corte Suprema sobre el despido injustificado?",
         "tool": "cl_buscar", "args": {"q": "Corte Suprema despido injustificado", "limite": 10}},
        {"id": "arancel", "nivel": 2, "puntos": 2, "check": c_arancel,
         "pregunta": "¿Cuánto cuesta una escritura pública?",
         "tool": "cl_notaria", "args": {"q": "arancel"}},
        {"id": "documento", "nivel": 3, "puntos": 3, "check": c_documento,
         "pregunta": "Genera el poder especial para vender un auto",
         "tool": "cl_documento",
         "args": {"plantilla": "poder-especial", "formato": "pdf", "datos": {
             "OTORGANTE": "Ana Pérez", "RUT": "9.876.543-2", "DOMICILIO": "Av. Siempre Viva 123",
             "MANDATARIO": "Pedro Soto", "RUT_MANDATARIO": "11.222.333-4",
             "FACULTADES": "vender el automóvil patente ABCD12",
             "CIUDAD": "Santiago", "FECHA": "2026-11-06"}}},
    ]


async def correr(salida: str = "resultados-ejercicio.json") -> dict:
    con = db.conectar(DB)
    tareas = preparar(con)
    detalle, puntos, logrados = [], 0, 0
    async with Cliente(sys.executable, ["-m", "mcp_leyes"]) as c:
        tools = await c.tools()
        for t in tareas:
            t0 = time.perf_counter()
            try:
                res = await c.llamar(t["tool"], t["args"])
                ok = bool(t["check"](res, con))
            except Exception as exc:  # noqa: BLE001
                res, ok = {"_error": str(exc)}, False
            ms = round((time.perf_counter() - t0) * 1000)
            puntos += t["puntos"]
            logrados += t["puntos"] if ok else 0
            detalle.append({"id": t["id"], "nivel": t["nivel"], "puntos": t["puntos"],
                            "ok": ok, "ms": ms, "pregunta": t["pregunta"],
                            "tool": t["tool"], "resultado": res})
    salida_final = {"herramientas": tools, "tareas": len(detalle),
                    "puntos": puntos, "logrados": logrados,
                    "puntaje": round(logrados / puntos, 4) if puntos else 0,
                    "detalle": detalle}
    Path(salida).write_text(json.dumps(salida_final, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida_final


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval.ejercicio")
    p.add_argument("--json", default="resultados-ejercicio.json")
    a = p.parse_args(argv)
    r = asyncio.run(correr(a.json))
    for d in r["detalle"]:
        print(f"  {'OK ' if d['ok'] else 'FALLA'} {d['id']:20s} {d['puntos']} pts  {d['ms']:>5} ms")
    print(json.dumps({k: r[k] for k in ("tareas", "puntos", "logrados", "puntaje")}, ensure_ascii=False))
    return 0 if r["puntaje"] >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
