"""Crea una cuantificación "a mano" SINTÉTICA de prueba_muros.dxf para probar comparar.py.

Diferencias puestas a propósito respecto de lo que debe salir del programa:
- el "cuantificador humano" sí tomó como muro de 15 cm el segmento suelto (x 50-52)  -> FALTANTE de 2.000 m
- no marcó el vano en extremo libre del caso 9 (93.000-93.925)                         -> SOBRANTE de 0.925 m
- muros dibujados como polilíneas cerradas (no bloques) y la L partida distinto (a ejes) -> mismo total
Cimiento con las reglas de PRUEBA (CC-PRUEBA1 0.40, CC-PRUEBA2 0.50).
"""
import os
import sys

import ezdxf
from openpyxl import Workbook

AQUI = os.path.dirname(os.path.abspath(__file__))
M15, V15, M10, M20 = "N1 Muro de 15cm", "N1 Muro de 15cm - Vano puerta", "N1 Muro de 10cm", "N1 Muro de 20cm"
C1, C2 = "Cimiento corrido CC1 de 0.40 x 0.20 m", "Cimiento corrido CC2 de 0.50 x 0.20 m"

# (capa, x0, y0, x1, y1, espesor) -> rectángulo cerrado sobre el eje
MUROS = [
    (M15, 0, 0, 4, 0, .15),
    (M15, 10, 0, 14, 0, .15), (M15, 10, 0, 10, 3, .15),                 # L a ejes: 4 + 3 = 7
    (M15, 20, 0, 26, 0, .15), (M15, 23, .075, 23, 3, .15),
    (M20, 60, 0, 66, 0, .20), (M10, 63, .10, 63, 3, .10),
    (M15, 30, 0, 36, 0, .15), (M15, 33, -2, 33, -.075, .15), (M15, 33, .075, 33, 2, .15),
    (M15, 40, 0, 42, 0, .15), (V15, 42, 0, 42.9, 0, .15), (M15, 42.9, 0, 46, 0, .15),
    (M15, 50, 0, 52, 0, .15),                                          # el segmento suelto, tomado como muro
    (M15, 90, 0, 93, 0, .15), (M15, 94, -2, 94, 2, .15),               # sin el vano en extremo
]
CIM = [
    (C1, [(0, 0), (4, 0)]), (C1, [(14, 0), (10, 0), (10, 3)]), (C1, [(20, 0), (26, 0)]), (C1, [(23, .2), (23, 3)]),
    (C2, [(60, 0), (66, 0)]), (C1, [(30, 0), (36, 0)]), (C1, [(33, -2), (33, -.2)]), (C1, [(33, .2), (33, 2)]),
    (C1, [(40, 0), (46, 0)]), (C1, [(50, 0), (52, 0)]), (C1, [(90, 0), (93.8, 0)]), (C1, [(94, -2), (94, 2)]),
]


def crear(dxf, xlsx):
    doc = ezdxf.new("R2018")
    doc.units = 6
    msp = doc.modelspace()
    rows = []
    for capa, x0, y0, x1, y1, t in MUROS:
        if capa not in doc.layers:
            doc.layers.add(capa)
        h = t / 2
        pts = [(x0, y0 - h), (x1, y1 - h), (x1, y1 + h), (x0, y0 + h)] if y0 == y1 else [(x0 - h, y0), (x1 - h, y1), (x1 + h, y1), (x0 + h, y0)]
        e = msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": capa})
        rows.append((capa, "Polyline", e.dxf.handle, abs(x1 - x0) + abs(y1 - y0)))
    for capa, pts in CIM:
        if capa not in doc.layers:
            doc.layers.add(capa)
        e = msp.add_lwpolyline(pts, dxfattribs={"layer": capa})
        L = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(pts, pts[1:]))
        rows.append((capa, "Polyline", e.dxf.handle, L))
    doc.saveas(dxf)
    wb = Workbook()
    ws = wb.active
    ws.title = "Extraccion"
    ws.append(["Name", "Layer", "Handle", "Length"])
    for capa, nm, h, L in rows:
        ws.append([nm, capa, h, L])
    wb.save(xlsx)


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else AQUI
    crear(os.path.join(d, "manual_prueba.dxf"), os.path.join(d, "manual_prueba.xlsx"))
    print("ok")
