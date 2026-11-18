"""Ícone do programa. Tamanhos pequenos (16-24 px) têm desenho próprio, uma pilha que lê bem;
do 32 px para cima, mouse branco sobre quadrado escuro com a barrinha de carga."""
from PIL import Image, ImageDraw, ImageFont

VERDE = (88, 200, 120, 255)
BRANCO = (255, 255, 255, 255)
ESCURO = (32, 32, 36, 255)
TAMANHOS = [16, 20, 24, 32, 48, 64, 256]


def _pilha(n):
    """Pilha horizontal desenhada pixel a pixel (sem meio-pixel) para 16, 20 e 24 px."""
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    altura = round(n * 0.5)                    # 8 px em 16
    topo = (n - altura) // 2
    corpo_dir = n - 3                          # deixa 2 px para o polo
    d.rectangle((0, topo, corpo_dir, topo + altura - 1), outline=BRANCO, width=1)
    polo = max(2, altura // 3)
    meio = topo + (altura - polo) // 2
    d.rectangle((corpo_dir + 1, meio, corpo_dir + 2, meio + polo - 1), fill=BRANCO)
    interno = corpo_dir - 3                    # carga com 1 px de folga por dentro
    d.rectangle((2, topo + 2, 2 + round(interno * 0.7), topo + altura - 3), fill=VERDE)
    return img


def _grande(n):
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = n / 256
    d.rounded_rectangle((8 * k, 8 * k, 248 * k, 248 * k), radius=56 * k, fill=ESCURO,
                        outline=(255, 255, 255, 60), width=max(1, round(4 * k)))   # borda clara: some menos na barra escura
    try:
        f = ImageFont.truetype("SegoeIcons.ttf", max(8, round(144 * k)))
        d.text((128 * k, 116 * k), "", font=f, fill=BRANCO, anchor="mm")    # mouse
    except OSError:
        pass
    d.rounded_rectangle((60 * k, 196 * k, 196 * k, 220 * k), radius=10 * k, fill=(70, 70, 76, 255))
    d.rounded_rectangle((60 * k, 196 * k, 150 * k, 220 * k), radius=10 * k, fill=VERDE)
    return img


def desenha(n):
    return _pilha(n) if n < 32 else _grande(n)


def salva(caminho_ico, caminho_png=None):
    grande = _grande(256)
    extras = [desenha(n) for n in TAMANHOS if n != 256]
    grande.save(caminho_ico, format="ICO", sizes=[(n, n) for n in TAMANHOS], append_images=extras)
    if caminho_png:
        _grande(128).save(caminho_png)
