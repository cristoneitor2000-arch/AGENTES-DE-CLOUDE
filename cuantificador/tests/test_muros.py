"""Reconocimiento de muros y cimiento sobre los DXF sintéticos: longitudes esperadas calculadas a mano.

Reglas (confirmadas por Chris, punto 5; motor est.py de la oficina):
  muro de eje a eje; donde otro eje pasa por el extremo se recorta medio espesor PROPIO (L sin mocheta:
  la esquina queda sin muro); con mocheta/columna en el extremo, el muro más largo llega a su cara lejana
  y el otro a la cara cercana; cruz: el más largo continuo, el otro se parte en el eje.
  cimiento: L al cruce de ejes (polilínea unida); T y cruz hasta la cara del cimiento que cruza; corrido por vanos.
  vano de puerta: claro libre de 0.70 a 1.50 descontando columnas.
Tipos de cimiento de PRUEBA (por etiqueta): CC1 ancho 0.40, MC1 ancho 0.50; tabiques de 0.10 sin cimiento.
"""
import math

import pytest

import cimiento
import lector
import muros
import revision

TOL = 1e-6
ESPERADO = [  # (tipo, espesor, p0, p1)
    ("muro", .15, (0, 0), (4, 0)),                     # 1 recto, extremos libres
    ("muro", .15, (10.075, 0), (14, 0)),               # 2 L sin mocheta: cada uno recorta medio espesor propio
    ("muro", .15, (10, .075), (10, 3)),
    ("muro", .15, (20, 0), (26, 0)),                   # 3 T: corrido 6.00
    ("muro", .15, (23, .075), (23, 3)),                #   el que llega: eje (y=0) + 0.075
    ("muro", .20, (60, 0), (66, 0)),                   # 3b T mixta
    ("muro", .10, (63, .05), (63, 3)),                 #   0.10: recorta medio espesor PROPIO (0.05)
    ("muro", .15, (30, 0), (36, 0)),                   # 4 cruz: el largo continuo
    ("muro", .15, (33, -2), (33, -.075)),              #   el corto partido en el eje, cada lado - 0.075
    ("muro", .15, (33, .075), (33, 2)),
    ("muro", .15, (40, 0), (42, 0)),                   # 5 muro | vano 0.90 | muro
    ("vano", .15, (42, 0), (42.9, 0)),
    ("muro", .15, (42.9, 0), (46, 0)),
    ("muro", .15, (90, 0), (93, 0)),                   # 9 vano en extremo libre (0.925)
    ("vano", .15, (93, 0), (93.925, 0)),
    ("muro", .15, (94, -2), (94, 2)),
]
CIM_ESPERADO = [  # (ancho, puntos)
    (.40, [(0, 0), (4, 0)]),
    (.40, [(14, 0), (10, 0), (10, 3)]),                # L al cruce de ejes, unida: 7.00
    (.40, [(20, 0), (26, 0)]), (.40, [(23, .20), (23, 3)]),
    (.50, [(60, 0), (66, 0)]),                         # el tabique de 0.10 no lleva
    (.40, [(30, 0), (36, 0)]), (.40, [(33, -2), (33, -.20)]), (.40, [(33, .20), (33, 2)]),
    (.40, [(40, 0), (46, 0)]),                         # corrido por el vano
    (.40, [(90, 0), (93.8, 0)]), (.40, [(94, -2), (94, 2)]),
]


@pytest.fixture(scope="module")
def res(plano, conf):
    doc, _ = lector.leer(plano)
    segs, arcos, _, _ = lector.extraer(doc, ["A-MURO"], 1.0)
    P = muros.Param.desde_config(conf[1])
    return muros.reconocer(segs, P), segs, arcos, P, lector.extraer_etiquetas(doc, 1.0)


def _norm(p0, p1):
    a, b = (round(p0[0], 6), round(p0[1], 6)), (round(p1[0], 6), round(p1[1], 6))
    return tuple(sorted((a, b)))


def _canon(pts):
    a = tuple((round(x, 6), round(y, 6)) for x, y in pts)
    return min(a, a[::-1])


def test_tramos_exactos(res):
    obtenidos = sorted((t["tipo"], round(t["esp"], 2), _norm(t["p0"], t["p1"])) for t in res[0].tramos)
    assert obtenidos == sorted((t, e, _norm(a, b)) for t, e, a, b in ESPERADO)


def test_largos(res):
    tot = {}
    for t in res[0].tramos:
        assert abs(t["largo"] - math.dist(t["p0"], t["p1"])) < TOL
        tot[(t["tipo"], round(t["esp"], 2))] = tot.get((t["tipo"], round(t["esp"], 2)), 0) + t["largo"]
    assert tot[("muro", .15)] == pytest.approx(41.725, abs=TOL)
    assert tot[("muro", .20)] == pytest.approx(6.0, abs=TOL)
    assert tot[("muro", .10)] == pytest.approx(2.95, abs=TOL)
    assert tot[("vano", .15)] == pytest.approx(1.825, abs=TOL)


def test_traslapes_solo_t_mixta(res):
    """La regla del motor (medio espesor propio) solo traslapa en la T de espesores distintos: 0.05 x 0.10."""
    polys = [revision.rect_tramo(t) for t in res[0].tramos]
    tras = []
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            a = polys[i].intersection(polys[j]).area
            if a > 1e-9:
                tras.append((round(a, 6), sorted((res[0].tramos[i]["esp"], res[0].tramos[j]["esp"]))))
    assert tras == [(0.005, [0.10, 0.20])]


def test_cimiento_por_etiquetas(res, tipos_prueba):
    r, *_, et = res
    asig, rv, labs = cimiento.asignar_tipos(r.corridas, et, tipos_prueba, {0.10}, 2.2)
    assert rv == [] and len(labs) == 11
    cims = cimiento.generar(r.corridas, tipos_prueba, asig, "Cimiento corrido {tipo} de {ancho} x {peralte} m")
    obt = sorted((round(c["regla"]["ancho"], 2), _canon(c["pts"])) for c in cims)
    assert obt == sorted((a, _canon(p)) for a, p in CIM_ESPERADO)
    for c in cims:
        assert c["largo"] == pytest.approx(sum(math.dist(a, b) for a, b in zip(c["pts"], c["pts"][1:])), abs=TOL)
    assert sum(c["largo"] for c in cims if c["regla"]["ancho"] == .40) == pytest.approx(43.2, abs=TOL)
    assert cimiento.validar_etiquetas(labs, cims, 2.2) == []


def test_cimiento_sin_tipos_o_sin_etiqueta_va_a_revision(res, tipos_prueba):
    r, *_, et = res
    asig, rv, _ = cimiento.asignar_tipos(r.corridas, et, {}, {0.10}, 2.2)
    assert asig == {} and len(rv) == len(r.corridas) - 1 and {x.motivo for x in rv} == {"cimiento sin etiqueta"}
    asig, rv, _ = cimiento.asignar_tipos(r.corridas, [], tipos_prueba, {0.10}, 2.2)
    assert asig == {} and {x.motivo for x in rv} == {"cimiento sin etiqueta"}


def test_tipo_por_defecto_declarado(res, tipos_prueba):
    r, *_ = res
    dflt = set()
    asig, rv, _ = cimiento.asignar_tipos(r.corridas, [], tipos_prueba, {0.10}, 2.2, por_defecto={"otros": "CC1"}, defecto=dflt)
    assert rv == [] and set(asig.values()) == {"CC1"} and len(dflt) == len(r.corridas) - 1


def test_etiquetas_de_tipos_distintos(res, tipos_prueba):
    r, *_ = res
    et = [lector.Etiqueta("CC1", 2, -0.6, "1", "T"), lector.Etiqueta("MC1", 3, -0.6, "2", "T")]
    asig, rv, _ = cimiento.asignar_tipos(r.corridas, et, tipos_prueba, {0.10}, 2.2)
    assert "etiquetas de tipos distintos" in {x.motivo for x in rv}


def test_etiqueta_sin_tramo(tipos_prueba):
    lab = [("CC1", lector.Etiqueta("CC1", 0, 0, "9", "T"))]
    cims = [dict(regla={"tipo": "CC1"}, pts=[(10, 0), (12, 0)])]
    assert [x.motivo for x in cimiento.validar_etiquetas(lab, cims, 2.2)] == ["etiqueta sin tramo de su tipo"]


def test_revisiones(res):
    r, segs, arcos, P, _ = res
    rv, st = revision.cobertura(segs, arcos, r, P)
    assert sorted(x.motivo for x in rv) == ["eje muy corto", "espesor fuera de lista", "segmento sin pareja"]
    assert [(x.motivo, round(x.x, 6), round(x.y, 6)) for x in r.revisiones] == [("esquina en L sin mocheta", 10.0, 0.0)]
    assert st["segmentos"] == 65
    # no reconocido = suelto 2.00 + fuera de lista (2 x 3.00 + 2 x 0.25) + corto (2 x 0.12 + 2 x 0.15) = 9.04
    assert st["largo_total"] - st["largo_reconocido"] == pytest.approx(9.04, abs=1e-6)


def test_ambiguo():
    segs = [lector.Seg(0, (0, 0), (3, 0), "A", "M", "LINE"), lector.Seg(1, (0, .10), (3, .10), "B", "M", "LINE"),
            lector.Seg(2, (0, .25), (3, .25), "C", "M", "LINE")]
    P = muros.Param(espesores=[.10, .15, .20])
    r = muros.reconocer(segs, P)
    assert r.tramos == []
    rv, _ = revision.cobertura(segs, [], r, P)
    assert {x.motivo for x in rv} == {"traslape ambiguo"}


def test_hueco_no_clasificado():
    """Hueco de 0.40: ni unión (<= 0.25) ni vano (0.70–1.50)."""
    segs = []
    for i, (a, b) in enumerate([(0, 2), (2.4, 5)]):
        segs += [lector.Seg(len(segs), (a, -.075), (b, -.075), str(i), "M", "LINE"),
                 lector.Seg(len(segs) + 1, (a, .075), (b, .075), str(i), "M", "LINE")]
    r = muros.reconocer(segs, muros.Param(espesores=[.15]))
    assert [x.motivo for x in r.revisiones] == ["hueco no clasificado"]
    assert sorted(round(t["largo"], 6) for t in r.tramos) == [2.0, 2.6]


def test_vano_fuera_de_rango():
    """Hueco de 1.80 (> 1.50): no es vano, son dos muros."""
    segs = []
    for i, (a, b) in enumerate([(0, 2), (3.8, 5)]):
        segs += [lector.Seg(len(segs), (a, -.075), (b, -.075), str(i), "M", "LINE"),
                 lector.Seg(len(segs) + 1, (a, .075), (b, .075), str(i), "M", "LINE")]
    r = muros.reconocer(segs, muros.Param(espesores=[.15]))
    assert [t["tipo"] for t in r.tramos] == ["muro", "muro"] and r.revisiones == []


def test_escala_mm(tmp_path, conf):
    import ezdxf
    from ezdxf.math import Matrix44
    import crear_dxf_prueba
    doc = ezdxf.readfile(crear_dxf_prueba.crear(str(tmp_path / "m.dxf")))
    for e in doc.modelspace():
        e.transform(Matrix44.scale(1000, 1000, 1))
    doc.units = 4
    doc.saveas(tmp_path / "mm.dxf")
    d2, _ = lector.leer(str(tmp_path / "mm.dxf"))
    assert lector.unidades(d2)[2] == 0.001
    segs, *_ = lector.extraer(d2, ["A-MURO"], 0.001)
    r = muros.reconocer(segs, muros.Param.desde_config(conf[1]))
    assert sum(t["largo"] for t in r.tramos if t["tipo"] == "muro" and round(t["esp"], 2) == .15) == pytest.approx(41.725, abs=1e-6)


def test_replicado_sin_cruces_entre_copias(plano, conf):
    src, _ = lector.leer(plano)
    segs1, *_ = lector.extraer(src, ["A-MURO"], 1.0)
    P = muros.Param.desde_config(conf[1])
    r1 = muros.reconocer(segs1, P)
    rv1, _ = revision.cobertura(segs1, [], r1, P)
    segs = []
    for i in range(4):
        for j in range(4):
            for s in segs1:
                segs.append(lector.Seg(len(segs), (s.p0[0] + 110 * i, s.p0[1] + 12 * j), (s.p1[0] + 110 * i, s.p1[1] + 12 * j),
                                       s.handle, s.capa, s.tipo))
    r = muros.reconocer(segs, P)
    rv, _ = revision.cobertura(segs, [], r, P)
    assert len(r.tramos) == 16 * len(r1.tramos)
    assert sum(t["largo"] for t in r.tramos) == pytest.approx(16 * sum(t["largo"] for t in r1.tramos), abs=1e-6)
    assert len(rv) == 16 * len(rv1)


# ------------------------------------------------------------------ emplantillado de blocks
@pytest.fixture(scope="module")
def rb(plano_bloques, conf):
    d, _ = lector.leer(plano_bloques)
    bl, malos = lector.extraer_bloques(d, ["BLK", "TABIQUE"], 1.0)
    assert malos == []
    cols = lector.extraer_poligonos(d, ["COL"], 1.0)
    zap = lector.extraer_poligonos(d, ["ZAP"], 1.0)
    P = muros.Param.desde_config(conf[1], espesor_por_capa={"TABIQUE": 0.10})
    return muros.reconocer([], P, bl, cols), bl, cols, zap, P, lector.extraer_etiquetas(d, 1.0)


def test_bloques_tramos(rb):
    r = rb[0]
    obt = sorted((t["tipo"], round(t["esp"], 2), _norm(t["p0"], t["p1"])) for t in r.tramos)
    esp = sorted([
        ("muro", .15, _norm((0, 0), (2, 0))), ("vano", .15, _norm((2, 0), (2.9, 0))),
        ("muro", .15, _norm((2.9, 0), (7.2, 0))),                          # la columna de 0.30 queda dentro del muro
        ("muro", .30, _norm((10, .075), (16.2, .075))),                    # doble hilada = contención, colas absorbidas
        ("muro", .10, _norm((20, 0), (22, 0))),                            # espesor declarado por capa
        ("muro", .15, _norm((29.85, 0), (34.15, 0))),                      # L con columna: el largo a la cara lejana
        ("muro", .15, _norm((30, .15), (30, 3.35))),                       #   el otro a la cara cercana
    ])
    assert obt == esp
    assert r.revisiones == []


def test_bloques_sin_columnas(rb):
    _, bl, _, _, P, _ = rb
    r = muros.reconocer([], P, bl, [])
    assert "hueco no clasificado" in {x.motivo for x in r.revisiones}   # sin la columna, el hueco de 0.30 no se adivina


def test_bloques_cimiento_y_zapata(rb, tipos_prueba):
    r, _, _, zap, _, et = rb
    asig, rv, labs = cimiento.asignar_tipos(r.corridas, et, tipos_prueba, {0.10}, 2.2)
    assert rv == []
    cims = cimiento.separar_zapatas(cimiento.generar(r.corridas, tipos_prueba, asig, "C {tipo} {ancho} {peralte}"), zap)
    got = sorted((c["capa"], round(c["largo"], 6)) for c in cims)
    assert got == sorted([("C CC1 0.40 0.20", 2.5), ("C CC1 0.40 0.20 (dentro de zapata)", 2.0), ("C CC1 0.40 0.20", 2.7),
                          ("C CC1 0.40 0.20", 7.5), ("C MC1 0.50 0.20", 6.2)])
    assert cimiento.validar_etiquetas(labs, cims, 2.2) == []


def test_bloques_cobertura(rb):
    r, bl, _, _, P, _ = rb
    rv, st = revision.cobertura([], [], r, P, bl)
    assert rv == [] and st["bloques"] == len(bl) and st["pct_bloques"] == 100.0
