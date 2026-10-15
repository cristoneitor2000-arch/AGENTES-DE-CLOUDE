"""cimiento.py – cimiento corrido a partir de los ejes de muro.

Tipos: tabla del proyecto (interfaz) tipo -> ancho x peralte (del detalle estructural), p. ej.
    {"CC1": {"ancho": 0.70, "peralte": 0.25, "color": 2, "color_dentro": 52},
     "MC1": {"ancho": 1.00, "peralte": 0.30, "color": 4, "color_dentro": 144}}
Asignación: cada etiqueta del plano cuyo texto es un tipo de la tabla (CC1, MC1, "CC-1"...) se asigna al eje
de muro más cercano (a <= dist_etiqueta, 2.2 m). Un eje toma el tipo de sus etiquetas; si no tiene etiqueta,
o tiene etiquetas de tipos distintos, va a REVISION (no se inventa). Los muros de espesor sin cimiento
(tabiques de 0.10) no llevan cimiento.
Validación: cada etiqueta debe tener un tramo de cimiento de su tipo a <= dist_etiqueta.

Trazo:
- L: los dos llegan al cruce de ejes y, si son de la misma capa, se unen en una sola polilínea.
- T: el que llega termina en la cara del cimiento que cruza (medio ancho de ese cimiento).
- Cruz: el cimiento del muro más largo sigue continuo; el otro se corta en las caras.
- Vano de puerta: el cimiento pasa corrido. Extremo libre: termina donde termina el eje.
- Lo que cae dentro de una zapata va en la capa '<capa> (dentro de zapata)'.
Polilínea ABIERTA con ancho global = ancho real.
"""
import math
import re

from muros import Revision, _interseccion


def norm_tipo(s):
    return re.sub(r"[\s\-_\.]", "", str(s or "")).upper()


def validar_tipos(tipos):
    """Devuelve (tipos limpios, errores)."""
    out, err = {}, []
    for k, r in (tipos or {}).items():
        if not str(k).strip():
            continue
        try:
            a, p = float(r["ancho"]), float(r["peralte"])
        except (KeyError, TypeError, ValueError):
            err.append(f"Tipo {k}: ancho o peralte faltante o no numérico")
            continue
        if a <= 0 or p <= 0:
            err.append(f"Tipo {k}: medidas no positivas")
            continue
        out[str(k).strip()] = dict(r, ancho=a, peralte=p, color=int(r.get("color", 2) or 2),
                                   color_dentro=int(r.get("color_dentro", 8) or 8))
    return out, err


def _dist_seg(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L2 = ax * ax + ay * ay
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L2))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def etiquetas_de_tipo(etiquetas, tipos):
    mapa = {norm_tipo(k): k for k in tipos}
    return [(mapa[norm_tipo(e.texto)], e) for e in etiquetas if norm_tipo(e.texto) in mapa]


def asignar_tipos(corridas, etiquetas, tipos, sin_cimiento, dist_max, gap_linea=2.5, heredados=None, por_defecto=None,
                  defecto=None):
    """Tipo de cimiento por corrida a partir de las etiquetas. Un eje sin etiqueta propia toma el tipo de su línea
    de muro (corridas colineales con huecos <= gap_linea) si todas las etiquetas de esa línea son del mismo tipo.
    por_defecto (opcional, lo declara el usuario por proyecto): {"contencion": "MC1", "otros": "CC1"}; solo se usa
    en ejes sin etiqueta propia ni de su línea, y queda anotado.
    Devuelve (asignacion, revisiones, etiquetas_usadas); `heredados` y `defecto` (sets) reciben los ids que heredaron o
    tomaron el tipo por defecto."""
    heredados = set() if heredados is None else heredados
    por_defecto = {k: v for k, v in (por_defecto or {}).items() if v}
    defecto = set() if defecto is None else defecto
    from muros import ejes
    revisiones = []
    labs = etiquetas_de_tipo(etiquetas, tipos)
    con = [W for W in corridas if round(W.esp, 2) not in sin_cimiento]
    por_corrida = {W.id: [] for W in con}
    for tipo, e in labs:
        best = None
        for W in con:
            t0, t1 = ejes(W)
            dd = _dist_seg((e.x, e.y), W.punto(t0), W.punto(t1))
            if dd <= dist_max and (best is None or dd < best[0]):
                best = (dd, W.id)
        if best:
            por_corrida[best[1]].append((tipo, best[0], e))
    # líneas de muro: corridas colineales (misma dirección, eje a <= medio espesor) con huecos <= gap_linea
    linea = {W.id: W.id for W in con}

    def raiz(i):
        while linea[i] != i:
            linea[i] = linea[linea[i]]
            i = linea[i]
        return i

    orden = sorted(con, key=lambda W: (W.grupo, W.c))
    for i, A in enumerate(orden):
        for B in orden[i + 1:]:
            if B.grupo != A.grupo or B.c - A.c > max(A.esp, B.esp) / 2 + 0.03:
                break
            if max(A.a, B.a) - min(A.b, B.b) <= gap_linea:
                linea[raiz(A.id)] = raiz(B.id)
    tipos_linea = {}
    for W in con:
        for tipo, _, _ in por_corrida[W.id]:
            tipos_linea.setdefault(raiz(W.id), set()).add(tipo)
    asig = {}
    for W in con:
        ls = por_corrida[W.id]
        t0, t1 = ejes(W)
        m = W.punto(t0 + (t1 - t0) / 3)
        tl = tipos_linea.get(raiz(W.id), set())
        if not ls and len(tl) == 1:
            asig[W.id] = next(iter(tl))
            heredados.add(W.id)
            continue
        dflt = por_defecto.get("contencion" if W.doble else "otros")
        if not ls and not tl and dflt in tipos:
            asig[W.id] = dflt
            defecto.add(W.id)
            continue
        if not ls:
            revisiones.append(Revision("cimiento sin etiqueta", m[0], m[1],
                                       f"eje de muro de {W.esp:.2f} m y {t1 - t0:.3f} m sin etiqueta de tipo a <= {dist_max} m"))
            continue
        ts = sorted({x[0] for x in ls})
        if len(ts) > 1:
            revisiones.append(Revision("etiquetas de tipos distintos", m[0], m[1],
                                       f"eje de {t1 - t0:.3f} m con etiquetas {', '.join(ts)}",
                                       tuple(x[2].handle for x in ls)))
            continue
        asig[W.id] = ts[0]
    return asig, revisiones, labs


def generar(corridas, tipos, asignacion, capa_fmt, corrido_por_vanos=True):
    """Devuelve lista de cimientos [{capa, regla, tipo, pts, largo, corridas, esp}] (antes de separar zapatas)."""
    from muros import _quitar

    R = {W.id: tipos[asignacion[W.id]] | {"tipo": asignacion[W.id]} for W in corridas if W.id in asignacion}

    def ancho(xid):
        r = R.get(xid)
        return r["ancho"] if r else 0.0

    def capa(r):
        return capa_fmt.format(tipo=r["tipo"], ancho=f"{r['ancho']:.2f}", peralte=f"{r['peralte']:.2f}")

    piezas = []
    for W in corridas:
        r = R.get(W.id)
        if not r:
            continue
        t = [W.a, W.b]
        link = [None, None]
        for k in (0, 1):
            inf = W.ext[k]
            if not inf:
                continue
            sg = 1 if k == 1 else -1
            X = corridas[inf[1]]
            s = _interseccion(W, X)[2]
            tP = inf[2]
            if inf[0] in ("T", "TV"):
                t[k] = tP - sg * (ancho(X.id) / 2) / s
            elif inf[0] == "L":
                t[k] = tP
                link[k] = (X.id, inf[3])
        tramos = [[t[0], t[1], "cim"]]
        if not corrido_por_vanos:
            for a, b, tipo in W.tramos:
                if tipo == "vano":
                    tramos = _quitar(tramos, a, b)
        for (tc, xid, s) in sorted(W.cruces):
            w = ancho(xid)
            if w > 0:
                tramos = _quitar(tramos, tc - (w / 2) / s, tc + (w / 2) / s)
        for a, b, _ in tramos:
            if b - a <= 1e-9:
                continue
            piezas.append(dict(corrida=W.id, t0=a, t1=b, capa=capa(r), regla=r, esp=W.esp,
                               link0=link[0] if abs(a - t[0]) < 1e-12 else None,
                               link1=link[1] if abs(b - t[1]) < 1e-12 else None))
    return _encadenar(piezas, corridas)


def separar_zapatas(cims, zapatas, sufijo=" (dentro de zapata)"):
    """Parte cada polilínea en lo que queda fuera y lo que cae dentro de zapatas (capa aparte)."""
    if not zapatas:
        return cims
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    Z = unary_union(zapatas)
    out = []
    for c in cims:
        ls = LineString(c["pts"])
        if not ls.intersects(Z):
            out.append(dict(c, dentro=False))
            continue
        for geom, dentro in ((ls.difference(Z), False), (ls.intersection(Z), True)):
            for g in _lineas(geom):
                if g.length <= 1e-9:
                    continue
                out.append(dict(c, pts=[tuple(p[:2]) for p in g.coords], largo=g.length, dentro=dentro,
                                capa=c["capa"] + (sufijo if dentro else "")))
    return out


def _lineas(g):
    if g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    if hasattr(g, "geoms"):
        from shapely.ops import linemerge
        ls = [x for x in g.geoms if x.geom_type == "LineString"]
        if not ls:
            return []
        m = linemerge(ls)
        return [m] if m.geom_type == "LineString" else list(m.geoms)
    return []


def validar_etiquetas(labs, cims, dist_max):
    """Cada etiqueta debe tener un tramo de su tipo a <= dist_max."""
    revisiones = []
    for tipo, e in labs:
        ok = False
        for c in cims:
            if c["regla"]["tipo"] != tipo:
                continue
            for a, b in zip(c["pts"], c["pts"][1:]):
                if _dist_seg((e.x, e.y), a, b) <= dist_max:
                    ok = True
                    break
            if ok:
                break
        if not ok:
            revisiones.append(Revision("etiqueta sin tramo de su tipo", e.x, e.y,
                                       f"etiqueta '{e.texto}' sin cimiento {tipo} a <= {dist_max} m", (e.handle,)))
    return revisiones


def _encadenar(piezas, corridas):
    """Une en una polilínea las piezas de la misma capa que se encuentran en L."""
    extremo = {}
    for i, p in enumerate(piezas):
        if p["link0"]:
            extremo[(p["corrida"], 0)] = (i, 0)
        if p["link1"]:
            extremo[(p["corrida"], 1)] = (i, 1)

    def vecino(i, k):
        p = piezas[i]
        ln = p["link1"] if k == 1 else p["link0"]
        if not ln:
            return None
        j = extremo.get(ln)
        if j is None or piezas[j[0]]["capa"] != p["capa"]:
            return None
        q = piezas[j[0]]
        back = q["link1"] if j[1] == 1 else q["link0"]
        if back != (p["corrida"], k):
            return None
        return j

    usados = set()
    cadenas = []

    def recorrer(i, k_entrada):
        cad = []
        while i is not None and i not in usados:
            usados.add(i)
            cad.append((i, k_entrada))
            nx = vecino(i, 1 - k_entrada)
            if nx is None:
                break
            i, k_entrada = nx
        return cad

    for i in range(len(piezas)):
        if i in usados:
            continue
        for k in (0, 1):
            if vecino(i, k) is None:
                cadenas.append(recorrer(i, k))
                break
    for i in range(len(piezas)):
        if i not in usados:
            cadenas.append(recorrer(i, 0))

    out = []
    for cad in cadenas:
        pts, largo, cors = [], 0.0, []
        for i, k_ent in cad:
            p = piezas[i]
            W = corridas[p["corrida"]]
            a, b = (p["t0"], p["t1"]) if k_ent == 0 else (p["t1"], p["t0"])
            pa, pb = W.punto(a), W.punto(b)
            if not pts or math.dist(pts[-1], pa) > 1e-6:
                pts.append(pa)
            pts.append(pb)
            largo += p["t1"] - p["t0"]
            cors.append(p["corrida"])
        p0 = piezas[cad[0][0]]
        out.append(dict(capa=p0["capa"], regla=p0["regla"], pts=pts, largo=largo, corridas=cors, esp=p0["esp"]))
    return out
