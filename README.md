# mcp-leyes-chile

mcp-name: io.github.billibu-n/mcp-leyes-chile

Servidor MCP de leyes chilenas con **cita verificable** (v0.2.2), fichas notariales curadas y
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
| `cl_documento` | Genera `.odt` y deriva `.pdf` (por defecto), `.docx` o `.md`, con marca de BORRADOR y la base legal de la plantilla |
| `cl_cobertura` | Qué cubre, hasta cuándo, y qué **no** cubre |

## Instalación

Desde PyPI:

```bash
pip install mcp-leyes-chile
mcp-leyes-chile --ingesta      # ~20 s: 9 normas, 6.246 artículos, 556 versiones
mcp-leyes-chile --selftest     # lista las 7 tools
```

O desde el código:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
python -m mcp_leyes --ingesta
python -m mcp_leyes --notaria-generar  # crea fichas desde el arancel (idempotente)
python -m mcp_leyes --smoke            # genera .odt + .pdf de prueba
python -m mcp_leyes                    # sirve por stdio
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

## Publicación

En el registro oficial: **`io.github.billibu-n/mcp-leyes-chile`** 0.2.2
(`https://registry.modelcontextprotocol.io`), paquete PyPI `mcp-leyes-chile`.

`server.json` cumple el esquema del registro: `registryType: pypi`, `transport: stdio`.
Publicar requiere `mcp-publisher login github` y autorización del dueño.

## Qué cambió en 0.2.2

El servidor pasó por una prueba de alto estrés de **41 comprobaciones** por el protocolo real
(parámetros hostiles, FTS5 roto, concurrencia, documentos en paralelo, lotes de 200). Encontró
nueve defectos; esta versión los corrige:

| Defecto | Antes | Ahora |
|---|---|---|
| Consulta de 54.000 caracteres | 44 s de bloqueo | 11 ms (recorte a 24 términos) |
| Fecha `ayer` o `2020-13-45` | viajaba a LeyChile: 90 s y el texto de **otra** versión | `[invalid_arg]` local en 1 ms |
| Centinela `2222-02-02` como fecha | respuesta con fecha falsa | `[invalid_arg]` que explica el centinela |
| `cl_citar` con una referencia suelta | rechazo del protocolo | acepta `"6369/14"` y la clasifica |
| Formato de `cl_documento` desconocido | caía en silencio a PDF | `[invalid_arg]` |
| Base legal de la plantilla | siempre art. 2116 (mandato) | 1793 y 1801 para compraventa, 2116 para poder |
| Salida `.md` | dejaba `{OTORGANTE}` sin sustituir | sustituye los campos |
| Dos documentos a la vez | se pisaban el mismo `.odt` | carpeta propia por llamada |
| 40 artículos concurrentes | 7,2 s | 0,15 s (prefiltro en SQL y conexiones cerradas) |

Además, esta versión incorpora las correcciones del ejercicio de evaluación de T-105, que
hasta ahora solo estaban en el repositorio: fuente con `i=None`, cita de artículo derogado que
decía «vigente», `[not_found]` sin nombre de norma, documento sin base legal, la Ley 19.496
en el corpus y las claves con sufijo `(DEL ART. 2)`.

## Cobertura y límites

- 9 cuerpos legales: DL 825, Código del Trabajo, Código Civil, Comercio, Penal, Constitución,
  Ley 19.628, Ley 19.496 y Arancel de notarios.
- **No** cubre jurisprudencia, tribunales, SII más allá de las normas, competencia territorial
  notarial estructurada, precios actuales ni firma de documentos.
- Los montos del arancel son **nominales de 1998**: el servidor los muestra y advierte, no
  calcula el precio final.

## Datos y licencias

- Código: Apache-2.0 (`LICENSE`).
- Fuente: LeyChile / BCN. El paquete **no redistribuye** el corpus: lo descarga en la máquina
  del usuario. Los términos de LeyChile no se pudieron verificar (2026-11-06).
- Fichas notariales: CC BY 4.0, con fuente y fecha por campo.

## Pruebas

```bash
python -m pytest -q                     # 30 tests
python -m eval.estres                   # 41 comprobaciones de estrés por stdio
python -m eval.correr --banco 60        # 66 tareas: exactitud 1.0, 0 alucinaciones
python -m eval.ejercicio                # 10 tareas de razonamiento (22/22)
python -m mcp_leyes --notaria           # 27 fichas, 0 fallos
```
