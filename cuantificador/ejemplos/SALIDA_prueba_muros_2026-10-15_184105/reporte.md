# Reporte de cuantificación – prueba_muros

- Fecha: 2026-10-15 18:41:05
- Plano original: `/home/user/AGENTES-DE-CLOUDE/cuantificador/tests/prueba_muros.dxf`
- sha256 original (inicio / fin): `ecc79badd04017f4b0d76ea839f6dd5d716a4b1a6e04d10c3c1ab8b150e4ff56` / `ecc79badd04017f4b0d76ea839f6dd5d716a4b1a6e04d10c3c1ab8b150e4ff56` → sin cambios
- Capas de origen: A-MURO
- Unidades: $INSUNITS = 6 (m); factor a metros usado = 1.0
- Espesores reconocidos (m): 0.10, 0.15, 0.20; nivel N1; altura de muro: 2.8
- Tiempo de proceso: 0.14 s

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

## Cantidades generadas

| Elemento | Capa | Cantidad de objetos | Longitud | Unidad |
|---|---|---|---|---|
| Cimiento corrido | Cimiento corrido CC-PRUEBA1 de 0.40 x 0.20 m | 10 | 43.200 | m |
| Cimiento corrido | Cimiento corrido CC-PRUEBA2 de 0.50 x 0.20 m | 1 | 6.000 | m |
| Muro | N1 Muro de 10cm | 1 | 2.900 | m |
| Muro | N1 Muro de 15cm | 12 | 41.875 | m |
| Muro | N1 Muro de 20cm | 1 | 6.000 | m |
| Vano puerta | N1 Muro de 15cm - Vano puerta | 2 | 1.825 | m |

## Marcas en REVISION por motivo

| Motivo | Marcas |
|---|---|
| eje muy corto | 1 |
| espesor fuera de lista | 1 |
| segmento sin pareja | 1 |

## Avisos

- ODA File Converter no encontrado (C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe): se entrega solo el DXF.

## Archivos

- `ejemplos/SALIDA_prueba_muros_2026-10-15_184105/prueba_muros - CUANT.dxf`
- `ejemplos/SALIDA_prueba_muros_2026-10-15_184105/DataExtraction_prueba_muros.xlsx`
- `ejemplos/SALIDA_prueba_muros_2026-10-15_184105/reporte.md`

## Limitaciones de esta versión

- Solo muros rectos dibujados como pares de líneas paralelas (LINE, LWPOLYLINE, POLYLINE) en el espacio modelo; no lee bloques, xrefs, MLINE ni hatch.
- Los arcos (muros curvos) no se analizan: van a REVISION.
- Las ventanas no se detectan en planta (el muro sigue dibujado bajo la ventana).
- El vano en extremo libre (hueco de puerta entre el fin de un muro y la cara del que cruza) se deduce y queda con observación 'verificar'.
- No asigna ejes (EP1-EP3) ni trata mochetas, columnas ni pines.
- El bloque de muro es estático (ezdxf no crea el xMuro dinámico): el largo va en el atributo LARGO y en la escala X.
- La regla de esquinas es un supuesto hasta que Chris la confirme.
