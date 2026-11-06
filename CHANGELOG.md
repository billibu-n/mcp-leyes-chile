# Historial de versiones

## 0.2.4 — 2026-11-06

Desambigua los artículos que comparten número en un compendio (T-110).

### Añadido

- `cl_articulo(..., cuerpo="Ley 4.808")` elige el cuerpo dentro del DFL 1. Sin
  `cuerpo` se mantiene el primero y se declara `coincidencias`.
- Si el cuerpo no existe, el error lista los cuerpos disponibles del artículo.

### Pruebas

- 34 tests (1 nuevo): mismo "art. 31" resuelto a Código Civil y a Ley 14.908.
- Ejemplo en PDF: contrato de compraventa con datos inventados, sin variables de
  plantilla.

## 0.2.3 — 2026-11-06

Corrige la atribución de artículos en compendios (T-109).

### Corregido

- El DFL 1 mezcla el Código Civil con leyes anexas (Registro Civil, menores,
  abandono de familia, herencias). El parser perdía la jerarquía y citaba un
  "art. 31" de la Ley 4.808 como "Código Civil, art. 31". Ahora cada parte
  guarda `cuerpo` y `cuerpo_corto`, y la cita usa el cuerpo real.
- Migración automática de la tabla `parte` (`ALTER TABLE`) para bases ya
  construidas; no hay que reingestar.
- `cl_buscar` devuelve `cuerpo` y `cuerpo_corto` por resultado.

### Pruebas

- 33 tests (4 nuevos): parseo jerárquico, cita por cuerpo, migración de columnas.
- Ingesta real: `Código Civil, art. 1793`; el art. 31 de la Ley 4.808 ya no se
  atribuye al Código Civil.

### Pendiente conocido

- Si dos cuerpos del mismo compendio tienen el mismo número de artículo, se
  devuelve el primero y se declara `coincidencias`. Falta un parámetro `cuerpo`
  para elegir; queda para 0.2.4.

## 0.2.2 — 2026-11-06

Prueba de alto estrés (T-106): 41 comprobaciones por el protocolo real. Nueve defectos
corregidos.

### Corregido (estrés)

- Consulta de 54.000 caracteres tardaba 44 s: recorte a 24 términos de 64 caracteres.
- `vigente_al` con fecha inválida (`ayer`, `2020-13-45`, `2020-02-30`): viajaba a LeyChile,
  tardaba hasta 90 s y devolvía el texto de otra versión como si fuera la pedida. Ahora
  `[invalid_arg]` local.
- `vigente_al=2222-02-02` (centinela de vigencia diferida) devuelve `[invalid_arg]` con la
  explicación, en vez de una fecha falsa.
- `cl_citar` acepta una referencia suelta (`"6369/14"`) y la clasifica.
- `cl_documento`: `formato` por defecto `pdf` (odt + pdf); formato desconocido devuelve
  `[invalid_arg]` en vez de caer en silencio a PDF.
- `base_legal` sale de la plantilla: 1793 y 1801 del Código Civil para compraventa, 2116
  solo para el poder.
- La salida `.md` sustituye los campos (antes dejaba `{OTORGANTE}` por usar `.format`).
- Dos documentos simultáneos comparten carpeta: ya no se pisan el `.odt`.
- `traer_articulo` prefiltra en SQL y las conexiones se cierran: 40 llamadas concurrentes
  pasan de 7,2 s a 0,15 s.
- `_clave_articulo` acepta `art. 1545` y `Artículo 1545`.

### Corregido (ejercicio T-105, sin publicar hasta ahora)

- `fuente` salía `https://www.leychile.cl/N?i=None` en toda respuesta real.
- La cita de un artículo derogado decía «texto vigente desde».
- `[not_found]` sin nombre de norma.
- El documento generado no citaba base legal.
- Falta la Ley 19.496 (consumidor) en el corpus.
- Los números de artículo con sufijo `(DEL ART. 2)` no se encontraban.

## 0.2.0 — 2026-11-06

- Primera publicación en PyPI y en el registro oficial.
- 7 tools, 8 normas, 6.098 artículos, historial de versiones con confianza.
- 27 fichas notariales, banco de 66 tareas, `server.json`.
