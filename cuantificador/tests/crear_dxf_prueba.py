"""Crea tests/prueba_muros.dxf: casos conocidos de muros dibujados por sus caras (metros, $INSUNITS = 6).

Cada caso está separado en X. Los contornos salen de la unión (shapely) de los rectángulos de cada muro,
como los dibujaría un arquitecto: caras continuas, cortadas solo donde llega otro muro.
Casos y longitudes esperadas: ver ESPERADO en test_muros.py.
"""
import os
import sys

import ezdxf
from shapely.geometry import Polygon
from shapely.ops import unary_union

AQUI = os.path.dirname(os.path.abspath(__file__))
CAPA = "A-MURO"


def rect(p0, p1, t):
    """Rectángulo de un muro de eje p0-p1 (horizontal o vertical) y espesor t."""
    (x0, y0), (x1, y1) = p0, p1
    if abs(y1 - y0) < 1e-12:
        a, b = sorted((x0, x1))
        return Polygon([(a, y0 - t / 2), (b, y0 - t / 2), (b, y0 + t / 2), (a, y0 + t / 2)])
    a, b = sorted((y0, y1))
    return Polygon([(x0 - t / 2, a), (x0 + t / 2, a), (x0 + t / 2, b), (x0 - t / 2, b)])


def contornos(polys):
    u = unary_union(polys)
    geoms = getattr(u, "geoms", [u])
    out = []
    for g in geoms:
        out.append(list(g.exterior.coords)[:-1])
        for r in g.interiors:
            out.append(list(r.coords)[:-1])
    return out


def dibujar(msp, polys, como="poli"):
    for pts in contornos(polys):
        if como == "poli":
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": CAPA})
        else:
            for a, b in zip(pts, pts[1:] + pts[:1]):
                msp.add_line(a, b, dxfattribs={"layer": CAPA})


def crear(ruta):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = 6
    doc.header["$INSUNITS"] = 6
    doc.layers.add(CAPA, color=7)
    doc.layers.add("A-TEXTO", color=3)
    doc.layers.add("A-COTA", color=2)
    msp = doc.modelspace()
    # 1 recto 0.15 (LINE)
    dibujar(msp, [rect((0, 0), (4, 0), 0.15)], "line")
    # 2 L 0.15: esquina en (10,0); A hasta (14,0), B hasta (10,3)
    dibujar(msp, [rect((9.925, 0), (14, 0), 0.15), rect((10, -0.075), (10, 3), 0.15)])
    # 3 T 0.15: A (20,0)-(26,0); B x=23 de y=0 a 3
    dibujar(msp, [rect((20, 0), (26, 0), 0.15), rect((23, 0), (23, 3), 0.15)])
    # 3b T mixta: A 0.20 (60,0)-(66,0); B 0.10 x=63 de y=0 a 3
    dibujar(msp, [rect((60, 0), (66, 0), 0.20), rect((63, 0), (63, 3), 0.10)], "line")
    # 4 cruz 0.15: A (30,0)-(36,0); B x=33 de y=-2 a 2
    dibujar(msp, [rect((30, 0), (36, 0), 0.15), rect((33, -2), (33, 2), 0.15)])
    # 5 muro con vano de 0.90: (40,0)-(46,0), puerta de x=42 a 42.90
    dibujar(msp, [rect((40, 0), (42, 0), 0.15), rect((42.9, 0), (46, 0), 0.15)], "line")
    # 6 segmento suelto
    msp.add_line((50, 0), (52, 0), dxfattribs={"layer": CAPA})
    # 7 espesor fuera de lista (0.25)
    dibujar(msp, [rect((70, 0), (73, 0), 0.25)], "line")
    # 8 muro corto: 0.12 de largo x 0.15
    dibujar(msp, [rect((80, 0), (80.12, 0), 0.15)])
    # 9 vano en extremo libre: muro (90,0)-(93,0) y muro perpendicular x=94 de y=-2 a 2 -> hueco 0.925
    dibujar(msp, [rect((90, 0), (93, 0), 0.15)], "line")
    dibujar(msp, [rect((94, -2), (94, 2), 0.15)])
    # machote: textos y una línea en capa 0 (deben ir a 00)
    msp.add_text("PLANTA DE PRUEBA", dxfattribs={"layer": "A-TEXTO", "height": 0.3}).set_placement((0, 5))
    msp.add_line((0, -3), (100, -3), dxfattribs={"layer": "0"})
    doc.saveas(ruta)
    return ruta


if __name__ == "__main__":
    print(crear(sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "prueba_muros.dxf")))
