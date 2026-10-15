# Reporte de cuantificación – s1_cuant_fix

- Fecha: 2026-10-15 19:55:43
- Plano original: `/tmp/claude-0/-home-user-AGENTES-DE-CLOUDE/ef6b3bd4-0393-5a8b-8bd4-2e46e273e163/scratchpad/real/s1_cuant_fix.dxf`
- sha256 original (inicio / fin): `94e74d4c54d48b6574e8359b481ebf5e5a23b7adb50cb46372004a8d82719fed` / `94e74d4c54d48b6574e8359b481ebf5e5a23b7adb50cb46372004a8d82719fed` → sin cambios
- Capas de origen: BLOCK251, block0.14, block 008, BLOKS 008
- Unidades: $INSUNITS = 6 (m); factor a metros usado = 1.0
- Espesores reconocidos (m): 0.10, 0.15, 0.20; nivel SOT; altura de muro: vacía (solo LARGO)
- Tiempo de proceso: 6.63 s

## Reconocimiento

| Concepto | Valor | Unidad |
|---|---|---|
| Segmentos analizados (LINE + polilíneas explotadas) | 0 | u |
| Arcos (no analizados) | 0 | u |
| Segmentos de longitud cero (omitidos) | 0 | u |
| Segmentos reconocidos completos | 0 | u |
| % reconocido por número de segmentos | 0.00 | % |
| Longitud de líneas analizadas | 0.000 | m |
| Longitud reconocida | 0.000 | m |
| % reconocido por longitud | 0.00 | % |
| Bloques del emplantillado analizados | 760 | u |
| Bloques dentro de un muro reconocido | 760 | u |
| % de bloques reconocidos | 100.00 | % |

## Cantidades generadas

| Elemento | Capa | Cantidad de objetos | Longitud | Unidad |
|---|---|---|---|---|
| Cimiento corrido | Cimiento corrido CC1 de 0.70 x 0.25 m | 9 | 27.880 | m |
| Cimiento corrido | Cimiento corrido CC1 de 0.70 x 0.25 m (dentro de zapata) | 10 | 22.204 | m |
| Cimiento corrido | Cimiento corrido MC1 de 1.00 x 0.30 m | 12 | 59.995 | m |
| Cimiento corrido | Cimiento corrido MC1 de 1.00 x 0.30 m (dentro de zapata) | 9 | 26.384 | m |
| Muro | SOT Muro de 10cm | 8 | 8.421 | m |
| Muro | SOT Muro de 15cm | 21 | 54.496 | m |
| Muro | SOT Muro de 20cm | 5 | 19.784 | m |
| Muro | SOT Muro de contencion de 30cm | 14 | 108.800 | m |
| Vano puerta | SOT Muro de 10cm - Vano puerta | 1 | 1.130 | m |
| Vano puerta | SOT Muro de 15cm - Vano puerta | 8 | 6.893 | m |
| Vano puerta | SOT Muro de 20cm - Vano puerta | 1 | 1.250 | m |

## Marcas en REVISION por motivo

| Motivo | Marcas |
|---|---|
| cimiento sin etiqueta | 10 |
| esquina en L sin mocheta | 2 |
| etiqueta sin tramo de su tipo | 6 |
| etiquetas de tipos distintos | 4 |
| hueco no clasificado | 20 |

## Avisos

- ODA File Converter no encontrado (C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe): se entrega solo el DXF.

## Archivos

- `/home/user/AGENTES-DE-CLOUDE/cuantificador/resultados/casa_jps_sotano_S-1/A_solo_etiquetas/SALIDA_s1_cuant_fix_2026-10-15_195543/s1_cuant_fix - CUANT.dxf`
- `/home/user/AGENTES-DE-CLOUDE/cuantificador/resultados/casa_jps_sotano_S-1/A_solo_etiquetas/SALIDA_s1_cuant_fix_2026-10-15_195543/DataExtraction_s1_cuant_fix.xlsx`
- `/home/user/AGENTES-DE-CLOUDE/cuantificador/resultados/casa_jps_sotano_S-1/A_solo_etiquetas/SALIDA_s1_cuant_fix_2026-10-15_195543/reporte.md`

## Limitaciones de esta versión

- Muros rectos: caras dibujadas como pares de líneas (LINE, LWPOLYLINE, POLYLINE) o emplantillado de blocks (INSERT). No lee xrefs no enlazados, MLINE ni hatch como muro.
- Los arcos (muros curvos) no se analizan: van a REVISION.
- Las ventanas no se detectan en planta (el muro sigue dibujado bajo la ventana).
- El vano en extremo libre (hueco de puerta entre el fin de un muro y la cara del que cruza) se deduce y queda con observación 'verificar'.
- Mochetas y columnas solo se usan para recortar extremos de muro y descontar en vanos (no se cuantifican). En una L sin mocheta, la regla del motor deja la esquina sin muro.
- No asigna ejes (EP1-EP3).
- El bloque de muro es estático (ezdxf no crea el xMuro dinámico): el largo va en el atributo LARGO y en la escala X.
- El tipo de cimiento sale de las etiquetas del plano: un eje sin etiqueta a <= 2.2 m o con etiquetas de tipos distintos queda sin cimiento y va a REVISION.
