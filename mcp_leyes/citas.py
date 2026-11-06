"""Contrato de cita: sin articulo verificado no hay respuesta.

R1 sin texto -> error; R2 centinela 2222 -> hueco, sin fecha; R3 derogado se marca;
R4 fuente enlazada; R5 formato con puntos de miles; R6 aviso legal.
"""
from __future__ import annotations

from . import bcn

AVISO = "Esto no es asesoría legal. Verifica con un profesional antes de actuar."

ABREV = {
    "decreto ley": "DL",
    "decreto con fuerza de ley": "DFL",
    "decreto": "Decreto",
    "ley": "Ley",
    "constitucion politica de la republica": "Constitución",
}


def con_puntos(numero: str) -> str:
    limpio = str(numero or "").strip()
    if not limpio.isdigit() or len(limpio) < 4:
        return limpio
    return f"{int(limpio):,}".replace(",", ".")


def nombre_norma(meta: dict) -> str:
    tipo = bcn.norm(meta.get("tipo", ""))
    etiqueta = ABREV.get(tipo, meta.get("tipo") or "Norma")
    return f"{etiqueta} {con_puntos(meta.get('numero'))}".strip()


def construir(meta: dict, parte: dict) -> dict:
    """Objeto de cita completo, con huecos declarados."""
    idn = meta.get("id_norma") or meta.get("id")
    meta = {**meta, "id_norma": idn}
    texto = (parte.get("texto") or "").strip()
    bruto = str(parte.get("nombre") or "").replace("°", "").replace("º", "").strip()
    import re as _re
    m = _re.match(r"(\d+)\s*(bis|ter|quater)?", bruto, _re.I)
    numero = (m.group(1) + (m.group(2) or "").lower()) if m else bruto.rstrip(".")
    variante = "texto alterno" if "(" in bruto else None
    desde = parte.get("fecha_version") or ""
    hueco = None
    if bcn.es_centinela(desde):
        hueco = "vigencia diferida por evento (centinela 2222-02-02)"
        desde = ""
    estado = "derogado" if (parte.get("derogado") == "derogado") else "vigente"
    if parte.get("transitorio") == "transitorio":
        estado = "transitorio"
    if estado == "derogado":
        cita = f"{nombre_norma(meta)}, art. {numero} (derogado"
        cita += f", última versión {desde})" if desde else ")"
        hueco = "articulo derogado: no esta vigente; no debe citarse como derecho aplicable"
    else:
        cita = f"{nombre_norma(meta)}, art. {numero}"
        if desde:
            cita += f", texto vigente desde {desde}"
    return {
        "idNorma": meta.get("id_norma"),
        "norma": nombre_norma(meta),
        "articulo": numero,
        "variante": variante,
        "texto": texto,
        "estado": estado,
        "vigente_desde": desde or None,
        "cita": cita,
        "fuente": f"https://www.leychile.cl/N?i={meta.get('id_norma')}",
        "verificado": meta.get("descargado", ""),
        "aviso": AVISO,
        "hueco": hueco,
    }
