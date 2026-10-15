"""revision.py – qué se reconoció y qué no: cobertura de las líneas de origen, marcas REVISION y reporte.md.

Una porción de línea de origen está "reconocida" si cae dentro de algún muro o vano generado
(rectángulo del tramo final, con tolerancia). Lo que sobra (> residuo_min) se marca con su motivo:
  traslape ambiguo        la línea tenía dos parejas posibles que se traslapan
  espesor fuera de lista  hay una paralela que se traslapa, pero a una separación que no está en la lista
  segmento sin pareja     no hay paralela a distancia de muro
  eje muy corto           el par formaba un eje menor que el umbral (y sus líneas no las explica otro muro)
  arco no analizado       los arcos no se emparejan en esta versión
"""
import math
from collections import Counter

from shapely import STRtree
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from muros import Revision, _espesor


def rect_tramo(t):
    (x0, y0), (x1, y1) = t["p0"], t["p1"]
    nx, ny = t["n"]
    h = t["esp"] / 2
    return Polygon([(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)])


def cobertura(segs, arcos, res, P, bloques=()):
    tol = max(0.01, 2 * P.tol_espesor)
    polys = [rect_tramo(t).buffer(tol, join_style=2) for t in res.tramos if t["largo"] > 1e-9]
    polys += [q.buffer(tol, join_style=2) for _, q, _, _ in getattr(res, "esquinas", [])]   # ya tienen su marca
    U = unary_union(polys) if (polys and arcos) else None   # solo para los arcos
    arbol = STRtree(polys) if polys else None

    def resto_de(g):
        if arbol is None:
            return g
        idx = arbol.query(g)
        return g.difference(unary_union([polys[i] for i in idx])) if len(idx) else g

    seg_linea = {}
    for L in res.lineas:
        for sid, _, _ in L.segs:
            seg_linea[sid] = L.id
    ambiguas = set()
    for p in res.piezas:
        if p.ambigua:
            ambiguas.update((p.linea_a, p.linea_b))

    sobrante = {}
    for s in segs:
        sobrante[s.id] = resto_de(LineString([s.p0, s.p1]))

    revisiones = []
    zonas = []        # (polígono, revisión): problemas que ya tienen marca; absorben las líneas que caen dentro
    # ejes cortos
    dentro_de_muro = lambda B: arbol is not None and any(polys[i].contains(Point(B.centro)) for i in arbol.query(Point(B.centro)))
    for W in res.cortas:
        sids = [sid for lid in W.lineas for sid, _, _ in res.lineas[lid].segs]
        if all(sobrante[sid].length <= P.residuo_min for sid in sids) and all(dentro_de_muro(bloques[b]) for b in W.bloques):
            continue   # p. ej. jambas de un vano angosto o un block suelto dentro de otro muro
        m = W.punto((W.a + W.b) / 2)
        rv = Revision("eje muy corto", m[0], m[1], f"eje de {W.largo:.3f} m (< {P.umbral_eje_corto} m), espesor {W.esp:.2f} m")
        revisiones.append(rv)
        zonas.append((_rect_corrida(W, W.a, W.b, W.esp / 2).buffer(tol, join_style=2), rv))

    lin_por_grupo = {}
    for L in res.lineas:
        lin_por_grupo.setdefault(L.grupo, []).append(L)
    resto_linea = {L.id: sum(sobrante[sid].length for sid, _, _ in L.segs) for L in res.lineas}
    # pares paralelos con separación fuera de la lista (las dos líneas sin reconocer)
    for g, ls in lin_por_grupo.items():
        d, n = res.grupos[g]
        ls = sorted((L for L in ls if resto_linea[L.id] > P.residuo_min and L.id not in ambiguas), key=lambda L: L.c)
        for i, A in enumerate(ls):
            for B in ls[i + 1:]:
                sep = B.c - A.c
                if sep > P.sep_busqueda_max:
                    break
                if sep <= P.tol_colineal or _espesor(sep, P) is not None:
                    continue
                t0, t1 = max(A.t0, B.t0), min(A.t1, B.t1)
                if t1 - t0 <= P.residuo_min:
                    continue
                poly = _rect(d, n, t0, t1, A.c, B.c).buffer(tol, join_style=2)
                if any(z.contains(poly.centroid) for z, _ in zonas):
                    continue
                tm, cm = (t0 + t1) / 2, (A.c + B.c) / 2
                rv = Revision("espesor fuera de lista", d[0] * tm + n[0] * cm, d[1] * tm + n[1] * cm,
                              f"par de líneas a {sep:.3f} m en {t1 - t0:.3f} m (lista: {', '.join(f'{e:.2f}' for e in P.espesores)})")
                revisiones.append(rv)
                zonas.append((poly, rv))

    zpolys = [poly.buffer(tol) for poly, _ in zonas]
    zarbol = STRtree(zpolys) if zpolys else None
    for s in segs:
        resto = sobrante[s.id]
        if resto.length <= P.residuo_min:
            continue
        z = None
        if zarbol is not None:
            z = next((zonas[i][1] for i in sorted(zarbol.query(resto)) if zpolys[i].contains(resto)), None)
        if z is not None:
            z.handles = tuple(sorted(set(z.handles) | {s.handle}))
            continue
        partes = list(getattr(resto, "geoms", [resto]))
        mayor = max(partes, key=lambda g: g.length)
        mx, my = mayor.interpolate(0.5, normalized=True).coords[0]
        lid = seg_linea[s.id]
        if lid in ambiguas:
            motivo, det = "traslape ambiguo", "la línea tiene dos parejas posibles que se traslapan"
        else:
            motivo, det = "segmento sin pareja", "sin paralela a distancia de muro"
        revisiones.append(Revision(motivo, mx, my, det + f"; sin reconocer {resto.length:.3f} de {s.largo:.3f} m", (s.handle,)))

    for a in arcos:
        if U is not None and U.contains(Point(a.medio)):
            continue
        revisiones.append(Revision("arco no analizado", a.medio[0], a.medio[1],
                                   f"arco R {a.radio:.3f} m, largo {a.largo:.3f} m", (a.handle,)))

    # bloques: los que no quedaron en ningún muro (los de tamaño o ancho fuera de lista ya tienen marca)
    marcados = {h for r in res.revisiones for h in r.handles}
    en_cortas = {b for W in res.cortas for b in W.bloques}
    n_blq_ok = 0
    for B in bloques:
        if B.id in res.bloques_usados or dentro_de_muro(B):
            n_blq_ok += 1
            continue
        if B.handle in marcados or B.id in en_cortas:
            continue
        revisiones.append(Revision("bloque sin muro", B.centro[0], B.centro[1],
                                   f"block de {B.largo:.3f} x {B.ancho:.3f} m que no quedó en ningún muro", (B.handle,)))

    largo_total = sum(s.largo for s in segs) + sum(a.largo for a in arcos)
    largo_rec = sum(s.largo - (sobrante[s.id].length if sobrante[s.id].length > P.residuo_min else 0.0) for s in segs)
    largo_rec += sum(a.largo for a in arcos if U is not None and U.contains(Point(a.medio)))
    n_ok = sum(1 for s in segs if sobrante[s.id].length <= P.residuo_min)
    stats = dict(segmentos=len(segs), arcos=len(arcos), segmentos_reconocidos=n_ok,
                 largo_total=largo_total, largo_reconocido=largo_rec,
                 pct_largo=(100.0 * largo_rec / largo_total) if largo_total else 0.0,
                 pct_segmentos=(100.0 * n_ok / len(segs)) if segs else 0.0,
                 bloques=len(bloques), bloques_reconocidos=n_blq_ok,
                 pct_bloques=(100.0 * n_blq_ok / len(bloques)) if bloques else 0.0)
    return revisiones, stats


def _rect(d, n, t0, t1, c0, c1):
    p = lambda t, c: (d[0] * t + n[0] * c, d[1] * t + n[1] * c)
    return Polygon([p(t0, c0), p(t1, c0), p(t1, c1), p(t0, c1)])


def _rect_corrida(W, t0, t1, h):
    return _rect(W.d, W.n, t0, t1, W.c - h, W.c + h)


def depurar(revisiones, radio):
    """Quita marcas del mismo motivo a menos de `radio` (p. ej. las dos caras de un muro fuera de lista)."""
    out = []
    for r in revisiones:
        if any(o.motivo == r.motivo and math.hypot(o.x - r.x, o.y - r.y) < radio for o in out):
            dup = next(o for o in out if o.motivo == r.motivo and math.hypot(o.x - r.x, o.y - r.y) < radio)
            dup.handles = tuple(sorted(set(dup.handles) | set(r.handles)))
            continue
        out.append(r)
    return out


def por_motivo(revisiones):
    return Counter(r.motivo for r in revisiones)


def escribir_reporte(ruta, info):
    """info: dict armado por pipeline.cuantificar."""
    st = info["stats"]
    L = []
    w = L.append
    w(f"# Reporte de cuantificación – {info['nombre']}")
    w("")
    w(f"- Fecha: {info['fecha']}")
    w(f"- Plano original: `{info['original']}`")
    w(f"- sha256 original (inicio / fin): `{info['sha_ini']}` / `{info['sha_fin']}` → {'sin cambios' if info['sha_ini'] == info['sha_fin'] else 'CAMBIÓ'}")
    w(f"- Capas de origen: {', '.join(info['capas'])}")
    w(f"- Unidades: $INSUNITS = {info['insunits']} ({info['unidades']}); factor a metros usado = {info['factor']}")
    w(f"- Espesores reconocidos (m): {', '.join(f'{e:.2f}' for e in info['espesores'])}; nivel {info['nivel']}; "
      f"altura de muro: {info['altura'] if info['altura'] is not None else 'vacía (solo LARGO)'}")
    w(f"- Tiempo de proceso: {info['tiempo']:.2f} s")
    w("")
    w("## Reconocimiento")
    w("")
    w("| Concepto | Valor | Unidad |")
    w("|---|---|---|")
    w(f"| Segmentos analizados (LINE + polilíneas explotadas) | {st['segmentos']} | u |")
    w(f"| Arcos (no analizados) | {st['arcos']} | u |")
    w(f"| Segmentos de longitud cero (omitidos) | {info['n_cero']} | u |")
    w(f"| Segmentos reconocidos completos | {st['segmentos_reconocidos']} | u |")
    w(f"| % reconocido por número de segmentos | {st['pct_segmentos']:.2f} | % |")
    w(f"| Longitud de líneas analizadas | {st['largo_total']:.3f} | m |")
    w(f"| Longitud reconocida | {st['largo_reconocido']:.3f} | m |")
    w(f"| % reconocido por longitud | {st['pct_largo']:.2f} | % |")
    w(f"| Bloques del emplantillado analizados | {st.get('bloques', 0)} | u |")
    w(f"| Bloques dentro de un muro reconocido | {st.get('bloques_reconocidos', 0)} | u |")
    w(f"| % de bloques reconocidos | {st.get('pct_bloques', 0):.2f} | % |")
    w("")
    w("## Cantidades generadas")
    w("")
    w("| Elemento | Capa | Cantidad de objetos | Longitud | Unidad |")
    w("|---|---|---|---|---|")
    for (el, capa), (n, lg) in sorted(info["resumen"].items()):
        w(f"| {el} | {capa} | {n} | {lg:.3f} | m |")
    w("")
    w("## Marcas en REVISION por motivo")
    w("")
    cnt = por_motivo(info["revisiones"])
    if cnt:
        w("| Motivo | Marcas |")
        w("|---|---|")
        for m, n in sorted(cnt.items()):
            w(f"| {m} | {n} |")
    else:
        w("Sin marcas.")
    w("")
    if info.get("avisos"):
        w("## Avisos")
        w("")
        for a in info["avisos"]:
            w(f"- {a}")
        w("")
    w("## Archivos")
    w("")
    for a in info["archivos"]:
        w(f"- `{a}`")
    w("")
    w("## Limitaciones de esta versión")
    w("")
    for a in LIMITACIONES:
        w(f"- {a}")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


LIMITACIONES = [
    "Muros rectos: caras dibujadas como pares de líneas (LINE, LWPOLYLINE, POLYLINE) o emplantillado de blocks (INSERT). No lee xrefs no enlazados, MLINE ni hatch como muro.",
    "Los arcos (muros curvos) no se analizan: van a REVISION.",
    "Las ventanas no se detectan en planta (el muro sigue dibujado bajo la ventana).",
    "El vano en extremo libre (hueco de puerta entre el fin de un muro y la cara del que cruza) se deduce y queda con observación 'verificar'.",
    "Mochetas y columnas solo se usan para recortar extremos de muro y descontar en vanos (no se cuantifican). En una L sin mocheta, la regla del motor deja la esquina sin muro.",
    "No asigna ejes (EP1-EP3).",
    "El bloque de muro es estático (ezdxf no crea el xMuro dinámico): el largo va en el atributo LARGO y en la escala X.",
    "El tipo de cimiento sale de las etiquetas del plano: un eje sin etiqueta a <= 2.2 m o con etiquetas de tipos distintos queda sin cimiento y va a REVISION.",
]
