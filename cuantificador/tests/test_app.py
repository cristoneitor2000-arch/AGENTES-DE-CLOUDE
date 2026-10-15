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
    assert [c for c, _ in a.capas][:1] and "A-MURO" in a.vars_capas
    assert a.v_fac.get() == "1.0"
    a.vars_capas["A-MURO"].set(True)
    assert a.capas_elegidas() == ["A-MURO"]
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
    root.destroy()
