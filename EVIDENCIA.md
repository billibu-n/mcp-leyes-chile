# EVIDENCIA — MVP mcp-leyes-chile (2026-11-06)

Todo lo de abajo se ejecutó en este equipo. Los comandos se repiten desde la raíz del repo.

## 1. Herramientas

```
$ .venv/bin/python -m mcp_leyes --selftest
{"version": "0.1.0", "tools": ["cl_buscar", "cl_articulo", "cl_versiones", "cl_citar",
 "cl_notaria", "cl_documento", "cl_cobertura"]}
rc=0
```

Por protocolo (no solo por import):

```
tools: ['cl_buscar', ..., 'cl_cobertura']
call_tool tipo: CallToolResult
cita por protocolo: DL 825, art. 14, texto vigente desde 2006-04-28
inexistente: [not_found] articulo 999 no existe en la
```

## 2. Ingesta real desde LeyChile

```
$ time .venv/bin/python -m mcp_leyes --ingesta
  6369: Decreto Ley 825: 146 partes, 83 versiones
  207436: Decreto con Fuerza de Ley 1: 854 partes, 134 versiones
  172986: Decreto con Fuerza de Ley 1: 3151 partes, 50 versiones
  1974: Código DE COMERCIO: 1734 partes, 38 versiones
  1984: Código PENAL: 798 partes, 165 versiones
  242302: Decreto 100: 269 partes, 58 versiones
  141599: Ley 19628: 35 partes, 8 versiones
  127917: Decreto 587 EXENTO: 7 partes, 2 versiones
OK 8 normas, 6098 articulos, 538 versiones
real 0m21,371s
```

## 3. Cita verificable

```
ARTICULO: DL 825, art. 14, texto vigente desde 2006-04-28 | vigente | 145 chars
  texto: Artículo 14°- Los contribuyentes afectos a las disposiciones del presente Título
         pagarán el impuesto con una tasa de 19%
  hueco: None | aviso: Esto no es asesoría legal...
VERSIONES: 83 | actual: 2026-03-05
CITAR ok: 1 faltan: 1 sin_fuente: 1
```

## 4. Documentos .odt (formato prioritario)

```
$ .venv/bin/python -m mcp_leyes --smoke
{"archivos": {"odt": "salidas/poder-especial.odt", "pdf": "salidas/poder-especial.pdf"},
 "aviso": "BORRADOR — NO VÁLIDO PARA PRESENTACIÓN", "ok": true, "pdf_bytes": 31925}
$ pdftotext salidas/poder-especial.pdf -
BORRADOR — NO VÁLIDO PARA PRESENTACIÓN
PODER ESPECIAL
En Santiago, a 2026-11-06, comparece don(ña) Ana Pérez...
```

`.docx` se deriva del `.odt` con `soffice --convert-to docx` (probado en T-102).

## 5. Pruebas

```
$ .venv/bin/python -m pytest -q
14 passed in 0.61s
```

Cubren: puntos de miles (21.643), centinela 2222, cita vigente/derogada, fichas notariales,
ODT sin marcadores, falta de campos, búsqueda, artículo inexistente, lote de citas y
cobertura con huecos.

## 6. Límites declarados

- 8 cuerpos legales; sin jurisprudencia ni tribunales.
- Historial: `cl_articulo(..., vigente_al=...)` recorta el artículo por encabezado sobre el
  texto histórico; el corte puede incluir el artículo siguiente (se marca como hueco).
- Notaría: requisitos y competencia territorial sin fuente estructurada (`sin_fuente`).
- El corpus se descarga; el paquete no lo redistribuye (licencia de LeyChile sin verificar).


## 7. Fase 2 (2026-11-06)

```
$ .venv/bin/python -m pytest -q
23 passed in 1.00s

$ .venv/bin/python -m eval.correr --banco 60
{"tareas": 66, "articulos": 60, "exactitud": 1.0, "alucinaciones": 0,
 "adversariales_fallidas": 0, "p95_ms": 14.2, "p50_ms": 5.4, "ok": true}

$ .venv/bin/python -m mcp_leyes --notaria
27 fichas, 0 fallos

$ .venv/bin/python -m mcp_leyes --notaria-generar
{"creadas": ["arancel-01", ... "arancel-24"], "total": 27}
```

Vigencia histórica (articulo 14 del DL 825 al 2015-01-01):

```
confianza: media | notas: True | len: 145
Artículo 14°- Los contribuyentes afectos ... pagarán el impuesto con una tasa de 19% ...
```

El recorte quitó las notas editoriales de LeyChile («LEY 19888 Art. 1º a) D.O.
13.08.2003»), que no son texto legal. Sin ese corte, el texto citado traía la anotación.

`server.json`: nombre `io.github.billibu-n/mcp-leyes-chile`, versión 0.2.0, descripción de
77 caracteres (el registro limita a 100), paquete PyPI y transporte stdio.


## 8. Publicación (2026-11-06)

Hecho:

```
$ mcp-publisher validate server.json
✅ server.json is valid

$ gh repo create billibu-n/mcp-leyes-chile --public
https://github.com/billibu-n/mcp-leyes-chile   (main, commit d82fb11)

$ mcp-publisher login github
Successfully authenticated!

$ mcp-publisher publish
Error: 400 registry validation failed for package 0 (mcp-leyes-chile):
       PyPI package 'mcp-leyes-chile' not found (status: 404)
```

Artefactos construidos y validados: `dist/mcp_leyes_chile-0.2.0.tar.gz` y `.whl`,
`twine check` PASSED, con `mcp-name: io.github.billibu-n/mcp-leyes-chile` en los metadatos.

Resuelto con el token del dueño y una segunda autorización del login:

```
$ twine upload dist/*
View at: https://pypi.org/project/mcp-leyes-chile/0.2.0/

$ mcp-publisher publish
✓ Successfully published
✓ Server io.github.billibu-n/mcp-leyes-chile version 0.2.0

$ curl ".../v0.1/servers?search=io.github.billibu-n/mcp-leyes-chile"
resultados: 1  |  io.github.billibu-n/mcp-leyes-chile 0.2.0
```

Publicado: PyPI y registro oficial del Model Context Protocol.

## 9. Version 0.2.2 (2026-11-06)

La 0.2.0 publicada estaba incompleta y el `--selftest` no lo veia: listaba 7 tools, pero el
wheel no llevaba los datos. Medido instalando la 0.2.0 desde PyPI fuera del repositorio:

```
$ pip install mcp-leyes-chile==0.2.0
$ python -c "from mcp_leyes import notaria, documentos; ..."
fichas: 0 | plantillas: []
DB por defecto: .../site-packages/data/corpus.db
```

Causa: `[tool.setuptools] packages = ["mcp_leyes"]` no incluye `notaria/` ni `plantillas/`,
que estaban en la raiz, y la base de datos se escribia dentro de site-packages (solo lectura).

En 0.2.2 los datos viven dentro del paquete y el estado va al home del usuario:

```
$ python -c "import zipfile; ..."
45 entradas | yaml: 27 | json: 2
```

Prueba de alto estres (41 comprobaciones por stdio, `eval/estres.py`):

| Corrida | Fallos | Hallazgo principal |
|---|---|---|
| Antes | 12 | consulta de 54.000 caracteres: 44 s; fecha `ayer`: 90 s |
| Despues | 0 | 11 ms y `[invalid_arg]` local |

```
$ python -m eval.estres
{"comprobaciones": 41, "fallos": 0, "ok": true}
```

La misma matriz contra el wheel instalado: 41/41.

Publicacion:

```
$ twine upload dist/*
View at: https://pypi.org/project/mcp-leyes-chile/0.2.2/

$ mcp-publisher login github -token ...   (el JWT de la sesion habia caducado)
✓ Successfully logged in
$ mcp-publisher publish
✓ Server io.github.billibu-n/mcp-leyes-chile version 0.2.2

$ curl ".../v0.1/servers?search=io.github.billibu-n/mcp-leyes-chile"
resultados: 2  |  0.2.0 active  |  0.2.2 active
```

GitHub: tag `v0.2.2` sobre el mismo arbol; wheel y sdist construidos con `python -m build`.
