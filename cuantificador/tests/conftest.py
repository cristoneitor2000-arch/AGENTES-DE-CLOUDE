import json
import os
import sys

import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, AQUI)


@pytest.fixture(scope="session")
def plano(tmp_path_factory):
    import crear_dxf_prueba
    return crear_dxf_prueba.crear(str(tmp_path_factory.mktemp("plano") / "prueba_muros.dxf"))


@pytest.fixture(scope="session")
def conf():
    import pipeline
    return pipeline.cargar_config()


@pytest.fixture(scope="session")
def reglas_prueba():
    with open(os.path.join(AQUI, "convenciones_prueba.json"), encoding="utf-8") as f:
        return json.load(f)["reglas_cimiento_prueba"]
