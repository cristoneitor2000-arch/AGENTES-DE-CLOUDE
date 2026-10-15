"""lector.py – lee el DXF, lista capas y extrae los segmentos de las capas de origen (en metros).

Las polilíneas se explotan a segmentos solo en memoria (virtual_entities): el archivo no se toca.
"""
import hashlib
import math
from dataclasses import dataclass

import ezdxf
from ezdxf import recover

# $INSUNITS -> metros por unidad de dibujo
FACTOR_UNIDADES = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}
NOMBRE_UNIDADES = {0: "sin unidad", 1: "pulgadas", 2: "pies", 4: "mm", 5: "cm", 6: "m"}
TIPOS = ("LINE", "LWPOLYLINE", "POLYLINE")


@dataclass
class Seg:
    id: int
    p0: tuple
    p1: tuple
    handle: str      # handle de la entidad original (una polilínea da varios segmentos con el mismo handle)
    capa: str
    tipo: str

    @property
    def largo(self):
        return math.dist(self.p0, self.p1)


@dataclass
class Arco:
    id: int
    centro: tuple
    radio: float
    a0: float        # grados
    a1: float
    handle: str
    capa: str

    @property
    def largo(self):
        da = (self.a1 - self.a0) % 360.0
        return math.radians(da) * self.radio

    @property
    def medio(self):
        a = math.radians(self.a0 + ((self.a1 - self.a0) % 360.0) / 2)
        return (self.centro[0] + self.radio * math.cos(a), self.centro[1] + self.radio * math.sin(a))


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def leer(ruta):
    """Devuelve (doc, avisos). Si la estructura está dañada usa recover."""
    try:
        return ezdxf.readfile(ruta), []
    except ezdxf.DXFStructureError:
        doc, aud = recover.readfile(ruta)
        return doc, [f"DXF recuperado con recover: {len(aud.errors)} errores, {len(aud.fixes)} correcciones"]


def unidades(doc):
    """(codigo $INSUNITS, nombre, factor a metros o None si no se puede saber)."""
    u = int(doc.header.get("$INSUNITS", 0) or 0)
    return u, NOMBRE_UNIDADES.get(u, f"código {u}"), FACTOR_UNIDADES.get(u)


def listar_capas(doc):
    """[(capa, n_lineas)] de todas las capas de la tabla; n = LINE/LWPOLYLINE/POLYLINE en el espacio modelo."""
    n = {}
    for e in doc.modelspace():
        if e.dxftype() in TIPOS:
            n[e.dxf.layer] = n.get(e.dxf.layer, 0) + 1
    nombres = {L.dxf.name for L in doc.layers} | set(n)
    return sorted(((c, n.get(c, 0)) for c in nombres), key=lambda x: x[0].lower())


def _es_polilinea_2d3d(e):
    return e.dxftype() != "POLYLINE" or e.is_2d_polyline or e.is_3d_polyline


def extraer(doc, capas, factor, tol_cero=1e-9):
    """Segmentos y arcos de las capas elegidas, en metros. Devuelve (segs, arcos, n_cero, omitidos)."""
    capas = set(capas)
    segs, arcos, n_cero, omitidos = [], [], 0, []
    f = float(factor)

    def add_line(p0, p1, h, capa, tipo):
        nonlocal n_cero
        a = (p0[0] * f, p0[1] * f)
        b = (p1[0] * f, p1[1] * f)
        if math.dist(a, b) <= tol_cero:
            n_cero += 1
            return
        segs.append(Seg(len(segs), a, b, h, capa, tipo))

    for e in doc.modelspace():
        t = e.dxftype()
        if t not in TIPOS or e.dxf.layer not in capas:
            continue
        h, capa = e.dxf.handle, e.dxf.layer
        if t == "LINE":
            add_line(e.dxf.start, e.dxf.end, h, capa, t)
            continue
        if not _es_polilinea_2d3d(e):
            omitidos.append((h, capa, "POLYLINE de malla/caras: no analizada"))
            continue
        try:
            partes = list(e.virtual_entities())
        except Exception as ex:  # polilínea defectuosa
            omitidos.append((h, capa, f"no se pudo explotar: {ex}"))
            continue
        for v in partes:
            vt = v.dxftype()
            if vt == "LINE":
                add_line(v.dxf.start, v.dxf.end, h, capa, t)
            elif vt == "ARC":
                c = v.dxf.center
                if v.dxf.hasattr("extrusion") and v.dxf.extrusion.z < 0:  # OCS espejado
                    c = v.ocs().to_wcs(c)
                    a0, a1 = 180.0 - v.dxf.end_angle, 180.0 - v.dxf.start_angle
                else:
                    a0, a1 = v.dxf.start_angle, v.dxf.end_angle
                arcos.append(Arco(len(arcos), (c[0] * f, c[1] * f), v.dxf.radius * f, a0, a1, h, capa))
    return segs, arcos, n_cero, omitidos
