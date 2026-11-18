"""Janela de Ajustes (tkinter, já vem com o Python). Roda numa thread própria; grava em nucleo.config."""
import threading
import tkinter as tk
from tkinter import ttk

import nucleo

_aberta = threading.Lock()
ORDEM_TIPO = {"headset": 0, "mouse": 1, "teclado": 2, "controle": 3, "bluetooth": 4}
TAMANHOS = {"Pequeno": 0.85, "Normal": 1.0, "Grande": 1.2}


def abre():
    if not _aberta.acquire(blocking=False):
        return                                  # já está aberta
    threading.Thread(target=_janela, daemon=True).start()


def _janela():
    try:
        Ajustes().raiz.mainloop()
    finally:
        _aberta.release()


class Ajustes:
    def __init__(self):
        cfg = nucleo.config()
        self.raiz = tk.Tk()
        self.raiz.title(f"Ajustes — {nucleo.APP}")
        self.raiz.resizable(False, False)
        self.raiz.attributes("-topmost", True)
        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass
        f = ttk.Frame(self.raiz, padding=16)
        f.grid()
        linha = 0

        def titulo(texto):
            nonlocal linha
            ttk.Label(f, text=texto, font=("Segoe UI Semibold", 10)).grid(row=linha, column=0, columnspan=3,
                                                                          sticky="w", pady=(10 if linha else 0, 4))
            linha += 1

        titulo("Onde mostrar")
        self.monitores = tk.StringVar(value=cfg["monitores"])
        ttk.Radiobutton(f, text="Na barra de todas as telas", value="todos", variable=self.monitores).grid(
            row=linha, column=0, columnspan=3, sticky="w"); linha += 1
        ttk.Radiobutton(f, text="Só na tela principal", value="principal", variable=self.monitores).grid(
            row=linha, column=0, columnspan=3, sticky="w"); linha += 1

        titulo("Aparência")
        ttk.Label(f, text="Tamanho dos ícones").grid(row=linha, column=0, sticky="w")
        nome_tam = min(TAMANHOS, key=lambda n: abs(TAMANHOS[n] - cfg["tamanho"]))
        self.tamanho = tk.StringVar(value=nome_tam)
        ttk.Combobox(f, textvariable=self.tamanho, values=list(TAMANHOS), state="readonly", width=10).grid(
            row=linha, column=1, sticky="w", padx=8); linha += 1
        ttk.Label(f, text="Mostrar só quando a bateria estiver em até (%)").grid(row=linha, column=0, sticky="w")
        self.mostrar_ate = tk.IntVar(value=cfg["mostrar_ate"])
        ttk.Spinbox(f, from_=5, to=100, increment=5, textvariable=self.mostrar_ate, width=6).grid(
            row=linha, column=1, sticky="w", padx=8)
        ttk.Label(f, text="100 = sempre", foreground="#777").grid(row=linha, column=2, sticky="w"); linha += 1

        titulo("Avisos")
        ttk.Label(f, text="Bateria fraca em (%)").grid(row=linha, column=0, sticky="w")
        self.alerta = tk.IntVar(value=cfg["alerta"])
        ttk.Spinbox(f, from_=5, to=50, increment=5, textvariable=self.alerta, width=6).grid(
            row=linha, column=1, sticky="w", padx=8); linha += 1
        self.aviso_fraca = tk.BooleanVar(value=cfg["aviso_fraca"])
        ttk.Checkbutton(f, text="Avisar quando a bateria ficar fraca", variable=self.aviso_fraca).grid(
            row=linha, column=0, columnspan=3, sticky="w"); linha += 1
        self.aviso_cheio = tk.BooleanVar(value=cfg["aviso_cheio"])
        ttk.Checkbutton(f, text="Avisar quando terminar de carregar", variable=self.aviso_cheio).grid(
            row=linha, column=0, columnspan=3, sticky="w"); linha += 1
        self.procurar = tk.BooleanVar(value=cfg["procurar_versao"])
        ttk.Checkbutton(f, text="Avisar quando sair versão nova no GitHub", variable=self.procurar).grid(
            row=linha, column=0, columnspan=3, sticky="w"); linha += 1

        titulo("Periféricos (marque os que aparecem; setas mudam a ordem)")
        conhecidos = dict(cfg["conhecidos"])
        for k, v in nucleo.instantaneo().items():
            conhecidos.setdefault(k, {"nome": v["nome"], "tipo": v["tipo"]})
        ordem = cfg["ordem"]
        self.chaves = sorted(conhecidos, key=lambda k: (ordem.index(k) if k in ordem else len(ordem),
                                                        ORDEM_TIPO.get(conhecidos[k]["tipo"], 9),
                                                        conhecidos[k]["nome"]))
        self.conhecidos = conhecidos
        self.visivel = {k: tk.BooleanVar(value=k not in cfg["ocultos"]) for k in self.chaves}
        self.lista = ttk.Frame(f)
        self.lista.grid(row=linha, column=0, columnspan=3, sticky="we"); linha += 1
        self.desenha_lista()

        botoes = ttk.Frame(f)
        botoes.grid(row=linha, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(botoes, text="Cancelar", command=self.raiz.destroy).grid(row=0, column=0, padx=4)
        ttk.Button(botoes, text="Salvar", command=self.salva).grid(row=0, column=1)
        self.raiz.bind("<Escape>", lambda e: self.raiz.destroy())

    def desenha_lista(self):
        for w in self.lista.winfo_children():
            w.destroy()
        if not self.chaves:
            ttk.Label(self.lista, text="Nenhum periférico encontrado ainda.", foreground="#777").grid(sticky="w")
            return
        online = nucleo.instantaneo()
        for i, k in enumerate(self.chaves):
            nome = self.conhecidos[k]["nome"] + ("" if k in online else "  (desligado)")
            ttk.Checkbutton(self.lista, text=nome, variable=self.visivel[k]).grid(row=i, column=0, sticky="w")
            ttk.Button(self.lista, text="↑", width=3, command=lambda i=i: self.move(i, -1)).grid(row=i, column=1)
            ttk.Button(self.lista, text="↓", width=3, command=lambda i=i: self.move(i, 1)).grid(row=i, column=2)

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
