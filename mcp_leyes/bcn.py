"""Acceso a LeyChile (BCN): XML articulado, versiones y texto historico.

Endpoints verificados el 2026-11-06:
  - obtxml?opt=7&idNorma=N      -> XML con articulado y fechaVersion por parte
  - Consulta/get_versiones      -> historial (vigenteDesde/vigenteHasta)
  - Navegar/get_norma_json      -> texto de una version concreta (idVersion)
El host servicios-leychile.bcn.cl responde 301 a nuevo.leychile.cl y 401 si el
User-Agent es el de curl por defecto: hay que fijar UA y seguir redirecciones.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

BASE = "https://nuevo.leychile.cl/servicios"
UA = "mcp-leyes-chile/0.1 (contacto: github)"
CENTINELA = "2222-02-02"
TIMEOUT = 45


class BCNError(RuntimeError):
    """Fallo de la fuente: se propaga como [upstream_error], nunca como texto."""


def _get(path: str, params: dict | None = None, intentos: int = 3) -> bytes:
    url = f"{BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 - se reintenta y se declara
            ultimo = exc
            time.sleep(1.0 * (i + 1))
    raise BCNError(f"sin respuesta de LeyChile: {ultimo}")


def xml_norma(id_norma: int) -> bytes:
    return _get("Consulta/obtxml", {"opt": 7, "idNorma": id_norma})


def versiones(id_norma: int) -> list[dict]:
    crudo = _get("Consulta/get_versiones", {"idNorma": id_norma, "formato": "json"})
    datos = json.loads(crudo.decode("utf-8", "ignore"))
    return (datos.get("Versiones") or {}).get("Version") or []


def texto_version(id_norma: int, fecha: str) -> str:
    """Texto aplanado de la version vigente al inicio 'fecha' (AAAA-MM-DD)."""
    crudo = _get("Navegar/get_norma_json",
                 {"idNorma": id_norma, "idVersion": fecha, "agrupa_partes": 1})
    return _aplanar(json.loads(crudo.decode("utf-8", "ignore")))


def _aplanar(obj, acc: list[str] | None = None) -> str:
    import html
    import re
    acc = [] if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("h", "t") and isinstance(v, str):
                acc.append(v)
            else:
                _aplanar(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _aplanar(item, acc)
    texto = html.unescape(re.sub(r"<[^>]+>", " ", " ".join(acc)))
    return re.sub(r"\s+", " ", texto).strip()


def norm(texto: str) -> str:
    """minusculas sin acentos, para comparar tipos de parte."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def es_centinela(fecha: str | None) -> bool:
    return bool(fecha) and str(fecha).startswith("2222")


def _ln(elem) -> str:
    from lxml import etree
    q = etree.QName(elem)
    return q.localname


def parsear(xml_bytes: bytes) -> dict:
    """Devuelve {meta, partes[]} en orden documental."""
    from lxml import etree
    try:
        raiz = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        raiz = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True, huge_tree=True))

    meta = {
        "id_norma": int(raiz.get("normaId") or 0),
        "fecha_version": raiz.get("fechaVersion"),
        "derogado": raiz.get("derogado") or "no derogado",
        "tipo": "", "numero": "", "titulo": "", "organismo": "",
        "fecha_promulgacion": "", "fecha_publicacion": "",
    }
    ident = raiz.find("{*}Identificador")
    if ident is not None:
        meta["fecha_promulgacion"] = ident.get("fechaPromulgacion", "")
        meta["fecha_publicacion"] = ident.get("fechaPublicacion", "")
        tipo = ident.find(".//{*}Tipo")
        numero = ident.find(".//{*}Numero")
        organismo = ident.find(".//{*}Organismo")
        meta["tipo"] = (tipo.text or "").strip() if tipo is not None else ""
        meta["numero"] = (numero.text or "").strip() if numero is not None else ""
        meta["organismo"] = (organismo.text or "").strip() if organismo is not None else ""
    for nodo in raiz.iter():
        if _ln(nodo) == "TituloNorma":
            meta["titulo"] = (nodo.text or "").strip()
            break

    partes = []
    orden = 0
    for elem in raiz.iter():
        if _ln(elem) != "EstructuraFuncional":
            continue
        orden += 1
        nombre = titulo = texto = ""
        for hijo in elem:
            n = _ln(hijo)
            if n == "Metadatos":
                for m in hijo:
                    if _ln(m) == "NombreParte":
                        nombre = (m.text or "").strip()
                    elif _ln(m) == "TituloParte":
                        titulo = (m.text or "").strip()
            elif n == "Texto":
                texto = (hijo.text or "").strip()
        partes.append({
            "orden": orden,
            "id_parte": elem.get("idParte"),
            "tipo": elem.get("tipoParte") or "",
            "clase": norm(elem.get("tipoParte") or ""),
            "nombre": nombre,
            "titulo": titulo,
            "texto": texto,
            "derogado": elem.get("derogado") or "",
            "transitorio": elem.get("transitorio") or "",
            "fecha_version": elem.get("fechaVersion") or "",
        })
    return {"meta": meta, "partes": partes}


CABECERA = re.compile(
    r"\bArt(?:ículo|iculo|\.)?\s*(\d+)\s*(bis|ter|quáter|quater)?\s*[°º]?\s*[.\-–—]+\s*",
    re.I,
)


def articulo_de_texto(texto: str, numero: str) -> dict | None:
    """Recorta un articulo del texto plano de una version historica.

    No es parseo estructural (LeyChile no lo expone): se corta por cabecera.
    Devuelve confianza y el hueco cuando el corte no tiene cabecera siguiente.
    """
    objetivo = re.sub(r"\D", "", str(numero))
    if not objetivo:
        return None
    cabeceras = list(CABECERA.finditer(texto))
    for i, m in enumerate(cabeceras):
        if m.group(1) != objetivo:
            continue
        fin = cabeceras[i + 1].start() if i + 1 < len(cabeceras) else len(texto)
        recorte = texto[m.start():fin].strip()
        if len(recorte) < 20:
            continue
        hueco = None
        if i + 1 >= len(cabeceras):
            hueco = "sin cabecera siguiente: el recorte llega al final del texto"
        notas = False
        marca = re.search(r"\s(?:NOTA:|LEY \d{3,} .*?D\.O\.)", recorte)
        if marca and marca.start() > 60:
            recorte = recorte[:marca.start()].rstrip()
            notas = True
            hueco = (hueco or "") + " se recortaron notas editoriales de LeyChile"
        return {"texto": recorte[:12000],
                "confianza": "media" if (hueco or notas) else "alta",
                "hueco": hueco, "notas_recortadas": notas}
    return None
