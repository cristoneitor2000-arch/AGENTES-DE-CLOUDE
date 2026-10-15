# Cuantificador automático DXF → DWG (prueba v1: muros y cimiento corrido)

Recibe un plano DXF (o DWG convertido con ODA), reconoce los muros dibujados por sus caras, genera el trazo de
cuantificación con las convenciones de Chris y entrega DXF, DWG, Excel de data extraction y reporte.
**Alcance: solo muros y cimiento corrido.**

## Uso

| Forma | Comando |
|---|---|
| Interfaz | `python app.py`, o `Cuantificador.exe` después de `build.bat` |
| Consola | `python pipeline.py PLANO.dxf --capas "A-MURO" [--espesores 0.10,0.15,0.20] [--nivel N1] [--altura 2.80] [--factor 1]` |
| Comparar contra lo hecho a mano | `python comparar.py --mio "<plano> - CUANT.dxf" --manual "<a mano>.dxf" --excel "<a mano>.xlsx" --config config.json --salida comparacion.xlsx` |
| Pruebas | `python -m pytest tests -q` (en Linux sin pantalla: `xvfb-run -a python -m pytest tests -q`) |
| Empaquetar | `build.bat` (en Windows) genera `dist\Cuantificador.exe` y copia los JSON junto al exe |

Requisitos: Python 3.11 o superior, `pip install -r requirements.txt` (ezdxf, openpyxl, shapely). tkinter viene con Python en Windows.

## Salidas (carpeta nueva `SALIDA_<nombre>_<fecha>` junto al plano)

| Archivo | Contenido |
|---|---|
| `<nombre> - COPIA ORIGINAL.dxf` | Copia de trabajo. El original no se abre para escribir; se compara su sha256 al inicio y al final |
| `<nombre> - CUANT.dxf` | Machote en la capa 00 más las capas de cuantificación |
| `<nombre> - CUANT.dwg` | Solo si se encuentra ODA (`config.json > oda_exe`). Si no, se avisa y se entrega solo el DXF |
| `DataExtraction_<nombre>.xlsx` | Hojas DATOS (una fila por objeto, con handle), RESUMEN (COUNTIFS/SUMIFS), REVISION y PARAMETROS. Arial 10, negro, centrado |
| `reporte.md` | Segmentos analizados, % reconocido, marcas REVISION por motivo, tiempo de proceso, avisos y limitaciones |

## Convenciones (`convenciones.json`, se editan sin tocar código)

Salen de las skills `cuantificar-mamposteria-cad` (`gen/est.py`, `est.lsp`), `qa-dxf-cuantificacion` y `dxf-unificado-cuantificacion`.

| Elemento | Capa | Entidad | Color | Transparencia |
|---|---|---|---|---|
| Machote | `00` (bloqueada); el resto de capas originales también bloqueadas | Todo el espacio modelo de la copia | 8 | — |
| Muro | `{nivel} Muro de {cm}cm` | INSERT del bloque estático `xMuro {cm}`: rectángulo de 1 m × espesor con hatch sólido dentro del bloque, escala X = largo en m, atributos ID, TIPO, ESPESOR, LARGO, ALTO, AREA (color 250, invisibles) | 1 | 50 % |
| Vano de puerta | `{nivel} Muro de {cm}cm - Vano puerta` | El mismo `xMuro`, solo el largo del vano | 42 | 50 % |
| Cimiento corrido | `Cimiento corrido {tipo} de {ancho} x {peralte} m` | LWPOLYLINE abierta por el eje, ancho global = ancho real, al fondo del orden de dibujo | Según la regla | 50 % |
| REVISION | `REVISION` | Círculo rojo y TEXT `Rnnn motivo` | 1 | — |

Grupos de capas: `CUANTIFICACION` > `MUROS` > `MUROS {nivel}`, y `CUANTIFICACION` > `CIMIENTO CORRIDO`.

**Reglas de cimiento: PENDIENTES.** `cimiento.reglas` está vacío. Mientras Chris no las llene, todo eje de muro va a
REVISION con "sin regla de cimiento". Formato:

```json
"reglas": {
  "0.10": {"con_cimiento": false},
  "0.15": {"con_cimiento": true, "tipo": "CC1", "ancho": 0.40, "peralte": 0.20, "color": 2}
}
```

## Cómo reconoce los muros (`muros.py`)

1. Toma LINE, LWPOLYLINE y POLYLINE de las capas elegidas. Las polilíneas se explotan solo en memoria.
2. Agrupa por dirección (`tol_angular`) y une los segmentos colineales que se tocan o traslapan.
3. Empareja paralelas cuya separación es un espesor de la lista (± `tol_espesor`) y que se traslapan en proyección; el eje es el tramo de traslape. Si una línea tiene dos parejas que se traslapan, es **traslape ambiguo** y va a REVISION.
4. Une ejes colineales del mismo espesor según el hueco entre ellos:

   | Hueco | Resultado |
   |---|---|
   | ≤ `union_max` (0.25 m) | Se une; es el paso de un muro que cruza |
   | `vano_min` a `vano_max` (0.60 a 2.05 m) | Vano de puerta |
   | Entre 0.25 y 0.60 m | REVISION ("hueco no clasificado") |

5. Resuelve los encuentros. **[Supuesto] pendiente de confirmar por Chris:**

   | Encuentro | Muros | Cimiento |
   |---|---|---|
   | L | El más largo se lleva la esquina; el otro llega a su cara | Los dos llegan al cruce de ejes y se unen en una polilínea |
   | T | El que llega termina en la cara del corrido | Termina en la cara del cimiento que cruza |
   | Cruz | El más largo sigue continuo; el otro se corta en sus caras | Igual que los muros |
   | Vano en extremo libre (0.60 a 2.05 m hasta la cara del muro que cruza) | Se traza el vano con la observación "verificar" | — |

   El cimiento pasa corrido por los vanos.
6. Revisa la cobertura: toda porción de línea de origen que no cae dentro de un muro o vano generado va a REVISION con su motivo:

   | Motivo | Cuándo |
   |---|---|
   | Segmento sin pareja | No hay paralela a distancia de muro |
   | Espesor fuera de lista | Hay paralela, pero a una separación que no está en la lista |
   | Eje muy corto | Eje menor que `umbral_eje_corto` |
   | Traslape ambiguo | La línea tiene dos parejas posibles que se traslapan |
   | Arco no analizado | Arcos (muros curvos) |
   | Sin regla de cimiento | El espesor no tiene regla en `convenciones.json` |

Cálculos en metros, sin redondeo intermedio. El factor de unidades sale de `$INSUNITS` y se puede corregir en la interfaz.

## Pruebas (`tests/`, 22 pruebas)

- `prueba_muros.dxf` (lo genera `crear_dxf_prueba.py`) trae estos casos: recto, L, T, T de espesores mixtos (0.20 con 0.10), cruz, muro con vano de 0.90, vano en extremo libre, segmento suelto, espesor fuera de lista (0.25) y muro corto (0.12). Las longitudes esperadas se calcularon a mano y están en `test_muros.py`.
- `convenciones_prueba.json` trae reglas de cimiento **de prueba** (no son de Chris): 0.10 sin cimiento, 0.15 ancho 0.40 y 0.20 ancho 0.50.
- `manual_prueba.dxf` y `manual_prueba.xlsx` son una cuantificación "a mano" sintética con diferencias puestas a propósito, para probar `comparar.py`.
- `test_pipeline.py` corre el proceso completo y revisa:
  - el `qa_dxf.py` de la skill sale sin ERROR;
  - el sha256 del original no cambia;
  - grupos, capas, colores y transparencia;
  - que cada handle del Excel exista en el DXF.
- `test_app.py` prueba la interfaz con Xvfb.

`ejemplos/SALIDA_prueba_muros_*` es el resultado sobre el plano de prueba **con las reglas de cimiento de prueba**: DXF, Excel, reporte, comparación y QA.

## Limitaciones conocidas (v1)

- Solo muros rectos dibujados como pares de líneas en el espacio modelo. No lee bloques, xrefs, MLINE ni hatch como muro.
- Los arcos no se analizan.
- Las ventanas no se detectan en planta.
- No asigna ejes (EP1 a EP3) ni trata mochetas, columnas ni pines. La regla de mocheta del skill (la toma el muro más largo) no está aplicada.
- El `xMuro` es estático; el dinámico de la oficina no se puede crear con ezdxf.
- DWG solo con ODA File Converter instalado. En el entorno de desarrollo no hubo ODA (dominio bloqueado), así que `convertir.py` no se probó contra ODA real.
- El `.exe` se genera en Windows con `build.bat`. En Linux se probó el empaquetado con PyInstaller (binario ELF), no el `.exe`.
