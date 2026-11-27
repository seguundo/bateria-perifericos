"""Desenho do painel (clique no ícone): nome, %, previsão, última recarga e gráfico dos últimos 7 dias."""
import time

from PIL import Image, ImageDraw

DIAS = 7
LACUNA = 30 * 60                       # mais que isto sem leitura: a linha é interrompida
SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def _suaviza(trecho):
    """Mediana de 5 pontos: tira o serrilhado dos aparelhos que oscilam."""
    saida = []
    for i, p in enumerate(trecho):
        viz = sorted(q[1] for q in trecho[max(0, i - 2): i + 3])
        saida.append((p[0], viz[len(viz) // 2], p[2]))
    return saida


def _quando(hora, agora):
    dias = (_meia_noite(agora) - _meia_noite(hora)) // 86400
    relogio = time.strftime("%H:%M", time.localtime(hora))
    if dias <= 0:
        return f"hoje às {relogio}"
    return f"ontem às {relogio}" if dias == 1 else f"há {int(dias)} dias"


def _meia_noite(hora):
    t = time.localtime(hora)
    return int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1)))


def desenha(v, pontos, previsao, escala, claro, fonte, agora=None):
    """Imagem RGBA do painel. v = leitura atual; pontos = [[hora, %, carregando]]; fonte(tam, peso)."""
    import nucleo
    agora = time.time() if agora is None else agora

    def e(x):
        return round(x * escala)

    fundo = (249, 249, 249, 252) if claro else (43, 43, 43, 252)
    borda = (0, 0, 0, 45) if claro else (255, 255, 255, 35)
    forte = (0, 0, 0, 255) if claro else (255, 255, 255, 255)
    apoio = (90, 90, 90, 255) if claro else (200, 200, 200, 255)
    grade = (225, 225, 225, 255) if claro else (72, 72, 72, 255)
    verde = (15, 123, 15, 255) if claro else (108, 203, 95, 255)
    azul = (0, 95, 184, 255) if claro else (96, 205, 255, 255)

    w, h, pad = e(340), e(240), e(14)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=e(9), fill=fundo, outline=borda)

    f_num, f_tit, f_txt = fonte(e(22), "Semibold Text"), fonte(e(13), "Semibold Text"), fonte(e(12), "Regular")
    f_eixo = fonte(e(11), "Regular")
    nivel = f"{v['nivel']}%"
    d.text((w - pad, e(24)), nivel, font=f_num, fill=forte, anchor="rm")
    nome = v["nome"]
    while d.textlength(nome, font=f_tit) > w - 3 * pad - d.textlength(nivel, font=f_num) and len(nome) > 4:
        nome = nome[:-2] + "…"
    d.text((pad, e(24)), nome, font=f_tit, fill=forte, anchor="lm")
    estado = "Dormindo" if v.get("dormindo") else "Carregando" if v["carregando"] else "Na bateria"
    d.text((pad, e(46)), previsao or f"{estado} · previsão ainda aprendendo", font=f_txt, fill=apoio, anchor="lm")
    rec = nucleo.ultima_recarga(pontos)
    texto = f"Última recarga {_quando(rec[0], agora)}, até {rec[1]}%" if rec else "Nenhuma recarga registrada ainda"
    d.text((pad, e(64)), texto, font=f_txt, fill=apoio, anchor="lm")

    # gráfico
    x0, x1, y0, y1 = pad + e(30), w - pad, e(88), h - e(34)
    inicio = _meia_noite(agora - (DIAS - 1) * 86400)
    fim = inicio + DIAS * 86400

    def px(t):
        return x0 + (t - inicio) / (fim - inicio) * (x1 - x0)

    def py(n):
        return y1 - n / 100 * (y1 - y0)

    for n in (0, 50, 100):
        d.line((x0, py(n), x1, py(n)), fill=grade, width=max(1, e(1)))
        d.text((x0 - e(6), py(n)), f"{n}", font=f_eixo, fill=apoio, anchor="rm")
    for i in range(DIAS):
        meio = inicio + i * 86400 + 43200
        rotulo = "hoje" if i == DIAS - 1 else SEMANA[time.localtime(meio).tm_wday]
        d.text((px(meio), y1 + e(13)), rotulo, font=f_eixo, fill=apoio, anchor="mm")

    trechos = []
    for p in pontos:
        if p[0] < inicio:
            continue
        if not trechos or p[0] - trechos[-1][-1][0] > LACUNA:
            trechos.append([])
        trechos[-1].append(p)
    if not trechos:
        d.text(((x0 + x1) / 2, py(75)), "Sem leituras nos últimos 7 dias", font=f_txt, fill=apoio, anchor="mm")
        return img

    k = 3                                            # desenha 3x maior e reduz: linha lisa
    camada = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    c = ImageDraw.Draw(camada)
    esp = e(2) * k
    for trecho in trechos:
        t = _suaviza(trecho)
        xy = [(px(p[0]) * k, py(p[1]) * k) for p in t]
        for i in range(1, len(t)):
            c.line((xy[i - 1], xy[i]), fill=verde if t[i][2] else azul, width=esp)
        for (x, y), p in ((xy[0], t[0]), (xy[-1], t[-1])):      # pontas redondas (e trecho de um ponto só)
            c.ellipse((x - esp / 2, y - esp / 2, x + esp / 2, y + esp / 2), fill=verde if p[2] else azul)
    img.alpha_composite(camada.resize((w, h), Image.LANCZOS))
    return img
