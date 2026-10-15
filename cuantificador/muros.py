"""muros.py – reconocimiento de muros a partir de las líneas de sus caras.

Pasos
1. Agrupar los segmentos por dirección (tolerancia angular) y unir los colineales que se tocan o traslapan.
2. Emparejar líneas paralelas cuya separación sea un espesor de la lista (± tol) y que se traslapen
   en proyección: el eje va en el tramo de traslape. Una línea con dos parejas que se traslapan
   = traslape ambiguo (no se adivina: va a REVISION).
3. Unir ejes colineales del mismo espesor: hueco <= union_max se une (muro que cruza, junta);
   vano_min <= hueco <= vano_max = vano de puerta; hueco intermedio = REVISION.
4. Resolver extremos contra los demás ejes: L, T, cruces y vano en extremo libre.
5. Tramos finales sin traslapes (muro | vano | muro) con la convención de esquinas:
   L -> el más largo se lleva la esquina; T -> el que llega termina en la cara del corrido;
   cruz -> el más largo sigue continuo y el otro se corta en sus caras.

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
    union_max: float = 0.25
    vano_min: float = 0.60
    vano_max: float = 2.05
    vano_en_extremo: bool = True
    umbral_eje_corto: float = 0.20
    tol_snap: float = 0.03
    angulo_min_esquina: float = 10.0  # grados; por debajo se consideran paralelos
    residuo_min: float = 0.05
    sep_busqueda_max: float = 0.60

    @classmethod
    def desde_config(cls, cfg, espesores=None):
        kw = {k: cfg[k] for k in cls.__dataclass_fields__ if k in cfg}
        if espesores is not None:
            kw["espesores"] = list(espesores)
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
    ext: list = field(default_factory=lambda: [None, None])   # info de extremo [inicio, fin]
    cruces: list = field(default_factory=list)                # [(t, otra_id, sin)] donde se corta esta
    corta: bool = False

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


# ---------------------------------------------------------------- utilidades
def _dirgrupos(segs, tol_rad):
    """Agrupa segmentos por dirección. Devuelve (grupo_de_seg, [(d, n)])."""
    if not segs:
        return [], []
    ang = [math.atan2(s.p1[1] - s.p0[1], s.p1[0] - s.p0[0]) % math.pi for s in segs]
    orden = sorted(range(len(segs)), key=lambda i: ang[i])
    clusters, cur = [], [orden[0]]
    for i in orden[1:]:
        if ang[i] - ang[cur[-1]] > tol_rad or ang[i] - ang[cur[0]] > 2 * tol_rad:
            clusters.append(cur)
            cur = [i]
        else:
            cur.append(i)
    clusters.append(cur)
    # cierre circular (0 ~ 180°)
    if len(clusters) > 1 and ang[clusters[0][0]] + math.pi - ang[clusters[-1][-1]] <= tol_rad:
        clusters[0] = clusters.pop() + clusters[0]
    gid = [0] * len(segs)
    dirs = []
    for g, cl in enumerate(clusters):
        sx = sy = 0.0
        for i in cl:
            gid[i] = g
            L = segs[i].largo
            sx += L * math.cos(2 * ang[i])
            sy += L * math.sin(2 * ang[i])
        a = math.atan2(sy, sx) / 2
        d = (math.cos(a), math.sin(a))
        dirs.append((d, (-d[1], d[0])))
    return gid, dirs


def _dot(u, v):
    return u[0] * v[0] + u[1] * v[1]


def _cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


def _espesor(sep, P):
    best = None
    for e in P.espesores:
        if abs(sep - e) <= P.tol_espesor + 1e-12 and (best is None or abs(sep - e) < abs(sep - best)):
            best = e
    return best


# ---------------------------------------------------------------- paso 1: líneas
def unir_colineales(segs, P):
    gid, dirs = _dirgrupos(segs, math.radians(P.tol_angular))
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
        # agrupar por desplazamiento c
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
            grupo_actual = [b[0]]
            fin = b[0][2]
            for it in b[1:]:
                if it[1] <= fin + P.tol_colineal:
                    grupo_actual.append(it)
                    fin = max(fin, it[2])
                else:
                    lineas.append(_nueva_linea(len(lineas), g, grupo_actual))
                    grupo_actual, fin = [it], it[2]
            lineas.append(_nueva_linea(len(lineas), g, grupo_actual))
    return lineas, dirs


def _nueva_linea(i, g, items):
    L = sum(x[2] - x[1] for x in items)
    c = sum(x[0] * (x[2] - x[1]) for x in items) / L if L > 0 else items[0][0]
    return Linea(i, g, c, min(x[1] for x in items), max(x[2] for x in items), [(x[3], x[1], x[2]) for x in items])


# ---------------------------------------------------------------- paso 2: pares
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
    # ambigüedad: una misma línea con dos piezas que se traslapan en proyección
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


# ---------------------------------------------------------------- paso 3: corridas
def armar_corridas(piezas, dirs, P, revisiones):
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
            if p.c - cur[-1].c <= P.tol_espesor:
                cur.append(p)
            else:
                bandas.append(cur)
                cur = [p]
        bandas.append(cur)
        for b in bandas:
            b.sort(key=lambda p: p.t0)
            actual = [b[0]]
            tramos = [[b[0].t0, b[0].t1, "muro"]]
            for p in b[1:]:
                fin = tramos[-1][1]
                hueco = p.t0 - fin
                if hueco <= P.union_max:
                    tramos[-1][1] = max(fin, p.t1)
                    actual.append(p)
                elif P.vano_min - 1e-9 <= hueco <= P.vano_max + 1e-9:
                    tramos.append([fin, p.t0, "vano"])
                    tramos.append([p.t0, p.t1, "muro"])
                    actual.append(p)
                else:
                    if hueco < P.vano_min:
                        cx = (fin + p.t0) / 2
                        cc = sum(q.c for q in actual) / len(actual)
                        revisiones.append(Revision("hueco no clasificado", d[0] * cx + n[0] * cc, d[1] * cx + n[1] * cc,
                                                   f"hueco de {hueco:.3f} m entre ejes colineales de {e:.2f} m "
                                                   f"(> unión {P.union_max} y < vano {P.vano_min})"))
                    corridas.append(_nueva_corrida(len(corridas), g, d, n, e, actual, tramos))
                    actual, tramos = [p], [[p.t0, p.t1, "muro"]]
            corridas.append(_nueva_corrida(len(corridas), g, d, n, e, actual, tramos))
    return corridas


def _nueva_corrida(i, g, d, n, e, ps, tramos):
    L = sum(p.t1 - p.t0 for p in ps)
    c = sum(p.c * (p.t1 - p.t0) for p in ps) / L
    sep = sum(p.sep * (p.t1 - p.t0) for p in ps) / L
    lin = set()
    for p in ps:
        lin.update((p.linea_a, p.linea_b))
    return Corrida(i, g, d, n, c, e, sep, [list(t) for t in tramos], lin)


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
    if arbol is None:
        return []
    return [corridas[i] for i in arbol.query(Point(p).buffer(radio))]


def resolver_encuentros(corridas, P):
    smin = math.sin(math.radians(P.angulo_min_esquina))
    if not corridas:
        return
    arbol, geoms = _indice(corridas)
    emax = max(W.esp for W in corridas)
    r_snap = (emax / 2) / smin + P.tol_snap + emax
    r_vano = r_snap + P.vano_max
    for W in corridas:
        for k in (0, 1):
            t_ext = W.a if k == 0 else W.b
            sg = 1 if k == 1 else -1
            mejor = None
            for X in _cerca(arbol, corridas, W.punto(t_ext), r_snap):
                if X is W:
                    continue
                r = _interseccion(W, X)
                if r is None or r[2] < smin:
                    continue
                tW, tX, s = r
                adelante = (tW - t_ext) * sg
                hx, hw = (X.esp / 2) / s, (W.esp / 2) / s
                if abs(adelante) > hx + P.tol_snap:
                    continue
                if tX < X.a - hw - P.tol_snap or tX > X.b + hw + P.tol_snap:
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
    # L mutuas; si no, se trata como T
    for W in corridas:
        for k in (0, 1):
            inf = W.ext[k]
            if inf and inf[0] == "L":
                X = corridas[inf[1]]
                otra = X.ext[inf[3]]
                if not (otra and otra[0] == "L" and otra[1] == W.id):
                    W.ext[k] = ("T", inf[1], inf[2], None)
    # vano en extremo libre: hueco de puerta entre el extremo y la cara del muro que cruza
    if P.vano_en_extremo:
        for W in corridas:
            for k in (0, 1):
                if W.ext[k] is not None:
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
                    hueco = (tW - t_ext) * sg - hx
                    if not (P.vano_min - 1e-9 <= hueco <= P.vano_max + 1e-9):
                        continue
                    if not (X.a + hw - P.tol_snap <= tX <= X.b - hw + P.tol_snap):
                        continue
                    if mejor is None or hueco < mejor[0]:
                        mejor = (hueco, ("TV", X.id, tW, hueco))
                if mejor:
                    W.ext[k] = mejor[1]
    # cruces: los dos ejes pasan; se corta el más corto
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
    """True si W gana la esquina / sigue continuo (más largo; empate: el de id menor)."""
    if abs(lw - lx) > 1e-9:
        return lw > lx
    return W.id < X.id


# ---------------------------------------------------------------- paso 5: tramos finales
def tramos_finales(corridas, revisiones):
    """Tramos de muro y vano sin traslapes. Devuelve lista de dict."""
    out = []
    obs_tv = "vano en extremo libre hasta la cara del muro que cruza: verificar"
    for W in corridas:
        tr = [[t[0], t[1], t[2], ""] for t in W.tramos]
        for k in (0, 1):
            inf = W.ext[k]
            if not inf:
                continue
            sg = 1 if k == 1 else -1
            X = corridas[inf[1]]
            r = _interseccion(W, X)
            s = r[2]
            tP = inf[2]
            hx = (X.esp / 2) / s
            if inf[0] == "T":
                nuevo = tP - sg * hx
            elif inf[0] == "L":
                lw = abs(tP - (W.b if k == 0 else W.a))
                lx = abs(r[1] - (X.b if inf[3] == 0 else X.a))
                nuevo = tP + sg * hx if _mayor(W, lw, X, lx) else tP - sg * hx
            else:  # TV: el muro queda donde está y se agrega el vano hasta la cara del que cruza
                cara = tP - sg * hx
                if k == 1:
                    tr.append([tr[-1][1], cara, "vano", obs_tv])
                else:
                    tr.insert(0, [cara, tr[0][0], "vano", obs_tv])
                continue
            if k == 1:
                tr[-1][1] = nuevo
            else:
                tr[0][0] = nuevo
        # cortes por cruce (esta corrida es la más corta)
        for (tc, xid, s) in sorted(W.cruces):
            h = (corridas[xid].esp / 2) / s
            tr = _quitar(tr, tc - h, tc + h)
        for t0, t1, tipo, obs in tr:
            L = t1 - t0
            if L <= 1e-9:
                p = W.punto((t0 + t1) / 2)
                revisiones.append(Revision("tramo nulo al resolver esquina", p[0], p[1],
                                           f"corrida {W.id}, espesor {W.esp:.2f} m, largo {L:.4f} m"))
                continue
            out.append(dict(corrida=W.id, tipo=tipo, esp=W.esp, sep=W.sep, p0=W.punto(t0), p1=W.punto(t1),
                            t0=t0, t1=t1, largo=L, d=W.d, n=W.n, obs=obs))
    return out


def _quitar(tramos, a, b):
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


# ---------------------------------------------------------------- todo junto
def reconocer(segs, P):
    revisiones = []
    lineas, dirs = unir_colineales(segs, P)
    piezas = emparejar(lineas, P)
    todas = armar_corridas(piezas, dirs, P, revisiones)
    validas, cortas = [], []
    for W in todas:
        (cortas if W.largo < P.umbral_eje_corto else validas).append(W)
    for i, W in enumerate(validas):
        W.id = i
    for W in cortas:
        W.corta = True
    resolver_encuentros(validas, P)
    res = Resultado(lineas, dirs, piezas, validas, cortas, revisiones)
    res.tramos = tramos_finales(validas, revisiones)
    return res
