# Reporte de cuantificación – prueba_bloques

- Fecha: 2026-10-15 19:56:36
- Plano original: `/home/user/AGENTES-DE-CLOUDE/cuantificador/tests/prueba_bloques.dxf`
- sha256 original (inicio / fin): `b8622b87498445394a7b04dce2c2ca5cb13a3f4729aa35193b78c88c6fcd339f` / `b8622b87498445394a7b04dce2c2ca5cb13a3f4729aa35193b78c88c6fcd339f` → sin cambios
- Capas de origen: BLK, TABIQUE
- Unidades: $INSUNITS = 6 (m); factor a metros usado = 1.0
- Espesores reconocidos (m): 0.10, 0.15, 0.20; nivel N1; altura de muro: 2.8
- Tiempo de proceso: 0.14 s

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
| Bloques del emplantillado analizados | 68 | u |
| Bloques dentro de un muro reconocido | 68 | u |
| % de bloques reconocidos | 100.00 | % |

## Cantidades generadas

| Elemento | Capa | Cantidad de objetos | Longitud | Unidad |
|---|---|---|---|---|
| Cimiento corrido | Cimiento corrido CC1 de 0.40 x 0.20 m | 3 | 12.700 | m |
| Cimiento corrido | Cimiento corrido CC1 de 0.40 x 0.20 m (dentro de zapata) | 1 | 2.000 | m |
| Cimiento corrido | Cimiento corrido MC1 de 0.50 x 0.20 m | 1 | 6.200 | m |
| Muro | N1 Muro de 10cm | 1 | 2.000 | m |
| Muro | N1 Muro de 15cm | 4 | 13.800 | m |
| Muro | N1 Muro de contencion de 30cm | 1 | 6.200 | m |
| Vano puerta | N1 Muro de 15cm - Vano puerta | 1 | 0.900 | m |

## Marcas en REVISION por motivo

Sin marcas.

## Avisos

- ODA File Converter no encontrado (C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe): se entrega solo el DXF.

## Archivos

- `ejemplos/SALIDA_prueba_bloques_2026-10-15_195636/prueba_bloques - CUANT.dxf`
- `ejemplos/SALIDA_prueba_bloques_2026-10-15_195636/DataExtraction_prueba_bloques.xlsx`
- `ejemplos/SALIDA_prueba_bloques_2026-10-15_195636/reporte.md`

## Limitaciones de esta versión

- Muros rectos: caras dibujadas como pares de líneas (LINE, LWPOLYLINE, POLYLINE) o emplantillado de blocks (INSERT). No lee xrefs no enlazados, MLINE ni hatch como muro.
- Los arcos (muros curvos) no se analizan: van a REVISION.
- Las ventanas no se detectan en planta (el muro sigue dibujado bajo la ventana).
- El vano en extremo libre (hueco de puerta entre el fin de un muro y la cara del que cruza) se deduce y queda con observación 'verificar'.
- Mochetas y columnas solo se usan para recortar extremos de muro y descontar en vanos (no se cuantifican). En una L sin mocheta, la regla del motor deja la esquina sin muro.
- No asigna ejes (EP1-EP3).
- El bloque de muro es estático (ezdxf no crea el xMuro dinámico): el largo va en el atributo LARGO y en la escala X.
- El tipo de cimiento sale de las etiquetas del plano: un eje sin etiqueta a <= 2.2 m o con etiquetas de tipos distintos queda sin cimiento y va a REVISION.
