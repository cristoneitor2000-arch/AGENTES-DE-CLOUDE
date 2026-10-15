# Cuantificador automático DXF → DWG (prueba v1: muros y cimiento corrido)

Recibe un plano DXF (o DWG convertido con ODA) y reconoce los muros dibujados de cualquiera de estas dos formas:
- por sus **caras** (pares de líneas);
- por el **emplantillado** de blocks.

Con eso genera el trazo de cuantificación con las convenciones de Chris y el cimiento corrido, y entrega DXF, DWG, Excel de data extraction y reporte.
**Alcance: solo muros y cimiento corrido.**

## Uso

| Forma | Comando |
|---|---|
| Interfaz | `python app.py`, o `Cuantificador.exe` después de `build.bat` |
| Consola | `python pipeline.py PLANO.dxf --capas "BLOCK251,BLOKS 008" --nivel SOT --tipos tipos.json --zapatas "Zapata Z1…" --columnas "MOCHETAS 004" --espesor-capa "BLOKS 008=0.10" [--tipo-defecto "contencion=MC1;otros=CC1"] [--ventana x0,y0,x1,y1] [--altura 2.80] [--factor 1]` |
| Comparar con lo hecho a mano | `python comparar.py --mio "<plano> - CUANT.dxf" --manual "<a mano>.dxf" [--excel "<a mano>.xlsx"] --config config.json --salida comparacion.xlsx` |
| Pruebas | `python -m pytest tests -q` (en Linux sin pantalla: `xvfb-run -a python -m pytest tests -q`) |
| Empaquetar | `build.bat` en Windows genera `dist\Cuantificador.exe` y copia los JSON junto al exe |

Requisitos: Python 3.11 o superior y `pip install -r requirements.txt` (ezdxf, openpyxl, shapely). En Windows, tkinter viene con Python.

### Interfaz

1. Seleccionar el plano. La interfaz lista las capas con su número de líneas y de blocks.
2. En la tabla de capas, marcar con clic el uso de cada una:
   - **Muros:** líneas de caras o blocks del emplantillado.
   - **Columnas / mochetas:** recortan los extremos de muro y se descuentan en los vanos.
   - **Zapatas:** separan el cimiento que cae dentro de zapata.
3. Cargar la **tabla de tipos de cimiento** del detalle estructural del proyecto: tipo, ancho × peralte, color y color dentro de zapata. Se puede guardar y cargar como JSON.
4. Parámetros:

   | Parámetro | Para qué |
   |---|---|
   | Espesores (por defecto 0.10 / 0.15 / 0.20) | Espesores de muro a reconocer |
   | Nivel | Prefijo de las capas (N1, SOT…) |
   | Altura | Opcional; vacía = solo LARGO |
   | Factor a metros | Sale de `$INSUNITS` |
   | Espesor por capa | Opcional, `capa=espesor`; p. ej. tabiques dibujados con block de 0.15 que son de 10 cm |
   | Tipo de cimiento para ejes sin etiqueta | Opcional; se declara por proyecto |
   | Ventana | Opcional; para no tomar los blocks de los detalles |

5. Cuantificar y abrir la carpeta de salida.

## Salidas (carpeta nueva `SALIDA_<nombre>_<fecha>` junto al plano)

| Archivo | Contenido |
|---|---|
| `<nombre> - COPIA ORIGINAL.dxf` | Copia de trabajo. El original no se abre para escribir; se compara su sha256 al inicio y al final |
| `<nombre> - CUANT.dxf` | Machote en la capa 00 más las capas de cuantificación |
| `<nombre> - CUANT.dwg` | Solo si se encuentra ODA (`config.json > oda_exe`). Si no, se avisa y se entrega solo el DXF |
| `DataExtraction_<nombre>.xlsx` | Hojas DATOS (una fila por objeto, con handle), RESUMEN (COUNTIFS/SUMIFS), REVISION y PARAMETROS. Arial 10, negro, centrado |
| `reporte.md` | Segmentos y blocks analizados, % reconocido, marcas REVISION por motivo, tiempo de proceso, avisos y limitaciones |

## Convenciones (`convenciones.json`, se editan sin tocar código)

| Elemento | Capa | Entidad | Color |
|---|---|---|---|
| Machote | `00` (bloqueada); el resto de capas originales también bloqueadas | Todo el espacio modelo de la copia | 8 |
| Muro | `{nivel} Muro de {cm}cm` | INSERT del bloque estático `xMuro {cm}`: rectángulo de 1 m × espesor con hatch dentro del bloque, escala X = largo, atributos ID, TIPO, ESPESOR, LARGO, ALTO, AREA (color 250) | 1 |
| Muro de contención (doble hilada) | `{nivel} Muro de contencion de 30cm`, en el grupo `MURO DE CONTENCION` | `xMuro 30` | 6 |
| Vano de puerta | `{nivel} Muro de {cm}cm - Vano puerta` | El mismo `xMuro`, solo el largo del vano | 42 |
| Cimiento corrido | `Cimiento corrido {tipo} de {ancho} x {peralte} m`, más `... (dentro de zapata)` | LWPOLYLINE abierta por el eje, ancho global = ancho, al fondo del orden de dibujo | Según la tabla |
| REVISION | `REVISION` | Círculo rojo y TEXT `Rnnn motivo` | 1 |

Transparencia del 50 % en las capas de cuantificación. Grupos de capas:
- `CUANTIFICACION` > `MUROS` > `MUROS {nivel}`
- `CUANTIFICACION` > `MURO DE CONTENCION`
- `CUANTIFICACION` > `CIMIENTO CORRIDO`

## Reglas (confirmadas por Chris)

### Muros

1. **Fuentes.**
   - Pares de líneas paralelas cuya separación es un espesor de la lista (± 5 mm).
   - Blocks del emplantillado: un INSERT de 0.15–0.60 × ≤ 0.26 m, cuyo ancho da el espesor (± 0.015).
2. **Doble hilada.** Dos hiladas a 0.12–0.19 m entre centros forman un muro de contención de 0.30. Las colas de ≤ 0.45 m se absorben. En la contención no hay puertas.
3. **Extremos** (motor `est.py`). El muro va de eje a eje. Donde otro eje pasa por su extremo, se recorta **medio espesor propio**. Si en el extremo hay mocheta o columna, el muro más largo que la toca llega a su cara lejana y los demás a la cara cercana. En un cruce, el más largo sigue continuo y el otro se parte en el eje. Una L sin mocheta deja la esquina sin muro y se marca en REVISION.
4. **Vano de puerta.** Claro libre de **0.70 a 1.50 m**, descontando columnas, entre muros colineales o desde el extremo libre hasta la cara del muro que cruza. Un hueco tapado por una columna se une. Un hueco entre 0.25 m y 0.70 m va a REVISION.

### Cimiento

1. **Tipo.** Sale de las **etiquetas del plano**: cada etiqueta (CC1, MC1…) se asigna al eje más cercano a ≤ 2.2 m.
2. **Validación.** Cada etiqueta debe tener un tramo de su tipo a ≤ 2.2 m.
3. **Eje sin etiqueta.**
   - Toma el tipo de su línea de muro, si es unánime.
   - Si no, el tipo por defecto declarado.
   - Si tampoco hay, va a REVISION.
4. **Etiquetas de tipos distintos** en un mismo eje: va a REVISION.
5. **Tabiques de 0.10:** sin cimiento.
6. **Trazo.** Las esquinas van al cruce de ejes (polilínea unida). En una T, hasta la cara del cimiento que cruza. Pasa corrido por los vanos. Lo que cae dentro de una zapata va en la capa `... (dentro de zapata)`.

## Pruebas (`tests/`)

| Archivo | Contenido |
|---|---|
| `prueba_muros.dxf` | Caras de muro: recto, L, T, T de espesores mixtos, cruz, vano de 0.90, vano en extremo libre, segmento suelto, espesor fuera de lista y muro corto, con etiquetas de cimiento |
| `prueba_bloques.dxf` | Emplantillado: puerta con columna, doble hilada, tabique con espesor por capa, L con columna en la esquina y zapata |
| `convenciones_prueba.json` | Tipos de cimiento **de prueba** (no son de Chris) |
| `manual_prueba.*` | Cuantificación "a mano" sintética con diferencias puestas a propósito, para `comparar.py` |

Hay 29 pruebas. Las longitudes esperadas se calcularon a mano. El QA `qa_dxf.py` de la skill sale sin ERROR.

| Carpeta | Contenido |
|---|---|
| `ejemplos/` | Salidas de los dos planos sintéticos |
| `resultados/casa_jps_sotano_S-1/` | Prueba contra el proyecto real, con su informe (`README.md`) |

## Limitaciones conocidas (v1)

- Solo muros rectos. No lee xrefs no enlazados, MLINE ni hatch como muro. Los arcos van a REVISION.
- Las ventanas no se ven en planta.
- Sin la capa de mochetas y columnas, las esquinas y los huecos de columna no se resuelven: van a REVISION.
- No asigna ejes (EP1 a EP3). El `xMuro` es estático, porque el dinámico no se puede crear con ezdxf.
- DWG solo con ODA File Converter. En el entorno de desarrollo se usó LibreDWG; su DXF necesita `herramientas/libredwg_fix_u.py` para los bloques dinámicos.
- El `.exe` se genera en Windows con `build.bat`. En Linux se probó el empaquetado con PyInstaller (binario ELF).
