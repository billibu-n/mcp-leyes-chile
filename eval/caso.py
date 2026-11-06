"""Caso real resuelto con el servidor: compraventa de un departamento en Providencia.

Llama por stdio a las 7 herramientas, toma el contrato que genera cl_documento y arma un
expediente .odt -> .pdf con antecedentes, minuta, base legal citada, tramite notarial y
trazabilidad de cada llamada. El PDF es el entregable; el .odt queda editable.

Uso:
    python -m eval.caso --salida /ruta/al/expediente
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

from mcp_leyes import documentos

from .cliente import Cliente

NS = {"text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}

DATOS = {
    "VENDEDOR": "María Soledad Contreras Rojas",
    "RUT_VENDEDOR": "12.345.678-9",
    "COMPRADOR": "Jorge Andrés Fuentes Silva",
    "RUT_COMPRADOR": "15.678.901-2",
    "BIEN": ("departamento N° 56 del piso 5 del edificio de Av. Providencia 1234, comuna de "
             "Providencia, Rol 1234-56, inscrito a fojas 1234 N° 5678 del Registro de Propiedad "
             "del Conservador de Bienes Raíces de Santiago, año 2010"),
    "PRECIO": "$185.000.000",
    "FORMA_PAGO": "al contado, contra entrega de la escritura definitiva",
    "CIUDAD": "Santiago",
    "FECHA": "6 de noviembre de 2026",
}

REFERENCIAS = ["172986/1793", "172986/1801", "172986/1810", "6369/14", "999999/1", "artículo 1545"]

CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.2">
 <office:automatic-styles>
  <style:style style:name="Portada" style:family="paragraph">
   <style:paragraph-properties fo:text-align="center" fo:margin-top="3cm" fo:margin-bottom="0.2cm"/>
   <style:text-properties fo:font-size="24pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Kicker" style:family="paragraph">
   <style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.1cm"/>
   <style:text-properties fo:font-size="9pt" fo:color="#6b6b6b" fo:letter-spacing="0.15cm"/>
  </style:style>
  <style:style style:name="Bajada" style:family="paragraph">
   <style:paragraph-properties fo:text-align="center" fo:margin-bottom="1.2cm"/>
   <style:text-properties fo:font-size="12pt" fo:color="#333333"/>
  </style:style>
  <style:style style:name="H1" style:family="paragraph">
   <style:paragraph-properties fo:margin-top="0.8cm" fo:margin-bottom="0.25cm" fo:keep-with-next="always"/>
   <style:text-properties fo:font-size="14pt" fo:font-weight="bold" fo:color="#1a3a5c"/>
  </style:style>
  <style:style style:name="H2" style:family="paragraph">
   <style:paragraph-properties fo:margin-top="0.45cm" fo:margin-bottom="0.15cm" fo:keep-with-next="always"/>
   <style:text-properties fo:font-size="11pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Cuerpo" style:family="paragraph">
   <style:paragraph-properties fo:text-align="justify" fo:margin-bottom="0.3cm"/>
   <style:text-properties fo:font-size="10.5pt"/>
  </style:style>
  <style:style style:name="Pequeno" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.25cm"/>
   <style:text-properties fo:font-size="8.5pt" fo:color="#555555"/>
  </style:style>
  <style:style style:name="Aviso" style:family="paragraph">
   <style:paragraph-properties fo:text-align="center" fo:margin-top="0.5cm" fo:margin-bottom="0.5cm"/>
   <style:text-properties fo:font-size="10pt" fo:font-weight="bold" fo:color="#a00000"/>
  </style:style>
  <style:style style:name="Tabla" style:family="table">
   <style:table-properties table:border-model="collapsing" fo:margin-bottom="0.4cm"/>
  </style:style>
  <style:style style:name="ColA" style:family="table-column">
   <style:table-column-properties style:column-width="4.2cm"/>
  </style:style>
  <style:style style:name="ColB" style:family="table-column">
   <style:table-column-properties style:column-width="11.6cm"/>
  </style:style>
  <style:style style:name="Celda" style:family="table-cell">
   <style:table-cell-properties fo:border="0.4pt solid #b8b8b8" fo:padding="0.12cm"
    fo:background-color="#f4f6f8"/>
   <style:paragraph-properties fo:margin-bottom="0cm"/>
   <style:text-properties fo:font-size="9pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="CeldaDato" style:family="table-cell">
   <style:table-cell-properties fo:border="0.4pt solid #b8b8b8" fo:padding="0.12cm"/>
   <style:paragraph-properties fo:margin-bottom="0cm"/>
   <style:text-properties fo:font-size="9pt"/>
  </style:style>
  <style:style style:name="CeldaTexto" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0cm"/>
   <style:text-properties fo:font-size="9pt"/>
  </style:style>
  <style:style style:name="CeldaRotulo" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0cm"/>
   <style:text-properties fo:font-size="9pt" fo:font-weight="bold"/>
  </style:style>
 </office:automatic-styles>
 <office:body><office:text>
{parrafos}
 </office:text></office:body>
</office:document-content>
"""

STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.2">
 <office:styles>
  <style:default-style style:family="paragraph">
   <style:paragraph-properties fo:orphans="2" fo:widows="2"/>
   <style:text-properties fo:font-family="Liberation Serif" fo:font-size="10.5pt"/>
  </style:default-style>
 </office:styles>
 <office:automatic-styles>
  <style:style style:name="A4" style:family="page-layout">
   <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm"
    fo:margin-top="2.2cm" fo:margin-bottom="2.2cm" fo:margin-left="2.4cm" fo:margin-right="2.4cm"/>
  </style:style>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="Standard" style:page-layout-name="A4"/>
 </office:master-styles>
</office:document-styles>
"""

MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
</manifest:manifest>
"""


# ---------------------------------------------------------------- piezas ODT

def p(estilo: str, texto: str) -> str:
    return f'  <text:p text:style-name="{estilo}">{escape(texto)}</text:p>'


def tabla(filas: list[tuple[str, str]]) -> str:
    out = ['  <table:table table:name="T" table:style-name="Tabla">',
           '   <table:table-column table:style-name="ColA"/>',
           '   <table:table-column table:style-name="ColB"/>']
    for rotulo, dato in filas:
        out.append("   <table:table-row>")
        out.append('    <table:table-cell table:style-name="Celda" office:value-type="string">'
                   f'<text:p text:style-name="CeldaRotulo">{escape(rotulo)}</text:p></table:table-cell>')
        out.append('    <table:table-cell table:style-name="CeldaDato" office:value-type="string">'
                   f'<text:p text:style-name="CeldaTexto">{escape(dato)}</text:p></table:table-cell>')
        out.append("   </table:table-row>")
    out.append("  </table:table>")
    return "\n".join(out)


def escribir_odt(parrafos: list[str], destino: Path) -> Path:
    contenido = CONTENT.format(parrafos="\n".join(parrafos))
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", contenido, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("styles.xml", STYLES, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("META-INF/manifest.xml", MANIFEST, compress_type=zipfile.ZIP_DEFLATED)
    return destino


def parrafos_de_odt(ruta: Path) -> list[str]:
    """Texto del contrato generado por cl_documento, en orden."""
    with zipfile.ZipFile(ruta) as z:
        raiz = etree.fromstring(z.read("content.xml"))
    salida = []
    for nodo in raiz.iter("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p",
                          "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}h"):
        texto = "".join(nodo.itertext()).strip()
        if texto:
            salida.append(texto)
    return salida


# ---------------------------------------------------------------- llamadas

async def recoger(cli, traza: list) -> dict:
    datos: dict = {}

    async def llamar(nombre: str, args: dict) -> dict:
        t0 = time.perf_counter()
        res = await cli.session.call_tool(nombre, args)
        ms = round((time.perf_counter() - t0) * 1000)
        texto = res.content[0].text if getattr(res, "content", None) else "{}"
        try:
            cuerpo = json.loads(texto)
        except json.JSONDecodeError:
            cuerpo = {"_crudo": texto}
        traza.append({"tool": nombre, "args": args, "ms": ms,
                      "error": bool(getattr(res, "is_error", False)), "resumen": _resumen(cuerpo)})
        return cuerpo

    datos["cobertura"] = await llamar("cl_cobertura", {})
    datos["ventas"] = await llamar("cl_versiones", {"id_norma": 172986})
    datos["citas"] = []
    for art in ("1793", "1801", "1810"):
        datos["citas"].append(await llamar("cl_articulo", {"id_norma": 172986, "articulo": art}))
    datos["lote"] = await llamar("cl_citar", {"referencias": REFERENCIAS})
    datos["ficha"] = await llamar("cl_notaria", {"ficha": "compraventa"})
    datos["contrato"] = await llamar("cl_documento",
                                     {"plantilla": "compraventa", "datos": DATOS, "formato": "pdf"})
    return datos


def _resumen(cuerpo: dict) -> str:
    if "error" in cuerpo:
        return cuerpo["error"][:70]
    if "total" in cuerpo:
        return f"{cuerpo['total']} resultados"
    if "cita" in cuerpo:
        return cuerpo["cita"]
    if "fichas" in cuerpo:
        n = len(cuerpo["fichas"])
        return f"{n} ficha" + ("s" if n != 1 else "")
    if "archivos" in cuerpo:
        return ", ".join(cuerpo["archivos"])
    if "ok" in cuerpo and "faltantes" in cuerpo:
        return f"{len(cuerpo['ok'])} ok, {len(cuerpo['faltantes'])} faltan"
    if "cobertura" in cuerpo:
        c = cuerpo["cobertura"]
        return f"{c['normas']} normas, {c['articulos']} articulos"
    if "versiones" in cuerpo:
        return f"{len(cuerpo['versiones'])} versiones"
    return ""


# ---------------------------------------------------------------- expediente

def expediente(datos: dict, salida: Path) -> Path:
    parrafos: list[str] = []
    cobertura = datos["cobertura"].get("cobertura", {})

    parrafos += [
        p("Kicker", "EXPEDIENTE DE CASO"),
        p("Portada", "Compraventa de departamento"),
        p("Bajada", "Providencia, Santiago — 6 de noviembre de 2026"),
        p("Cuerpo", "Documento generado por mcp-leyes-chile 0.2.2 por el protocolo MCP: cada "
                    "cita se recuperó del corpus local y se verificó contra LeyChile (BCN)."),
        p("Aviso", "BORRADOR — NO VÁLIDO PARA PRESENTACIÓN"),
        p("Pequeno", "Este expediente demuestra el servidor con un caso completo. No es "
                     "asesoría legal: el acto lo califica el notario y lo revisa un abogado."),
    ]

    parrafos += [p("H1", "1. El caso")]
    parrafos += [tabla([
        ("Vendedor", f"{DATOS['VENDEDOR']} — RUT {DATOS['RUT_VENDEDOR']}"),
        ("Comprador", f"{DATOS['COMPRADOR']} — RUT {DATOS['RUT_COMPRADOR']}"),
        ("Bien", DATOS["BIEN"]),
        ("Precio", DATOS["PRECIO"]),
        ("Forma de pago", DATOS["FORMA_PAGO"]),
        ("Otorgamiento", f"{DATOS['CIUDAD']}, {DATOS['FECHA']}"),
        ("Corpus consultado", f"{cobertura.get('normas', '?')} normas, "
                              f"{cobertura.get('articulos', '?')} artículos, "
                              f"{cobertura.get('versiones', '?')} versiones"),
    ])]

    contrato = datos["contrato"]
    if contrato.get("archivos", {}).get("odt"):
        parrafos += [p("H1", "2. Minuta de compraventa")]
        parrafos += [p("Pequeno", "Generada por cl_documento con la plantilla «compraventa». "
                                  "El .odt editable acompaña a este expediente.")]
        for linea in parrafos_de_odt(Path(contrato["archivos"]["odt"])):
            if linea.startswith("BORRADOR"):
                continue
            estilo = "H2" if linea.isupper() and len(linea) < 60 else "Cuerpo"
            parrafos.append(p(estilo, linea))

    parrafos += [p("H1", "3. Base legal citada")]
    parrafos += [p("Pequeno", "Texto recuperado del corpus; la vigencia es la que declara "
                              "LeyChile para esa versión. Fuente enlazada en cada cita.")]
    for cita in datos["citas"]:
        if "error" in cita:
            parrafos.append(p("Cuerpo", f"[sin_fuente] {cita['error']}"))
            continue
        parrafos.append(p("H2", cita["cita"]))
        texto = " ".join((cita.get("texto") or "").split())
        parrafos.append(p("Cuerpo", texto[:900]))
        parrafos.append(p("Pequeno", f"Fuente: {cita['fuente']} · consultado 2026-11-06"))

    lote = datos["lote"]
    if lote.get("ok") or lote.get("faltantes"):
        parrafos += [p("H2", "Verificación del lote (cl_citar)")]
        for item in lote.get("ok", []):
            parrafos.append(p("Pequeno", f"OK — {item.get('cita', item.get('referencia'))}"))
        for item in lote.get("faltantes", []):
            parrafos.append(p("Pequeno", f"FALTA — {item['referencia']}: {item['motivo']}"))
        for item in lote.get("sin_fuente_verificable", []):
            parrafos.append(p("Pequeno", f"SIN FUENTE — {item['referencia']}: {item['motivo']}"))

    ficha = (datos["ficha"].get("fichas") or [{}])[0]
    parrafos += [p("H1", "4. Trámite notarial")]
    parrafos += [p("H2", ficha.get("tramite", "Compraventa de inmueble"))]
    parrafos += [p("Cuerpo", ficha.get("para_que", ""))]
    for campo, rotulo in (("requisitos", "Requisitos"), ("documentos", "Documentos")):
        for item in ficha.get(campo) or []:
            estado = item.get("estado", "sin_fuente")
            marca = "verificado" if estado == "verificado" else "sin fuente"
            parrafos.append(p("Pequeno", f"{rotulo}: {item['texto']} [{marca}]"))
    arancel = ficha.get("arancel") or {}
    if arancel:
        parrafos.append(p("H2", "Arancel"))
        parrafos.append(p("Cuerpo", arancel.get("texto_nominal", "")))
        parrafos.append(p("Pequeno", arancel.get("advertencia", "")))
    competencia = ficha.get("competencia") or {}
    if competencia.get("estado") == "sin_fuente":
        parrafos.append(p("Pequeno", "Competencia territorial: sin fuente estructurada; "
                                     "se declara hueco."))

    parrafos += [p("H1", "5. Trazabilidad")]
    filas = [(f"{i + 1}. {t['tool']}", f"{json.dumps(t['args'], ensure_ascii=False)[:70]} · "
                                      f"{t['ms']} ms · {t['resumen'][:70]}")
             for i, t in enumerate(datos["traza"])]
    parrafos.append(tabla(filas))

    parrafos += [p("H1", "6. Límites declarados")]
    for linea in datos["cobertura"].get("no_cubre", []):
        parrafos.append(p("Cuerpo", f"— {linea}"))
    parrafos.append(p("Pequeno", datos["cobertura"].get("fuente", "")))
    parrafos.append(p("Aviso", "BORRADOR — NO VÁLIDO PARA PRESENTACIÓN"))

    odt = escribir_odt(parrafos, salida / "expediente.odt")
    pdf = documentos._soffice(odt, "pdf", salida)
    final = salida / "caso-compraventa-2026-11-06.pdf"
    if final != pdf:
        pdf.replace(final)
    return final


async def correr(salida: Path) -> dict:
    salida.mkdir(parents=True, exist_ok=True)
    traza: list = []
    comando = documentos_comando()
    async with Cliente(*comando) as cli:
        datos = await recoger(cli, traza)
    datos["traza"] = traza
    pdf = expediente(datos, salida)
    contrato_pdf = datos["contrato"].get("archivos", {}).get("pdf")
    if contrato_pdf and Path(contrato_pdf).exists():
        (salida / "minuta.pdf").write_bytes(Path(contrato_pdf).read_bytes())
    (salida / "traza.json").write_text(json.dumps(traza, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return {"pdf": str(pdf), "bytes": pdf.stat().st_size, "llamadas": len(traza),
            "citas": len(datos["citas"]), "salida": str(salida)}


def documentos_comando() -> tuple[str, tuple]:
    import os
    import sys
    if os.environ.get("MCP_LEYES_CMD"):
        partes = os.environ["MCP_LEYES_CMD"].split()
        return partes[0], tuple(partes[1:])
    vecino = Path(sys.executable).parent / "mcp-leyes-chile"
    return (str(vecino) if vecino.exists() else "mcp-leyes-chile"), ()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval.caso")
    p.add_argument("--salida", default="salidas/caso-compraventa")
    a = p.parse_args(argv)
    r = asyncio.run(correr(Path(a.salida)))
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["bytes"] > 20_000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
