"""Cria o ícone do programa e o atalho "Bateria Perifericos" (nesta pasta e no Menu Iniciar).

O atalho abre o bateria.py com o pythonw.exe (o Python sem janela preta). Assim não existe .exe
próprio, que é o que os antivírus costumam apagar por engano. Rode uma vez: python criar_atalho.py
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

PASTA = os.path.dirname(os.path.abspath(__file__))
ICO = os.path.join(PASTA, "icone.ico")
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
SCRIPT = os.path.join(PASTA, "bateria.py")


def cria_icone():
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), radius=56, fill=(32, 32, 36, 255))
    try:
        f = ImageFont.truetype("SegoeIcons.ttf", 150)
        d.text((128, 128), "", font=f, fill=(255, 255, 255, 255), anchor="mm")   # mouse
    except Exception:
        pass
    d.rounded_rectangle((60, 196, 196, 220), radius=10, fill=(70, 70, 76, 255))
    d.rounded_rectangle((60, 196, 150, 220), radius=10, fill=(90, 200, 120, 255))     # barrinha de bateria
    img.save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])


def cria_atalho(destino):
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:DESTINO);"
        "$s.TargetPath=$env:PYW; $s.Arguments='\"'+$env:SCRIPT+'\"';"
        "$s.WorkingDirectory=$env:PASTA; $s.IconLocation=$env:ICO+',0';"
        "$s.Description='Bateria dos Periféricos'; $s.Save()"
    )
    env = dict(os.environ, DESTINO=destino, PYW=PYW, SCRIPT=SCRIPT, PASTA=PASTA, ICO=ICO)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, check=True)


if __name__ == "__main__":
    if not os.path.exists(PYW):
        sys.exit("Não achei o pythonw.exe ao lado do Python.")
    cria_icone()
    cria_atalho(os.path.join(PASTA, "Bateria Perifericos.lnk"))
    menu = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs", "Bateria Perifericos.lnk")
    cria_atalho(menu)
    print("Atalhos criados: nesta pasta e no Menu Iniciar.")
