"""Ejecuta el banco y mide exactitud, alucinaciones y latencia."""
from __future__ import annotations

import argparse
import json
import statistics
import time

from mcp_leyes import db, server

from . import banco


def _p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def correr(n: int, salida: str = "") -> dict:
    con = db.conectar(server.DB)
    articulos = banco.construir(con, n)
    adversas = banco.adversariales(con)
    latencias, aciertos, alucinaciones, detalles = [], 0, 0, []

    for t in articulos:
        t0 = time.perf_counter()
        r = server.cl_articulo(t["idNorma"], t["articulo"])
        latencias.append((time.perf_counter() - t0) * 1000)
        obtenido = r.get("texto", "")
        import hashlib
        sha = hashlib.sha256(obtenido.strip().encode()).hexdigest()
        ok = sha in (t.get("esperados_sha") or [t["esperado_sha"]])
        aciertos += int(ok)
        if not ok and r.get("cita"):
            alucinaciones += 1
        detalles.append({"id": t["id"], "ok": ok})

    fallos_adv = 0
    for t in adversas:
        t0 = time.perf_counter()
        if t["tipo"] == "articulo_inexistente":
            r = server.cl_articulo(t["idNorma"], t["articulo"])
            ok = str(r.get("error", "")).startswith("[not_found]")
        elif t["tipo"] == "norma_inexistente":
            r = server.cl_articulo(t["idNorma"], t["articulo"])
            ok = str(r.get("error", "")).startswith("[not_found]")
        elif t["tipo"] == "centinela":
            r = server.cl_articulo(t["idNorma"], t["articulo"])
            ok = r.get("vigente_desde") is None and "2222" not in r.get("cita", "")
        elif t["tipo"] == "derogado":
            r = server.cl_articulo(t["idNorma"], t["articulo"])
            ok = r.get("estado") == "derogado"
        elif t["tipo"] == "busqueda_vacia":
            r = server.cl_buscar(t["q"])
            ok = r.get("total") == 0
        else:
            r = server.cl_buscar(t["q"], limite=3)
            ok = "resultados" in r
        latencias.append((time.perf_counter() - t0) * 1000)
        fallos_adv += int(not ok)
        detalles.append({"id": t["id"], "ok": ok})

    total = len(articulos)
    exactitud = aciertos / total if total else 0.0
    res = {
        "tareas": total + len(adversas),
        "articulos": total,
        "exactitud": round(exactitud, 4),
        "alucinaciones": alucinaciones,
        "adversariales_fallidas": fallos_adv,
        "p95_ms": round(_p95(latencias), 1),
        "p50_ms": round(statistics.median(latencias), 1) if latencias else 0.0,
        "detalles": detalles,
    }
    res["ok"] = exactitud >= 0.98 and alucinaciones == 0 and fallos_adv == 0 and res["p95_ms"] <= 1500
    if salida:
        open(salida, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval.correr")
    p.add_argument("--banco", type=int, default=60)
    p.add_argument("--json", default="")
    a = p.parse_args(argv)
    r = correr(a.banco, a.json)
    print(json.dumps({k: v for k, v in r.items() if k != "detalles"}, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
