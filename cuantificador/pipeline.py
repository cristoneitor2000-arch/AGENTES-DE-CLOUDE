"""pipeline.py – proceso completo (lo usa la interfaz y también se puede correr por consola).

python pipeline.py PLANO.dxf --capas "A-MURO,MUROS" [--espesores 0.10,0.15,0.20] [--nivel N1]
                   [--altura 2.80] [--factor 1] [--salida CARPETA] [--conv convenciones.json] [--config config.json]
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import time

import cimiento
import convertir
import escritor
import extraccion
import lector
import muros
import revision


def carpeta_app():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def cargar_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def cargar_config(ruta_conv=None, ruta_cfg=None):
    base = carpeta_app()
    return (cargar_json(ruta_conv or os.path.join(base, "convenciones.json")),
            cargar_json(ruta_cfg or os.path.join(base, "config.json")))


def preparar_entrada(ruta, cfg, log):
    """Lee las capas del plano para la interfaz. Si es DWG lo convierte a DXF en una carpeta temporal."""
    if ruta.lower().endswith(".dwg"):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="cuant_dwg_")
        dxf, err = convertir.dwg_a_dxf(cfg.get("oda_exe"), ruta, tmp, cfg.get("oda_version_salida", "ACAD2018"))
        log(f"DWG convertido a DXF temporal con ODA: {dxf}")
        return dxf
    return ruta


def cuantificar(ruta, capas, espesores, nivel, altura, factor, conv, cfg, log=print, progreso=lambda p: None,
                carpeta_salida=None):
    t_ini = time.perf_counter()
    avisos = []
    ruta = os.path.abspath(ruta)
    sha_ini = lector.sha256(ruta)
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    fecha = datetime.datetime.now()
    base_sal = carpeta_salida or cfg.get("carpeta_salida") or os.path.dirname(ruta)
    salida = os.path.join(base_sal, f"SALIDA_{nombre}_{fecha:%Y-%m-%d_%H%M%S}")
    os.makedirs(salida, exist_ok=False)
    log(f"Carpeta de salida: {salida}")
    progreso(5)

    # 1. copia de trabajo (el original no se abre para escribir)
    if ruta.lower().endswith(".dwg"):
        copia, err = convertir.dwg_a_dxf(cfg.get("oda_exe"), ruta, salida, cfg.get("oda_version_salida", "ACAD2018"))
        nueva = os.path.join(salida, f"{nombre} - COPIA ORIGINAL.dxf")
        os.replace(copia, nueva)
        copia = nueva
        log("DWG convertido a DXF con ODA para trabajar.")
    else:
        copia = os.path.join(salida, f"{nombre} - COPIA ORIGINAL.dxf")
        shutil.copy2(ruta, copia)
    doc, av = lector.leer(copia)
    avisos += av
    insunits, uname, fdet = lector.unidades(doc)
    if factor is None:
        if fdet is None:
            raise ValueError(f"$INSUNITS = {insunits} ({uname}): no se puede saber la unidad. Indicar el factor a metros.")
        factor = fdet
    elif fdet is not None and abs(factor - fdet) > 1e-12:
        avisos.append(f"Factor indicado {factor} distinto del de $INSUNITS ({fdet}, {uname}): se usó el indicado.")
    if insunits == 0:
        avisos.append("$INSUNITS = 0 (sin unidad): confirmar el factor con una cota conocida.")
    if doc.dxfversion < "AC1018":
        avisos.append(f"Versión DXF {doc.dxfversion} anterior a 2004: la transparencia de capa puede perderse.")
    k = 1.0 / factor
    log(f"Unidades: $INSUNITS = {insunits} ({uname}); factor a metros = {factor}")
    progreso(15)

    # 2. reconocimiento
    segs, arcos, n_cero, omitidos = lector.extraer(doc, capas, factor)
    for h, c, m in omitidos:
        avisos.append(f"Entidad {h} en {c}: {m}")
    log(f"Segmentos: {len(segs)}, arcos: {len(arcos)}, longitud cero: {n_cero}")
    P = muros.Param.desde_config(cfg, espesores)
    res = muros.reconocer(segs, P)
    log(f"Ejes de muro: {len(res.corridas)} (cortos: {len(res.cortas)}); tramos: {len(res.tramos)}")
    progreso(40)
    cc = conv["cimiento"]
    cims, rv_cim = cimiento.generar(res.corridas, cc.get("reglas", {}), cc["capa"], cc.get("corrido_por_vanos", True))
    rv_cob, stats = revision.cobertura(segs, arcos, res, P)
    rconv = conv["revision"]
    revisiones = res.revisiones + rv_cim + revision.depurar(rv_cob, 2 * rconv["radio"])
    log(f"Reconocido: {stats['pct_largo']:.2f} % de la longitud; marcas REVISION: {len(revisiones)}")
    progreso(55)

    # 3. escritura del DXF
    cm = lambda e: int(round(e * 100))
    cmu, cvp = conv["muro"], conv["vano_puerta"]
    capa_muro = lambda e: cmu["capa"].format(nivel=nivel, cm=cm(e))
    capa_vano = lambda e: cvp["capa"].format(nivel=nivel, cm=cm(e))
    nuevas = set()
    for t in res.tramos:
        nuevas.add(capa_muro(t["esp"]) if t["tipo"] == "muro" else capa_vano(t["esp"]))
    for c in cims:
        nuevas.add(c["capa"])
    nuevas.add(rconv["capa"])
    for n in nuevas:
        escritor.validar_capa(n)
    n_mach = escritor.preparar_machote(doc, conv, nuevas)
    log(f"Machote: {n_mach} objetos pasados a la capa {conv['machote']['capa']}")
    for t in res.tramos:
        if t["tipo"] == "muro":
            escritor.capa(doc, capa_muro(t["esp"]), cmu["color"], cmu.get("transparencia", 0.5))
        else:
            escritor.capa(doc, capa_vano(t["esp"]), cvp["color"], cvp.get("transparencia", 0.5))
    for c in cims:
        escritor.capa(doc, c["capa"], int(c["regla"].get("color", 2)), cc.get("transparencia", 0.5))
    escritor.capa(doc, rconv["capa"], rconv["color"], 0.0, "Marcas de lo que el programa no reconoció con seguridad")

    msp = doc.modelspace()
    propios, bloques = set(), {}
    for e in sorted({t["esp"] for t in res.tramos}):
        bn = escritor.nombre_bloque(doc, cmu["bloque"].format(cm=cm(e)), propios)
        if bn != cmu["bloque"].format(cm=cm(e)):
            avisos.append(f"El plano ya tenía un bloque '{cmu['bloque'].format(cm=cm(e))}': se usó '{bn}'.")
        escritor.definir_bloque_muro(doc, bn, e, k, cmu.get("color_atributos", 250))
        propios.add(bn)
        bloques[e] = bn

    elementos = []
    cnt = {"Muro": 0, "Vano puerta": 0, "Cimiento corrido": 0}
    pref = {"Muro": "M", "Vano puerta": "V", "Cimiento corrido": "C"}
    handles_cim = []
    for c in cims:
        cnt["Cimiento corrido"] += 1
        pl = escritor.polilinea_cimiento(msp, c["capa"], c["pts"], c["regla"]["ancho"], k)
        handles_cim.append(pl.dxf.handle)
        r = c["regla"]
        elementos.append(dict(id=f"C-{cnt['Cimiento corrido']:03d}", elemento="Cimiento corrido", capa=c["capa"], esp=c["esp"],
                              tipo_cim=r["tipo"], ancho=r["ancho"], peralte=r["peralte"], largo=c["largo"], handle=pl.dxf.handle,
                              p0=c["pts"][0], p1=c["pts"][-1],
                              obs=(f"polilínea unida en esquina ({len(c['pts'])} vértices)" if len(c["pts"]) > 2 else "")))
    for t in res.tramos:
        el = "Muro" if t["tipo"] == "muro" else "Vano puerta"
        cnt[el] += 1
        ide = f"{pref[el]}-{cnt[el]:03d}"
        lay = capa_muro(t["esp"]) if el == "Muro" else capa_vano(t["esp"])
        alt = altura if el == "Muro" else None
        attrs = dict(ID=ide, TIPO=(f"Muro de {cm(t['esp'])}cm" if el == "Muro" else f"Vano puerta {cm(t['esp'])}cm"),
                     ESPESOR=f"{t['esp']:.2f}", LARGO=f"{t['largo']:.4f}",
                     ALTO=(f"{alt:.4f}" if alt is not None else ""), AREA=(f"{t['largo'] * alt:.4f}" if alt is not None else ""))
        br = escritor.insertar_muro(msp, bloques[t["esp"]], lay, t, k, attrs, cmu.get("color_atributos", 250))
        obs = t["obs"]
        if el == "Vano puerta":
            obs = (obs + "; " if obs else "") + "paño sobre vano no calculado (falta altura de vano)"
        if abs(t["sep"] - t["esp"]) > 1e-4:
            obs = (obs + "; " if obs else "") + f"separación medida {t['sep']:.4f} m"
        elementos.append(dict(id=ide, elemento=el, capa=lay, esp=t["esp"], largo=t["largo"], altura=alt, handle=br.dxf.handle,
                              p0=t["p0"], p1=t["p1"], obs=obs))
    for i, r in enumerate(revisiones, start=1):
        escritor.marca_revision(msp, rconv["capa"], r, rconv["radio"], rconv["altura_texto"], k, i)
    if cc.get("al_fondo", True):
        escritor.al_fondo(msp, handles_cim)
    g = conv["grupos"]
    l_mur = sorted({e["capa"] for e in elementos if e["elemento"] != "Cimiento corrido"})
    l_cim = sorted({e["capa"] for e in elementos if e["elemento"] == "Cimiento corrido"})
    hijos = []
    if l_mur:
        hijos.append((g["muros"], l_mur, [(g["muros_nivel"].format(nivel=nivel), l_mur, [])]))
    if l_cim:
        hijos.append((g["cimiento"], l_cim, []))
    if hijos:
        escritor.agregar_grupos(doc, [(g["raiz"], l_mur + l_cim, hijos)])
    progreso(70)
    dxf_sal = os.path.join(salida, f"{nombre} - CUANT.dxf")
    rep_guardado, _ = escritor.guardar_verificado(doc, dxf_sal)
    log(f"DXF guardado y verificado: {dxf_sal} ({rep_guardado['tamano_mb']} MB, HANDSEED ok)")
    archivos = [dxf_sal]
    progreso(80)

    # 4. DWG
    oda = cfg.get("oda_exe")
    if convertir.disponible(oda):
        try:
            dwg, err = convertir.dxf_a_dwg(oda, dxf_sal, salida, cfg.get("oda_version_salida", "ACAD2018"))
            archivos.append(dwg)
            log(f"DWG generado: {dwg}")
        except convertir.ODAError as ex:
            avisos.append(f"No se generó el DWG: {ex}")
    else:
        avisos.append(f"ODA File Converter no encontrado ({oda}): se entrega solo el DXF.")
    progreso(88)

    # 5. Excel y reporte
    resumen = {}
    for e in elementos:
        n, lg = resumen.get((e["elemento"], e["capa"]), (0, 0.0))
        resumen[(e["elemento"], e["capa"])] = (n + 1, lg + e["largo"])
    xls = os.path.join(salida, f"DataExtraction_{nombre}.xlsx")
    parametros = [("Plano original", ruta, ""), ("sha256 original", sha_ini, ""), ("Copia de trabajo", copia, ""),
                  ("DXF de salida", dxf_sal, ""), ("Capas de origen", ", ".join(capas), ""),
                  ("$INSUNITS", f"{insunits} ({uname})", ""), ("Factor a metros", factor, "m/unidad"),
                  ("Espesores", ", ".join(f"{e:.2f}" for e in P.espesores), "m"), ("Nivel", nivel, ""),
                  ("Altura de muro", altura if altura is not None else "(vacía: solo LARGO)", "m" if altura is not None else ""),
                  ("Tolerancia de espesor", P.tol_espesor, "m"), ("Tolerancia angular", P.tol_angular, "°"),
                  ("Unión de ejes colineales hasta", P.union_max, "m"), ("Vano de puerta", f"{P.vano_min} a {P.vano_max}", "m"),
                  ("Umbral de eje corto", P.umbral_eje_corto, "m"), ("Snap de esquinas", P.tol_snap, "m"),
                  ("Reglas de cimiento", json.dumps(cc.get("reglas", {}), ensure_ascii=False), ""),
                  ("Fecha", f"{fecha:%Y-%m-%d %H:%M:%S}", "")]
    extraccion.escribir(xls, elementos, revisiones, parametros)
    archivos.append(xls)
    log(f"Excel: {xls}")
    sha_fin = lector.sha256(ruta)
    if sha_fin != sha_ini:
        avisos.append("¡El sha256 del original cambió durante el proceso!")
    info = dict(nombre=nombre, fecha=f"{fecha:%Y-%m-%d %H:%M:%S}", original=ruta, sha_ini=sha_ini, sha_fin=sha_fin,
                capas=list(capas), insunits=insunits, unidades=uname, factor=factor, espesores=P.espesores, nivel=nivel,
                altura=altura, n_cero=n_cero, stats=stats, resumen=resumen, revisiones=revisiones, avisos=avisos,
                archivos=archivos + [os.path.join(salida, "reporte.md")], tiempo=time.perf_counter() - t_ini,
                salida=salida, dxf=dxf_sal, xlsx=xls, elementos=elementos, guardado=rep_guardado)
    revision.escribir_reporte(os.path.join(salida, "reporte.md"), info)
    for a in avisos:
        log("AVISO: " + a)
    progreso(100)
    log(f"Listo en {info['tiempo']:.2f} s")
    return info


def _float_o_none(s):
    s = (s or "").strip().replace(",", ".")
    return float(s) if s else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plano")
    ap.add_argument("--capas", required=True)
    ap.add_argument("--espesores", default=None)
    ap.add_argument("--nivel", default=None)
    ap.add_argument("--altura", default="")
    ap.add_argument("--factor", default="")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--conv", default=None)
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    conv, cfg = cargar_config(a.conv, a.config)
    esp = [float(x) for x in a.espesores.split(",")] if a.espesores else cfg["espesores"]
    info = cuantificar(a.plano, [c.strip() for c in a.capas.split(",") if c.strip()], esp, a.nivel or cfg.get("nivel", "N1"),
                       _float_o_none(a.altura), _float_o_none(a.factor), conv, cfg, carpeta_salida=a.salida)
    return info


if __name__ == "__main__":
    main()
