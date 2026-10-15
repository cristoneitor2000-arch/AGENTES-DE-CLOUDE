"""app.py – interfaz (tkinter) del cuantificador de muros y cimiento corrido.

convenciones.json y config.json se leen de la carpeta del programa (junto al .exe cuando está empaquetado).
"""
import json
import os
import queue
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cimiento  # noqa: E402
import lector    # noqa: E402
import pipeline  # noqa: E402

TITULO = "Cuantificador DXF – muros y cimiento corrido (prueba v1)"
ROLES = ("muros", "columnas", "zapatas")
SI, NO = "✔", ""


class App:
    def __init__(self, root):
        self.root = root
        root.title(TITULO)
        root.geometry("1100x860")
        root.minsize(900, 700)
        self.q = queue.Queue()
        self.ruta = None
        self.salida = None
        self.capas = []
        self.rol = {r: set() for r in ROLES}
        self.trabajando = False
        try:
            self.conv, self.cfg = pipeline.cargar_config()
        except Exception as ex:
            messagebox.showerror(TITULO, f"No se pudieron leer convenciones.json / config.json:\n{ex}")
            raise
        self._armar()
        for k, r in self.conv["cimiento"].get("tipos", {}).items():
            self._agregar_tipo(k, r.get("ancho"), r.get("peralte"), r.get("color", 2), r.get("color_dentro", 8))
        self.root.after(100, self._leer_cola)

    # ---------------------------------------------------------- interfaz
    def _armar(self):
        pad = dict(padx=6, pady=3)
        f = ttk.Frame(self.root)
        f.pack(fill="both", expand=True, padx=8, pady=8)

        fila = ttk.Frame(f)
        fila.pack(fill="x", **pad)
        ttk.Button(fila, text="Seleccionar plano (DXF o DWG)", command=self.seleccionar).pack(side="left")
        self.lbl_plano = ttk.Label(fila, text="(ningún plano)", foreground="#555")
        self.lbl_plano.pack(side="left", padx=10)

        medio = ttk.Frame(f)
        medio.pack(fill="both", expand=True, **pad)
        medio.columnconfigure(0, weight=3)
        medio.columnconfigure(1, weight=2)
        medio.rowconfigure(0, weight=1)

        # capas por rol
        cap = ttk.LabelFrame(medio, text="Capas del plano (clic en la columna para marcar el uso)")
        cap.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        barra = ttk.Frame(cap)
        barra.pack(fill="x", padx=6, pady=4)
        ttk.Label(barra, text="Filtrar:").pack(side="left")
        self.filtro = tk.StringVar()
        self.filtro.trace_add("write", lambda *_: self._pintar_capas())
        ttk.Entry(barra, textvariable=self.filtro, width=22).pack(side="left", padx=4)
        self.lbl_sel = ttk.Label(barra, text="")
        self.lbl_sel.pack(side="right")
        cols = ("lineas", "bloques", "muros", "columnas", "zapatas")
        self.tv = ttk.Treeview(cap, columns=cols, show="tree headings", height=14, selectmode="browse")
        self.tv.heading("#0", text="Capa")
        self.tv.column("#0", width=260, anchor="w")
        for c, t, w in (("lineas", "Líneas", 60), ("bloques", "Blocks", 60), ("muros", "Muros", 60),
                        ("columnas", "Columnas / mochetas", 120), ("zapatas", "Zapatas", 70)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor="center")
        sb = ttk.Scrollbar(cap, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        sb.pack(side="left", fill="y", pady=4)
        self.tv.bind("<Button-1>", self._clic_capa)

        # tipos de cimiento
        tip = ttk.LabelFrame(medio, text="Tipos de cimiento corrido (del detalle estructural)")
        tip.grid(row=0, column=1, sticky="nsew")
        tc = ("tipo", "ancho", "peralte", "color", "dentro")
        self.tt = ttk.Treeview(tip, columns=tc, show="headings", height=7)
        for c, t, w in (("tipo", "Tipo", 70), ("ancho", "Ancho (m)", 70), ("peralte", "Peralte (m)", 75),
                        ("color", "Color", 50), ("dentro", "Color dentro zapata", 110)):
            self.tt.heading(c, text=t)
            self.tt.column(c, width=w, anchor="center")
        self.tt.pack(fill="both", expand=True, padx=6, pady=4)
        ent = ttk.Frame(tip)
        ent.pack(fill="x", padx=6)
        self.e_tipo, self.e_ancho, self.e_per, self.e_col, self.e_cold = (tk.StringVar() for _ in range(5))
        self.e_col.set("2")
        self.e_cold.set("8")
        for v, w in ((self.e_tipo, 7), (self.e_ancho, 7), (self.e_per, 7), (self.e_col, 5), (self.e_cold, 5)):
            ttk.Entry(ent, textvariable=v, width=w).pack(side="left", padx=2)
        bt = ttk.Frame(tip)
        bt.pack(fill="x", padx=6, pady=4)
        ttk.Button(bt, text="Agregar", command=self._agregar_desde_campos).pack(side="left")
        ttk.Button(bt, text="Quitar", command=lambda: [self.tt.delete(i) for i in self.tt.selection()]).pack(side="left", padx=4)
        ttk.Button(bt, text="Cargar…", command=self._cargar_tipos).pack(side="left", padx=4)
        ttk.Button(bt, text="Guardar…", command=self._guardar_tipos).pack(side="left")
        ttk.Label(tip, text="El tipo de cada muro sale de las etiquetas del plano (p. ej. CC1, MC1)\n"
                            "a <= 2.2 m. Tabiques de 0.10: sin cimiento.", foreground="#555").pack(anchor="w", padx=6, pady=(0, 4))

        par = ttk.LabelFrame(f, text="Parámetros")
        par.pack(fill="x", **pad)
        self.v_esp = tk.StringVar(value=", ".join(f"{e:.2f}" for e in self.cfg.get("espesores", [0.10, 0.15, 0.20])))
        self.v_niv = tk.StringVar(value=self.cfg.get("nivel", "N1"))
        self.v_alt = tk.StringVar(value="")
        self.v_fac = tk.StringVar(value="")
        self.v_ecap = tk.StringVar(value="")
        self.v_dcont = tk.StringVar(value="")
        self.v_dotro = tk.StringVar(value="")
        self.v_ven = tk.StringVar(value="")
        campos = [("Espesores de muro (m):", self.v_esp, 20), ("Nivel:", self.v_niv, 8),
                  ("Altura de muro (m, vacío = solo largo):", self.v_alt, 8), ("Factor a metros:", self.v_fac, 10),
                  ("Espesor por capa (opcional) capa=esp; …:", self.v_ecap, 26), ("Ventana x0,y0,x1,y1 (m, opcional):", self.v_ven, 26),
                  ("Tipo sin etiqueta – contención (opcional):", self.v_dcont, 8), ("Tipo sin etiqueta – otros (opcional):", self.v_dotro, 8)]
        for i, (t, v, w) in enumerate(campos):
            ttk.Label(par, text=t).grid(row=i // 2, column=(i % 2) * 2, sticky="e", padx=6, pady=3)
            ttk.Entry(par, textvariable=v, width=w).grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=6, pady=3)
        self.lbl_uni = ttk.Label(par, text="", foreground="#555")
        self.lbl_uni.grid(row=4, column=0, columnspan=4, sticky="w", padx=6)

        acc = ttk.Frame(f)
        acc.pack(fill="x", **pad)
        self.btn_cuant = ttk.Button(acc, text="Cuantificar", command=self.cuantificar)
        self.btn_cuant.pack(side="left")
        self.btn_abrir = ttk.Button(acc, text="Abrir carpeta de salida", command=self.abrir_salida, state="disabled")
        self.btn_abrir.pack(side="left", padx=8)
        self.prog = ttk.Progressbar(acc, mode="determinate", maximum=100)
        self.prog.pack(side="left", fill="x", expand=True, padx=8)

        self.log_txt = ScrolledText(f, height=9, font=("Consolas", 9), state="disabled")
        self.log_txt.pack(fill="both", expand=True, **pad)

    def log(self, m):
        if m:
            self.q.put(("log", m))

    def _escribir_log(self, m):
        self.log_txt.configure(state="normal")
        self.log_txt.insert("end", m + "\n")
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")

    def _leer_cola(self):
        try:
            while True:
                tipo, val = self.q.get_nowait()
                if tipo == "log":
                    self._escribir_log(val)
                elif tipo == "prog":
                    self.prog["value"] = val
                elif tipo == "fin":
                    self._fin(val)
                elif tipo == "error":
                    self._error(val)
        except queue.Empty:
            pass
        self.root.after(100, self._leer_cola)

    # ---------------------------------------------------------- capas
    def seleccionar(self, ruta=None):
        ruta = ruta or filedialog.askopenfilename(title="Plano", filetypes=[("Planos", "*.dxf *.dwg"), ("DXF", "*.dxf"), ("DWG", "*.dwg")])
        if not ruta:
            return
        try:
            leible = pipeline.preparar_entrada(ruta, self.cfg, self.log)
            doc, av = lector.leer(leible)
        except Exception as ex:
            messagebox.showerror(TITULO, f"No se pudo leer el plano:\n{ex}")
            self.log(f"ERROR al leer: {ex}")
            return
        for a in av:
            self.log("AVISO: " + a)
        self.ruta = ruta
        self.lbl_plano.configure(text=ruta)
        u, nombre, f = lector.unidades(doc)
        self.v_fac.set("" if f is None else repr(f))
        self.lbl_uni.configure(text=f"$INSUNITS = {u} ({nombre})" + ("" if f is not None else " – indicar el factor a metros a mano"))
        self.capas = lector.listar_capas(doc)
        self.rol = {r: set() for r in ROLES}
        self._pintar_capas()
        self.log(f"Plano: {ruta} | {len(self.capas)} capas | $INSUNITS = {u} ({nombre})")

    def _pintar_capas(self):
        self.tv.delete(*self.tv.get_children())
        filtro = self.filtro.get().strip().lower()
        for c, n, b in self.capas:
            if filtro and filtro not in c.lower():
                continue
            self.tv.insert("", "end", iid=c, text=c, values=(n, b, *(SI if c in self.rol[r] else NO for r in ROLES)))
        self._contar()

    def _clic_capa(self, ev):
        if self.tv.identify_region(ev.x, ev.y) != "cell":
            return
        col = self.tv.identify_column(ev.x)
        fila = self.tv.identify_row(ev.y)
        idx = int(col.replace("#", "")) - 3   # #3 = muros
        if not fila or not (0 <= idx < len(ROLES)):
            return
        self.marcar(fila, ROLES[idx], fila not in self.rol[ROLES[idx]])

    def marcar(self, capa, rol, valor=True):
        (self.rol[rol].add if valor else self.rol[rol].discard)(capa)
        if self.tv.exists(capa):
            vals = list(self.tv.item(capa, "values"))
            vals[2 + ROLES.index(rol)] = SI if valor else NO
            self.tv.item(capa, values=vals)
        self._contar()

    def _contar(self):
        self.lbl_sel.configure(text=" | ".join(f"{r}: {len(self.rol[r])}" for r in ROLES))

    def capas_elegidas(self, rol="muros"):
        return sorted(self.rol[rol])

    # ---------------------------------------------------------- tipos de cimiento
    def _agregar_tipo(self, tipo, ancho, peralte, color=2, dentro=8):
        tipo = str(tipo).strip()
        if not tipo:
            return
        for i in self.tt.get_children():
            if self.tt.item(i, "values")[0] == tipo:
                self.tt.delete(i)
        self.tt.insert("", "end", values=(tipo, ancho, peralte, color, dentro))

    def _agregar_desde_campos(self):
        try:
            a, p = float(self.e_ancho.get().replace(",", ".")), float(self.e_per.get().replace(",", "."))
            c, cd = int(self.e_col.get() or 2), int(self.e_cold.get() or 8)
        except ValueError:
            messagebox.showwarning(TITULO, "Ancho y peralte deben ser números (m); colores, enteros ACI.")
            return
        self._agregar_tipo(self.e_tipo.get(), f"{a:.2f}", f"{p:.2f}", c, cd)
        self.e_tipo.set("")

    def tipos(self):
        out = {}
        for i in self.tt.get_children():
            t, a, p, c, cd = self.tt.item(i, "values")
            out[t] = {"ancho": float(a), "peralte": float(p), "color": int(c), "color_dentro": int(cd)}
        return out

    def _cargar_tipos(self):
        r = filedialog.askopenfilename(title="Tabla de tipos", filetypes=[("JSON", "*.json")])
        if not r:
            return
        with open(r, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.items():
            self._agregar_tipo(k, v["ancho"], v["peralte"], v.get("color", 2), v.get("color_dentro", 8))

    def _guardar_tipos(self):
        r = filedialog.asksaveasfilename(title="Guardar tabla de tipos", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if r:
            with open(r, "w", encoding="utf-8") as fh:
                json.dump(self.tipos(), fh, ensure_ascii=False, indent=2)

    # ---------------------------------------------------------- proceso
    def _parametros(self):
        esp = [float(x.replace(",", ".")) for x in self.v_esp.get().replace(";", " ").replace(", ", " ").split() if x.strip()]
        if not esp or any(e <= 0 for e in esp):
            raise ValueError("Espesores inválidos: escribir por ejemplo 0.10 0.15 0.20")
        alt = self.v_alt.get().strip().replace(",", ".")
        alt = float(alt) if alt else None
        if alt is not None and alt <= 0:
            raise ValueError("La altura debe ser mayor que cero o quedar vacía")
        fac = self.v_fac.get().strip().replace(",", ".")
        fac = float(fac) if fac else None
        niv = self.v_niv.get().strip()
        if not niv:
            raise ValueError("Indicar el nivel (p. ej. N1)")
        ecap = pipeline.parse_espesor_capa(self.v_ecap.get())
        ven = self.v_ven.get().strip()
        ven = tuple(float(v) for v in ven.replace(";", ",").split(",")) if ven else None
        if ven is not None and (len(ven) != 4 or ven[0] >= ven[2] or ven[1] >= ven[3]):
            raise ValueError("Ventana: x0,y0,x1,y1 con x0 < x1 e y0 < y1")
        tipos, err = cimiento.validar_tipos(self.tipos())
        if err:
            raise ValueError("; ".join(err))
        dflt = {"contencion": self.v_dcont.get().strip(), "otros": self.v_dotro.get().strip()}
        for k, v in dflt.items():
            if v and v not in tipos:
                raise ValueError(f"Tipo por defecto '{v}' no está en la tabla de tipos")
        return esp, niv, alt, fac, ecap, ven, tipos, dflt

    def cuantificar(self, esperar=False):
        if self.trabajando:
            return
        if not self.ruta:
            messagebox.showwarning(TITULO, "Primero seleccionar un plano.")
            return
        capas = self.capas_elegidas("muros")
        if not capas:
            messagebox.showwarning(TITULO, "Marcar al menos una capa en la columna Muros.")
            return
        try:
            esp, niv, alt, fac, ecap, ven, tipos, dflt = self._parametros()
        except ValueError as ex:
            messagebox.showwarning(TITULO, str(ex))
            return
        self.trabajando = True
        self.btn_cuant.configure(state="disabled")
        self.btn_abrir.configure(state="disabled")
        self.prog["value"] = 0
        self.log(f"--- Cuantificando. Muros: {', '.join(capas)}")

        def trabajo():
            try:
                info = pipeline.cuantificar(self.ruta, capas, esp, niv, alt, fac, self.conv, self.cfg, log=self.log,
                                            progreso=lambda p: self.q.put(("prog", p)),
                                            capas_columnas=self.capas_elegidas("columnas"),
                                            capas_zapatas=self.capas_elegidas("zapatas"),
                                            tipos_cimiento=tipos, ventana=ven, espesor_por_capa=ecap, tipo_por_defecto=dflt)
                self.q.put(("fin", info))
            except Exception as ex:
                self.q.put(("error", f"{ex}\n{traceback.format_exc()}"))

        th = threading.Thread(target=trabajo, daemon=True)
        th.start()
        if esperar:
            th.join()

    def _fin(self, info):
        self.trabajando = False
        self.salida = info["salida"]
        self.btn_cuant.configure(state="normal")
        self.btn_abrir.configure(state="normal")
        st = info["stats"]
        self.log(f"Reconocido {st['pct_largo']:.2f} % de las líneas y {st['pct_bloques']:.2f} % de los blocks; "
                 f"REVISION: {len(info['revisiones'])} marcas. Ver reporte.md")
        self.ultimo = info

    def _error(self, msg):
        self.trabajando = False
        self.btn_cuant.configure(state="normal")
        self._escribir_log("ERROR: " + msg)
        messagebox.showerror(TITULO, msg.split("\n")[0])

    def abrir_salida(self):
        if not self.salida:
            return
        if os.name == "nt":
            os.startfile(self.salida)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", self.salida])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":   # modo consola (pruebas): mismos argumentos que pipeline.py
        pipeline.main(sys.argv[2:])
        return
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if os.name == "nt" else "clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
