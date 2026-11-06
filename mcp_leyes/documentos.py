"""Documentos: .odt es el formato editable prioritario; .pdf y .docx derivan de el.

No usa odfpy: un .odt es un ZIP con content.xml, styles.xml y manifest. La
sustitucion de {{campos}} se hace sobre el texto, y LibreOffice convierte.
Una sola conversion a la vez: el perfil de LibreOffice se bloquea (medido).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

PAQUETE = Path(__file__).resolve().parent
PLANTILLAS = PAQUETE / "plantillas"
# Un paquete instalado vive en site-packages (solo lectura): las salidas van al home.
CASA = Path(os.environ.get("MCP_LEYES_HOME") or Path.home() / ".mcp-leyes-chile")
SALIDAS = Path(os.environ.get("MCP_LEYES_SALIDAS") or CASA / "salidas")
PERFIL_LO = Path(tempfile.gettempdir()) / "mcp-leyes-lo-profile"
_candado = threading.Lock()

CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.2">
 <office:automatic-styles>
  <style:style style:name="Titulo" style:family="paragraph">
   <style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.6cm"/>
   <style:text-properties fo:font-size="16pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Cuerpo" style:family="paragraph">
   <style:paragraph-properties fo:text-align="justify" fo:margin-bottom="0.35cm"/>
   <style:text-properties fo:font-size="11pt"/>
  </style:style>
  <style:style style:name="Aviso" style:family="paragraph">
   <style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.8cm"/>
   <style:text-properties fo:font-size="9pt" fo:font-weight="bold" fo:color="#a00000"/>
  </style:style>
  <style:style style:name="Firma" style:family="paragraph">
   <style:paragraph-properties fo:text-align="center" fo:margin-top="1.2cm"/>
   <style:text-properties fo:font-size="11pt"/>
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
   <style:text-properties fo:font-family="Liberation Serif" fo:font-size="11pt"/>
  </style:default-style>
 </office:styles>
 <office:automatic-styles>
  <style:page-layout style:name="A4">
   <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm"
    fo:margin-top="2.5cm" fo:margin-bottom="2.5cm" fo:margin-left="2.5cm" fo:margin-right="2.5cm"/>
  </style:page-layout>
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


class DocumentoError(RuntimeError):
    pass


def plantillas() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in PLANTILLAS.glob("*.json")}


def _validar(plantilla: dict, datos: dict) -> None:
    faltan = [c["nombre"] for c in plantilla["campos"]
              if c.get("requerido") and not str(datos.get(c["nombre"], "")).strip()]
    if faltan:
        raise DocumentoError(f"[invalid_arg] faltan campos: {', '.join(faltan)}")


def _rellenar(texto: str, datos: dict) -> str:
    """Sustituye {{CAMPO}}. Con .format(), '{{CAMPO}}' queda como '{CAMPO}': no sustituye."""
    for k, v in datos.items():
        texto = texto.replace("{{%s}}" % k, escape(str(v)))
    return texto


def _parrafos(plantilla: dict, datos: dict) -> str:
    salida = ['  <text:p text:style-name="Aviso">BORRADOR — NO VÁLIDO PARA PRESENTACIÓN</text:p>',
              f'  <text:h text:style-name="Titulo" text:outline-level="1">{escape(plantilla["titulo"])}</text:h>']
    for p in plantilla["parrafos"]:
        salida.append(f'  <text:p text:style-name="Cuerpo">{_rellenar(p, datos)}</text:p>')
    for linea in plantilla.get("cierre", []):
        if linea:
            salida.append(f'  <text:p text:style-name="Firma">{_rellenar(linea, datos)}</text:p>')
        else:
            salida.append('  <text:p text:style-name="Firma"/>')
    return "\n".join(salida)


def crear_odt(plantilla: dict, datos: dict, destino: Path) -> Path:
    _validar(plantilla, datos)
    contenido = CONTENT.format(parrafos=_parrafos(plantilla, datos))
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", contenido, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("styles.xml", STYLES, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("META-INF/manifest.xml", MANIFEST, compress_type=zipfile.ZIP_DEFLATED)
    return destino


def _soffice(origen: Path, formato: str, outdir: Path) -> Path:
    if shutil.which("soffice") is None:
        raise DocumentoError("[upstream_error] falta LibreOffice (soffice)")
    with _candado:
        proc = subprocess.run(
            ["soffice", "--headless", f"-env:UserInstallation=file://{PERFIL_LO}",
             "--convert-to", formato, "--outdir", str(outdir), str(origen)],
            capture_output=True, timeout=180, text=True,
        )
    if proc.returncode != 0:
        raise DocumentoError(f"[upstream_error] LibreOffice fallo: {proc.stderr[-300:]}")
    salida = outdir / (origen.stem + "." + formato)
    if not salida.exists():
        raise DocumentoError(f"[upstream_error] no se genero {salida.name}")
    return salida


FORMATOS = {"odt", "pdf", "docx", "md"}


def generar(plantilla_id: str, datos: dict, formatos=("odt", "pdf")) -> dict:
    plantilla = plantillas().get(plantilla_id)
    if not plantilla:
        raise DocumentoError(f"[not_found] plantilla desconocida: {plantilla_id}")
    pedidos = tuple(formatos) or ("odt",)
    desconocidos = [f for f in pedidos if f not in FORMATOS]
    if desconocidos:
        raise DocumentoError(f"[invalid_arg] formato no soportado: {', '.join(desconocidos)}; "
                             f"usa {', '.join(sorted(FORMATOS))}")
    # Carpeta propia por llamada: dos documentos a la vez se pisaban el mismo .odt.
    SALIDAS.mkdir(parents=True, exist_ok=True)
    carpeta = SALIDAS / f"{plantilla_id}-{uuid.uuid4().hex[:8]}"
    carpeta.mkdir(parents=True, exist_ok=True)
    odt = crear_odt(plantilla, datos, carpeta / f"{plantilla_id}.odt")
    rutas = {"odt": str(odt)}
    if "pdf" in pedidos:
        rutas["pdf"] = str(_soffice(odt, "pdf", carpeta))
    if "docx" in pedidos:
        rutas["docx"] = str(_soffice(odt, "docx", carpeta))
    if "md" in pedidos:
        md = carpeta / f"{plantilla_id}.md"
        md.write_text("\n\n".join([plantilla["titulo"]] + [
            _rellenar(p, datos) for p in plantilla["parrafos"]]), encoding="utf-8")
        rutas["md"] = str(md)
    return {"plantilla": plantilla_id, "archivos": rutas,
            "aviso": "BORRADOR — NO VÁLIDO PARA PRESENTACIÓN"}
