import json
import zipfile
from pathlib import Path

import pytest

from mcp_leyes import bcn, citas, db, documentos, notaria


def test_con_puntos():
    assert citas.con_puntos("21643") == "21.643"
    assert citas.con_puntos("825") == "825"


def test_nombre_norma():
    assert citas.nombre_norma({"tipo": "Decreto Ley", "numero": "825"}) == "DL 825"
    assert citas.nombre_norma({"tipo": "Ley", "numero": "21643"}) == "Ley 21.643"


def test_centinela():
    assert bcn.es_centinela("2222-02-02")
    assert not bcn.es_centinela("2026-02-05")
    assert not bcn.es_centinela("")


def test_cita_con_centinela_no_lleva_fecha():
    meta = {"id_norma": 1, "tipo": "Decreto con Fuerza de Ley", "numero": "1"}
    parte = {"nombre": "1", "texto": "Artículo 1.- ...", "fecha_version": "2222-02-02",
             "derogado": "", "transitorio": ""}
    c = citas.construir(meta, parte)
    assert c["vigente_desde"] is None
    assert "2222" not in c["cita"]
    assert c["hueco"]


def test_cita_vigente():
    meta = {"id_norma": 6369, "tipo": "Decreto Ley", "numero": "825"}
    parte = {"nombre": "14", "texto": "Artículo 14.- ...", "fecha_version": "2006-04-28",
             "derogado": "", "transitorio": ""}
    c = citas.construir(meta, parte)
    assert c["cita"] == "DL 825, art. 14, texto vigente desde 2006-04-28"
    assert c["estado"] == "vigente"
    assert c["fuente"].endswith("i=6369")


def test_cita_derogada():
    meta = {"id_norma": 1, "tipo": "Ley", "numero": "1000"}
    parte = {"nombre": "9", "texto": "x", "fecha_version": "2000-01-01",
             "derogado": "derogado", "transitorio": ""}
    assert citas.construir(meta, parte)["estado"] == "derogado"


def test_fichas_notariales_validas():
    assert notaria.validar() == []
    assert len(notaria.cargar()) >= 3


def test_ficha_sin_fuente_se_marca():
    f = notaria.cargar()["poder-especial"]
    assert any(i["estado"] == "sin_fuente" for i in f["requisitos"])
    assert f["arancel"]["advertencia"]


def test_documento_odt_rellena_y_no_deja_marcadores(tmp_path):
    p = documentos.plantillas()["poder-especial"]
    datos = {c["nombre"]: "X" for c in p["campos"]}
    odt = documentos.crear_odt(p, datos, tmp_path / "x.odt")
    with zipfile.ZipFile(odt) as z:
        contenido = z.read("content.xml").decode()
        assert z.read("mimetype") == b"application/vnd.oasis.opendocument.text"
    assert "{{" not in contenido
    assert "BORRADOR" in contenido


def test_documento_falta_campo(tmp_path):
    p = documentos.plantillas()["poder-especial"]
    with pytest.raises(documentos.DocumentoError):
        documentos.crear_odt(p, {"OTORGANTE": "Ana"}, tmp_path / "x.odt")


def _db_falsa(tmp_path):
    con = db.conectar(tmp_path / "t.db")
    meta = {"id_norma": 6369, "tipo": "Decreto Ley", "numero": "825", "titulo": "IVA",
            "organismo": "Hacienda", "fecha_publicacion": "1974-12-31",
            "fecha_promulgacion": "1974-12-27", "fecha_version": "2026-02-05",
            "derogado": "no derogado"}
    partes = [{"orden": 1, "id_parte": "1", "tipo": "Artículo", "clase": "articulo",
               "nombre": "14", "titulo": "", "texto": "Artículo 14.- Los contribuyentes...",
               "derogado": "", "transitorio": "", "fecha_version": "2006-04-28"}]
    db.guardar(con, meta, partes, "sha", "2026-11-06T00:00:00")
    db.guardar_versiones(con, 6369, [{"@vigenteDesde": "2026-03-05",
                                      "@vigenteHasta": "2222-02-01",
                                      "@tipoVersion": "Última Versión"}])
    con.commit()
    return con


def test_db_busqueda_y_articulo(tmp_path):
    con = _db_falsa(tmp_path)
    assert db.buscar(con, "contribuyentes")
    assert db.traer_articulo(con, 6369, "14.")[0]["texto"].startswith("Artículo 14")
    assert db.cobertura(con)["articulos"] == 1


def test_server_articulo_inexistente(tmp_path, monkeypatch):
    from mcp_leyes import server
    _db_falsa(tmp_path)
    monkeypatch.setattr(server, "DB", str(tmp_path / "t.db"))
    r = server.cl_articulo(id_norma=6369, articulo="999")
    assert r["error"].startswith("[not_found]")


def test_server_cobertura_declara_huecos(tmp_path, monkeypatch):
    from mcp_leyes import server
    _db_falsa(tmp_path)
    monkeypatch.setattr(server, "DB", str(tmp_path / "t.db"))
    r = server.cl_cobertura()
    assert r["cobertura"]["articulos"] == 1
    assert "jurisprudencia" in r["no_cubre"]


def test_server_citar_lote(tmp_path, monkeypatch):
    from mcp_leyes import server
    _db_falsa(tmp_path)
    monkeypatch.setattr(server, "DB", str(tmp_path / "t.db"))
    r = server.cl_citar(["6369/14", "6369/999"])
    assert len(r["ok"]) == 1 and len(r["faltantes"]) == 1


def test_articulo_de_texto_corta_por_cabecera():
    texto = ("Artículo 1.- Primero, texto largo suficiente para pasar el umbral. "
             "Artículo 2.- Segundo, tambien largo suficiente para el corte. "
             "Artículo 3.- Tercero final.")
    r = bcn.articulo_de_texto(texto, "2")
    assert r["confianza"] == "alta"
    assert r["texto"].startswith("Artículo 2")
    assert "Tercero" not in r["texto"]


def test_articulo_de_texto_ultimo_marca_hueco():
    texto = "Artículo 1.- Uno largo suficiente para el umbral minimo. Artículo 2.- Dos final."
    r = bcn.articulo_de_texto(texto, "2")
    assert r["confianza"] == "media" and r["hueco"]


def test_numerales_arancel_no_parte_los_montos():
    t = ("1) Por escritura pública $2.500.- y algo; 2) Por página $300.-; "
         "24) Por certificado $1.200.-")
    assert notaria.numerales_arancel(t) == [
        (1, "Por escritura pública $2.500.- y algo;"),
        (2, "Por página $300.-;"),
        (24, "Por certificado $1.200.-")]


def test_generar_fichas_desde_arancel(tmp_path):
    con = db.conectar(tmp_path / "t.db")
    meta = {"id_norma": 127917, "tipo": "Decreto", "numero": "587", "titulo": "Arancel",
            "organismo": "Justicia", "fecha_publicacion": "1998-12-03",
            "fecha_promulgacion": "1998-11-30", "fecha_version": "2020-02-07",
            "derogado": "no derogado"}
    partes = [{"orden": 1, "id_parte": "1", "tipo": "Artículo", "clase": "articulo",
               "nombre": "1", "titulo": "",
               "texto": "90) Por escritura $2.500.-; 91) Por página $300.-",
               "derogado": "", "transitorio": "", "fecha_version": "2020-02-07"}]
    db.guardar(con, meta, partes, "sha", "2026-11-06T00:00:00")
    creadas = notaria.generar_desde_arancel(con, destino=tmp_path)
    assert creadas == ["arancel-90", "arancel-91"]
    assert (tmp_path / "arancel-90.yaml").exists()


def test_server_articulo_ambiguo(tmp_path, monkeypatch):
    from mcp_leyes import server
    con = db.conectar(tmp_path / "a.db")
    meta = {"id_norma": 1, "tipo": "Ley", "numero": "1", "titulo": "X", "organismo": "",
            "fecha_publicacion": "", "fecha_promulgacion": "", "fecha_version": "",
            "derogado": "no derogado"}
    partes = [{"orden": i, "id_parte": str(i), "tipo": "Artículo", "clase": "articulo",
               "nombre": "1", "titulo": "", "texto": f"Artículo 1.- version {i}",
               "derogado": "", "transitorio": "", "fecha_version": "2020-01-01"}
              for i in (1, 2)]
    db.guardar(con, meta, partes, "sha", "2026-11-06T00:00:00")
    con.commit()
    monkeypatch.setattr(server, "DB", str(tmp_path / "a.db"))
    r = server.cl_articulo(1, "1")
    assert r["coincidencias"] == 2 and "comparten el numero" in r["hueco"]


def test_server_json_valido():
    import pathlib
    d = json.loads(pathlib.Path("server.json").read_text(encoding="utf-8"))
    assert d["name"].startswith("io.github.")
    assert d["name"].endswith("/mcp-leyes-chile")
    assert len(d["description"]) <= 100
    assert d["packages"][0]["registryType"] == "pypi"
    assert d["packages"][0]["transport"]["type"] == "stdio"


def test_banco_construye_tareas(tmp_path):
    from eval import banco
    con = db.conectar(tmp_path / "b.db")
    meta = {"id_norma": 2, "tipo": "Ley", "numero": "2", "titulo": "Y", "organismo": "",
            "fecha_publicacion": "", "fecha_promulgacion": "", "fecha_version": "",
            "derogado": "no derogado"}
    partes = [{"orden": 1, "id_parte": "1", "tipo": "Artículo", "clase": "articulo",
               "nombre": "1", "titulo": "", "texto": "x" * 300, "derogado": "",
               "transitorio": "", "fecha_version": "2020-01-01"}]
    db.guardar(con, meta, partes, "sha", "2026-11-06T00:00:00")
    t = banco.construir(con, 5)
    assert len(t) == 1 and t[0]["esperados_sha"]
    assert banco.adversariales(con)


def test_banco_adversariales_incluye_centinela_y_derogado(tmp_path):
    from eval import banco
    con = db.conectar(tmp_path / "c.db")
    meta = {"id_norma": 3, "tipo": "Ley", "numero": "3", "titulo": "Z", "organismo": "",
            "fecha_publicacion": "", "fecha_promulgacion": "", "fecha_version": "",
            "derogado": "no derogado"}
    partes = [
        {"orden": 1, "id_parte": "1", "tipo": "Artículo", "clase": "articulo", "nombre": "9",
         "titulo": "", "texto": "y" * 300, "derogado": "", "transitorio": "",
         "fecha_version": "2222-02-02"},
        {"orden": 2, "id_parte": "2", "tipo": "Artículo", "clase": "articulo", "nombre": "10",
         "titulo": "", "texto": "z" * 300, "derogado": "derogado", "transitorio": "",
         "fecha_version": "2000-01-01"},
    ]
    db.guardar(con, meta, partes, "sha", "2026-11-06T00:00:00")
    tipos = {t["tipo"] for t in banco.adversariales(con)}
    assert {"centinela", "derogado", "articulo_inexistente", "busqueda_vacia"} <= tipos


def test_articulo_de_texto_recorta_notas_editoriales():
    texto = ("Artículo 1.- Texto del articulo con largo suficiente para pasar el umbral de "
             "sesenta caracteres. LEY 19888 Art. 1 D.O. 13.08.2003 NOTA: algo editorial.")
    r = bcn.articulo_de_texto(texto, "1")
    assert r["notas_recortadas"] is True
    assert "D.O." not in r["texto"]
    assert r["confianza"] == "media"


def test_cita_derogada_no_dice_vigente():
    meta = {"id_norma": 1, "tipo": "Ley", "numero": "1000"}
    parte = {"nombre": "47", "texto": "x", "fecha_version": "1989-10-20",
             "derogado": "derogado", "transitorio": ""}
    c = citas.construir(meta, parte)
    assert "vigente desde" not in c["cita"]
    assert "derogado" in c["cita"] and c["hueco"]


# --- regresiones del estres 0.2.2 (T-106) ---------------------------------

def test_fecha_valida_rechaza_basura():
    assert bcn.fecha_valida("2015-01-01") is None
    assert "AAAA-MM-DD" in bcn.fecha_valida("2020-13-45")
    assert "AAAA-MM-DD" in bcn.fecha_valida("ayer")
    assert "centinela" in bcn.fecha_valida("2222-02-02")
    assert "futuro" in bcn.fecha_valida("2999-01-01")
    assert "1900" in bcn.fecha_valida("1850-01-01")


def test_buscar_recorta_consulta_gigante(tmp_path):
    con = _db_falsa(tmp_path)
    tokens, recortado = db.recortar("contribuyentes " * 6000)
    assert recortado and len(tokens.split()) == db.MAX_TOKENS
    assert db.buscar(con, "contribuyentes " * 6000)


def test_clave_articulo_acepta_formas():
    assert db._clave_articulo("art. 1545") == "1545"
    assert db._clave_articulo("Artículo 1545") == "1545"
    assert db._clave_articulo("11 BIS (DEL ART. 7)") == "11bis"


def test_documento_md_sustituye(tmp_path, monkeypatch):
    monkeypatch.setattr(documentos, "SALIDAS", tmp_path)
    p = documentos.plantillas()["poder-especial"]
    datos = {c["nombre"]: f"valor-{c['nombre']}" for c in p["campos"]}
    r = documentos.generar("poder-especial", datos, ("odt", "md"))
    texto = Path(r["archivos"]["md"]).read_text(encoding="utf-8")
    assert "valor-OTORGANTE" in texto
    assert "{OTORGANTE}" not in texto


def test_documento_formato_invalido(tmp_path, monkeypatch):
    monkeypatch.setattr(documentos, "SALIDAS", tmp_path)
    p = documentos.plantillas()["poder-especial"]
    datos = {c["nombre"]: "X" for c in p["campos"]}
    with pytest.raises(documentos.DocumentoError) as exc:
        documentos.generar("poder-especial", datos, ("odt", "exe"))
    assert "[invalid_arg]" in str(exc.value)


def test_documento_dos_llamadas_no_se_pisan(tmp_path, monkeypatch):
    monkeypatch.setattr(documentos, "SALIDAS", tmp_path)
    p = documentos.plantillas()["poder-especial"]
    datos = {c["nombre"]: "X" for c in p["campos"]}
    a = documentos.generar("poder-especial", datos, ("odt",))
    b = documentos.generar("poder-especial", datos, ("odt",))
    assert a["archivos"]["odt"] != b["archivos"]["odt"]
