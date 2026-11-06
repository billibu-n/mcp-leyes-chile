# Historial de versiones

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
