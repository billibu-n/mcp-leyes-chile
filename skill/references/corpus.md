# Corpus de la skill

Descargado de LeyChile (Biblioteca del Congreso Nacional de Chile) y empaquetado
como texto legible (`data/corpus.jsonl`, una línea JSON por texto de artículo).

| idNorma | Norma | Textos |
|---|---|---:|
| 172986 | Código Civil | 2.839 |
| 207436 | Código del Trabajo | 854 |
| 1974 | Código de Comercio | 1.734 |
| 1984 | Código Penal | 798 |
| 242302 | Constitución | 269 |
| 6369 | DL 825 (IVA) | 146 |
| 61438 | Ley 19.496 (consumidor) | 170 |
| 141599 | Ley 19.628 (datos personales) | 35 |
| 127917 | Decreto 587 (arancel notarios) | 7 |

Total: 6.852 textos de artículo.

## Campos

`id_norma`, `norma`, `cuerpo` (cuerpo legal de origen), `seccion`, `nombre`
(número del artículo), `titulo`, `texto`, `derogado`, `transitorio`,
`fecha_version`, `url`.

## Nota sobre el DFL 1 (idNorma 172986)

Ese compendio contiene el Código Civil y varias leyes anexas (Registro Civil,
cambio de nombre, menores, abandono de familia, impuesto a las herencias). El
exportador conserva la jerarquía del XML y **solo incluye los artículos cuyo
cuerpo es el Código Civil**; así un "art. 31" no se atribuye al cuerpo equivocado.

## Actualización

El corpus se regenera con el exportador del proyecto (requiere red a LeyChile).
Si se actualiza, cambia también la fecha en `SKILL.md` y vuelve a correr las
pruebas de `PRUEBA.md`.
