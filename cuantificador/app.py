"""app.py – interfaz (tkinter) del cuantificador de muros y cimiento corrido.

convenciones.json y config.json se leen de la carpeta del programa (junto al .exe cuando está empaquetado).
"""
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

import lector    # noqa: E402
import pipeline  # noqa: E402

TITULO = "Cuantificador DXF – muros y cimiento corrido (prueba v1)"


class App:
    def __init__(self, root):
        self.root = root
        root.title(TITULO)
        root.geometry("900x720")
        root.minsize(760, 600)
        self.q = queue.Queue()
        self.ruta = None
        self.salida = None
        self.vars_capas = {}
        self.trabajando = False
        try:
            self.conv, self.cfg = pipeline.cargar_config()
        except Exception as ex:
            messagebox.showerror(TITULO, f"No se pudieron leer convenciones.json / config.json:\n{ex}")
            raise
        self._armar()
        self.root.after(100, self._leer_cola)

    # ---------------------------------------------------------- interfaz
    def _armar(self):
        pad = dict(padx=8, pady=4)
        f = ttk.Frame(self.root)
        f.pack(fill="both", expand=True, padx=10, pady=10)

        fila = ttk.Frame(f)
        fila.pack(fill="x", **pad)
        ttk.Button(fila, text="Seleccionar plano (DXF o DWG)", command=self.seleccionar).pack(side="left")
        self.lbl_plano = ttk.Label(fila, text="(ningún plano)", foreground="#555")
        self.lbl_plano.pack(side="left", padx=10)

        cap = ttk.LabelFrame(f, text="Capas de origen de muros")
        cap.pack(fill="both", expand=True, **pad)
        barra = ttk.Frame(cap)
        barra.pack(fill="x", padx=6, pady=4)
        ttk.Label(barra, text="Filtrar:").pack(side="left")
        self.filtro = tk.StringVar()
        self.filtro.trace_add("write", lambda *_: self._pintar_capas())
        ttk.Entry(barra, textvariable=self.filtro, width=24).pack(side="left", padx=4)
        ttk.Button(barra, text="Marcar visibles", command=lambda: self._marcar(True)).pack(side="left", padx=2)
        ttk.Button(barra, text="Desmarcar todas", command=lambda: self._marcar(False, todas=True)).pack(side="left", padx=2)
        self.lbl_sel = ttk.Label(barra, text="")
        self.lbl_sel.pack(side="right")
        cont = ttk.Frame(cap)
        cont.pack(fill="both", expand=True, padx=6, pady=4)
        self.canvas = tk.Canvas(cont, highlightthickness=0, height=170)
        sb = ttk.Scrollbar(cont, orient="vertical", command=self.canvas.yview)
        self.lista = ttk.Frame(self.canvas)
        self.lista.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.lista, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        par = ttk.LabelFrame(f, text="Parámetros")
        par.pack(fill="x", **pad)
        self.v_esp = tk.StringVar(value=", ".join(f"{e:.2f}" for e in self.cfg.get("espesores", [0.10, 0.15, 0.20])))
        self.v_niv = tk.StringVar(value=self.cfg.get("nivel", "N1"))
        self.v_alt = tk.StringVar(value="")
        self.v_fac = tk.StringVar(value="")
        self.lbl_uni = ttk.Label(par, text="")
        campos = [("Espesores de muro (m):", self.v_esp, 22), ("Nivel:", self.v_niv, 8),
                  ("Altura de muro (m, vacío = solo largo):", self.v_alt, 8), ("Factor a metros:", self.v_fac, 10)]
        for i, (t, v, w) in enumerate(campos):
            ttk.Label(par, text=t).grid(row=i // 2, column=(i % 2) * 2, sticky="e", padx=6, pady=4)
            ttk.Entry(par, textvariable=v, width=w).grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=6, pady=4)
        self.lbl_uni.grid(row=2, column=0, columnspan=4, sticky="w", padx=6)

        acc = ttk.Frame(f)
        acc.pack(fill="x", **pad)
        self.btn_cuant = ttk.Button(acc, text="Cuantificar", command=self.cuantificar)
        self.btn_cuant.pack(side="left")
        self.btn_abrir = ttk.Button(acc, text="Abrir carpeta de salida", command=self.abrir_salida, state="disabled")
        self.btn_abrir.pack(side="left", padx=8)
        self.prog = ttk.Progressbar(acc, mode="determinate", maximum=100)
        self.prog.pack(side="left", fill="x", expand=True, padx=8)

        self.log_txt = ScrolledText(f, height=12, font=("Consolas", 9), state="disabled")
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
        self.vars_capas = {c: tk.BooleanVar(value=False) for c, _ in self.capas}
        for v in self.vars_capas.values():
            v.trace_add("write", lambda *_: self._contar())
        self._pintar_capas()
        self.log(f"Plano: {ruta} | {len(self.capas)} capas | $INSUNITS = {u} ({nombre})")

    def _pintar_capas(self):
        for w in self.lista.winfo_children():
            w.destroy()
        filtro = self.filtro.get().strip().lower()
        for c, n in getattr(self, "capas", []):
            if filtro and filtro not in c.lower():
                continue
            ttk.Checkbutton(self.lista, text=f"{c}   ({n} líneas)", variable=self.vars_capas[c]).pack(anchor="w")
        self._contar()

    def _marcar(self, valor, todas=False):
        filtro = self.filtro.get().strip().lower()
        for c, v in self.vars_capas.items():
            if todas or not filtro or filtro in c.lower():
                v.set(valor)

    def _contar(self):
        self.lbl_sel.configure(text=f"{len(self.capas_elegidas())} capas elegidas")

    def capas_elegidas(self):
        return [c for c, v in self.vars_capas.items() if v.get()]

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
        return esp, niv, alt, fac

    def cuantificar(self, esperar=False):
        if self.trabajando:
            return
        if not self.ruta:
            messagebox.showwarning(TITULO, "Primero seleccionar un plano.")
            return
        capas = self.capas_elegidas()
        if not capas:
            messagebox.showwarning(TITULO, "Elegir al menos una capa de origen de muros.")
            return
        try:
            esp, niv, alt, fac = self._parametros()
        except ValueError as ex:
            messagebox.showwarning(TITULO, str(ex))
            return
        self.trabajando = True
        self.btn_cuant.configure(state="disabled")
        self.btn_abrir.configure(state="disabled")
        self.prog["value"] = 0
        self.log(f"--- Cuantificando con capas: {', '.join(capas)}")

        def trabajo():
            try:
                info = pipeline.cuantificar(self.ruta, capas, esp, niv, alt, fac, self.conv, self.cfg, log=self.log,
                                            progreso=lambda p: self.q.put(("prog", p)))
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
        self.log(f"Reconocido {st['pct_largo']:.2f} % de la longitud; REVISION: {len(info['revisiones'])} marcas. Ver reporte.md")
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
