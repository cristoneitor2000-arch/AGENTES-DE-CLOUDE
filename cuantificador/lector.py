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
    """[(capa, n_lineas, n_insert)] de todas las capas de la tabla (conteo en el espacio modelo)."""
    n, b = {}, {}
    for e in doc.modelspace():
        t = e.dxftype()
        if t in TIPOS:
            n[e.dxf.layer] = n.get(e.dxf.layer, 0) + 1
        elif t == "INSERT":
            b[e.dxf.layer] = b.get(e.dxf.layer, 0) + 1
    nombres = {L.dxf.name for L in doc.layers} | set(n) | set(b)
    return sorted(((c, n.get(c, 0), b.get(c, 0)) for c in nombres), key=lambda x: x[0].lower())


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


# ---------------------------------------------------------------- bloques, polígonos y etiquetas
@dataclass
class Bloque:
    """Pieza del emplantillado (un INSERT = un block de mampostería), como rectángulo orientado."""
    id: int
    centro: tuple
    d: tuple          # dirección del lado largo
    largo: float
    ancho: float
    handle: str
    capa: str


@dataclass
class Etiqueta:
    texto: str
    x: float
    y: float
    handle: str
    capa: str


def _dentro(p, ventana):
    return ventana is None or (ventana[0] <= p[0] <= ventana[2] and ventana[1] <= p[1] <= ventana[3])


def _puntos_insert(e):
    pts = []
    for v in e.virtual_entities():
        t = v.dxftype()
        if t == "LINE":
            pts += [v.dxf.start, v.dxf.end]
        elif t == "LWPOLYLINE":
            pts += list(v.vertices_in_wcs())
        elif t == "POLYLINE":
            pts += [x.dxf.location for x in v.vertices]
        elif t == "INSERT":
            pts += _puntos_insert(v)
        elif t == "SOLID" or t == "3DFACE":
            pts += [v.dxf.get(a) for a in ("vtx0", "vtx1", "vtx2", "vtx3") if v.dxf.hasattr(a)]
    return [(p[0], p[1]) for p in pts]


def rectangulo_minimo(pts):
    """(centro, d, largo, ancho) del rectángulo mínimo rotado."""
    from shapely.geometry import MultiPoint
    r = MultiPoint(pts).minimum_rotated_rectangle
    if r.geom_type != "Polygon":
        return None
    c = list(r.exterior.coords)[:4]
    l0, l1 = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    a, b = (c[0], c[1]) if l0 >= l1 else (c[1], c[2])
    L, W = max(l0, l1), min(l0, l1)
    if L <= 0:
        return None
    d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    if d[0] < -1e-12 or (abs(d[0]) <= 1e-12 and d[1] < 0):
        d = (-d[0], -d[1])
    cen = r.centroid
    return (cen.x, cen.y), d, L, W


def extraer_bloques(doc, capas, factor, ventana=None):
    """INSERT de las capas elegidas como rectángulos orientados (en metros). Devuelve (bloques, sin_geometria)."""
    capas = set(capas)
    out, malos = [], []
    for e in doc.modelspace().query("INSERT"):
        if e.dxf.layer not in capas:
            continue
        try:
            pts = [(x * factor, y * factor) for x, y in _puntos_insert(e)]
        except Exception:
            pts = []
        rm = rectangulo_minimo(pts) if len(pts) >= 3 else None
        if rm is None:
            malos.append((e.dxf.handle, e.dxf.layer))
            continue
        c, d, L, W = rm
        if not _dentro(c, ventana):
            continue
        out.append(Bloque(len(out), c, d, L, W, e.dxf.handle, e.dxf.layer))
    return out, malos


def extraer_poligonos(doc, capas, factor, ventana=None):
    """Contornos de columnas/mochetas o zapatas (en metros): polilíneas cerradas, hatch, INSERT (rectángulo
    mínimo de su geometría) y polígonos que cierran las líneas sueltas (polygonize)."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import polygonize, unary_union
    capas = set(capas)
    f = float(factor)
    polys, lineas = [], []
    for e in doc.modelspace():
        if e.dxf.layer not in capas:
            continue
        t = e.dxftype()
        try:
            if t == "LWPOLYLINE":
                pts = [(x * f, y * f) for x, y in ((p[0], p[1]) for p in e.vertices_in_wcs())]
                if e.closed and len(pts) >= 3:
                    polys.append(Polygon(pts))
                elif len(pts) >= 2:
                    lineas.append(LineString(pts))
            elif t == "POLYLINE" and (e.is_2d_polyline or e.is_3d_polyline):
                pts = [(v.dxf.location[0] * f, v.dxf.location[1] * f) for v in e.vertices]
                if e.is_closed and len(pts) >= 3:
                    polys.append(Polygon(pts))
                elif len(pts) >= 2:
                    lineas.append(LineString(pts))
            elif t == "LINE":
                lineas.append(LineString([(e.dxf.start[0] * f, e.dxf.start[1] * f), (e.dxf.end[0] * f, e.dxf.end[1] * f)]))
            elif t == "HATCH":
                for path in e.paths:
                    if hasattr(path, "vertices") and len(path.vertices) >= 3:
                        polys.append(Polygon([(v[0] * f, v[1] * f) for v in path.vertices]))
            elif t == "INSERT":
                pts = [(x * f, y * f) for x, y in _puntos_insert(e)]
                if len(pts) >= 3:
                    from shapely.geometry import MultiPoint
                    r = MultiPoint(pts).minimum_rotated_rectangle
                    if r.geom_type == "Polygon":
                        polys.append(r)
        except Exception:
            continue
    if lineas:
        polys += list(polygonize(unary_union(lineas)))
    polys = [p.buffer(0) for p in polys if p.is_valid or p.buffer(0).area > 0]
    polys = [p for p in polys if p.area > 1e-6 and _dentro((p.centroid.x, p.centroid.y), ventana)]
    return polys


def extraer_etiquetas(doc, factor, ventana=None):
    """TEXT, MTEXT y atributos del espacio modelo (en metros)."""
    out = []
    f = float(factor)

    def add(texto, p, h, capa):
        q = (p[0] * f, p[1] * f)
        if texto and _dentro(q, ventana):
            out.append(Etiqueta(texto.strip(), q[0], q[1], h, capa))

    for e in doc.modelspace():
        t = e.dxftype()
        try:
            if t == "TEXT":
                p = e.dxf.align_point if (e.dxf.halign or e.dxf.valign) and e.dxf.hasattr("align_point") else e.dxf.insert
                add(e.dxf.text, p, e.dxf.handle, e.dxf.layer)
            elif t == "MTEXT":
                add(e.plain_text(), e.dxf.insert, e.dxf.handle, e.dxf.layer)
            elif t == "INSERT":
                for a in e.attribs:
                    add(a.dxf.text, a.dxf.insert, a.dxf.handle, e.dxf.layer)
        except Exception:
            continue
    return out


def filtrar_ventana(segs, arcos, ventana):
    if ventana is None:
        return segs, arcos
    s2 = [s for s in segs if _dentro(((s.p0[0] + s.p1[0]) / 2, (s.p0[1] + s.p1[1]) / 2), ventana)]
    for i, s in enumerate(s2):
        s.id = i
    a2 = [a for a in arcos if _dentro(a.medio, ventana)]
    for i, a in enumerate(a2):
        a.id = i
    return s2, a2
