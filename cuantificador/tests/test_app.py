"""La interfaz abre, lista capas, cuantifica y habilita 'Abrir carpeta' (requiere pantalla; en Linux: xvfb-run)."""
import copy
import os

import pytest

tk = pytest.importorskip("tkinter")


def test_interfaz(plano, conf, tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("sin pantalla")
    import app
    a = app.App(root)
    a.cfg = dict(conf[1], carpeta_salida=str(tmp_path))
    a.seleccionar(plano)
    assert "A-MURO" in [c for c, _, _ in a.capas]
    assert a.v_fac.get() == "1.0"
    a.marcar("A-MURO", "muros")
    assert a.capas_elegidas("muros") == ["A-MURO"]
    assert a.tv.item("A-MURO", "values")[2] == "✔"
    a._agregar_tipo("CC1", "0.40", "0.20", 2, 52)
    a._agregar_tipo("MC1", "0.50", "0.20", 4, 144)
    assert a.tipos()["CC1"] == {"ancho": 0.40, "peralte": 0.20, "color": 2, "color_dentro": 52}
    a.v_alt.set("2.80")
    a.cuantificar(esperar=True)
    for _ in range(50):
        root.update()
        if not a.trabajando:
            break
    assert not a.trabajando and a.salida and os.path.isdir(a.salida)
    assert str(a.btn_abrir["state"]) == "normal"
    assert a.prog["value"] == 100
    log = a.log_txt.get("1.0", "end")
    assert "Reconocido" in log and "ERROR" not in log
    assert any(e["elemento"] == "Cimiento corrido" for e in a.ultimo["elementos"])
    root.destroy()
