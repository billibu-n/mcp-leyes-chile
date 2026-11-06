---
name: leyes-chile
description: Investiga y redacta derecho chileno con citas verificables. Busca en un corpus local de 9 normas y 6.852 textos de artículo (LeyChile/BCN) y devuelve norma, artículo, texto y URL. Úsala cuando pidan "qué dice la ley", "cita el artículo", revisar o redactar contratos chilenos (compraventa, arrendamiento, mandato, poder) o resolver dudas de Código Civil, Código del Trabajo, Código Penal, Código de Comercio, IVA, consumidor, datos personales o notarial.
when_to_use: |
  - Consultas sobre legislación chilena y citas de artículos.
  - Redacción o revisión de contratos chilenos y escrituras.
  - Verificar el texto vigente de un artículo antes de usarlo.
  - NO usar para derecho extranjero ni para asesoría legal personalizada.
---

# Leyes Chile — citas verificables

## Qué hace

Busca en un corpus local descargado de LeyChile (Biblioteca del Congreso Nacional)
y devuelve el texto del artículo con su norma, número, fecha de versión y URL.
No inventa citas: si el artículo no está, lo dice.

## Corpus

9 normas, 6.852 textos de artículo: Código Civil, Código del Trabajo, Código de
Comercio, Código Penal, Constitución, DL 825 (IVA), Ley 19.496 (consumidor),
Ley 19.628 (datos personales) y Decreto 587 (arancel de notarios).

No incluye jurisprudencia, doctrina ni historia de la ley. No reemplaza la
consulta al texto oficial cuando el asunto es complejo.

## Comandos

Ejecuta desde la carpeta de la skill. El script no usa red ni escribe archivos.

```bash
python3 scripts/consulta.py normas
python3 scripts/consulta.py buscar "compraventa" --limite 5
python3 scripts/consulta.py buscar "despido injustificado" --norma 207436
python3 scripts/consulta.py articulo 172986 1793
```

`--norma` acepta el idNorma (172986 Código Civil, 207436 Código del Trabajo,
1974 Comercio, 1984 Penal, 242302 Constitución, 6369 DL 825, 61438 Ley 19.496,
141599 Ley 19.628, 127917 Decreto 587).

## Flujo obligatorio

1. **Identifica la norma.** Si no sabes el idNorma, corre `normas`.
2. **Busca con dos o tres formulaciones.** "compraventa", "contrato de compraventa",
   "vendedor comprador". Si no hay resultados, dilo; no inventes el artículo.
3. **Lee el artículo completo** con `articulo` antes de citarlo. El extracto del
   buscador no basta para redactar.
4. **Cita** con el formato: `Norma, art. N, texto vigente desde AAAA-MM-DD` y la URL.
   Si el artículo está derogado, dilo y no lo presentes como derecho vigente.
5. **Redacta** cada afirmación jurídica con su cita al lado. Separa hechos de derecho.

## Reglas de cita

- **R1** Sin texto verificado no hay cita. Si `articulo` devuelve `no_encontrado`,
  no hay respuesta: declara el hueco.
- **R2** Si la fecha de vigencia es el centinela `2222-02-02`, la vigencia está
  diferida por evento: no pongas fecha, declara el hueco.
- **R3** Artículo derogado: se marca `(derogado)` y no se usa como derecho aplicable.
- **R4** Toda cita lleva la URL de LeyChile que devuelve el script.
- **R5** Los números de norma van con punto de miles (Ley 19.496, no 19496).
- **R6** Cierra con el aviso: "Esto no es asesoría legal. Verifica con un
  profesional antes de actuar."

## Formato de salida

```
**Cita:** Código Civil, art. 1793, texto vigente desde 2000-05-30.
**Fuente:** https://www.leychile.cl/N?i=172986
**Texto:** "La compraventa es un contrato en que una de las partes se obliga a
dar una cosa y la otra a pagarla en dinero…"
**Aplicación:** [qué significa para el caso, en una o dos frases]
```

## Ejemplo

Consulta: "¿Qué exige el Código Civil para la compraventa?"

```bash
python3 scripts/consulta.py buscar "compraventa" --limite 3
python3 scripts/consulta.py articulo 172986 1793
```

Salida esperada: art. 1793 (definición), luego 1796 (prohibiciones) y las reglas
de capacidad. Cita cada uno con su fecha y URL; no resumas de memoria.

## Límites

- Corpus con fecha de descarga; un artículo puede haber cambiado después.
  Si el caso es urgente, contrasta con el texto oficial enlazado.
- No hay jurisprudencia: para "cómo han fallado los tribunales", dilo y no cites.
- No des asesoría personalizada ni calcules plazos o montos sin el texto que los fije.
- No escribas datos personales del cliente en el chat ni en los comandos.

Aviso: esto no es asesoría legal. Verifica con un profesional antes de actuar.
