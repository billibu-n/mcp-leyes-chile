"""Juez externo ciego (z.ai/GLM): evalua la calidad de las respuestas, no el hash."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCRIPT = Path.home() / "sede/trabajo/.dsh/biblioteca/scripts/segunda-opinion.py"

RUBRICA = """Eres evaluador externo de un servidor MCP juridico chileno. Recibes UNA pregunta y
la respuesta cruda del servidor. NO conoces la respuesta correcta, asi que no juzgues si el
derecho esta bien: juzga si la respuesta es verificable y honesta.

Criterios (0 a 3):
- 3: cita norma y articulo concretos, con fuente o fecha, y declara lo que no cubre.
- 2: cita, pero con algun hueco de fuente o de vigencia no declarado.
- 1: responde sin cita verificable, o evita la pregunta sin decir por que.
- 0: inventa, contradice la evidencia del propio JSON, o presenta un borrador como valido.

Devuelve SOLO un objeto JSON valido, sin markdown:
{"puntaje":0,"cita_verificable":false,"honestidad":"alta|media|baja","problemas":["..."]}
"""


def _evaluar(tarea: dict, tmp: Path) -> dict:
    respuesta = json.dumps(tarea["resultado"], ensure_ascii=False)[:2500]
    brief = (f"PREGUNTA: {tarea['pregunta']}\nHERRAMIENTA: {tarea['tool']}\n"
             f"RESPUESTA (JSON crudo):\n{respuesta}\n")
    bp = tmp / f"brief-{tarea['id']}.txt"
    op = tmp / f"out-{tarea['id']}.json"
    bp.write_text(RUBRICA + brief, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "--brief", str(bp), "--raw",
                           "--out", str(op)], capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not op.exists():
        return {"id": tarea["id"], "error": proc.stderr[-200:]}
    datos = json.loads(op.read_text(encoding="utf-8"))
    juicio = datos.get("juicio")
    if isinstance(juicio, str):
        try:
            juicio = json.loads(juicio)
        except json.JSONDecodeError:
            juicio = {"puntaje": None, "problemas": [juicio[:200]]}
    return {"id": tarea["id"], "latencia_s": datos.get("latencia_s"), **(juicio or {})}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval.juez")
    p.add_argument("--resultados", default="resultados-ejercicio.json")
    p.add_argument("--json", default="juicio-externo.json")
    p.add_argument("--cuantos", type=int, default=6)
    p.add_argument("--solo", default="", help="ids separados por coma")
    a = p.parse_args(argv)
    r = json.loads(Path(a.resultados).read_text(encoding="utf-8"))
    # prioriza las tareas de mayor nivel y luego alterna
    orden = sorted(r["detalle"], key=lambda d: (-d["nivel"], d["id"]))
    elegidas = ([d for d in orden if d["id"] in a.solo.split(",")] if a.solo
                else orden[:a.cuantos])
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ThreadPoolExecutor(max_workers=3) as ex:
            juicios = list(ex.map(lambda t: _evaluar(t, tmp), elegidas))
    por_id = {d["id"]: d for d in r["detalle"]}
    acuerdan = 0
    for j in juicios:
        auto = por_id.get(j["id"], {}).get("ok")
        j["automatico_ok"] = auto
        if isinstance(j.get("puntaje"), int):
            j["acuerdo"] = (j["puntaje"] >= 2) == bool(auto)
            acuerdan += int(j["acuerdo"])
    val = [j["puntaje"] for j in juicios if isinstance(j.get("puntaje"), int)]
    resumen = {"juzgadas": len(juicios), "con_puntaje": len(val),
               "promedio": round(sum(val) / len(val), 2) if val else None,
               "acuerdo": acuerdan, "juicios": juicios}
    Path(a.json).write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: resumen[k] for k in ("juzgadas", "con_puntaje", "promedio", "acuerdo")},
                     ensure_ascii=False))
    return 0 if len(val) == len(juicios) else 1


if __name__ == "__main__":
    raise SystemExit(main())
