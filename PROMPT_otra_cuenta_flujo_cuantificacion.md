Crea una habilidad (skill) permanente llamada "flujo-cuantificacion-chris" con el contenido de abajo. Si no puedes crear habilidades en esta cuenta, guárdalo en tu memoria como reglas obligatorias. Aplícala siempre que yo te pase planos (PDF, DWG o DXF) para cuantificar, cuando hagas o corrijas scripts/LISP de cuantificación, y cuando prepares extracciones, comparativos, memorias de cálculo o presupuestos. Confirma al final qué guardaste y dónde.

=== CONTENIDO DE LA HABILIDAD ===

FLUJO: Planos recibidos (PDF/DWG/DXF + información) → cuantificación en AutoCAD → extracción a Excel → memoria de cálculo → PPTO.
- Trabaja con criterio propio de ingeniero; no hagas preguntas de rutina: decide, avanza y declara supuestos. Solo detente si falta un dato que bloquea y no hay supuesto defendible.
- Si AutoCAD, el DWG o un script da error, resuélvelo tú (AUDIT, RECOVER, corregir el script) y reporta qué pasó.
- Lee los planos completos (plantas, secciones, detalles, cuadros, notas); el medio (PDF, DWG o DXF) es libre. Cruza información y reporta discrepancias.
- Si un script existente contradice estas reglas, corrige el script primero.

PREPARACIÓN DEL DWG:
1. Al abrir el plano, crear la capa "00" y meter todo el plano original en ella.
2. Bloquear todas las capas.
3. Desbloquear solo la capa "0" y las capas de cuantificación con las que se trabaja.
4. Borrar del Model todo objeto que no sirva para cuantificar, luego PURGE y AUDIT. El archivo debe quedar optimizado y liviano.
5. Lo trazado para cuantificar se ve SOBRE la planta, nunca debajo (DRAWORDER: plano al fondo, cuantificación al frente).
6. Guardar con todo bloqueado excepto la capa 0 y los grupos de capas de cuantificación.

GRUPOS DE CAPAS: jerarquía Cuantificación → Disciplina → Elemento → capas individuales.
Ejemplo 10 zapatas: Cuantificación > Cimentación > Zapatas > Z-01 ... Z-10.
MURO DE CONTENCIÓN: si existe, tiene su propio grupo con TODOS sus elementos (cimientos, zapatas, muros, mochetas, columnas, soleras, pines, vigas, etc.). Nunca mezclarlos con los elementos generales de la edificación.

REPRESENTACIÓN:
- Cimientos: polilíneas.
- Elementos estructurales (zapatas, columnas, mochetas, vigas, etc.): bloques con atributos editables con doble clic, como bloque normal.
- Muros: bloque dinámico de muro con parámetros de altura y eje.
- IHS e IEE: misma mecánica; recorridos con polilíneas y elementos individuales con bloques.

MUROS – REGLA DE VANOS: en vanos de puertas y ventanas el bloque de muro lleva la ALTURA TOTAL DEL MURO, no 2.10 m ni la altura del vano, porque el formato de Excel resta las áreas de vanos. Verifica que ningún muro quede con 2.10 m indebidamente y que el vano se descuente una sola vez.

NOMBRES DE ARCHIVO (DWG y Excel): AAAA_MM_DD_Cuant_<Disciplina>_<nivel o área>, sin tildes ni espacios.
Ej.: 2026_10_12_Cuant_Cimentacion_Nivel1.dwg. Nunca sobrescribir el original.

EXCEL:
- Extracciones de datos y comparativos (se presentan a jefes): muy limpios, entendibles, sin ruido visual, todo centrado y ordenado, unidades en columna propia, totales claros, Arial 10 negro.
- PPTO y memoria de cálculo: NO se toca nada de formato ni estética; solo se ingresan cantidades y precios.

CHECKLIST ANTES DE ENTREGAR: capa 00 y bloqueos correctos; grupos jerárquicos y muro de contención separado; representación correcta por tipo; muros en vanos con altura total; cuantificación sobre la planta; DWG optimizado (PURGE/AUDIT); nombres con fecha; Excel limpio o PPTO intacto; reporte de supuestos, discrepancias, errores corregidos y limitaciones.
