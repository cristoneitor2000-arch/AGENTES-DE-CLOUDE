# Reporte de cuantificación – prueba_muros

- Fecha: 2026-10-15 19:56:35
- Plano original: `/home/user/AGENTES-DE-CLOUDE/cuantificador/tests/prueba_muros.dxf`
- sha256 original (inicio / fin): `d751f44235a6c2a1b6f5e38a85d23bbba19073c134d8cce648c9dbd4e4eed929` / `d751f44235a6c2a1b6f5e38a85d23bbba19073c134d8cce648c9dbd4e4eed929` → sin cambios
- Capas de origen: A-MURO
- Unidades: $INSUNITS = 6 (m); factor a metros usado = 1.0
- Espesores reconocidos (m): 0.10, 0.15, 0.20; nivel N1; altura de muro: 2.8
- Tiempo de proceso: 0.21 s

## Reconocimiento

| Concepto | Valor | Unidad |
|---|---|---|
| Segmentos analizados (LINE + polilíneas explotadas) | 65 | u |
| Arcos (no analizados) | 0 | u |
| Segmentos de longitud cero (omitidos) | 0 | u |
| Segmentos reconocidos completos | 56 | u |
| % reconocido por número de segmentos | 86.15 | % |
| Longitud de líneas analizadas | 113.390 | m |
| Longitud reconocida | 104.350 | m |
| % reconocido por longitud | 92.03 | % |
| Bloques del emplantillado analizados | 0 | u |
| Bloques dentro de un muro reconocido | 0 | u |
| % de bloques reconocidos | 0.00 | % |

## Cantidades generadas

| Elemento | Capa | Cantidad de objetos | Longitud | Unidad |
|---|---|---|---|---|
| Cimiento corrido | Cimiento corrido CC1 de 0.40 x 0.20 m | 10 | 43.200 | m |
| Cimiento corrido | Cimiento corrido MC1 de 0.50 x 0.20 m | 1 | 6.000 | m |
| Muro | N1 Muro de 10cm | 1 | 2.950 | m |
| Muro | N1 Muro de 15cm | 12 | 41.725 | m |
| Muro | N1 Muro de 20cm | 1 | 6.000 | m |
| Vano puerta | N1 Muro de 15cm - Vano puerta | 2 | 1.825 | m |

## Marcas en REVISION por motivo

| Motivo | Marcas |
|---|---|
| eje muy corto | 1 |
| espesor fuera de lista | 1 |
| esquina en L sin mocheta | 1 |
| segmento sin pareja | 1 |

## Avisos

- ODA File Converter no encontrado (C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe): se entrega solo el DXF.

## Archivos

- `ejemplos/SALIDA_prueba_muros_2026-10-15_195635/prueba_muros - CUANT.dxf`
- `ejemplos/SALIDA_prueba_muros_2026-10-15_195635/DataExtraction_prueba_muros.xlsx`
- `ejemplos/SALIDA_prueba_muros_2026-10-15_195635/reporte.md`

## Limitaciones de esta versión

- Muros rectos: caras dibujadas como pares de líneas (LINE, LWPOLYLINE, POLYLINE) o emplantillado de blocks (INSERT). No lee xrefs no enlazados, MLINE ni hatch como muro.
- Los arcos (muros curvos) no se analizan: van a REVISION.
- Las ventanas no se detectan en planta (el muro sigue dibujado bajo la ventana).
- El vano en extremo libre (hueco de puerta entre el fin de un muro y la cara del que cruza) se deduce y queda con observación 'verificar'.
- Mochetas y columnas solo se usan para recortar extremos de muro y descontar en vanos (no se cuantifican). En una L sin mocheta, la regla del motor deja la esquina sin muro.
- No asigna ejes (EP1-EP3).
- El bloque de muro es estático (ezdxf no crea el xMuro dinámico): el largo va en el atributo LARGO y en la escala X.
- El tipo de cimiento sale de las etiquetas del plano: un eje sin etiqueta a <= 2.2 m o con etiquetas de tipos distintos queda sin cimiento y va a REVISION.
