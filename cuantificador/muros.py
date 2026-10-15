"""muros.py – reconocimiento de muros.

Dos fuentes, que se pueden mezclar:
  a) caras dibujadas con líneas: pares de paralelas a un espesor de la lista;
  b) emplantillado: cada INSERT es un block (rectángulo de 0.15–0.60 x <= 0.26 m); su ancho da el espesor.

Pasos
1. Agrupar por dirección (tolerancia angular). Líneas: unir colineales y emparejar paralelas (una línea con
   dos parejas que se traslapan = traslape ambiguo -> REVISION). Bloques: cada block es una pieza de eje.
2. Corridas: piezas colineales del mismo espesor. Hueco <= union_max (o tapado por columnas) se une;
   claro libre de vano_min a vano_max (0.70–1.50, descontando columnas) = vano de puerta; lo demás corta
   la corrida (si el hueco es menor que un vano -> REVISION).
3. Doble hilada: dos corridas paralelas a 0.12–0.19 entre centros = muro de contención (0.30); las
   hiladas sueltas cortas en sus extremos se absorben.
4. Encuentros entre ejes: L, T, cruz y vano en extremo libre (hueco de puerta hasta la cara del que cruza).
5. Tramos (regla del motor est.py de la oficina): el muro va de eje a eje; donde otro eje pasa por su
   extremo se recorta medio espesor PROPIO; si en el extremo hay mocheta/columna, el muro más largo que la
   toca llega a su cara lejana y los demás a la cara cercana (la mocheta intermedia es del muro que la
   contiene). En un cruce el más largo sigue continuo y el otro se parte en el eje.
Todo en metros, sin redondeo intermedio.
"""
import math
from dataclasses import dataclass, field


@dataclass
class Param:
    espesores: list
    tol_espesor: float = 0.005
    tol_angular: float = 0.5          # grados
    tol_colineal: float = 0.002
    tol_banda: float = 0.02           # desplazamiento máximo entre ejes de una misma corrida
    union_max: float = 0.25
    vano_min: float = 0.70
    vano_max: float = 1.50
    vano_en_extremo: bool = True
    umbral_eje_corto: float = 0.20
    tol_snap: float = 0.03
    angulo_min_esquina: float = 10.0  # grados; por debajo se consideran paralelos
    residuo_min: float = 0.05
    sep_busqueda_max: float = 0.60
    # emplantillado
    tol_ancho_block: float = 0.015
    block_largo_min: float = 0.15
    block_largo_max: float = 0.60
    block_ancho_max: float = 0.26
    doble_hilada_sep_min: float = 0.12
    doble_hilada_sep_max: float = 0.19
    doble_hilada_espesor: float = 0.30
    doble_hilada_absorber: float = 0.45
    doble_hilada_union: float = 2.05
    espesor_por_capa: dict = field(default_factory=dict)   # {"BLOKS 008": 0.10}: espesor declarado por capa
    # mochetas / columnas (est.py)
    toque_mocheta: float = 0.095
    mocheta_extremo: float = 0.35

    @classmethod
    def desde_config(cls, cfg, espesores=None, espesor_por_capa=None):
        kw = {k: cfg[k] for k in cls.__dataclass_fields__ if k in cfg}
        if espesores is not None:
            kw["espesores"] = list(espesores)
        if espesor_por_capa:
            kw["espesor_por_capa"] = {str(k): float(v) for k, v in espesor_por_capa.items()}
        return cls(**kw)


@dataclass
class Linea:
    id: int
    grupo: int
    c: float
    t0: float
    t1: float
    segs: list = field(default_factory=list)   # [(seg_id, t0, t1)]


@dataclass
class Pieza:
    linea_a: int
    linea_b: int
    esp: float
    sep: float
    c: float
    t0: float
    t1: float
    grupo: int
    ambigua: bool = False
    bloque: int = -1


@dataclass
class Corrida:
    """Eje de muro (una o varias piezas colineales del mismo espesor)."""
    id: int
    grupo: int
    d: tuple
    n: tuple
    c: float
    esp: float
    sep: float
    tramos: list                      # [[t0, t1, 'muro'|'vano']] sobre el eje, en orden
    lineas: set = field(default_factory=set)
    bloques: set = field(default_factory=set)
    ext: list = field(default_factory=lambda: [None, None])   # info de extremo [inicio, fin]
    cruces: list = field(default_factory=list)                # [(t, otra_id, sin)] donde se parte esta
    corta: bool = False
    doble: bool = False
    obs: str = ""

    @property
    def a(self):
        return self.tramos[0][0]

    @property
    def b(self):
        return self.tramos[-1][1]

    @property
    def largo(self):
        return self.b - self.a

    def punto(self, t):
        return (self.d[0] * t + self.n[0] * self.c, self.d[1] * t + self.n[1] * self.c)


@dataclass
class Revision:
    motivo: str
    x: float
    y: float
    detalle: str = ""
    handles: tuple = ()


@dataclass
class Resultado:
    lineas: list
    grupos: list            # [(d, n)]
    piezas: list
    corridas: list          # corridas válidas (no cortas)
    cortas: list            # corridas por debajo del umbral
    revisiones: list
    tramos: list = field(default_factory=list)   # tramos finales (dict)
    bloques_usados: set = field(default_factory=set)
    esquinas: list = field(default_factory=list)     # [(punto, polígono, esp_a, esp_b)] L sin mocheta


# ---------------------------------------------------------------- utilidades
def _dot(u, v):
    return u[0] * v[0] + u[1] * v[1]


def _cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


def _espesor(sep, P, tol=None):
    tol = P.tol_espesor if tol is None else tol
    best = None
    for e in P.espesores:
        if abs(sep - e) <= tol + 1e-12 and (best is None or abs(sep - e) < abs(sep - best)):
            best = e
    return best


def _dirgrupos(pares, tol_rad):
    """pares: [(p0, p1)]. Agrupa por dirección. Devuelve (grupo_de_cada_par, [(d, n)])."""
    if not pares:
        return [], []
    ang = [math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi for a, b in pares]
    lar = [math.dist(a, b) for a, b in pares]
    orden = sorted(range(len(pares)), key=lambda i: ang[i])
    clusters, cur = [], [orden[0]]
    for i in orden[1:]:
        if ang[i] - ang[cur[-1]] > tol_rad or ang[i] - ang[cur[0]] > 2 * tol_rad:
            clusters.append(cur)
            cur = [i]
        else:
            cur.append(i)
    clusters.append(cur)
    if len(clusters) > 1 and ang[clusters[0][0]] + math.pi - ang[clusters[-1][-1]] <= tol_rad:
        clusters[0] = clusters.pop() + clusters[0]
    gid = [0] * len(pares)
    dirs = []
    for g, cl in enumerate(clusters):
        sx = sy = 0.0
        for i in cl:
            gid[i] = g
            sx += lar[i] * math.cos(2 * ang[i])
            sy += lar[i] * math.sin(2 * ang[i])
        a = math.atan2(sy, sx) / 2
        d = (math.cos(a), math.sin(a))
        dirs.append((d, (-d[1], d[0])))
    return gid, dirs


# ---------------------------------------------------------------- paso 1a: líneas
def unir_colineales(segs, gid, dirs, P):
    por_grupo = {}
    for s in segs:
        g = gid[s.id]
        d, n = dirs[g]
        t0, t1 = _dot(d, s.p0), _dot(d, s.p1)
        if t0 > t1:
            t0, t1 = t1, t0
        mid = ((s.p0[0] + s.p1[0]) / 2, (s.p0[1] + s.p1[1]) / 2)
        por_grupo.setdefault(g, []).append((_dot(n, mid), t0, t1, s.id))
    lineas = []
    for g, items in por_grupo.items():
        items.sort()
        bandas, cur = [], [items[0]]
        for it in items[1:]:
            if it[0] - cur[-1][0] <= P.tol_colineal:
                cur.append(it)
            else:
                bandas.append(cur)
                cur = [it]
        bandas.append(cur)
        for b in bandas:
            b.sort(key=lambda x: x[1])
            actual = [b[0]]
            fin = b[0][2]
            for it in b[1:]:
                if it[1] <= fin + P.tol_colineal:
                    actual.append(it)
                    fin = max(fin, it[2])
                else:
                    lineas.append(_nueva_linea(len(lineas), g, actual))
                    actual, fin = [it], it[2]
            lineas.append(_nueva_linea(len(lineas), g, actual))
    return lineas


def _nueva_linea(i, g, items):
    L = sum(x[2] - x[1] for x in items)
    c = sum(x[0] * (x[2] - x[1]) for x in items) / L if L > 0 else items[0][0]
    return Linea(i, g, c, min(x[1] for x in items), max(x[2] for x in items), [(x[3], x[1], x[2]) for x in items])


def emparejar(lineas, P):
    emax = max(P.espesores) + P.tol_espesor
    por_grupo = {}
    for L in lineas:
        por_grupo.setdefault(L.grupo, []).append(L)
    piezas = []
    for g, ls in por_grupo.items():
        ls.sort(key=lambda L: L.c)
        for i, A in enumerate(ls):
            for B in ls[i + 1:]:
                sep = B.c - A.c
                if sep > emax:
                    break
                e = _espesor(sep, P)
                if e is None:
                    continue
                t0, t1 = max(A.t0, B.t0), min(A.t1, B.t1)
                if t1 - t0 <= P.tol_colineal * 5:
                    continue
                piezas.append(Pieza(A.id, B.id, e, sep, (A.c + B.c) / 2, t0, t1, g))
    por_linea = {}
    for k, p in enumerate(piezas):
        por_linea.setdefault(p.linea_a, []).append(k)
        por_linea.setdefault(p.linea_b, []).append(k)
    for ks in por_linea.values():
        for x in range(len(ks)):
            for y in range(x + 1, len(ks)):
                p, q = piezas[ks[x]], piezas[ks[y]]
                if min(p.t1, q.t1) - max(p.t0, q.t0) > P.tol_colineal * 5:
                    p.ambigua = q.ambigua = True
    return piezas


# ---------------------------------------------------------------- paso 1b: bloques del emplantillado
def piezas_de_bloques(bloques, gid0, gid, dirs, P, revisiones):
    piezas = []
    for k, B in enumerate(bloques):
        if not (P.block_largo_min - 1e-9 <= B.largo <= P.block_largo_max + 1e-9 and B.ancho <= P.block_ancho_max + 1e-9):
            revisiones.append(Revision("bloque no reconocido", B.centro[0], B.centro[1],
                                       f"INSERT de {B.largo:.3f} x {B.ancho:.3f} m: no es un block de mampostería "
                                       f"({P.block_largo_min}–{P.block_largo_max} x <= {P.block_ancho_max} m)", (B.handle,)))
            continue
        e = P.espesor_por_capa.get(B.capa) or _espesor(B.ancho, P, P.tol_ancho_block)
        if e is None:
            revisiones.append(Revision("bloque de ancho fuera de lista", B.centro[0], B.centro[1],
                                       f"block de {B.ancho:.3f} m de ancho (lista: {', '.join(f'{x:.2f}' for x in P.espesores)}"
                                       f" ± {P.tol_ancho_block})", (B.handle,)))
            continue
        g = gid[gid0 + k]
        d, n = dirs[g]
        tc = _dot(d, B.centro)
        piezas.append(Pieza(-1, -1, e, B.ancho, _dot(n, B.centro), tc - B.largo / 2, tc + B.largo / 2, g, bloque=B.id))
    return piezas


# ---------------------------------------------------------------- paso 2: corridas
def _cubierto_por_columnas(columnas, d, n, c, esp, a, b):
    """Intervalos [t0, t1] del hueco (a, b) tapados por columnas que cruzan la franja del muro."""
    if not columnas or b <= a:
        return []
    from shapely.geometry import Polygon
    p = lambda t, cc: (d[0] * t + n[0] * cc, d[1] * t + n[1] * cc)
    franja = Polygon([p(a, c - esp / 2), p(b, c - esp / 2), p(b, c + esp / 2), p(a, c + esp / 2)])
    out = []
    for col in columnas:
        if not col.intersects(franja):
            continue
        inter = col.intersection(franja)
        if inter.is_empty or inter.area <= 1e-9:
            continue
        ts = [_dot(d, q) for q in _coords(inter)]
        out.append((max(a, min(ts)), min(b, max(ts))))
    out.sort()
    fus = []
    for x, y in out:
        if fus and x <= fus[-1][1] + 1e-9:
            fus[-1] = (fus[-1][0], max(fus[-1][1], y))
        else:
            fus.append((x, y))
    return fus


def _coords(g):
    if hasattr(g, "geoms"):
        for h in g.geoms:
            yield from _coords(h)
    elif hasattr(g, "exterior"):
        yield from g.exterior.coords
    else:
        yield from g.coords


def _libres(a, b, tapados):
    out, cur = [], a
    for x, y in tapados:
        if x > cur:
            out.append((cur, x))
        cur = max(cur, y)
    if b > cur:
        out.append((cur, b))
    return out


def armar_corridas(piezas, dirs, P, revisiones, columnas=()):
    buenas = [p for p in piezas if not p.ambigua]
    clave = {}
    for p in buenas:
        clave.setdefault((p.grupo, p.esp), []).append(p)
    corridas = []
    for (g, e), ps in clave.items():
        d, n = dirs[g]
        ps.sort(key=lambda p: p.c)
        bandas, cur = [], [ps[0]]
        for p in ps[1:]:
            if p.c - cur[-1].c <= P.tol_banda:
                cur.append(p)
            else:
                bandas.append(cur)
                cur = [p]
        bandas.append(cur)
        for b in bandas:
            b.sort(key=lambda p: p.t0)
            cc = sum(q.c * (q.t1 - q.t0) for q in b) / sum(q.t1 - q.t0 for q in b)
            actual = [b[0]]
            tramos = [[b[0].t0, b[0].t1, "muro"]]
            for p in b[1:]:
                fin = tramos[-1][1]
                hueco = p.t0 - fin
                if hueco <= P.union_max:
                    tramos[-1][1] = max(fin, p.t1)
                    actual.append(p)
                    continue
                libres = _libres(fin, p.t0, _cubierto_por_columnas(columnas, d, n, cc, e, fin, p.t0))
                libre = sum(y - x for x, y in libres)
                if libre <= P.union_max:                      # el hueco lo tapa una columna: el muro sigue
                    tramos[-1][1] = p.t1
                    actual.append(p)
                elif len(libres) == 1 and P.vano_min - 1e-9 <= libre <= P.vano_max + 1e-9:
                    x, y = libres[0]
                    tramos[-1][1] = x                         # el muro llega a la columna (si la hay)
                    tramos.append([x, y, "vano"])
                    tramos.append([y, p.t1, "muro"])
                    actual.append(p)
                else:
                    if libre < P.vano_min:
                        cx = (fin + p.t0) / 2
                        revisiones.append(Revision("hueco no clasificado", d[0] * cx + n[0] * cc, d[1] * cx + n[1] * cc,
                                                   f"claro libre de {libre:.3f} m entre ejes colineales de {e:.2f} m "
                                                   f"(> unión {P.union_max} y < vano {P.vano_min})"))
                    corridas.append(_nueva_corrida(len(corridas), g, d, n, e, actual, tramos))
                    actual, tramos = [p], [[p.t0, p.t1, "muro"]]
            corridas.append(_nueva_corrida(len(corridas), g, d, n, e, actual, tramos))
    return corridas


def _nueva_corrida(i, g, d, n, e, ps, tramos):
    L = sum(p.t1 - p.t0 for p in ps)
    c = sum(p.c * (p.t1 - p.t0) for p in ps) / L
    sep = sum(p.sep * (p.t1 - p.t0) for p in ps) / L
    lin, blq = set(), set()
    for p in ps:
        if p.bloque >= 0:
            blq.add(p.bloque)
        else:
            lin.update((p.linea_a, p.linea_b))
    return Corrida(i, g, d, n, c, e, sep, [list(t) for t in tramos], lin, blq)


# ---------------------------------------------------------------- paso 3: doble hilada
def doble_hilada(corridas, P):
    """Dos hiladas paralelas a doble_hilada_sep_min–max entre centros = muro de contención (doble_hilada_espesor).
    Se trabaja por bandas: todos los pedazos de cada hilada que se traslapan con la otra forman la zona doble;
    las zonas dobles se unen a través de huecos <= doble_hilada_union (en contención no hay puertas); lo que
    sobra de una hilada se absorbe si mide <= doble_hilada_absorber y toca una zona doble, si no queda como
    muro sencillo."""
    pares = []
    por_g = {}
    for W in corridas:
        por_g.setdefault(W.grupo, []).append(W)
    for g, cs in por_g.items():
        cs.sort(key=lambda W: W.c)
        for i, A in enumerate(cs):
            for B in cs[i + 1:]:
                sep = B.c - A.c
                if sep > P.doble_hilada_sep_max:
                    break
                if sep < P.doble_hilada_sep_min or abs(A.esp + B.esp - P.doble_hilada_espesor) > 0.02:
                    continue
                o0, o1 = max(A.a, B.a), min(A.b, B.b)
                if o1 - o0 > 1e-9:
                    pares.append((g, (A.c + B.c) / 2, o0, o1, A, B, sep))
    if not pares:
        return corridas
    pares.sort(key=lambda x: (x[0], x[1]))
    bandas, cur = [], [pares[0]]
    for p in pares[1:]:
        if p[0] == cur[-1][0] and p[1] - cur[-1][1] <= P.tol_banda:
            cur.append(p)
        else:
            bandas.append(cur)
            cur = [p]
    bandas.append(cur)
    usadas, nuevas = set(), []
    for bd in bandas:
        filas = {}
        for _, _, _, _, A, B, _ in bd:
            for W in (A, B):
                if W.id not in usadas:
                    filas[W.id] = W
        if not filas:
            continue
        g = bd[0][0]
        cm = sum(x[1] * (x[3] - x[2]) for x in bd) / sum(x[3] - x[2] for x in bd)
        sep = sum(x[6] * (x[3] - x[2]) for x in bd) / sum(x[3] - x[2] for x in bd)
        ivs = sorted((x[2], x[3]) for x in bd)
        zonas = [list(ivs[0])]
        for x0, x1 in ivs[1:]:
            if x0 - zonas[-1][1] <= P.doble_hilada_union:
                zonas[-1][1] = max(zonas[-1][1], x1)
            else:
                zonas.append([x0, x1])
        sueltos = []
        for W in filas.values():
            resto = [[W.a, W.b]]
            for z0, z1 in zonas:
                resto = [[t0, t1] for t0, t1, *_ in _quitar([[r0, r1, ""] for r0, r1 in resto], z0, z1)]
            for r0, r1 in resto:
                toca = [z for z in zonas if abs(z[0] - r1) <= P.union_max or abs(r0 - z[1]) <= P.union_max]
                if r1 - r0 <= P.doble_hilada_absorber and toca:
                    z = toca[0]
                    z[0], z[1] = min(z[0], r0), max(z[1], r1)
                else:
                    sueltos.append((W, r0, r1))
        A0 = next(iter(filas.values()))
        w = sum(W.sep for W in filas.values()) / len(filas)
        for z0, z1 in zonas:
            nuevas.append(Corrida(-1, g, A0.d, A0.n, cm, P.doble_hilada_espesor, sep + w, [[z0, z1, "muro"]],
                                  set().union(*[W.lineas for W in filas.values()]), set().union(*[W.bloques for W in filas.values()]),
                                  doble=True, obs=f"doble hilada ({sep:.3f} m entre centros)"))
        for W, r0, r1 in sueltos:
            tr = _recortar(W.tramos, r0, r1)
            if tr:
                tr[0][2] = tr[-1][2] = "muro"
                nuevas.append(Corrida(-1, W.grupo, W.d, W.n, W.c, W.esp, W.sep, tr, set(W.lineas), set(W.bloques)))
        usadas.update(filas)
    out = [W for W in corridas if W.id not in usadas] + nuevas
    for i, W in enumerate(out):
        W.id = i
    return out


def _quitar(tramos, a, b):
    """Quita el intervalo (a, b) de una lista de tramos [t0, t1, ...]."""
    out = []
    for t0, t1, *resto in tramos:
        if t1 <= a or t0 >= b:
            out.append([t0, t1, *resto])
            continue
        if t0 < a:
            out.append([t0, a, *resto])
        if t1 > b:
            out.append([b, t1, *resto])
    return out


def _recortar(tramos, a, b):
    out = []
    for t0, t1, tipo in tramos:
        x, y = max(t0, a), min(t1, b)
        if y - x > 1e-9:
            out.append([x, y, tipo])
    return out


# ---------------------------------------------------------------- paso 4: encuentros
def _interseccion(W, X):
    """Parámetro tW sobre W y tX sobre X del cruce de ejes, y |sen θ|."""
    den = _dot(X.n, W.d)
    if abs(den) < 1e-12:
        return None
    tW = (X.c - W.c * _dot(X.n, W.n)) / den
    P = W.punto(tW)
    return tW, _dot(X.d, P), abs(_cross(W.d, X.d))


def _indice(corridas):
    from shapely import STRtree
    from shapely.geometry import LineString
    geoms = [LineString([W.punto(W.a), W.punto(W.b)]) for W in corridas]
    return STRtree(geoms), geoms


def _cerca(arbol, corridas, p, radio):
    from shapely.geometry import Point
    return [corridas[i] for i in arbol.query(Point(p).buffer(radio))]


def resolver_encuentros(corridas, P, columnas=()):
    smin = math.sin(math.radians(P.angulo_min_esquina))
    if not corridas:
        return
    arbol, geoms = _indice(corridas)
    emax = max(W.esp for W in corridas)
    from shapely.geometry import Point
    cols = [c.buffer(0.05) for c in columnas]
    cmax = max((max(c.bounds[2] - c.bounds[0], c.bounds[3] - c.bounds[1]) for c in columnas), default=0.0)
    r_snap = (emax / 2) / smin + P.tol_snap + emax + cmax
    r_vano = r_snap + P.vano_max + 1.0
    for W in corridas:
        for k in (0, 1):
            t_ext = W.a if k == 0 else W.b
            sg = 1 if k == 1 else -1
            E = W.punto(t_ext)
            # si el extremo toca una mocheta/columna, el muro termina en su cara: se amplía la tolerancia
            extra = max((max(c.bounds[2] - c.bounds[0], c.bounds[3] - c.bounds[1]) for c in cols if c.contains(Point(E))), default=0.0)
            mejor = None
            for X in _cerca(arbol, corridas, E, r_snap):
                if X is W:
                    continue
                r = _interseccion(W, X)
                if r is None or r[2] < smin:
                    continue
                tW, tX, s = r
                adelante = (tW - t_ext) * sg
                hx, hw = (X.esp / 2) / s, (W.esp / 2) / s
                if abs(adelante) > hx + P.tol_snap + extra:
                    continue
                if tX < X.a - hw - P.tol_snap - extra or tX > X.b + hw + P.tol_snap + extra:
                    continue
                if tX < X.a + P.tol_snap:
                    info = ("L", X.id, tW, 0)
                elif tX > X.b - P.tol_snap:
                    info = ("L", X.id, tW, 1)
                else:
                    info = ("T", X.id, tW, None)
                dist = abs(adelante - hx)
                if mejor is None or dist < mejor[0]:
                    mejor = (dist, info)
            if mejor:
                W.ext[k] = mejor[1]
    for W in corridas:
        for k in (0, 1):
            inf = W.ext[k]
            if inf and inf[0] == "L":
                X = corridas[inf[1]]
                otra = X.ext[inf[3]]
                if not (otra and otra[0] == "L" and otra[1] == W.id):
                    W.ext[k] = ("T", inf[1], inf[2], None)
    if P.vano_en_extremo:
        for W in corridas:
            for k in (0, 1):
                if W.ext[k] is not None or W.doble:      # en el muro de contención no hay puertas
                    continue
                t_ext = W.a if k == 0 else W.b
                sg = 1 if k == 1 else -1
                mejor = None
                for X in _cerca(arbol, corridas, W.punto(t_ext), r_vano):
                    if X is W:
                        continue
                    r = _interseccion(W, X)
                    if r is None or r[2] < smin:
                        continue
                    tW, tX, s = r
                    hx, hw = (X.esp / 2) / s, (W.esp / 2) / s
                    cara = tW - sg * hx
                    a, b = (cara, t_ext) if k == 0 else (t_ext, cara)
                    if b <= a:
                        continue
                    libres = _libres(a, b, _cubierto_por_columnas(columnas, W.d, W.n, W.c, W.esp, a, b))
                    libre = sum(y - x for x, y in libres)
                    if not (P.vano_min - 1e-9 <= libre <= P.vano_max + 1e-9 and len(libres) == 1):
                        continue
                    if not (X.a + hw - P.tol_snap <= tX <= X.b - hw + P.tol_snap):
                        continue
                    if mejor is None or libre < mejor[0]:
                        mejor = (libre, ("TV", X.id, tW, libres[0]))
                if mejor:
                    W.ext[k] = mejor[1]
    for i, W in enumerate(corridas):
        for j in arbol.query(geoms[i]):
            if j <= i:
                continue
            X = corridas[j]
            r = _interseccion(W, X)
            if r is None or r[2] < smin:
                continue
            tW, tX, s = r
            if not (W.a + (X.esp / 2) / s + P.tol_snap < tW < W.b - (X.esp / 2) / s - P.tol_snap):
                continue
            if not (X.a + (W.esp / 2) / s + P.tol_snap < tX < X.b - (W.esp / 2) / s - P.tol_snap):
                continue
            if _mayor(W, W.largo, X, X.largo):
                X.cruces.append((tX, W.id, s))
            else:
                W.cruces.append((tW, X.id, s))


def _mayor(W, lw, X, lx):
    """True si W es el más largo (empate: el de id menor)."""
    if abs(lw - lx) > 1e-9:
        return lw > lx
    return W.id < X.id


# ---------------------------------------------------------------- paso 5: tramos finales
def ejes(W):
    """Extremos de eje a eje: en L o T el cruce de ejes; libre o TV, donde termina lo dibujado."""
    t = [W.a, W.b]
    for k in (0, 1):
        inf = W.ext[k]
        if inf and inf[0] in ("L", "T"):
            t[k] = inf[2]
    return t


def _mochetas(corridas, columnas, P):
    """Por corrida: [(u, a, id_columna)] de las columnas/mochetas que la tocan, y el dueño de cada una."""
    toca = {W.id: [] for W in corridas}
    duenos = {}
    if not columnas:
        return toca, duenos
    largos = {W.id: (lambda t: t[1] - t[0])(ejes(W)) for W in corridas}
    for k, col in enumerate(columnas):
        cand = []
        cen = col.centroid
        for W in corridas:
            e0, e1 = ejes(W)
            ts = [_dot(W.d, q) for q in _coords(col)]
            u = (min(ts) + max(ts)) / 2
            a = (max(ts) - min(ts)) / 2
            v = _dot(W.n, (cen.x, cen.y)) - W.c
            if abs(v) < W.esp / 2 + P.toque_mocheta and e0 - 0.2 <= u <= e1 + 0.2:
                cand.append((W.id, u, a, e0, e1))
        if not cand:
            continue
        for wid, u, a, e0, e1 in cand:
            toca[wid].append((u, a, k))
        medio = [x for x in cand if x[3] + P.mocheta_extremo < x[1] < x[4] - P.mocheta_extremo]
        duenos[k] = medio[0][0] if medio else max(cand, key=lambda x: (largos[x[0]], -x[0]))[0]
    return toca, duenos


def _esquina(W, k, corridas, esquinas):
    """L sin mocheta: la regla deja el cuadrado de la esquina sin muro. Se registra una vez por esquina."""
    inf = W.ext[k]
    if not inf or inf[0] != "L":
        return
    X = corridas[inf[1]]
    clave = tuple(sorted((W.id, X.id)))
    if clave in esquinas:
        return
    from shapely.geometry import Polygon
    s = _interseccion(W, X)[2]
    tP = inf[2]
    hx, hw = (X.esp / 2) / s, W.esp / 2
    q = lambda t, c: (W.d[0] * t + W.n[0] * c, W.d[1] * t + W.n[1] * c)
    esquinas[clave] = (W.punto(tP), Polygon([q(tP - hx, W.c - hw), q(tP + hx, W.c - hw), q(tP + hx, W.c + hw), q(tP - hx, W.c + hw)]),
                       W.esp, X.esp)


def tramos_finales(corridas, revisiones, columnas=(), P=None, esquinas=None):
    """Tramos de muro y vano. Devuelve lista de dict."""
    P = P or Param(espesores=[])
    toca, duenos = _mochetas(corridas, columnas, P)
    esquinas = {} if esquinas is None else esquinas
    out = []
    obs_tv = "vano en extremo libre hasta la cara del muro que cruza: verificar"
    for W in corridas:
        e0, e1 = ejes(W)
        tr = [[t[0], t[1], t[2], ""] for t in W.tramos]
        tr[0][0], tr[-1][1] = e0, e1
        h2 = W.esp / 2
        # vanos en extremo libre
        for k in (0, 1):
            inf = W.ext[k]
            if inf and inf[0] == "TV":
                x, y = inf[3]
                if k == 1:
                    tr[-1][1] = x
                    tr.append([x, y, "vano", obs_tv])
                else:
                    tr[0][0] = y
                    tr.insert(0, [x, y, "vano", obs_tv])
        # cortes de cruce: la corrida más corta se parte en el eje del otro
        cortes = sorted(tc for tc, _, _ in W.cruces)
        piezas = [tr]
        for tc in cortes:
            nuevas = []
            for p in piezas:
                if p[0][0] < tc < p[-1][1]:
                    izq = [list(x) for x in p if x[0] < tc]
                    der = [list(x) for x in p if x[1] > tc]
                    izq[-1][1] = tc
                    der[0][0] = tc
                    nuevas += [izq, der]
                else:
                    nuevas.append(p)
            piezas = nuevas
        moch = sorted(toca.get(W.id, []))
        for p in piezas:
            u0, u1 = p[0][0], p[-1][1]
            es_inicio, es_fin = abs(u0 - e0) < 1e-9, abs(u1 - e1) < 1e-9
            inicio_en_eje = (not es_inicio) or (W.ext[0] is not None and W.ext[0][0] in ("L", "T"))
            fin_en_eje = (not es_fin) or (W.ext[1] is not None and W.ext[1][0] in ("L", "T"))
            if p[0][2] == "muro":
                s = [m for m in moch if m[0] - u0 < P.mocheta_extremo and m[0] > u0 - 0.2]
                if s:
                    u, a, k = s[0]
                    p[0][0] = u - a if duenos.get(k) == W.id else u + a
                elif inicio_en_eje:
                    p[0][0] = u0 + h2
                    if es_inicio:
                        _esquina(W, 0, corridas, esquinas)
            if p[-1][2] == "muro":
                e = [m for m in moch if u1 - m[0] < P.mocheta_extremo and m[0] < u1 + 0.2]
                if e:
                    u, a, k = e[-1]
                    p[-1][1] = u + a if duenos.get(k) == W.id else u - a
                elif fin_en_eje:
                    p[-1][1] = u1 - h2
                    if es_fin:
                        _esquina(W, 1, corridas, esquinas)
            for t0, t1, tipo, obs in p:
                L = t1 - t0
                if L <= 1e-9:
                    q = W.punto((t0 + t1) / 2)
                    revisiones.append(Revision("tramo nulo al resolver esquina", q[0], q[1],
                                               f"corrida {W.id}, espesor {W.esp:.2f} m, largo {L:.4f} m"))
                    continue
                o = obs
                if W.obs and tipo == "muro":
                    o = (o + "; " if o else "") + W.obs
                out.append(dict(corrida=W.id, tipo=tipo, esp=W.esp, sep=W.sep, p0=W.punto(t0), p1=W.punto(t1),
                                t0=t0, t1=t1, largo=L, d=W.d, n=W.n, obs=o, doble=W.doble))
    return out


# ---------------------------------------------------------------- todo junto
def reconocer(segs, P, bloques=(), columnas=()):
    revisiones = []
    pares = [(s.p0, s.p1) for s in segs]
    for B in bloques:
        h = B.largo / 2
        pares.append(((B.centro[0] - B.d[0] * h, B.centro[1] - B.d[1] * h), (B.centro[0] + B.d[0] * h, B.centro[1] + B.d[1] * h)))
    gid, dirs = _dirgrupos(pares, math.radians(P.tol_angular))
    lineas = unir_colineales(segs, gid, dirs, P) if segs else []
    piezas = emparejar(lineas, P) if lineas else []
    piezas += piezas_de_bloques(list(bloques), len(segs), gid, dirs, P, revisiones)
    todas = armar_corridas(piezas, dirs, P, revisiones, columnas) if piezas else []
    todas = doble_hilada(todas, P)
    validas, cortas = [], []
    for W in todas:
        (cortas if W.largo < P.umbral_eje_corto else validas).append(W)
    for i, W in enumerate(validas):
        W.id = i
    for W in cortas:
        W.corta = True
    resolver_encuentros(validas, P, columnas)
    res = Resultado(lineas, dirs, piezas, validas, cortas, revisiones)
    esquinas = {}
    res.tramos = tramos_finales(validas, revisiones, columnas, P, esquinas)
    res.esquinas = list(esquinas.values())
    for p, _, ea, eb in res.esquinas:
        revisiones.append(Revision("esquina en L sin mocheta", p[0], p[1],
                                   f"encuentro en L de muros de {ea:.2f} y {eb:.2f} m sin mocheta ni columna: por la regla del motor "
                                   f"(medio espesor propio) la esquina queda sin muro; si hay mocheta, marcar su capa"))
    res.bloques_usados = set().union(*[W.bloques for W in validas]) if validas else set()
    return res
