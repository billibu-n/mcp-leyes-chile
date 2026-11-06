"""Alto estres contra el servidor por el protocolo MCP real (stdio).

No mide "que la funcion devuelva algo": manda parametros hostiles, concurrencia,
FTS5 con sintaxis rota, documentos en paralelo y lotes grandes. Cada comprobacion
declara que deberia pasar; el fallo dice donde duele.

Uso:
    python -m eval.estres            # corre todo y escribe eval/estres-<fecha>.json
    python -m eval.estres -v         # lista cada comprobacion
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import statistics
import sys
import time
import zipfile
from pathlib import Path

from mcp_leyes import db

from .cliente import Cliente

RAIZ = Path(__file__).resolve().parent.parent
DB = os.environ.get("MCP_LEYES_DB") or str(RAIZ / "data" / "corpus.db")
TIMEOUT = 90.0

COMPROBACIONES: list = []


def comprueba(fn):
    COMPROBACIONES.append(fn)
    return fn


def _txt(r) -> str:
    return json.dumps(r, ensure_ascii=False, default=str)


async def crudo(cli, nombre: str, args: dict):
    """Llama sin lanzar: devuelve (ok, resultado|excepcion)."""
    try:
        return True, await asyncio.wait_for(cli.session.call_tool(nombre, args), TIMEOUT)
    except Exception as exc:  # noqa: BLE001 - el estres busca justo esto
        return False, exc


def _cuerpo(r) -> dict:
    if getattr(r, "content", None):
        try:
            return json.loads(r.content[0].text)
        except Exception:  # noqa: BLE001
            return {"_crudo": r.content[0].text}
    return {}


def _texto(r) -> str:
    return r.content[0].text if getattr(r, "content", None) else ""


def _es_error(r) -> bool:
    """El SDK 2.x marca is_error; ademas hay rechazos que llegan como texto."""
    return (bool(getattr(r, "is_error", False)) or (isinstance(r, dict) and "error" in r)
            or "rejected arguments" in _texto(r) or "Unknown tool" in _texto(r))


# ---------------------------------------------------------------- protocolo

@comprueba
async def p01_tools(cli, ctx):
    nombres = await cli.tools()
    esperado = {"cl_buscar", "cl_articulo", "cl_versiones", "cl_citar",
                "cl_notaria", "cl_documento", "cl_cobertura"}
    return set(nombres) == esperado, f"{len(nombres)} tools: {sorted(nombres)}"


@comprueba
async def p02_tool_inexistente(cli, ctx):
    ok, r = await crudo(cli, "cl_no_existe", {})
    return (not ok) or _es_error(r), f"{type(r).__name__}: {_texto(r)[:80] or str(r)[:80]}"


@comprueba
async def p03_falta_argumento(cli, ctx):
    ok, r = await crudo(cli, "cl_buscar", {})
    return ok and _es_error(r), f"rechazo controlado: {_texto(r)[:80]}"


@comprueba
async def p04_concurrencia_correlacion(cli, ctx):
    """40 llamadas simultaneas: cada respuesta debe traer SU consulta."""
    consultas = [f"voto n{i}" for i in range(40)]
    res = await asyncio.gather(*[crudo(cli, "cl_buscar", {"q": q}) for q in consultas])
    malas = [i for i, (ok, r) in enumerate(res)
             if not ok or _cuerpo(r).get("consulta") != consultas[i]]
    return not malas, f"{len(malas)} respuestas cruzadas de 40"


@comprueba
async def p05_arranque(cli, ctx):
    tiempos = []
    for _ in range(3):
        t0 = time.perf_counter()
        async with Cliente(*ctx["cmd"]) as c:
            await c.llamar("cl_cobertura", {})
        tiempos.append(time.perf_counter() - t0)
    return max(tiempos) < 6.0, "arranques: " + ", ".join(f"{t:.2f}s" for t in tiempos)


# ---------------------------------------------------------------- busqueda

HOSTILES = ['NEAR(', '"', '*', '-', 'AND', '(', ':', '^', 'a OR b', '""', '%%', "' OR 1=1--",
            'neumatico*', '{nombre}', '\\', '..', '<script>']


@comprueba
async def b01_fts_hostil(cli, ctx):
    fallos = []
    for q in HOSTILES:
        ok, r = await crudo(cli, "cl_buscar", {"q": q})
        if not ok or _es_error(r):
            fallos.append(q)
    return not fallos, f"{len(fallos)}/{len(HOSTILES)} queries rompen: {fallos}"


@comprueba
async def b02_vacia(cli, ctx):
    malas = []
    for q in ["", "   ", "...", "¿?", "\t\n"]:
        ok, r = await crudo(cli, "cl_buscar", {"q": q})
        if not ok or _es_error(r) or _cuerpo(r).get("total") != 0:
            malas.append(q)
    return not malas, f"{len(malas)} vacias mal tratadas"


@comprueba
async def b03_query_gigante(cli, ctx):
    q = ("contrato " * 6000).strip()
    t0 = time.perf_counter()
    ok, r = await crudo(cli, "cl_buscar", {"q": q})
    ms = (time.perf_counter() - t0) * 1000
    return ok and not _es_error(r) and ms < 5000, f"{len(q)} chars en {ms:.0f} ms"


@comprueba
async def b04_unicode(cli, ctx):
    casos = ["ñuñoa", "N°", "ARTÍCULO", "“contrato”", "año", "Peña"]
    fallos = []
    for q in casos:
        ok, r = await crudo(cli, "cl_buscar", {"q": q})
        if not ok or _es_error(r):
            fallos.append(q)
    return not fallos, f"{len(fallos)} fallos unicode: {fallos}"


@comprueba
async def b05_determinismo(cli, ctx):
    a = _cuerpo(await cli.session.call_tool("cl_buscar", {"q": "contrato", "limite": 20}))
    b = _cuerpo(await cli.session.call_tool("cl_buscar", {"q": "contrato", "limite": 20}))
    ca = [(x["id_norma"], x["nombre"]) for x in a.get("resultados", [])]
    cb = [(x["id_norma"], x["nombre"]) for x in b.get("resultados", [])]
    return ca == cb and len(ca) > 0, f"{len(ca)} resultados, iguales={ca == cb}"


@comprueba
async def b06_limite(cli, ctx):
    fallos = []
    for valor, tope in [(0, 1), (-5, 1), (1000, 50), ("7", 7), ("muchos", None)]:
        ok, r = await crudo(cli, "cl_buscar", {"q": "contrato", "limite": valor})
        if tope is None:  # un tipo invalido puede rechazarse: lo que no vale es el silencio
            if ok and not _es_error(r):
                fallos.append((valor, "aceptado sin error"))
            continue
        if not ok or _es_error(r):
            fallos.append((valor, "error"))
            continue
        n = len(_cuerpo(r).get("resultados", []))
        if n > tope:
            fallos.append((valor, n))
    return not fallos, f"fallos: {fallos}"


@comprueba
async def b07_campos(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_buscar", {"q": "contrato", "limite": 20}))
    res = r.get("resultados", [])
    mal = [x for x in res if not x.get("id_norma") or not x.get("fragmento")]
    return bool(res) and not mal, f"{len(res)} resultados, {len(mal)} incompletos"


# ---------------------------------------------------------------- articulos

@comprueba
async def a01_articulo(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_articulo", {"id_norma": 6369, "articulo": "14"}))
    return (r.get("idNorma") == 6369 and "i=6369" in (r.get("fuente") or "")
            and (r.get("texto") or "").startswith("Artículo 14")
            and "aviso" in r), f"cita={r.get('cita')}"


@comprueba
async def a02_bis(cli, ctx):
    a = _cuerpo(await cli.session.call_tool("cl_articulo", {"id_norma": 6369, "articulo": "3 bis"}))
    b = _cuerpo(await cli.session.call_tool("cl_articulo", {"id_norma": 6369, "articulo": "3 BIS"}))
    c = _cuerpo(await cli.session.call_tool("cl_articulo", {"id_norma": 6369, "articulo": "art. 3 bis"}))
    return (a.get("cita") == b.get("cita") == c.get("cita") and "error" not in a,
            f"{a.get('cita')} | {b.get('cita')} | {c.get('cita')}")


@comprueba
async def a03_inexistente(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_articulo", {"id_norma": 6369, "articulo": "99999"}))
    e = r.get("error") or ""
    return "[not_found]" in e and "DL 825" in e and "i=6369" in e, e[:140]


@comprueba
async def a04_norma_fuera(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_articulo", {"id_norma": 999999, "articulo": "1"}))
    return "[not_found]" in (r.get("error") or ""), (r.get("error") or "")[:140]


@comprueba
async def a05_fecha_invalida(cli, ctx):
    malas = []
    for f in ["2020-13-45", "ayer", "2020-02-30", "", "0000-00-00"]:
        r = _cuerpo(await cli.session.call_tool(
            "cl_articulo", {"id_norma": 6369, "articulo": "14", "vigente_al": f}))
        e = r.get("error") or ""
        if f and "[invalid_arg]" not in e:
            malas.append((f, e[:60] or "sin error"))
    return not malas, f"{malas}"


@comprueba
async def a06_fecha_futura(cli, ctx):
    r = _cuerpo(await cli.session.call_tool(
        "cl_articulo", {"id_norma": 6369, "articulo": "14", "vigente_al": "2222-02-02"}))
    e = r.get("error") or ""
    return "[invalid_arg]" in e, e[:140]


@comprueba
async def a07_fecha_historica(cli, ctx):
    r = _cuerpo(await cli.session.call_tool(
        "cl_articulo", {"id_norma": 6369, "articulo": "14", "vigente_al": "2015-01-01"}))
    return (r.get("vigente_al") == "2015-01-01" and r.get("confianza") in ("alta", "media")
            and "aviso" in r), f"confianza={r.get('confianza')}"


# ---------------------------------------------------------------- versiones

@comprueba
async def a08_formas_de_nombrar(cli, ctx):
    """El usuario escribe 'art. 1545' o 'ARTÍCULO 1545': las cuatro deben dar la misma cita."""
    citas_ = []
    for forma in ["1545", "art. 1545", "Artículo 1545", "ARTÍCULO 1545"]:
        r = _cuerpo(await cli.session.call_tool("cl_articulo", {"id_norma": 172986, "articulo": forma}))
        citas_.append(r.get("cita"))
    return len(set(citas_)) == 1 and bool(citas_[0]), f"{len(set(citas_))} variantes: {citas_[0]}"



@comprueba
async def v01_versiones(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_versiones", {"id_norma": 6369}))
    v = r.get("versiones", [])
    fechas = [x["vigente_desde"] for x in v]
    return len(v) >= 80 and fechas == sorted(fechas, reverse=True), f"{len(v)} versiones"


@comprueba
async def v02_sin_historial(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_versiones", {"id_norma": 999999}))
    return "[not_found]" in (r.get("error") or ""), (r.get("error") or "")[:100]


# ---------------------------------------------------------------- citar

@comprueba
async def c01_lote_mixto(cli, ctx):
    refs = ["6369/14", "6369/99999", "999999/1", "artículo 1545", "bogus", "172986/1545",
            "1984/1", "127917/1", "61438/1", "242302/19"]
    r = _cuerpo(await cli.session.call_tool("cl_citar", {"referencias": refs}))
    total = len(r.get("ok", [])) + len(r.get("faltantes", [])) + len(r.get("sin_fuente_verificable", []))
    return total == len(refs) and len(r.get("ok", [])) >= 4, f"{total}/{len(refs)} clasificadas"


@comprueba
async def c02_string(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_citar", {"referencias": "6369/14"}))
    total = len(r.get("ok", [])) + len(r.get("faltantes", [])) + len(r.get("sin_fuente_verificable", []))
    return total == 1, f"string tratado como {total} referencias"


@comprueba
async def c03_lote_grande(cli, ctx):
    refs = ["6369/14"] * 100 + ["999999/1"] * 100
    t0 = time.perf_counter()
    r = _cuerpo(await cli.session.call_tool("cl_citar", {"referencias": refs}))
    ms = (time.perf_counter() - t0) * 1000
    total = len(r.get("ok", [])) + len(r.get("faltantes", [])) + len(r.get("sin_fuente_verificable", []))
    return total == 200 and ms < 5000, f"{total}/200 en {ms:.0f} ms"


# ---------------------------------------------------------------- notaria

@comprueba
async def n01_mayusculas(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_notaria", {"q": "COMPRAVENTA"}))
    return len(r.get("fichas", [])) >= 1, f"{len(r.get('fichas', []))} fichas"


@comprueba
async def n02_inexistente(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_notaria", {"ficha": "no-existe"}))
    return "[not_found]" in (r.get("error") or ""), (r.get("error") or "")[:100]


@comprueba
async def n03_todas(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_notaria", {}))
    return len(r.get("fichas", [])) == 27, f"{len(r.get('fichas', []))} fichas"


# ---------------------------------------------------------------- documentos

DATOS = {"OTORGANTE": "Ana Pérez", "RUT": "9.876.543-2", "DOMICILIO": "Av. Siempre Viva 123",
         "MANDATARIO": "Pedro Soto", "RUT_MANDATARIO": "11.222.333-4",
         "FACULTADES": "vender el automóvil patente ABCD12", "CIUDAD": "Santiago",
         "FECHA": "2026-11-06"}


@comprueba
async def d01_poder(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_documento", {"plantilla": "poder-especial", "datos": DATOS}))
    odt, pdf = Path(r["archivos"]["odt"]), Path(r["archivos"]["pdf"])
    base = r.get("base_legal") or []
    return (odt.exists() and pdf.exists() and pdf.stat().st_size > 1000
            and "2116" in _txt(base)), f"pdf={pdf.stat().st_size if pdf.exists() else 0}B base={base[0].get('cita') if base else None}"


@comprueba
async def d02_compraventa_base(cli, ctx):
    datos = {"VENDEDOR": "María Contreras", "RUT_VENDEDOR": "12.345.678-9",
             "COMPRADOR": "Jorge Fuentes", "RUT_COMPRADOR": "15.678.901-2",
             "BIEN": "departamento rol 1234-56", "PRECIO": "$185.000.000",
             "FORMA_PAGO": "al contado", "CIUDAD": "Santiago", "FECHA": "2026-11-06"}
    r = _cuerpo(await cli.session.call_tool(
        "cl_documento", {"plantilla": "compraventa", "datos": datos, "formato": "odt"}))
    base = _txt(r.get("base_legal"))
    return "2116" not in base and ("1793" in base or "1801" in base), f"base={base[:120]}"


@comprueba
async def d03_faltan_campos(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_documento", {"plantilla": "poder-especial", "datos": {"RUT": "1-9"}}))
    return "[invalid_arg]" in _txt(r), _txt(r)[:140]


@comprueba
async def d04_plantilla(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_documento", {"plantilla": "../../etc/passwd", "datos": DATOS}))
    return "[not_found]" in _txt(r), _txt(r)[:140]


@comprueba
async def d05_md(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_documento", {"plantilla": "poder-especial", "datos": DATOS, "formato": "md"}))
    md = Path(r["archivos"]["md"]).read_text(encoding="utf-8")
    return "Ana Pérez" in md and "{OTORGANTE}" not in md, f"{len(md)} chars, sustituye={'Ana Pérez' in md}"


@comprueba
async def d06_concurrencia(cli, ctx):
    """Cuatro documentos a la vez: cada archivo devuelto debe llevar SU nombre."""
    nombres = [f"Otorgante Numero{chr(65 + i)}" for i in range(4)]
    tareas = [crudo(cli, "cl_documento", {"plantilla": "poder-especial",
                                          "datos": {**DATOS, "OTORGANTE": n},
                                          "formato": "odt"}) for n in nombres]
    res = await asyncio.gather(*tareas)
    malos = []
    for nombre, (ok, r) in zip(nombres, res):
        if not ok:
            malos.append((nombre, "error"))
            continue
        ruta = _cuerpo(r).get("archivos", {}).get("odt")
        if not ruta or not Path(ruta).exists():
            malos.append((nombre, "sin archivo"))
            continue
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("content.xml").decode("utf-8")
        if nombre not in xml:
            malos.append((nombre, "contenido de otro"))
    return not malos, f"{malos}"


@comprueba
async def d07_xml_escapado(cli, ctx):
    datos = {**DATOS, "OTORGANTE": 'Ana & "Peña" <hija>', "FACULTADES": "vender <todo> & algo"}
    r = _cuerpo(await cli.session.call_tool("cl_documento", {"plantilla": "poder-especial", "datos": datos, "formato": "odt"}))
    from lxml import etree
    with zipfile.ZipFile(r["archivos"]["odt"]) as z:
        etree.fromstring(z.read("content.xml"))
    return True, "XML valido con &, < y comillas"


@comprueba
async def d08_formato(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_documento", {"plantilla": "poder-especial", "datos": DATOS, "formato": "exe"}))
    return "[invalid_arg]" in _txt(r), _txt(r)[:120]


@comprueba
async def d09_docx(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_documento", {"plantilla": "poder-especial",
                                                             "datos": DATOS, "formato": "docx"}))
    docx = Path(r["archivos"]["docx"])
    with zipfile.ZipFile(docx) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return docx.stat().st_size > 5000 and "Ana Pérez" in xml, f"{docx.stat().st_size} B"


# ---------------------------------------------------------------- cobertura

@comprueba
async def k01_cobertura(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_cobertura", {}))
    c = r.get("cobertura", {})
    con = db.conectar(DB)
    real = db.cobertura(con)
    con.close()
    igual = all(c.get(k) == real[k] for k in ("normas", "articulos", "versiones"))
    return igual, f"{c} vs {real}"


@comprueba
async def k02_aviso(cli, ctx):
    r = _cuerpo(await cli.session.call_tool("cl_articulo", {"id_norma": 172986, "articulo": "1545"}))
    return "aviso" in r and "asesor" in r["aviso"], r.get("aviso", "")[:80]


# ---------------------------------------------------------------- carga

@comprueba
async def l01_secuencial(cli, ctx):
    llamadas = [("cl_buscar", {"q": "contrato"}), ("cl_articulo", {"id_norma": 6369, "articulo": "14"}),
                ("cl_versiones", {"id_norma": 1974}), ("cl_cobertura", {}),
                ("cl_notaria", {"q": "poder"})] * 20
    tiempos, errores = [], 0
    for nombre, args in llamadas:
        t0 = time.perf_counter()
        ok, r = await crudo(cli, nombre, args)
        tiempos.append((time.perf_counter() - t0) * 1000)
        if not ok or _es_error(r):
            errores += 1
    tiempos.sort()
    p50 = statistics.median(tiempos)
    p95 = tiempos[int(len(tiempos) * 0.95)]
    return errores == 0 and p95 < 2000, f"100 llamadas, p50={p50:.0f}ms p95={p95:.0f}ms errores={errores}"


@comprueba
async def l02_concurrente(cli, ctx):
    t0 = time.perf_counter()
    res = await asyncio.gather(*[crudo(cli, "cl_articulo", {"id_norma": 172986, "articulo": "1545"})
                                 for _ in range(40)])
    ms = (time.perf_counter() - t0) * 1000
    errores = sum(1 for ok, r in res if not ok or _es_error(r))
    return errores == 0 and ms < 15000, f"40 concurrentes en {ms:.0f}ms, errores={errores}"


# ---------------------------------------------------------------- motor

def _comando() -> tuple[str, tuple]:
    """El script del entorno donde corre la prueba, o el del PATH."""
    import os
    if os.environ.get("MCP_LEYES_CMD"):
        partes = os.environ["MCP_LEYES_CMD"].split()
        return partes[0], tuple(partes[1:])
    vecino = Path(sys.executable).parent / "mcp-leyes-chile"
    return (str(vecino) if vecino.exists() else "mcp-leyes-chile"), ()


async def correr(verbose: bool = False) -> dict:
    ctx = {"cmd": _comando()}
    resultados = []
    print(f"mcp-leyes-chile estres · {len(COMPROBACIONES)} comprobaciones", file=sys.stderr)
    async with Cliente(*ctx["cmd"]) as cli:
        for fn in COMPROBACIONES:
            t0 = time.perf_counter()
            try:
                ok, detalle = await fn(cli, ctx)
            except Exception as exc:  # noqa: BLE001
                ok, detalle = False, f"{type(exc).__name__}: {str(exc)[:160]}"
            ms = (time.perf_counter() - t0) * 1000
            resultados.append({"id": fn.__name__, "ok": bool(ok), "detalle": detalle, "ms": round(ms)})
            if verbose or not ok:
                print(f"{'OK  ' if ok else 'FALLA'} {fn.__name__:<28} {detalle} [{ms:.0f}ms]",
                      file=sys.stderr)
    fallos = [r for r in resultados if not r["ok"]]
    salida = {"fecha": dt.datetime.now().isoformat(timespec="seconds"),
              "comprobaciones": len(resultados), "fallos": len(fallos),
              "ok": not fallos, "resultados": resultados}
    return salida


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval.estres")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--salida", default="")
    a = p.parse_args(argv)
    r = asyncio.run(correr(a.verbose))
    destino = Path(a.salida) if a.salida else RAIZ / "eval" / f"estres-{dt.date.today()}.json"
    destino.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in r.items() if k != "resultados"}, ensure_ascii=False))
    for f in r["resultados"]:
        if not f["ok"]:
            print(f"  FALLA {f['id']}: {f['detalle']}")
    print(f"escrito: {destino}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
