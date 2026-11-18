"""Cria o atalho "Bateria Perifericos" nesta pasta e no Menu Iniciar. Rode uma vez: python criar_atalho.py

O atalho abre o bateria.py com o pythonw.exe (o Python sem janela preta, assinado digitalmente).
Não existe .exe próprio, que é o que os antivírus costumam apagar por engano.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

import atalho

PASTA = os.path.dirname(os.path.abspath(__file__))
ICO = os.path.join(PASTA, "icone.ico")
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
SCRIPT = os.path.join(PASTA, "bateria.py")


def cria_icone():
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), radius=56, fill=(32, 32, 36, 255))
    try:
        f = ImageFont.truetype("SegoeIcons.ttf", 144)
        d.text((128, 120), "", font=f, fill=(255, 255, 255, 255), anchor="mm")   # mouse
    except OSError:
        pass
    d.rounded_rectangle((60, 196, 196, 220), radius=10, fill=(70, 70, 76, 255))
    d.rounded_rectangle((60, 196, 150, 220), radius=10, fill=(90, 200, 120, 255))     # barrinha de bateria
    img.save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])


def cria_atalhos():
    cria_icone()
    comum = dict(alvo=PYW, argumentos=f'"{SCRIPT}"', pasta=PASTA, icone=ICO, descricao="Bateria dos Periféricos",
                 aumid=atalho.AUMID)
    atalho.cria(os.path.join(PASTA, "Bateria dos Periféricos.lnk"), **comum)
    atalho.cria(os.path.join(atalho.MENU_INICIAR, "Bateria dos Periféricos.lnk"), **comum)


if __name__ == "__main__":
    if not os.path.exists(PYW):
        sys.exit("Não achei o pythonw.exe ao lado do Python.")
    cria_atalhos()
    print("Atalhos criados: nesta pasta e no Menu Iniciar.")
