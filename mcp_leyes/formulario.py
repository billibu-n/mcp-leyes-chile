"""Formulario HTML local: pregunta los campos y devuelve .odt + .pdf."""
from __future__ import annotations

import html
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from . import documentos

PLANTILLA = "poder-especial"


def _pagina(plantilla: dict) -> str:
    campos = "\n".join(
        f'<label>{html.escape(c["etiqueta"])}<br>'
        f'<input name="{c["nombre"]}" {"required" if c.get("requerido") else ""} '
        f'value=""></label><br><br>'
        for c in plantilla["campos"])
    return f"""<!doctype html><html lang="es"><meta charset="utf-8">
<title>{html.escape(plantilla["titulo"])}</title>
<h1>{html.escape(plantilla["titulo"])}</h1>
<p><strong>Borrador.</strong> No es asesoría legal ni documento válido para presentar.</p>
<form method="post" action="/generar">{campos}<button>Generar .odt y PDF</button></form>"""


class Handler(BaseHTTPRequestHandler):
    plantilla_id = PLANTILLA

    def _enviar(self, codigo: int, cuerpo: bytes, tipo="text/html; charset=utf-8"):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/salida/"):
            nombre = os.path.basename(self.path)
            ruta = documentos.SALIDAS / nombre
            if ruta.exists():
                tipo = "application/pdf" if nombre.endswith(".pdf") else "application/vnd.oasis.opendocument.text"
                return self._enviar(200, ruta.read_bytes(), tipo)
            return self._enviar(404, b"no existe")
        p = documentos.plantillas()[self.plantilla_id]
        return self._enviar(200, _pagina(p).encode("utf-8"))

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(n).decode("utf-8", "ignore")
        datos = {k: re.sub(r"[<>]", "", v[0]) for k, v in parse_qs(crudo).items()}
        try:
            r = documentos.generar(self.plantilla_id, datos, ("odt", "pdf"))
        except documentos.DocumentoError as exc:
            return self._enviar(400, f"<p>{html.escape(str(exc))}</p>".encode())
        enlaces = " · ".join(
            f'<a href="/salida/{os.path.basename(v)}">{k.upper()}</a>' for k, v in r["archivos"].items())
        self._enviar(200, f"<p>Listo: {enlaces}</p>".encode())


def servir(puerto: int = 8801, plantilla: str = PLANTILLA) -> None:
    Handler.plantilla_id = plantilla
    print(f"http://127.0.0.1:{puerto}/  (plantilla {plantilla})")
    ThreadingHTTPServer(("127.0.0.1", puerto), Handler).serve_forever()
