"""Cria o atalho "Bateria dos Periféricos" nesta pasta e no Menu Iniciar. Rode uma vez: python criar_atalho.py

O atalho abre o bateria.py com o pythonw.exe (o Python sem janela preta, assinado digitalmente).
Não existe .exe próprio, que é o que os antivírus costumam apagar por engano.
"""
import os
import sys

import atalho
import icone

PASTA = os.path.dirname(os.path.abspath(__file__))
ICO = os.path.join(PASTA, "icone.ico")
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
SCRIPT = os.path.join(PASTA, "bateria.py")


def cria_atalhos():
    icone.salva(ICO)
    comum = dict(alvo=PYW, argumentos=f'"{SCRIPT}"', pasta=PASTA, icone=ICO, descricao="Bateria dos Periféricos",
                 aumid=atalho.AUMID)
    atalho.cria(os.path.join(PASTA, "Bateria dos Periféricos.lnk"), **comum)
    atalho.cria(os.path.join(atalho.MENU_INICIAR, "Bateria dos Periféricos.lnk"), **comum)


if __name__ == "__main__":
    if not os.path.exists(PYW):
        sys.exit("Não achei o pythonw.exe ao lado do Python.")
    cria_atalhos()
    print("Atalhos criados: nesta pasta e no Menu Iniciar.")
