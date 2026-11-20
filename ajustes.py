"""Janela de Ajustes (tkinter + tema sv-ttk, que imita o Windows 11). Roda numa thread própria."""
import ctypes
import gc
import os
import threading
import tkinter as tk
import winreg
from tkinter import ttk

import nucleo

_aberta = threading.Lock()
TAMANHOS = {"Pequeno": 0.85, "Normal": 1.0, "Grande": 1.2}


def abre():
    if not _aberta.acquire(blocking=False):
        return                                  # já está aberta
    threading.Thread(target=_janela, daemon=True).start()


def _janela():
    try:
        janela = Ajustes()
        janela.raiz.mainloop()
        del janela
    finally:
        gc.collect()          # solta os objetos do Tk nesta thread (evita "Tcl_AsyncDelete" se outra thread os coletar)
        _aberta.release()


def _tema_claro():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 1
    except OSError:
        return True


class Ajustes:
    def __init__(self):
        cfg = nucleo.config()
        self.claro = _tema_claro()
        self.apoio = "#5A5A5A" if self.claro else "#C8C8C8"       # cor do texto de apoio
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.raiz.title(f"Ajustes · {nucleo.APP}")
        self.raiz.resizable(False, False)
        self.raiz.attributes("-topmost", True)
        icone = os.path.join(nucleo.PASTA_DADOS, "icone.ico")
        if os.path.exists(icone):
            try:
                self.raiz.iconbitmap(icone)
            except tk.TclError:
                pass
        try:
            import sv_ttk
            sv_ttk.set_theme("light" if self.claro else "dark")
            self.destaque = "Accent.TButton"
        except Exception:
            ttk.Style().theme_use("vista")
            self.destaque = "TButton"
        estilo = ttk.Style()
        estilo.configure("Titulo.TLabel", font=("Segoe UI Variable Text Semibold", 11))
        estilo.configure("Apoio.TLabel", font=("Segoe UI Variable Text", 9), foreground=self.apoio)

        f = ttk.Frame(self.raiz, padding=(20, 16, 20, 18))
        f.grid(sticky="nsew")
        f.columnconfigure(0, weight=1)
        self.linha = 0

        self.titulo(f, "Onde mostrar")
        self.monitores = tk.StringVar(value=cfg["monitores"])
        self.item(f, ttk.Radiobutton(f, text="Na barra de todas as telas", value="todos", variable=self.monitores))
        self.item(f, ttk.Radiobutton(f, text="Só na tela principal", value="principal", variable=self.monitores))

        self.titulo(f, "Aparência")
        nome_tam = min(TAMANHOS, key=lambda n: abs(TAMANHOS[n] - cfg["tamanho"]))
        self.tamanho = tk.StringVar(value=nome_tam)
        self.campo(f, "Tamanho dos ícones",
                   ttk.Combobox(f, textvariable=self.tamanho, values=list(TAMANHOS), state="readonly", width=9))
        self.mostrar_ate = tk.IntVar(value=cfg["mostrar_ate"])
        self.campo(f, "Mostrar quando a bateria estiver em até (%)",
                   ttk.Spinbox(f, from_=5, to=100, increment=5, textvariable=self.mostrar_ate, width=7),
                   apoio="Deixe em 100 para mostrar sempre.")

        self.titulo(f, "Avisos")
        self.alerta = tk.IntVar(value=cfg["alerta"])
        self.campo(f, "Bateria fraca em (%)",
                   ttk.Spinbox(f, from_=5, to=50, increment=5, textvariable=self.alerta, width=7))
        self.aviso_fraca = tk.BooleanVar(value=cfg["aviso_fraca"])
        self.item(f, ttk.Checkbutton(f, text="Avisar quando a bateria ficar fraca", variable=self.aviso_fraca))
        self.aviso_cheio = tk.BooleanVar(value=cfg["aviso_cheio"])
        self.item(f, ttk.Checkbutton(f, text="Avisar quando terminar de carregar", variable=self.aviso_cheio))
        self.procurar = tk.BooleanVar(value=cfg["procurar_versao"])
        self.item(f, ttk.Checkbutton(f, text="Avisar quando sair versão nova no GitHub", variable=self.procurar))

        self.titulo(f, "Periféricos")
        self.item(f, ttk.Label(f, text="Marque os que aparecem na barra. As setas mudam a ordem.", style="Apoio.TLabel"),
                  pady=(0, 6))
        conhecidos = dict(cfg["conhecidos"])
        for k, v in nucleo.instantaneo().items():
            conhecidos.setdefault(k, {"nome": v["nome"], "tipo": v["tipo"]})
        ordem = cfg["ordem"]
        self.chaves = sorted(conhecidos, key=lambda k: (ordem.index(k) if k in ordem else len(ordem),
                                                        nucleo.ORDEM_TIPO.get(conhecidos[k]["tipo"], 9),
                                                        conhecidos[k]["nome"]))
        self.conhecidos = conhecidos
        self.visivel = {k: tk.BooleanVar(value=k not in cfg["ocultos"]) for k in self.chaves}
        self.lista = ttk.Frame(f)
        self.item(f, self.lista)
        self.lista.columnconfigure(1, weight=1)
        self.desenha_lista()

        botoes = ttk.Frame(f)
        botoes.grid(row=self.linha, column=0, columnspan=2, sticky="e", pady=(20, 0))
        ttk.Button(botoes, text="Cancelar", command=self.raiz.destroy, width=10).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(botoes, text="Salvar", command=self.salva, style=self.destaque, width=10).grid(row=0, column=1)
        self.raiz.bind("<Escape>", lambda e: self.raiz.destroy())
        self.raiz.bind("<Return>", lambda e: self.salva())

        self.raiz.update_idletasks()
        self.barra_escura()
        w, h = self.raiz.winfo_reqwidth(), self.raiz.winfo_reqheight()
        self.raiz.geometry(f"+{(self.raiz.winfo_screenwidth() - w) // 2}+{(self.raiz.winfo_screenheight() - h) // 3}")
        self.raiz.deiconify()

    # --- montagem ---
    def titulo(self, f, texto):
        ttk.Label(f, text=texto, style="Titulo.TLabel").grid(row=self.linha, column=0, columnspan=2, sticky="w",
                                                             pady=(14 if self.linha else 0, 6))
        self.linha += 1

    def item(self, f, widget, pady=(0, 2)):
        widget.grid(row=self.linha, column=0, columnspan=2, sticky="we", pady=pady)
        self.linha += 1

    def campo(self, f, rotulo, widget, apoio=None):
        ttk.Label(f, text=rotulo).grid(row=self.linha, column=0, sticky="w", pady=(2, 2))
        widget.grid(row=self.linha, column=1, sticky="e", padx=(16, 0), pady=(2, 2))
        self.linha += 1
        if apoio:
            ttk.Label(f, text=apoio, style="Apoio.TLabel").grid(row=self.linha, column=0, columnspan=2, sticky="w",
                                                                pady=(0, 4))
            self.linha += 1

    def barra_escura(self):
        """Barra de título escura quando o Windows está no tema escuro (como os apps do sistema)."""
        if self.claro:
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.raiz.winfo_id())
            valor = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(valor), ctypes.sizeof(valor))
        except Exception:
            pass

    def desenha_lista(self):
        for w in self.lista.winfo_children():
            w.destroy()
        if not self.chaves:
            ttk.Label(self.lista, text="Nenhum periférico encontrado ainda.", style="Apoio.TLabel").grid(sticky="w")
            return
        online = nucleo.instantaneo()
        ultimo = len(self.chaves) - 1
        for i, k in enumerate(self.chaves):
            ttk.Checkbutton(self.lista, text=self.conhecidos[k]["nome"], variable=self.visivel[k]).grid(
                row=i, column=0, sticky="w", pady=1)
            if k not in online:
                ttk.Label(self.lista, text="desligado", style="Apoio.TLabel").grid(row=i, column=1, sticky="w",
                                                                                  padx=(6, 0))
            sobe = ttk.Button(self.lista, text="↑", width=3, command=lambda i=i: self.move(i, -1))
            desce = ttk.Button(self.lista, text="↓", width=3, command=lambda i=i: self.move(i, 1))
            sobe.grid(row=i, column=2, padx=(12, 4), pady=1)
            desce.grid(row=i, column=3, pady=1)
            if k not in online:                      # só dá para esquecer o que está desligado
                ttk.Button(self.lista, text="Esquecer", width=9, command=lambda k=k: self.esquece(k)).grid(
                    row=i, column=4, padx=(8, 0), pady=1)
            if i == 0:
                sobe.state(["disabled"])
            if i == ultimo:
                desce.state(["disabled"])

    def esquece(self, chave):
        nucleo.esquece(chave)
        self.chaves = [k for k in self.chaves if k != chave]
        self.conhecidos.pop(chave, None)
        self.visivel.pop(chave, None)
        self.desenha_lista()

    def move(self, i, passo):
        j = i + passo
        if 0 <= j < len(self.chaves):
            self.chaves[i], self.chaves[j] = self.chaves[j], self.chaves[i]
            self.desenha_lista()

    def salva(self):
        def numero(var, minimo, maximo, padrao):
            try:
                return max(minimo, min(maximo, int(var.get())))
            except (tk.TclError, ValueError):
                return padrao
        nucleo.muda_config(
            monitores=self.monitores.get(),
            tamanho=TAMANHOS.get(self.tamanho.get(), 1.0),
            mostrar_ate=numero(self.mostrar_ate, 5, 100, 100),
            alerta=numero(self.alerta, 5, 50, 15),
            aviso_fraca=self.aviso_fraca.get(),
            aviso_cheio=self.aviso_cheio.get(),
            procurar_versao=self.procurar.get(),
            ocultos=[k for k in self.chaves if not self.visivel[k].get()],
            ordem=list(self.chaves),
        )
        self.raiz.destroy()
