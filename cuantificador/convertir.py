"""convertir.py – DWG <-> DXF con ODA File Converter (línea de comandos).

ODAFileConverter <carpeta entrada> <carpeta salida> <versión> <tipo> <recursivo> <auditar> [filtro]
  versión: ACAD2018 ... ; tipo: DWG | DXF ; recursivo 0/1 ; auditar 0/1
Se convierte desde una carpeta temporal con una sola copia del archivo, para no tocar el original.
"""
import glob
import os
import shutil
import subprocess
import tempfile


class ODAError(RuntimeError):
    pass


def disponible(oda_exe):
    return bool(oda_exe) and os.path.isfile(oda_exe)


def _convertir(oda_exe, ruta, carpeta_salida, tipo, version, filtro):
    if not disponible(oda_exe):
        raise ODAError(f"No se encontró ODA File Converter en: {oda_exe!r} (revisar config.json > oda_exe)")
    ent = tempfile.mkdtemp(prefix="oda_in_")
    sal = tempfile.mkdtemp(prefix="oda_out_")
    try:
        shutil.copy2(ruta, ent)
        cmd = [oda_exe, ent, sal, version, tipo, "0", "1", filtro]
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = 0x08000000   # CREATE_NO_WINDOW
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, **kw)
        ext = "." + tipo.lower()
        hechos = glob.glob(os.path.join(sal, "*" + ext)) + glob.glob(os.path.join(sal, "*" + ext.upper()))
        if not hechos:
            raise ODAError(f"ODA no generó el {tipo} (código {p.returncode}). {p.stdout[-400:]} {p.stderr[-400:]}")
        base = os.path.splitext(os.path.basename(ruta))[0] + ext
        destino = os.path.join(carpeta_salida, base)
        shutil.copy2(hechos[0], destino)
        err = glob.glob(os.path.join(sal, "*.err"))
        return destino, (open(err[0], encoding="utf-8", errors="ignore").read() if err else "")
    finally:
        shutil.rmtree(ent, ignore_errors=True)
        shutil.rmtree(sal, ignore_errors=True)


def dwg_a_dxf(oda_exe, ruta_dwg, carpeta_salida, version="ACAD2018"):
    return _convertir(oda_exe, ruta_dwg, carpeta_salida, "DXF", version, "*.DWG")


def dxf_a_dwg(oda_exe, ruta_dxf, carpeta_salida, version="ACAD2018"):
    return _convertir(oda_exe, ruta_dxf, carpeta_salida, "DWG", version, "*.DXF")
