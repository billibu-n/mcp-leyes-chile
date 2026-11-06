# mcp-leyes-chile

mcp-name: io.github.billibu-n/mcp-leyes-chile

Servidor MCP de leyes chilenas con **cita verificable** (v0.2.0), fichas notariales curadas y
generación de documentos **`.odt`** (editable), `.pdf` y `.docx`.

No es asesoría legal. Es una herramienta para que una persona llegue a la notaría con el
borrador hecho y para que un abogado no presente una cita que no exista.

## Qué hace

| Tool | Para qué |
|---|---|
| `cl_buscar` | Busca artículos por texto en el corpus local (SQLite FTS5) |
| `cl_articulo` | Texto literal + cita con `vigente_desde`, fuente y aviso; acepta `vigente_al` (AAAA-MM-DD) para la versión histórica |
| `cl_versiones` | Historial de versiones de una norma (83 en el DL 825) |
| `cl_citar` | Verifica un lote: `ok`, `faltantes`, `sin_fuente_verificable` |
| `cl_notaria` | 27 fichas: trámite, arancel y estado por campo (24 generadas del Decreto 587) |
| `cl_documento` | Genera `.odt` y deriva `.pdf`/`.docx`, con marca de BORRADOR |
| `cl_cobertura` | Qué cubre, hasta cuándo, y qué **no** cubre |

## Instalación

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
python -m mcp_leyes --ingesta      # ~21 s: 8 normas, 6.098 artículos, 538 versiones
python -m mcp_leyes --notaria-generar  # crea fichas desde el arancel (idempotente)
python -m mcp_leyes --selftest     # lista las 7 tools
python -m mcp_leyes --smoke        # genera .odt + .pdf de prueba
python -m mcp_leyes                # sirve por stdio
```

Configuración en un host MCP (ejemplo):

```json
{"mcpServers": {"leyes-chile": {"command": "python", "args": ["-m", "mcp_leyes"],
  "env": {"MCP_LEYES_DB": "/ruta/a/corpus.db"}}}}
```

## Formulario HTML

```bash
python -m mcp_leyes --formulario 8801
# http://127.0.0.1:8801/  -> pregunta los campos -> .odt + .pdf
```

## Publicación (pendiente de autorización)

`server.json` está listo y cumple el esquema del registro:
`io.github.billibu-n/mcp-leyes-chile` v0.2.0, `registryType: pypi`, `transport: stdio`.
Publicar requiere `mcp-publisher login github` y autorización del dueño.

## Cobertura y límites

- 8 cuerpos legales (DL 825, Código del Trabajo, Código Civil, Comercio, Penal,
  Constitución, Ley 19.628, Arancel de notarios).
- **No** cubre jurisprudencia, tribunales, SII más allá de las normas, competencia
  territorial notarial estructurada, precios actuales ni firma de documentos.
- Los montos del arancel son **nominales de 1998**: el servidor los muestra y advierte,
  no calcula el precio final.

## Datos y licencias

- Código: Apache-2.0 (`LICENSE`).
- Fuente: LeyChile / BCN. El paquete **no redistribuye** el corpus: lo descarga en la
  máquina del usuario. Los términos de LeyChile no se pudieron verificar (2026-11-06).
- Fichas notariales: CC BY 4.0, con fuente y fecha por campo.

## Pruebas

```bash
python -m pytest -q                     # 23 tests
python -m eval.correr --banco 60        # 66 tareas: exactitud 1.0, 0 alucinaciones, p95 14 ms
python -m mcp_leyes --notaria           # 27 fichas, 0 fallos
```
