# Contrato de citas (R1–R6)

Reglas que el agente debe cumplir al usar la skill. Están tomadas del contrato
del servidor `mcp-leyes-chile` y adaptadas al corpus local.

## R1 — Sin texto verificado no hay cita

Si `consulta.py articulo` devuelve `{"error": "no_encontrado"}`, el artículo no
está en el corpus. No lo reconstruyas de memoria ni cites "aproximadamente".
Declara el hueco y ofrece buscar otra norma o el texto oficial.

## R2 — Vigencia diferida

Si `vigente_desde` es `2222-02-02` (centinela), la norma tiene vigencia diferida
por evento. No pongas fecha; escribe: "vigencia diferida, verificar el evento".

## R3 — Derogado

Si `estado` es `derogado`, la cita se escribe con `(derogado)` y el artículo no
se usa como derecho aplicable. Sirve para explicar historia, no para fundar una
demanda o un contrato.

## R4 — Fuente enlazada

Toda cita lleva la URL que devuelve el script (`https://www.leychile.cl/N?i=ID`).
Sin URL no es cita verificable.

## R5 — Formato

- Norma con punto de miles: Ley 19.496, Ley 19.628, DL 825.
- Artículo: `art. 1793`, `art. 31 bis`.
- Fecha ISO: `2020-05-30`.

## R6 — Aviso

Todo entregable termina con:

> Esto no es asesoría legal. Verifica con un profesional antes de actuar.

## Qué no es una cita

- "El Código Civil dice que…" sin artículo.
- Un artículo sin fecha de versión.
- Un resumen de un buscador sin abrir el texto completo.
- Una cita de jurisprudencia: el corpus no la tiene.
