"""escritor.py – escribe el DXF cuantificado sobre la COPIA del plano.

- Machote: todo el espacio modelo a la capa 00 (color 8, bloqueada) y el resto de capas originales bloqueadas.
- Muros y vanos: bloque estático 'xMuro <cm>' (rectángulo de 1 m x espesor + hatch sólido, dentro del bloque)
  insertado en el inicio del tramo, rotado, con escala X = largo en m y atributos ID, TIPO, ESPESOR, LARGO,
  ALTO, AREA (color 250, invisibles). En la capa de muro solo hay INSERT (QA R10).
- Cimiento: polilínea abierta por el eje con ancho global = ancho real, al fondo del orden de dibujo.
- REVISION: círculo rojo + texto con el motivo.
- Grupos de capas y guardado con auditoría y control de $HANDSEED (funciones de cuantdxf.py,
  skill dxf-unificado-cuantificacion).
"""
import math
import os

import ezdxf
from ezdxf.entities import DXFGraphic

INVALIDOS = set('<>/\\":;?*|,=`')
TAGS = ("ID", "TIPO", "ESPESOR", "LARGO", "ALTO", "AREA")
DESC = "Generado por el cuantificador automático v1"


def validar_capa(n):
    malos = [c for c in n if c in INVALIDOS]
    if malos:
        raise ValueError(f"Nombre de capa inválido {n!r}: {malos}")
    return n


def capa(doc, nombre, color, transparencia=0.0, descripcion=DESC):
    validar_capa(nombre)
    if nombre in doc.layers:
        L = doc.layers.get(nombre)
        L.color = color
    else:
        L = doc.layers.add(nombre, color=color)
    L.on()
    L.thaw()
    L.unlock()
    if transparencia:
        L.transparency = transparencia
    if descripcion:
        try:
            L.description = descripcion
        except Exception:
            pass
    return L


def preparar_machote(doc, conv, capas_nuevas=()):
    m = conv["machote"]
    n = 0
    for e in doc.modelspace():
        if e.dxf.layer != m["capa"]:
            e.dxf.layer = m["capa"]
            n += 1
    L = capa(doc, m["capa"], m["color"], 0.0, "Machote: plano original")
    if m.get("bloquear_capas_originales", True):
        for l in doc.layers:
            nm = l.dxf.name
            if nm in ("0", "Defpoints", m["capa"]) or nm in capas_nuevas:
                continue
            l.lock()
    if m.get("bloquear", True):
        L.lock()
    return n


def nombre_bloque(doc, base, propios):
    """Si el plano ya trae un bloque con ese nombre (p. ej. el xMuro dinámico), usa otro nombre."""
    if base in propios or base not in doc.blocks:
        return base
    return base + " CUANT"


def definir_bloque_muro(doc, nombre, esp, k, color_attr):
    if nombre in doc.blocks:
        return
    b = doc.blocks.new(name=nombre, base_point=(0, 0))
    h = esp * k / 2
    pts = [(0, -h), (k, -h), (k, h), (0, h)]
    b.add_lwpolyline(pts, close=True, dxfattribs={"layer": "0", "color": 256})
    ht = b.add_hatch(color=256, dxfattribs={"layer": "0"})
    ht.paths.add_polyline_path(pts, is_closed=True)
    for i, tag in enumerate(TAGS):
        b.add_attdef(tag, insert=(0, -h - 0.1 * k * (i + 1)), text="",
                     dxfattribs={"height": 0.08 * k, "layer": "0", "color": color_attr, "flags": 1})


def insertar_muro(msp, bloque, layer, t, k, attrs, color_attr):
    (x0, y0), (x1, y1) = t["p0"], t["p1"]
    rot = math.degrees(math.atan2(y1 - y0, x1 - x0))
    br = msp.add_blockref(bloque, (x0 * k, y0 * k), dxfattribs={"layer": layer, "rotation": rot,
                                                               "xscale": t["largo"], "yscale": 1.0, "zscale": 1.0})
    for i, tag in enumerate(TAGS):
        br.add_attrib(tag, attrs.get(tag, ""), insert=(x0 * k, y0 * k - 0.1 * k * (i + 1)),
                      dxfattribs={"height": 0.08 * k, "layer": layer, "color": color_attr, "flags": 1})
    return br


def polilinea_cimiento(msp, layer, pts, ancho, k):
    return msp.add_lwpolyline([(x * k, y * k) for x, y in pts], close=False,
                              dxfattribs={"layer": layer, "const_width": ancho * k})


def marca_revision(msp, layer, r, radio, alto, k, idx):
    c = msp.add_circle((r.x * k, r.y * k), radio * k, dxfattribs={"layer": layer, "color": 1})
    txt = f"R{idx:03d} {r.motivo}"
    t = msp.add_text(txt, dxfattribs={"layer": layer, "color": 1, "height": alto * k})
    t.set_placement((r.x * k + radio * k * 1.1, r.y * k))
    return c, t


def al_fondo(msp, handles):
    if not handles:
        return
    orden = dict(msp.get_redraw_order())
    for i, h in enumerate(handles, start=1):
        orden[h] = format(i, "X")
    msp.set_redraw_order(orden)


# ------------------------------------------------- grupos de capas (cuantdxf.add_layer_groups, ampliada)
def agregar_grupos(doc, arbol):
    """arbol = [(nombre, [capas], [subárbol])]. Si el plano ya trae grupos, se agregan al lado."""
    head = doc.layers.head
    hx = head.get_extension_dict() if head.has_extension_dict else head.new_extension_dict()

    def nuevo_dict(xd):
        d = xd.add_dictionary("ACLYDICTIONARY", hard_owned=True)
        d.dxf.hard_owned = 1
        d.dxf.cloning = 1
        return d

    raiz = hx["ACLYDICTIONARY"] if "ACLYDICTIONARY" in hx else nuevo_dict(hx)

    def armar(d, nodos):
        usados = set(d.keys())
        i = 1
        for nombre, capas, hijos in nodos:
            while f"*A{i}" in usados:
                i += 1
            key = f"*A{i}"
            usados.add(key)
            xr = d.add_xrecord(key)
            xr.reset([(1, "AcLyLayerGroup"), (90, 1), (300, nombre)] + [(330, doc.layers.get(n).dxf.handle) for n in capas])
            if hijos:
                armar(nuevo_dict(xr.new_extension_dict()), hijos)

    armar(raiz, arbol)


def leer_grupos(doc):
    """{'CUANTIFICACION > MUROS': [capas]} (cuantdxf.read_layer_groups)."""
    h2n = {l.dxf.handle: l.dxf.name for l in doc.layers}
    out = {}
    head = doc.layers.head
    if not head.has_extension_dict or "ACLYDICTIONARY" not in head.get_extension_dict():
        return out

    def walk(d, path):
        for _k, xr in d.items():
            tags = list(xr.tags)
            nombre = [t.value for t in tags if t.code == 300][0]
            out[" > ".join(path + (nombre,))] = sorted(h2n.get(t.value, "?") for t in tags if t.code == 330 and t.value != xr.dxf.owner)
            if xr.has_extension_dict and "ACLYDICTIONARY" in xr.get_extension_dict():
                walk(xr.get_extension_dict()["ACLYDICTIONARY"], path + (nombre,))

    walk(head.get_extension_dict()["ACLYDICTIONARY"], ())
    return out


# ------------------------------------------------- guardado seguro (cuantdxf.save_checked)
def _limpiar_diccionarios(doc):
    n = 0
    for o in list(doc.entitydb.values()):
        if o.dxftype() != "DICTIONARY" or not o.is_alive:
            continue
        for k, v in list(o.items()):
            if isinstance(v, str):
                ent = doc.entitydb.get(v)
                malo = ent is None or isinstance(ent, DXFGraphic)
            else:
                malo = (not hasattr(v, "dxf")) or doc.entitydb.get(v.dxf.handle) is not v or isinstance(v, DXFGraphic)
            if malo:
                o.discard(k)
                n += 1
    return n


def _handle_max_y_seed(ruta):
    lineas = open(ruta, encoding="utf-8", errors="ignore").read().split("\n")
    mx, seed = 0, None
    for i in range(0, len(lineas) - 1):
        c = lineas[i].strip()
        if c == "$HANDSEED":
            seed = int(lineas[i + 2].strip(), 16)
        if c in ("5", "105") and i % 2 == 0:
            try:
                mx = max(mx, int(lineas[i + 1].strip(), 16))
            except ValueError:
                pass
    return mx, seed


def guardar_verificado(doc, ruta):
    n_dict = _limpiar_diccionarios(doc)
    aud = doc.audit()
    doc.saveas(ruta)
    mx, seed = _handle_max_y_seed(ruta)
    d2 = ezdxf.readfile(ruta)
    a2 = d2.audit()
    rep = dict(diccionarios_limpiados=n_dict, auditoria_errores=len(aud.errors), auditoria_correcciones=len(aud.fixes),
               relectura_errores=len(a2.errors), relectura_correcciones=len(a2.fixes),
               handle_max=hex(mx), handseed=hex(seed or 0), handseed_ok=(seed or 0) >= mx,
               tamano_mb=round(os.path.getsize(ruta) / 1e6, 2))
    if not rep["handseed_ok"] or rep["relectura_errores"]:
        raise RuntimeError(f"El DXF de salida no quedó limpio: {rep}")
    return rep, d2
