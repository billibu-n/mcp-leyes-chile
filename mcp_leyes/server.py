"""Servidor MCP: 7 herramientas, cita obligatoria, cobertura declarada."""
from __future__ import annotations

import os
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from . import bcn, citas, db, documentos, notaria

RAIZ = Path(__file__).resolve().parent.parent
DB = os.environ.get("MCP_LEYES_DB", str(RAIZ / "data" / "corpus.db"))

INSTRUCCIONES = """Servidor de leyes chilenas y labor notarial.
Orden de uso: cl_buscar -> cl_articulo -> cl_citar. Nunca cites sin llamar a cl_articulo.
Si una herramienta devuelve [sin_fuente], [not_found] o [upstream_error], dilo tal cual.
Toda respuesta con contenido juridico debe conservar el campo 'aviso'.
La cobertura real se consulta con cl_cobertura; no la supongas."""

mcp = MCPServer(
    name="mcp-leyes-chile",
    version="0.2.0",
    instructions=INSTRUCCIONES,
    description="Leyes chilenas con cita verificable, fichas notariales y documentos .odt/.pdf",
)


def _con():
    return db.conectar(DB)


def _error(codigo: str, detalle: str) -> dict:
    return {"error": f"[{codigo}] {detalle}"}


@mcp.tool()
def cl_buscar(q: str, limite: int = 10, solo_vigentes: bool = True) -> dict:
    """Busca articulos por texto. Devuelve idNorma, norma, articulo y fragmento."""
    con = _con()
    filas = db.buscar(con, q, max(1, min(limite, 50)), solo_vigentes)
    n = db.norma(con, filas[0]["id_norma"]) if filas else None
    return {"consulta": q, "total": len(filas), "resultados": filas,
            "norma_ejemplo": n["titulo"] if n else None}


@mcp.tool()
def cl_articulo(id_norma: int, articulo: str, vigente_al: str = "") -> dict:
    """Texto literal + objeto de cita. Sin fuente no devuelve texto."""
    con = _con()
    meta = db.norma(con, id_norma)
    if not meta:
        return _error("not_found", f"norma {id_norma} no esta en el indice; corre la ingesta")
    meta["descargado"] = meta.get("descargado") or ""
    if vigente_al:
        try:
            texto = bcn.texto_version(id_norma, vigente_al)
        except bcn.BCNError as exc:
            return _error("upstream_error", str(exc))
        hallado = bcn.articulo_de_texto(texto, articulo)
        if not hallado:
            return _error("not_found", f"el articulo {articulo} no aparece en la version de {vigente_al}")
        actual = db.traer_articulo(con, id_norma, articulo)
        sin_cambios = bool(actual) and actual[0]["texto"][:200] == hallado["texto"][:200]
        return {"idNorma": id_norma, "articulo": articulo, "texto": hallado["texto"],
                "vigente_al": vigente_al, "metodo": "recorte por cabecera sobre texto historico",
                "confianza": hallado["confianza"], "sin_cambios": sin_cambios,
                "notas_recortadas": hallado.get("notas_recortadas", False),
                "fuente": f"https://www.leychile.cl/N?i={id_norma}&f={vigente_al}",
                "aviso": citas.AVISO, "hueco": hallado["hueco"]}
    partes = db.traer_articulo(con, id_norma, articulo)
    if not partes:
        return _error("not_found", f"articulo {articulo} no existe en la norma {id_norma}")
    cita = citas.construir(meta, partes[0])
    if len(partes) > 1:
        cita["coincidencias"] = len(partes)
        cita["hueco"] = (cita.get("hueco") or "") + " varios articulos comparten el numero; se devuelve el primero"
    return cita


@mcp.tool()
def cl_versiones(id_norma: int) -> dict:
    """Historial de versiones con rango de vigencia y advertencia de centinela."""
    con = _con()
    filas = db.versiones_de(con, id_norma)
    if not filas:
        return _error("not_found", f"sin historial para {id_norma}; corre la ingesta")
    return {"idNorma": id_norma, "versiones": filas,
            "actual": next((f for f in filas if f["tipo_version"] == "Última Versión"), None),
            "aviso_centinela": "2222-02-02 significa vigencia diferida por evento, no una fecha"}


@mcp.tool()
def cl_citar(referencias: list[str]) -> dict:
    """Verifica un lote de referencias. Devuelve ok, faltantes y sin_fuente_verificable."""
    con = _con()
    ok, faltan, sin_fuente = [], [], []
    for ref in referencias:
        idn, art = _parsear_ref(ref)
        if not idn:
            sin_fuente.append({"referencia": ref, "motivo": "no se pudo identificar la norma"})
            continue
        meta = db.norma(con, idn)
        if not meta:
            faltan.append({"referencia": ref, "motivo": f"norma {idn} fuera del indice"})
            continue
        partes = db.traer_articulo(con, idn, art) if art else []
        if art and not partes:
            faltan.append({"referencia": ref, "motivo": "articulo inexistente"})
            continue
        ok.append(citas.construir(meta, partes[0]) if partes else
                  {"idNorma": idn, "norma": citas.nombre_norma(meta), "cita": citas.nombre_norma(meta)})
    return {"ok": ok, "faltantes": faltan, "sin_fuente_verificable": sin_fuente}


def _parsear_ref(ref: str) -> tuple[int | None, str]:
    m = re.match(r"\s*(\d{3,7})\s*/\s*(\w+)", ref)
    if m:
        return int(m.group(1)), m.group(2)
    m = re.search(r"art(?:ículo)?\.?\s*([\w]+)", ref, re.I)
    art = m.group(1) if m else ""
    return None, art


@mcp.tool()
def cl_notaria(ficha: str = "", q: str = "") -> dict:
    """Ficha de tramite notarial con fuente y estado por campo. No calcula precios."""
    resultados = notaria.buscar(q=q, ficha=ficha)
    if not resultados:
        return _error("not_found", "sin ficha para esa consulta")
    return {"fichas": resultados,
            "aviso": "Los montos son nominales y pueden estar desactualizados. No es asesoría legal."}


@mcp.tool()
def cl_documento(plantilla: str, datos: dict, formato: str = "odt") -> dict:
    """Genera .odt (prioritario) y deriva .pdf/.docx. Marca de borrador obligatoria."""
    formatos = {"odt": ("odt",), "pdf": ("odt", "pdf"), "docx": ("odt", "docx"),
                "md": ("odt", "md")}.get(formato, ("odt", "pdf"))
    try:
        return documentos.generar(plantilla, datos, formatos)
    except documentos.DocumentoError as exc:
        return {"error": str(exc)}


@mcp.tool()
def cl_cobertura() -> dict:
    """Que cubre el servidor, hasta cuando, y que NO cubre."""
    con = _con()
    c = db.cobertura(con)
    huecos = []
    for f in notaria.cargar().values():
        for campo in ("requisitos", "documentos"):
            for item in f.get(campo) or []:
                if item.get("estado") == "sin_fuente":
                    huecos.append(f"{f['id']}.{campo}: {item['texto']}")
    return {"cobertura": c, "huecos": huecos[:20],
            "no_cubre": ["jurisprudencia", "tribunales", "SII mas alla de las normas",
                         "competencia territorial notarial estructurada",
                         "precios actuales de notaria", "firma ni presentacion de documentos"],
            "fuente": "LeyChile (BCN)", "verificado": c["ultima_ingesta"] or ""}
