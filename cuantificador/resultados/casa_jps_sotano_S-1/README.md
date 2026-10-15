# Prueba real: Casa JPS, sótano (S-1)

## Archivos recibidos

| Archivo | Uso en la prueba | sha256 |
|---|---|---|
| `SOTANO - CIMENTACION ZAPATAS Y PINES S-1 - CUANT.dwg` | Entrada: capas originales del plano, más tu cimiento | `5f50eb5f…3b55` |
| `2026_10_12_Cuant_Cimentacion.dwg` | Referencia de muros y vanos a mano: xMuro SOT, contención, tabiques | `f6a1c3f0…3f26` |

Los originales no se modificaron: el sha256 de las copias coincide con el de lo subido.

## Conversión DWG a DXF

En este entorno no hay ODA File Converter (el dominio está bloqueado por la red), así que se usó LibreDWG 0.13.3 compilado desde el código fuente.
`dwg2dxf` deja los INSERT de bloques dinámicos con el nombre `*U` (781 y 820 referencias). Se repararon con `herramientas/libredwg_fix_u.py`, que toma de `dwgread -O JSON` el handle del bloque de cada INSERT. Después de la reparación quedaron 0 INSERT sin definición. Con ODA, en Windows, este paso no hace falta.

## Corrida (`pipeline.py`)

| Parámetro | Valor | Fuente |
|---|---|---|
| Capas de muros (emplantillado) | `BLOCK251, block0.14, block 008, BLOKS 008` (760 blocks de 0.40 × 0.15/0.20) | [Dato] plano |
| Espesor por capa | `BLOKS 008 = 0.10` | [Supuesto] Deducido de la comparación: esos blocks miden 0.15, pero en tu archivo son muros de 10 cm. **Confirmar** |
| Ventana | x −36 a 14, y −19 a 11 m (planta; excluye los detalles) | [Dato] plano |
| Tipos de cimiento | CC1 0.70 × 0.25 (color 2/52), MC1 1.00 × 0.30 (color 4/144) | [Dato] tu mensaje y los colores de tus capas |
| Etiquetas | 40 TEXT en la capa TEX5 (22 MC1, 18 CC1) | [Dato] plano |
| Zapatas | Tus capas `Zapata Z1…Z8` (bloques ya cuantificados) | [Supuesto] La capa `ZAPATA` del plano trae contornos abiertos e incompletos |
| Columnas / mochetas | `MOCHETAS 004` (2 polígonos). Las columnas reales están en `Xref_Muros_Sotano`, que no viene en el DWG | [Dato] |
| Variante A | Tipo de cimiento solo por etiquetas (comportamiento por defecto) | |
| Variante B | A más tipo por defecto para ejes sin etiqueta: contención = MC1, otros = CC1 | [Supuesto] Tomado de tu skill (JPS 5b) |

## Muros contra `2026_10_12_Cuant_Cimentacion` (iguales en A y B)

| Clase | Automático (m) | A mano (m) | Diferencia (m) | Diferencia % |
|---|---|---|---|---|
| Muro de contención 30 cm | 108.800 | 114.825 | −6.025 | −5.25 % |
| Muro 20 cm | 19.784 | 20.499 | −0.715 | −3.49 % |
| Muro 15 cm | 54.496 | 51.789 | +2.707 | +5.23 % |
| Muro 10 cm | 8.421 | 6.867 | +1.554 | +22.64 % |
| **Total de muros** | **191.501** | **193.980** | **−2.479** | **−1.28 %** |
| Vanos (10 + 15 + 20) | 9.273 | 4.730 | +4.543 | +96 % |

Causas, verificadas en la superposición:

1. **Faltan las mochetas y columnas** (están en el xref).
   - En tus esquinas el muro más largo llega a la cara lejana de la mocheta. Aquí la regla recorta medio espesor y se pierden 0.3–1.1 m por esquina.
   - Los huecos que en realidad son columnas salen como "hueco no clasificado" (20 marcas) o como vanos de más.
2. **Muro norte, tramo x −11.6 a −8.1.** En el emplantillado es una sola hilada (15 cm); en tu cuantificación es contención. Explica +3.1 m en 15 cm y −3.5 m en contención.
3. **Tabiques.** Con `BLOKS 008 = 0.10`, los tabiques cuadran en posición. Sobran 3 tramos de 10 cm:
   - 0.58 m en x = −2.41, que a mano es un vano de 10 cm (0.66 m);
   - dos blocks sueltos de 0.40 m de `BLOKS 008` junto a la contención noreste (x ≈ 8.4, y ≈ 4.8), que a mano no se cuentan.

## Cimiento contra `S-1 - CUANT`

| Clase | A: auto (m) | B: auto (m) | A mano (m) | Diferencia A | Diferencia B |
|---|---|---|---|---|---|
| CC1 0.70 | 27.880 | 31.998 | 42.030 | −33.7 % | −23.9 % |
| CC1 0.70 dentro de zapata | 22.204 | 25.630 | 40.445 | −45.1 % | −36.6 % |
| MC1 1.00 | 59.995 | 72.037 | 86.506 | −30.7 % | −16.7 % |
| MC1 1.00 dentro de zapata | 26.384 | 31.705 | 36.302 | −27.3 % | −12.7 % |

- **Sobrantes:** casi 0 (1 o 2 tramos). El programa no inventa cimiento.
- **Faltantes:** todos tienen muro al lado; ninguno es una franja sin muro.

| Causa del faltante (variante B) | Longitud |
|---|---|
| Ejes con marca REVISION (sin etiqueta a ≤ 2.2 m, o con etiquetas CC1 y MC1 a la vez). En el muro norte las etiquetas están más cerca del muro de 15 cm que del de contención | ≈ 31.2 m |
| Muros de 10 cm (`BLOKS 008`) que en tu S-1 sí llevan cimiento, contra la regla "tabiques de 0.10 sin cimiento" | ≈ 6.7 m |
| Extremos de franja, sin marca | ≈ 6.5 m |

## Marcas REVISION

| Motivo | Marcas en A | Marcas en B |
|---|---|---|
| Hueco no clasificado (columnas del xref) | 20 | 20 |
| Cimiento sin etiqueta | 10 | 2 |
| Etiqueta sin tramo de su tipo | 6 | 3 |
| Etiquetas de tipos distintos | 4 | 4 |
| Esquina en L sin mocheta | 2 | 2 |

## Para cerrar la diferencia

1. **Subir `Xref_Muros_Sotano.dwg`.** Trae las mochetas y columnas, y posiblemente los muros que no están en el emplantillado.
2. **Confirmar** que `BLOKS 008` son tabiques de 10 cm, y si esos tabiques llevan cimiento o no.
3. **Revisar las 4 marcas** "etiquetas de tipos distintos" del muro norte.
