"""cimiento.py – cimiento corrido a partir de los ejes de muro.

Regla por espesor de muro (convenciones.json > cimiento > reglas, clave '0.15'):
    {"con_cimiento": true, "tipo": "CC1", "ancho": 0.40, "peralte": 0.20, "color": 2}
    {"con_cimiento": false}                -> el muro no lleva cimiento (sin marca)
Espesor sin regla o con regla incompleta -> REVISION (no se inventa).

Trazo (convención [Supuesto] de esquinas):
- L: los dos llegan al cruce de ejes y, si son de la misma capa, se unen en una sola polilínea.
- T: el que llega termina en la cara del cimiento que cruza (medio ancho de ese cimiento).
- Cruz: el cimiento del muro más largo sigue continuo; el otro se corta en las caras.
- Vano de puerta: el cimiento pasa corrido (corrido_por_vanos).
- Extremo libre: termina donde termina el eje del muro.
Polilínea ABIERTA con ancho global = ancho real.
"""
from muros import Revision, _interseccion, _quitar


def clave_espesor(e):
    return f"{e:.2f}"


def regla(reglas, esp):
    """(regla | None, problema | None)."""
    r = reglas.get(clave_espesor(esp))
    if r is None:
        return None, f"sin regla de cimiento para muro de {esp:.2f} m"
    if r.get("con_cimiento") is False:
        return {"con_cimiento": False}, None
    faltan = [k for k in ("tipo", "ancho", "peralte") if r.get(k) in (None, "")]
    if faltan:
        return None, f"regla de cimiento incompleta para {esp:.2f} m (falta {', '.join(faltan)})"
    try:
        a, p = float(r["ancho"]), float(r["peralte"])
    except (TypeError, ValueError):
        return None, f"regla de cimiento con ancho/peralte no numérico para {esp:.2f} m"
    if a <= 0 or p <= 0:
        return None, f"regla de cimiento con medidas no positivas para {esp:.2f} m"
    return dict(r, con_cimiento=True, ancho=a, peralte=p), None


def generar(corridas, reglas, capa_fmt, corrido_por_vanos=True):
    """Devuelve (cimientos, revisiones). cimientos: [{capa, regla, pts, largo, corridas, esp}]"""
    revisiones = []
    R = {}
    for W in corridas:
        r, prob = regla(reglas, W.esp)
        R[W.id] = r
        if prob:
            m = W.punto(W.a + (W.b - W.a) / 3)   # a 1/3 del eje: en un cruce no se tapan las dos marcas
            revisiones.append(Revision("sin regla de cimiento", m[0], m[1], prob + f" (eje de {W.largo:.3f} m)"))

    def ancho(xid):
        r = R.get(xid)
        return r["ancho"] if r and r.get("con_cimiento") else 0.0

    def capa(r):
        return capa_fmt.format(tipo=r["tipo"], ancho=f"{r['ancho']:.2f}", peralte=f"{r['peralte']:.2f}")

    piezas = []   # dict(corrida, t0, t1, capa, regla, link0, link1)
    for W in corridas:
        r = R[W.id]
        if not r or not r.get("con_cimiento"):
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
    return _encadenar(piezas, corridas), revisiones


def _encadenar(piezas, corridas):
    """Une en una polilínea las piezas de la misma capa que se encuentran en L."""
    extremo = {}   # (corrida, k) -> (indice pieza, k)
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
        """Recorre desde la pieza i entrando por el extremo k_entrada."""
        cad = []
        while i is not None and i not in usados:
            usados.add(i)
            k_salida = 1 - k_entrada
            cad.append((i, k_entrada))
            nx = vecino(i, k_salida)
            if nx is None:
                break
            i, k_entrada = nx
        return cad

    # primero las cadenas abiertas (empiezan en un extremo sin vecino)
    for i in range(len(piezas)):
        if i in usados:
            continue
        for k in (0, 1):
            if vecino(i, k) is None:
                cadenas.append(recorrer(i, k))
                break
    # lo que queda son ciclos cerrados: se cortan en cualquier punto (polilínea abierta)
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
            if not pts:
                pts.append(pa)
            elif abs(pts[-1][0] - pa[0]) > 1e-6 or abs(pts[-1][1] - pa[1]) > 1e-6:
                pts.append(pa)   # no debería pasar: el encuentro en L comparte el cruce de ejes
            pts.append(pb)
            largo += p["t1"] - p["t0"]
            cors.append(p["corrida"])
        p0 = piezas[cad[0][0]]
        out.append(dict(capa=p0["capa"], regla=p0["regla"], pts=pts, largo=largo, corridas=cors, esp=p0["esp"]))
    return out
