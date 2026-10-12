---
name: flujo-cuantificacion-chris
description: Flujo de trabajo y reglas obligatorias de Chris para cuantificar cualquier proyecto en AutoCAD (DWG/DXF/PDF) y pasar a Excel: capa 00, grupos de capas de cuantificación, bloqueo de capas, orden de dibujo, nombres de archivo con fecha, muros con altura total en vanos, muros de contención como grupo independiente, representación por polilíneas o bloques, y formato de Excel (extracciones y comparativos limpios; PPTO y memoria solo cantidades y precios). Úsala siempre que se reciban planos para cuantificar, se cree o corrija un script/LISP de cuantificación, se arme un grupo de capas, se guarde un DWG o Excel de cuantificación, o se prepare una extracción, comparativo, memoria de cálculo o presupuesto.
---

# Flujo de cuantificación de Chris

Reglas de trabajo obligatorias. Tienen prioridad sobre cualquier script, plantilla o costumbre anterior. Si un script existente las contradice, corrige primero el script y después cuantifica.

## 1. Flujo general

Planos recibidos (PDF / DWG / DXF + información) → **cuantificación en AutoCAD** → extracción a Excel → memoria de cálculo → presupuesto (PPTO).

- Trabaja con criterio propio de ingeniero. No hagas preguntas de rutina: decide, avanza y declara el supuesto en el reporte. Solo detente si falta un dato que bloquea la cuantificación y no hay supuesto técnicamente defendible.
- Si AutoCAD, el DWG o el script da error, resuélvelo tú (AUDIT, RECOVER, corregir el script, etc.) y reporta qué falló y cómo se corrigió.
- Lectura de planos: libre (PDF, DWG o DXF), pero completa. Lee plantas, secciones, detalles, cuadros, notas y especificaciones; cruza la información y reporta discrepancias.

## 2. Preparación del DWG

1. Al abrir el plano, crear la capa **`00`** y pasar **todo el contenido original** a esa capa.
2. Bloquear **todas** las capas.
3. Desbloquear solo la capa **`0`** y las capas de cuantificación con las que se va a trabajar.
4. Optimizar el archivo: borrar del Model los objetos que no sirven ni ayudan a la cuantificación (lo que no aporte geometría, ejes, cotas o referencias útiles), luego `PURGE` (incluye regapps) y `AUDIT`. El DWG final debe quedar liviano.
5. Todo lo trazado para cuantificar debe verse **sobre** la planta, nunca debajo: enviar el plano (capa 00) al fondo y la cuantificación al frente (`DRAWORDER`), hatches con orden de dibujo al frente.

## 3. Grupos de capas (filtros de grupo)

Estructura jerárquica: **Cuantificación → Disciplina/Sistema → Elemento → capas individuales**.

Ejemplo, 10 zapatas:
```
Cuantificación
└── Cimentación
    └── Zapatas
        ├── Z-01 ... Z-10   (10 capas, una por zapata o por tipo según el caso)
```

- Al guardar, el DWG queda con **todo bloqueado excepto la capa 0 y las capas de los grupos de cuantificación**.

### Muros de contención: grupo independiente y completo
Si el proyecto tiene muro de contención, se crea **su propio grupo de capas con todos sus elementos**: cimientos, zapatas, muros, mochetas, columnas, soleras, pines, vigas, etc. según el plano.
- **Nunca** mezclar elementos del muro de contención con los elementos generales de la edificación (ni en capas, ni en grupos, ni en la extracción).

```
Cuantificación
├── Cimentación ...           (edificación)
├── Muros ...                 (edificación)
└── Muro de contención
    ├── Cimientos / Zapatas
    ├── Muros
    ├── Mochetas / Columnas
    ├── Soleras
    └── Pines ...
```

## 4. Representación de elementos

| Elemento | Representación |
|---|---|
| Cimientos (corridos) | Polilíneas |
| Elementos estructurales (zapatas, columnas, mochetas, vigas, etc.) | Bloques con atributos editables con doble clic, como un bloque normal |
| Muros | Bloque dinámico de muro con parámetros de altura y eje (el mismo que ya se ha usado en cuantificaciones anteriores) |
| Instalaciones hidrosanitarias (IHS) e eléctricas (IEE) | Misma mecánica: recorridos/tuberías con polilíneas, elementos individuales (artefactos, cajas, tomas, luminarias, registros, etc.) con bloques |

## 5. Muros: regla de vanos (corrección obligatoria)

- En los tramos de **vanos de puertas y ventanas**, el bloque de muro lleva la **altura total del muro**, **no 2.10 m** ni la altura del vano.
- Motivo: el formato de Excel descuenta (resta) las áreas de vanos por su cuenta. Si en CAD se pone la altura del vano o se descuenta ahí, el vano se resta dos veces.
- Verificación antes de entregar: ningún bloque de muro debe tener altura = 2.10 m (u otra altura de puerta/ventana) salvo que el muro realmente mida eso; revisar que el descuento de vanos exista una sola vez (en el Excel).

## 6. Nomenclatura de archivos

DWG y Excel con fecha en formato inglés al inicio: `AAAA_MM_DD_Cuant_<Disciplina>_<nivel o área>`

Ejemplos:
- `2026_10_12_Cuant_Cimentacion_Nivel1.dwg`
- `2026_10_12_Cuant_Muros_AreaA.xlsx`
- `2026_10_12_Cuant_MuroContencion_Lindero.dwg`

Sin tildes ni espacios en el nombre. Nunca sobrescribir el original: cada versión es un archivo nuevo.

## 7. Excel

**Extracciones de datos y comparativos** (se presentan a jefes):
- Limpios, entendibles, sin ruido visual: pocos colores, sin bordes excesivos, sin columnas auxiliares visibles.
- Todo centrado y bien ordenado (secuencia constructiva / por grupo de capas), encabezados claros, unidades en su propia columna, totales evidentes.
- Arial 10, negro, salvo que el formato del destinatario indique otro.

**Libros de PPTO y memoria de cálculo**:
- **No se toca nada del formato ni de la estética existente.** Solo se ingresan cantidades y precios en las celdas correspondientes.
- No insertar/eliminar filas, columnas, hojas, estilos ni fórmulas salvo instrucción expresa.

## 8. Checklist antes de entregar

- [ ] Todo el plano original en capa `00`; capas bloqueadas salvo `0` y cuantificación.
- [ ] Grupos de capas jerárquicos; muro de contención en grupo propio y completo.
- [ ] Cimientos = polilíneas; estructurales = bloques editables; muros = bloque dinámico; IHS/IEE = polilíneas + bloques.
- [ ] Muros en vanos con altura total (ninguna altura 2.10 m indebida).
- [ ] Cuantificación dibujada sobre la planta (draworder).
- [ ] DWG optimizado (objetos inútiles borrados, PURGE, AUDIT sin errores).
- [ ] Nombres `AAAA_MM_DD_Cuant_...` en DWG y Excel.
- [ ] Extracción/comparativo limpio; PPTO y memoria sin cambios de formato.
- [ ] Reporte: supuestos, discrepancias de planos, errores corregidos y limitaciones.
