"""Reconocimiento de muros y cimiento sobre el DXF sintético: longitudes esperadas calculadas a mano.

Convención probada ([Supuesto] hasta que Chris la confirme):
  L  -> el más largo se lleva la esquina; el otro llega a su cara
  T  -> el que llega termina en la cara del corrido
  cruz -> el más largo continuo; el otro se corta en las caras
  cimiento: L al cruce de ejes (polilínea unida), T y cruz hasta la cara del cimiento que cruza, corrido por vanos
Reglas de cimiento de PRUEBA: 0.10 sin cimiento; 0.15 ancho 0.40; 0.20 ancho 0.50.
"""
import json
import math
import os

import pytest

import cimiento
import lector
import muros

TOL = 1e-6
# (tipo, espesor, p0, p1)  -> el largo es la distancia p0-p1
ESPERADO = [
    ("muro", .15, (0, 0), (4, 0)),                     # 1 recto
    ("muro", .15, (9.925, 0), (14, 0)),                # 2 L: A (4.00 a ejes) se lleva la esquina = 4.075
    ("muro", .15, (10, .075), (10, 3)),                #   L: B llega a la cara de A = 2.925
    ("muro", .15, (20, 0), (26, 0)),                   # 3 T: corrido 6.00
    ("muro", .15, (23, .075), (23, 3)),                #   T: el que llega, 2.925
    ("muro", .20, (60, 0), (66, 0)),                   # 3b T mixta
    ("muro", .10, (63, .10), (63, 3)),                 #   0.10 a la cara del de 0.20 = 2.90
    ("muro", .15, (30, 0), (36, 0)),                   # 4 cruz: el largo continuo 6.00
    ("muro", .15, (33, -2), (33, -.075)),              #   el corto en dos: 1.925 + 1.925
    ("muro", .15, (33, .075), (33, 2)),
    ("muro", .15, (40, 0), (42, 0)),                   # 5 vano: muro | vano | muro
    ("vano", .15, (42, 0), (42.9, 0)),
    ("muro", .15, (42.9, 0), (46, 0)),
    ("muro", .15, (90, 0), (93, 0)),                   # 9 vano en extremo libre
    ("vano", .15, (93, 0), (93.925, 0)),
    ("muro", .15, (94, -2), (94, 2)),
]
CIM_ESPERADO = [  # (ancho, puntos)
    (.40, [(0, 0), (4, 0)]),
    (.40, [(14, 0), (10, 0), (10, 3)]),               # L unida al cruce de ejes: 7.00
    (.40, [(20, 0), (26, 0)]), (.40, [(23, .20), (23, 3)]),        # T: 3 - 0.20 = 2.80
    (.50, [(60, 0), (66, 0)]),                                        # el 0.10 no lleva
    (.40, [(30, 0), (36, 0)]), (.40, [(33, -2), (33, -.20)]), (.40, [(33, .20), (33, 2)]),
    (.40, [(40, 0), (46, 0)]),                                        # corrido por el vano
    (.40, [(90, 0), (93.8, 0)]), (.40, [(94, -2), (94, 2)]),         # vano en extremo: hasta la cara del cimiento
]


@pytest.fixture(scope="module")
def res(plano, conf):
    _, cfg = conf
    doc, _ = lector.leer(plano)
    segs, arcos, _, _ = lector.extraer(doc, ["A-MURO"], 1.0)
    P = muros.Param.desde_config(cfg)
    return muros.reconocer(segs, P), segs, arcos, P


def _norm(p0, p1):
    a, b = (round(p0[0], 6), round(p0[1], 6)), (round(p1[0], 6), round(p1[1], 6))
    return tuple(sorted((a, b)))


def test_tramos_exactos(res):
    r = res[0]
    obtenidos = sorted((t["tipo"], round(t["esp"], 2), _norm(t["p0"], t["p1"])) for t in r.tramos)
    esperados = sorted((t, e, _norm(a, b)) for t, e, a, b in ESPERADO)
    assert obtenidos == esperados


def test_largos(res):
    r = res[0]
    for t in r.tramos:
        assert abs(t["largo"] - math.dist(t["p0"], t["p1"])) < TOL
    tot = {}
    for t in r.tramos:
        tot[(t["tipo"], round(t["esp"], 2))] = tot.get((t["tipo"], round(t["esp"], 2)), 0) + t["largo"]
    assert tot[("muro", .15)] == pytest.approx(41.875, abs=TOL)
    assert tot[("muro", .20)] == pytest.approx(6.0, abs=TOL)
    assert tot[("muro", .10)] == pytest.approx(2.9, abs=TOL)
    assert tot[("vano", .15)] == pytest.approx(1.825, abs=TOL)


def test_sin_traslapes_entre_muros(res):
    from shapely.geometry import Polygon
    from revision import rect_tramo
    polys = [rect_tramo(t) for t in res[0].tramos]
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            assert polys[i].intersection(polys[j]).area < 1e-9, (res[0].tramos[i], res[0].tramos[j])


def test_esquina_l_suma_a_ejes(res):
    L = [t for t in res[0].tramos if 9 < t["p0"][0] < 15 and t["tipo"] == "muro"]
    assert sum(t["largo"] for t in L) == pytest.approx(7.0, abs=TOL)


def test_cimiento(res, reglas_prueba):
    r = res[0]
    cims, rv = cimiento.generar(r.corridas, reglas_prueba, "Cimiento corrido {tipo} de {ancho} x {peralte} m")
    assert rv == []
    obt = sorted((round(c["regla"]["ancho"], 2), tuple((round(x, 6), round(y, 6)) for x, y in c["pts"])) for c in cims)
    def canon(pts):
        a = tuple((round(x, 6), round(y, 6)) for x, y in pts)
        return min(a, a[::-1])
    obt = sorted((a, canon(p)) for a, p in obt)
    esp = sorted((a, canon(p)) for a, p in CIM_ESPERADO)
    assert obt == esp
    for c in cims:
        assert c["largo"] == pytest.approx(sum(math.dist(a, b) for a, b in zip(c["pts"], c["pts"][1:])), abs=TOL)
    assert sum(c["largo"] for c in cims if c["regla"]["ancho"] == .40) == pytest.approx(43.2, abs=TOL)


def test_cimiento_sin_regla_va_a_revision(res):
    cims, rv = cimiento.generar(res[0].corridas, {}, "x {tipo} {ancho} {peralte}")
    assert cims == []
    assert len(rv) == len(res[0].corridas)
    assert all(r.motivo == "sin regla de cimiento" for r in rv)


def test_cimiento_regla_incompleta(res):
    cims, rv = cimiento.generar(res[0].corridas, {"0.15": {"con_cimiento": True, "tipo": "CC1"}}, "x {tipo} {ancho} {peralte}")
    assert any("incompleta" in r.detalle for r in rv)


def test_revisiones(res):
    import revision
    r, segs, arcos, P = res
    rv, st = revision.cobertura(segs, arcos, r, P)
    mot = sorted(x.motivo for x in rv)
    assert mot == ["eje muy corto", "espesor fuera de lista", "segmento sin pareja"]
    pos = {x.motivo: (x.x, x.y) for x in rv}
    assert 79.9 < pos["eje muy corto"][0] < 80.2
    assert 70 < pos["espesor fuera de lista"][0] < 73
    assert 50 < pos["segmento sin pareja"][0] < 52
    assert st["segmentos"] == 65
    # no reconocido = suelto 2.00 + fuera de lista (2 x 3.00 + 2 x 0.25) + corto (2 x 0.12 + 2 x 0.15) = 9.04
    assert st["largo_total"] - st["largo_reconocido"] == pytest.approx(9.04, abs=1e-6)


def test_ambiguo():
    """Tres paralelas a 0.10 y 0.15 de la del medio: no se adivina."""
    from lector import Seg
    segs = [Seg(0, (0, 0), (3, 0), "A", "M", "LINE"), Seg(1, (0, .10), (3, .10), "B", "M", "LINE"),
            Seg(2, (0, .25), (3, .25), "C", "M", "LINE")]
    P = muros.Param(espesores=[.10, .15, .20])
    r = muros.reconocer(segs, P)
    assert r.tramos == []
    import revision
    rv, _ = revision.cobertura(segs, [], r, P)
    assert {x.motivo for x in rv} == {"traslape ambiguo"}


def test_hueco_no_clasificado():
    """Hueco de 0.40 entre dos tramos colineales: ni junta (<= 0.25) ni vano (>= 0.60)."""
    from lector import Seg
    segs = []
    for i, (a, b) in enumerate([(0, 2), (2.4, 5)]):
        segs += [Seg(len(segs), (a, -.075), (b, -.075), str(i), "M", "LINE"), Seg(len(segs) + 1, (a, .075), (b, .075), str(i), "M", "LINE")]
    P = muros.Param(espesores=[.15])
    r = muros.reconocer(segs, P)
    assert [x.motivo for x in r.revisiones] == ["hueco no clasificado"]
    assert sorted(round(t["largo"], 6) for t in r.tramos) == [2.0, 2.6]


def test_escala_mm(tmp_path, conf):
    """El mismo plano en mm (factor 0.001) da las mismas longitudes en m."""
    import ezdxf
    import crear_dxf_prueba
    src = crear_dxf_prueba.crear(str(tmp_path / "m.dxf"))
    doc = ezdxf.readfile(src)
    from ezdxf.math import Matrix44
    for e in doc.modelspace():
        e.transform(Matrix44.scale(1000, 1000, 1))
    doc.units = 4
    doc.saveas(tmp_path / "mm.dxf")
    d2, _ = lector.leer(str(tmp_path / "mm.dxf"))
    assert lector.unidades(d2)[2] == 0.001
    segs, *_ = lector.extraer(d2, ["A-MURO"], 0.001)
    r = muros.reconocer(segs, muros.Param.desde_config(conf[1]))
    assert sum(t["largo"] for t in r.tramos if t["tipo"] == "muro" and round(t["esp"], 2) == .15) == pytest.approx(41.875, abs=1e-6)


def test_replicado_sin_cruces_entre_copias(plano, conf):
    """4 x 4 copias del plano: todo debe dar exactamente 16 veces lo de una copia (el índice espacial no mezcla)."""
    import ezdxf
    import revision
    src = ezdxf.readfile(plano)
    segs1, *_ = lector.extraer(src, ["A-MURO"], 1.0)
    P = muros.Param.desde_config(conf[1])
    r1 = muros.reconocer(segs1, P)
    rv1, _ = revision.cobertura(segs1, [], r1, P)
    from lector import Seg
    segs = []
    for i in range(4):
        for j in range(4):
            for s in segs1:
                segs.append(Seg(len(segs), (s.p0[0] + 110 * i, s.p0[1] + 12 * j), (s.p1[0] + 110 * i, s.p1[1] + 12 * j), s.handle, s.capa, s.tipo))
    r = muros.reconocer(segs, P)
    rv, _ = revision.cobertura(segs, [], r, P)
    assert len(r.tramos) == 16 * len(r1.tramos)
    assert sum(t["largo"] for t in r.tramos) == pytest.approx(16 * sum(t["largo"] for t in r1.tramos), abs=1e-6)
    assert len(rv) == 16 * len(rv1)
