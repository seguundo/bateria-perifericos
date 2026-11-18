"""Bateria dos Periféricos — faixa fixa na barra de tarefas com o ícone e a % de cada periférico sem fio.

Arquivos:
- bateria.py  (este) faixa na barra, dica ao passar o mouse, menu, avisos e aviso de versão nova
- leitores.py um leitor por marca (Attack Shark, Corsair, Bluetooth, Logitech, Razer, HeadsetControl)
- nucleo.py   estado compartilhado, configuração, histórico e previsão de duração
- ajustes.py  janela de ajustes

A faixa é uma janelinha transparente por cima da barra de tarefas (o Windows 11 não deixa
programas escreverem dentro da barra). Arraste para o lado para mudar de lugar; botão direito = menu.
"""
import ctypes
import json
import os
import sys
import threading
import time
import urllib.request
import winreg
from ctypes import wintypes as wt

from PIL import Image, ImageChops, ImageDraw, ImageFont

import ajustes
import atalho
import leitores
import nucleo
from nucleo import APP, VERSAO

PASTA = os.path.dirname(os.path.abspath(__file__))

# Ícones da fonte do Windows 11 (Segoe Fluent Icons)
G_HEADSET, G_MOUSE, G_CONTROLE, G_BLUETOOTH, G_RAIO, G_TECLADO = "", "", "", "", "", ""
GLIFO = {"headset": G_HEADSET, "mouse": G_MOUSE, "teclado": G_TECLADO, "controle": G_CONTROLE, "bluetooth": G_BLUETOOTH}
ORDEM_TIPO = {"headset": 0, "mouse": 1, "teclado": 2, "controle": 3, "bluetooth": 4}


# ---------- Aparência ----------
def fonte(nomes, tam):
    for f in nomes:
        try:
            return ImageFont.truetype(f, max(6, int(tam)))
        except Exception:
            pass
    return ImageFont.load_default()


def tema_claro():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "SystemUsesLightTheme")[0] == 1
    except OSError:
        return False


def itens_visiveis(cfg):
    ordem = cfg["ordem"]
    lista = [dict(v, chave=k) for k, v in nucleo.instantaneo().items()
             if k not in cfg["ocultos"] and v["nivel"] <= cfg["mostrar_ate"]]
    lista.sort(key=lambda i: (ordem.index(i["chave"]) if i["chave"] in ordem else len(ordem),
                              ORDEM_TIPO.get(i["tipo"], 9), i["nome"]))
    return lista


def desenha_faixa(itens, altura, escala, alerta):
    """Devolve (imagem RGBA, regiões [(x0, x1, chave)]). Fundo com alfa 1: dá para clicar e arrastar."""
    claro = tema_claro()
    cor = (0, 0, 0, 255) if claro else (255, 255, 255, 255)
    vermelho = (196, 43, 28, 255) if claro else (255, 110, 100, 255)
    f_icone = fonte(("SegoeIcons.ttf", "segmdl2.ttf"), round(17 * escala))
    f_raio = fonte(("SegoeIcons.ttf", "segmdl2.ttf"), round(10 * escala))
    f_txt = fonte(("segoeui.ttf",), round(13.5 * escala))
    pad, gap_icone, gap_item = round(6 * escala), round(5 * escala), round(16 * escala)

    medidor = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    blocos, largura = [], pad
    for i, it in enumerate(itens):
        txt = f"{it['nivel']}%"
        wi = medidor.textlength(GLIFO.get(it["tipo"], G_BLUETOOTH), font=f_icone)
        wtx = medidor.textlength(txt, font=f_txt)
        wr = medidor.textlength(G_RAIO, font=f_raio) + round(2 * escala) if it["carregando"] else 0
        blocos.append((it, txt, wi, wtx, wr))
        largura += wi + gap_icone + wtx + wr + (gap_item if i < len(itens) - 1 else 0)
    largura = int(largura + pad)

    img = Image.new("RGBA", (max(largura, 1), altura), (0, 0, 0, 1))
    d = ImageDraw.Draw(img)
    x, meio, regioes = pad, altura / 2, []
    for it, txt, wi, wtx, wr in blocos:
        x0 = x
        c = vermelho if (it["nivel"] <= alerta and not it["carregando"]) else cor
        d.text((x, meio), GLIFO.get(it["tipo"], G_BLUETOOTH), font=f_icone, fill=cor, anchor="lm")
        x += wi + gap_icone
        d.text((x, meio + round(0.5 * escala)), txt, font=f_txt, fill=c, anchor="lm")
        x += wtx
        if wr:
            x += round(2 * escala)
            d.text((x, meio), G_RAIO, font=f_raio, fill=cor, anchor="lm")
            x += wr - round(2 * escala)
        regioes.append((int(x0 - gap_item / 2), int(x + gap_item / 2), it["chave"]))
        x += gap_item
    return img, regioes


def desenha_dica(linhas, escala):
    """linhas: [(texto, negrito)]. Balão no estilo das dicas do Windows 11."""
    claro = tema_claro()
    fundo = (249, 249, 249, 250) if claro else (43, 43, 43, 250)
    borda = (0, 0, 0, 40) if claro else (255, 255, 255, 30)
    cor = (0, 0, 0, 255) if claro else (255, 255, 255, 255)
    cor2 = (90, 90, 90, 255) if claro else (200, 200, 200, 255)
    f_n = fonte(("segoeuib.ttf", "segoeui.ttf"), round(12.5 * escala))
    f_r = fonte(("segoeui.ttf",), round(12 * escala))
    pad, entre = round(10 * escala), round(4 * escala)
    med = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    medidas = []
    for texto, negrito in linhas:
        caixa = med.textbbox((0, 0), texto, font=f_n if negrito else f_r)
        medidas.append((caixa[2] - caixa[0], round(16 * escala)))
    w = int(max(m[0] for m in medidas) + 2 * pad)
    h = int(sum(m[1] for m in medidas) + entre * (len(linhas) - 1) + 2 * pad)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(7 * escala), fill=fundo, outline=borda)
    y = pad
    for (texto, negrito), (_, alt) in zip(linhas, medidas):
        d.text((pad, y + alt / 2), texto, font=f_n if negrito else f_r, fill=cor if negrito else cor2, anchor="lm")
        y += alt + entre
    return img


# ---------- Avisos do Windows ----------
AUMID = atalho.AUMID


ICONE_PNG = os.path.join(nucleo.PASTA_DADOS, "icone.png")
ICONE_ICO = os.path.join(nucleo.PASTA_DADOS, "icone.ico")


def registra_avisos():
    """Cria o ícone do programa e dá nome/ícone próprios às notificações (em vez de 'Python')."""
    try:
        os.makedirs(nucleo.PASTA_DADOS, exist_ok=True)
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((8, 8, 248, 248), radius=56, fill=(32, 32, 36, 255))
        d.text((128, 120), G_MOUSE, font=fonte(("SegoeIcons.ttf",), 144), fill=(255, 255, 255, 255), anchor="mm")
        d.rounded_rectangle((60, 196, 196, 220), radius=10, fill=(70, 70, 76, 255))
        d.rounded_rectangle((60, 196, 150, 220), radius=10, fill=(90, 200, 120, 255))
        img.save(ICONE_PNG)
        img.save(ICONE_ICO, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}") as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP)
            winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, ICONE_PNG)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AUMID)
    except Exception:
        pass


_bandeja = None


def avisa(titulo, texto):
    """Notificação do Windows, pelo ícone do programa na bandeja (API oficial, sem PowerShell)."""
    if _bandeja is not None:
        _bandeja.fila.append((titulo, texto))
        user32.PostMessageW(_bandeja.app.ctrl, WM_AVISO, 0, 0)


# ---------- Versão nova no GitHub ----------
def _tupla(v):
    try:
        return tuple(int(p) for p in v.lstrip("vV").split("."))
    except ValueError:
        return (0,)


def procura_versao(app):
    if nucleo.espera(30):
        return
    while True:
        if nucleo.config()["procurar_versao"]:
            try:
                pedido = urllib.request.Request(f"https://api.github.com/repos/{nucleo.REPO}/releases/latest",
                                                headers={"User-Agent": "BateriaPerifericos",
                                                         "Accept": "application/vnd.github+json"})
                with urllib.request.urlopen(pedido, timeout=15) as r:
                    dados = json.load(r)
                tag, pagina = dados.get("tag_name", ""), dados.get("html_url", "")
                if _tupla(tag) > _tupla(VERSAO) and pagina.startswith(f"https://github.com/{nucleo.REPO}/"):
                    app.nova_versao = (tag, pagina)
                    if nucleo.config().get("versao_avisada") != tag:
                        avisa("Versão nova disponível", f"{APP} {tag}. Clique com o botão direito nos ícones da barra.")
                        nucleo.muda_config(versao_avisada=tag)
            except Exception:
                pass
        if nucleo.espera(24 * 3600):
            return


# ---------- Iniciar com o Windows ----------
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def comando_inicio():
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw}" "{os.path.join(PASTA, "bateria.py")}"'


def inicia_com_windows():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except OSError:
        return False


def alterna_inicio():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN, 0, winreg.KEY_SET_VALUE) as k:
        if inicia_com_windows():
            winreg.DeleteValue(k, APP)
        else:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, comando_inicio())


# ---------- Win32 ----------
user32, gdi32, kernel32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.restype = wt.HWND
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
user32.FindWindowW.restype = wt.HWND
user32.FindWindowExW.restype = wt.HWND
user32.FindWindowExW.argtypes = [wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR]
user32.GetForegroundWindow.restype = wt.HWND
user32.MonitorFromWindow.restype = wt.HANDLE
user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
user32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.c_void_p]
user32.CreatePopupMenu.restype = wt.HMENU
user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID]
user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE),
                                       wt.HDC, ctypes.POINTER(wt.POINT), wt.DWORD, ctypes.c_void_p, wt.DWORD]
user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.GetDpiForWindow.argtypes = [wt.HWND]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
kernel32.GetModuleHandleW.restype = wt.HMODULE
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]

WM_DESTROY, WM_TIMER, WM_NCHITTEST, WM_MOVING, WM_EXITSIZEMOVE, WM_ENTERSIZEMOVE = 0x2, 0x113, 0x84, 0x216, 0x232, 0x231
WM_NCRBUTTONUP, WM_RBUTTONUP, WM_CLOSE = 0xA5, 0x205, 0x10
HTCAPTION, HTTRANSPARENT = 2, -1
WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_NOACTIVATE, WS_EX_TRANSPARENT = 0x80000, 0x80, 0x8, 0x08000000, 0x20
HWND_TOPMOST = wt.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x1, 0x2, 0x10, 0x40
ULW_ALPHA = 2
TPM_RETURNCMD, TPM_RIGHTBUTTON = 0x100, 0x2
MF_STRING, MF_CHECKED, MF_SEPARATOR, MF_GRAYED = 0x0, 0x8, 0x800, 0x1
CLASSE = "BateriaPerifericosFaixa"


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


JANELAS = {}       # hwnd -> objeto que trata as mensagens


@WNDPROC
def _wndproc(hwnd, msg, wp, lp):
    dono = JANELAS.get(hwnd)
    if dono is not None:
        r = dono.mensagem(hwnd, msg, wp, lp)
        if r is not None:
            return r
    return user32.DefWindowProcW(hwnd, msg, wp, lp)


def registra_classe():
    wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=_wndproc,
                     hInstance=kernel32.GetModuleHandleW(None), hCursor=user32.LoadCursorW(None, 32512),
                     lpszClassName=CLASSE)
    user32.RegisterClassExW(ctypes.byref(wc))


def cria_janela(extra=0):
    return user32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE | extra,
                                  CLASSE, APP, WS_POPUP, 0, 0, 1, 1, None, None,
                                  kernel32.GetModuleHandleW(None), None)


def pinta(hwnd, img, x, y):
    """Mostra a imagem RGBA na janela em camadas, com transparência por pixel."""
    w, h = img.size
    a = img.split()[3]
    r, g, b = (ImageChops.multiply(c, a) for c in img.split()[:3])
    dados = Image.merge("RGBA", (b, g, r, a)).tobytes()
    tela = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(tela)
    bi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
    bits = ctypes.c_void_p()
    bmp = gdi32.CreateDIBSection(mem, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
    ctypes.memmove(bits, dados, len(dados))
    antigo = gdi32.SelectObject(mem, bmp)
    user32.UpdateLayeredWindow(hwnd, tela, ctypes.byref(wt.POINT(x, y)), ctypes.byref(wt.SIZE(w, h)), mem,
                               ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(BLENDFUNCTION(0, 0, 255, 1)), ULW_ALPHA)
    gdi32.SelectObject(mem, antigo)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(None, tela)


def para_frente(hwnd):
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)


def retangulo(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def monitor_de(hwnd):
    mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
    return mi.rcMonitor


PROCESSOS_SISTEMA = {"explorer.exe", "textinputhost.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe",
                     "searchhost.exe", "searchapp.exe", "lockapp.exe", "shellhost.exe", "tabtip.exe"}


def processo(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)      # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf, n = ctypes.create_unicode_buffer(260), wt.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def monitor_em_tela_cheia(ignorar):
    """Retângulo do monitor onde há um jogo/vídeo em tela cheia em primeiro plano, ou None."""
    fg = user32.GetForegroundWindow()
    if not fg or fg in ignorar or not user32.IsWindowVisible(fg):
        return None
    nome = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(fg, nome, 64)
    if nome.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        return None
    # janelas invisíveis do próprio Windows (bandeja ^, teclado de toque, Iniciar...) ocupam a tela
    # inteira mas não são jogo/vídeo: ignora as "camufladas" e as dos processos do sistema
    camuflada = wt.DWORD()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(fg, 14, ctypes.byref(camuflada), 4) == 0 and camuflada.value:
        return None
    if processo(fg) in PROCESSOS_SISTEMA:
        return None
    r, m = retangulo(fg), monitor_de(fg)
    if r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom:
        return (m.left, m.top, m.right, m.bottom)
    return None


def barras():
    """[(id, hwnd, retângulo, borda esquerda da bandeja ou None)] de todas as barras de tarefas."""
    res = []
    tb = user32.FindWindowW("Shell_TrayWnd", None)
    if tb:
        r = retangulo(tb)
        tn = user32.FindWindowExW(tb, None, "TrayNotifyWnd", None)
        esq = retangulo(tn).left if tn else None
        res.append(("principal", tb, r, esq if esq and r.left < esq < r.right else None))
    h = None
    while True:
        h = user32.FindWindowExW(None, h, "Shell_SecondaryTrayWnd", None)
        if not h:
            break
        r = retangulo(h)
        res.append((f"tela {r.left},{r.top}", h, r, None))
    return res


# ---------- Faixa (uma por barra de tarefas) ----------
class Faixa:
    def __init__(self, app, id_barra):
        self.app, self.id = app, id_barra
        self.hwnd = cria_janela()
        JANELAS[self.hwnd] = self
        self.ultimo = None
        self.img, self.regioes = None, []
        self.pos = (0, 0)
        self.visivel = False
        self.arrastando = False
        self.barra_rect = None

    def atualiza(self, tb, r, bandeja_esq, itens, cfg, cheia):
        self.barra_rect = (r.left, r.top, r.right, r.bottom)
        m = monitor_de(tb)
        if not itens or (cheia and cheia == (m.left, m.top, m.right, m.bottom)):
            self.esconde()
            return
        try:
            esc = user32.GetDpiForWindow(tb) / 96
        except Exception:
            esc = 1.0
        esc_txt = esc * cfg["tamanho"]
        altura = r.bottom - r.top
        chave = (tuple((i["chave"], i["tipo"], i["nivel"], i["carregando"]) for i in itens),
                 altura, esc_txt, tema_claro(), cfg["alerta"])
        if chave != self.ultimo:
            self.ultimo = chave
            self.img, self.regioes = desenha_faixa(itens, altura, esc_txt, cfg["alerta"])
        w, h = self.img.size
        margem = cfg["margens"].get(self.id)
        if margem is None:
            if self.id == "principal":
                ref = bandeja_esq if bandeja_esq else r.right - round(330 * esc)
                margem = r.right - ref + round(8 * esc)      # encosta na setinha ^ com uma folga pequena
            else:
                margem = round(100 * esc)                    # barra secundária: à esquerda do relógio
        x = max(r.left, r.right - margem - w)
        if not self.arrastando:
            pinta(self.hwnd, self.img, x, r.top)
            self.pos = (x, r.top)
        para_frente(self.hwnd)
        self.visivel = True

    def esconde(self):
        if self.visivel:
            user32.ShowWindow(self.hwnd, 0)
            self.visivel = False

    def item_em(self, px, py):
        if not self.visivel or self.img is None:
            return None
        x, y = self.pos
        w, h = self.img.size
        if not (x <= px < x + w and y <= py < y + h):
            return None
        for x0, x1, chave in self.regioes:
            if x0 <= px - x < x1:
                return chave, x + (x0 + x1) // 2
        return None

    def destroi(self):
        JANELAS.pop(self.hwnd, None)
        user32.DestroyWindow(self.hwnd)

    def mensagem(self, hwnd, msg, wp, lp):
        if msg == WM_NCHITTEST:
            return HTCAPTION                       # arrastar com o botão esquerdo
        if msg == WM_ENTERSIZEMOVE:
            self.arrastando = True
            self.app.dica.esconde()
            return 0
        if msg == WM_MOVING:                       # só anda na horizontal
            rc = ctypes.cast(lp, ctypes.POINTER(wt.RECT)).contents
            altura = rc.bottom - rc.top
            rc.top, rc.bottom = self.pos[1], self.pos[1] + altura
            return 1
        if msg == WM_EXITSIZEMOVE:
            self.arrastando = False
            r = retangulo(hwnd)
            self.pos = (r.left, r.top)
            if self.barra_rect:
                margens = nucleo.config()["margens"]
                margens[self.id] = self.barra_rect[2] - r.right
                nucleo.muda_config(margens=margens)
            return 0
        if msg in (WM_NCRBUTTONUP, WM_RBUTTONUP):
            self.app.menu(self)
            return 0
        return None


# ---------- Dica ao passar o mouse ----------
class Dica:
    def __init__(self):
        self.hwnd = cria_janela(WS_EX_TRANSPARENT)   # não pega cliques
        JANELAS[self.hwnd] = self
        self.chave = None
        self.desde = 0
        self.visivel = False
        self.ultimo = None

    def linhas(self, chave):
        v = nucleo.instantaneo().get(chave)
        if not v:
            return None
        estado = "carregando" if v["carregando"] else "na bateria"
        prev = nucleo.previsao(chave)
        linhas = [(v["nome"], True), (f"{v['nivel']}% · {estado}", False)]
        linhas.append((prev or "previsão: aprendendo o ritmo de uso…", False))
        visto = int(time.time() - v["visto"])
        quando = "agora" if visto < 60 else f"há {visto // 60} min"
        linhas.append((f"via {v['origem'] or '—'} · lido {quando}", False))
        return linhas

    def mostra(self, faixa, chave, centro_x):
        agora = time.time()
        if chave != self.chave:
            self.chave, self.desde = chave, agora
            self.esconde(manter_chave=True)
            return
        if agora - self.desde < 0.4:                 # espera um pouquinho, como as dicas do Windows
            return
        linhas = self.linhas(chave)
        if not linhas:
            return self.esconde()
        esc = user32.GetDpiForWindow(faixa.hwnd) / 96 if faixa.hwnd else 1.0
        if (linhas, centro_x, esc) != self.ultimo or not self.visivel:
            self.ultimo = (linhas, centro_x, esc)
            img = desenha_dica(linhas, esc)
            w, h = img.size
            bl, bt, br, bb = faixa.barra_rect
            m = monitor_de(faixa.hwnd)
            x = min(max(centro_x - w // 2, m.left + 4), m.right - w - 4)
            y = bt - h - round(8 * esc)
            pinta(self.hwnd, img, x, y)
        para_frente(self.hwnd)
        self.visivel = True

    def esconde(self, manter_chave=False):
        if not manter_chave:
            self.chave = None
        if self.visivel:
            user32.ShowWindow(self.hwnd, 0)
            self.visivel = False

    def mensagem(self, hwnd, msg, wp, lp):
        if msg == WM_NCHITTEST:
            return HTTRANSPARENT
        return None


# ---------- Ícone na bandeja (menu e notificações) ----------
class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT), ("uFlags", wt.UINT),
                ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD), ("szInfo", wt.WCHAR * 256),
                ("uVersion", wt.UINT), ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wt.HICON)]


shell32 = ctypes.windll.shell32
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
user32.LoadImageW.restype = wt.HANDLE
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
WM_BANDEJA, WM_AVISO = 0x8001, 0x8002            # WM_APP + n
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
NIIF_USER, NIIF_LARGE_ICON = 4, 0x20


class Bandeja:
    def __init__(self, app):
        self.app = app
        self.fila = []
        self.icone = user32.LoadImageW(None, ICONE_ICO, 1, 0, 0, 0x10 | 0x40)        # LR_LOADFROMFILE|DEFAULTSIZE
        self.icone_grande = user32.LoadImageW(None, ICONE_ICO, 1, 64, 64, 0x10)
        self.adiciona()

    def dados(self):
        n = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.app.ctrl, uID=1)
        return n

    def adiciona(self):
        n = self.dados()
        n.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        n.uCallbackMessage, n.hIcon, n.szTip = WM_BANDEJA, self.icone, APP
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(n))

    def mostra_fila(self):
        while self.fila:
            titulo, texto = self.fila.pop(0)
            n = self.dados()
            n.uFlags = NIF_INFO
            n.szInfoTitle, n.szInfo = titulo[:63], texto[:255]
            n.dwInfoFlags = NIIF_USER | NIIF_LARGE_ICON
            n.hBalloonIcon = self.icone_grande
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(n))

    def remove(self):
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.dados()))


class _PseudoFaixa:            # o menu aberto pela bandeja não pertence a nenhuma faixa
    def __init__(self, hwnd):
        self.hwnd, self.id = hwnd, None


# ---------- Programa ----------
class App:
    def __init__(self):
        registra_classe()
        self.ctrl = cria_janela()            # janela escondida só para os relógios
        JANELAS[self.ctrl] = self
        self.faixas = {}
        self.dica = Dica()
        self.nova_versao = None
        self.cheia_seguidas = 0
        self.avisados_fraca, self.avisados_cheio = set(), set()
        self.ultimo_salvo = time.time()
        global _bandeja
        _bandeja = self.bandeja = Bandeja(self)
        self.msg_barra_criada = user32.RegisterWindowMessageW("TaskbarCreated")   # Explorer reiniciou
        user32.SetTimer(self.ctrl, 1, 1000, None)
        user32.SetTimer(self.ctrl, 2, 200, None)   # dica + manter por cima (clicar na barra a joga por cima)
        self.tick()

    def tick(self):
        cfg = nucleo.config()
        itens = itens_visiveis(cfg)
        cheia = monitor_em_tela_cheia(set(JANELAS))
        self.cheia_seguidas = self.cheia_seguidas + 1 if cheia else 0
        cheia = cheia if self.cheia_seguidas >= 2 else None        # 2 s seguidos: não some por um piscar
        presentes = set()
        for id_barra, tb, r, esq in barras():
            if cfg["monitores"] == "principal" and id_barra != "principal":
                continue
            presentes.add(id_barra)
            if id_barra not in self.faixas:
                self.faixas[id_barra] = Faixa(self, id_barra)
            self.faixas[id_barra].atualiza(tb, r, esq, itens, cfg, cheia)
        for id_barra in [i for i in self.faixas if i not in presentes]:
            self.faixas.pop(id_barra).destroi()
        self.confere_avisos(cfg)
        if time.time() - self.ultimo_salvo > 300:
            nucleo.salva()
            self.ultimo_salvo = time.time()

    def confere_avisos(self, cfg):
        for chave, v in nucleo.instantaneo().items():
            if chave in cfg["ocultos"]:
                continue
            if cfg["aviso_fraca"] and not v["carregando"] and v["nivel"] <= cfg["alerta"]:
                if chave not in self.avisados_fraca:
                    self.avisados_fraca.add(chave)
                    avisa("Bateria fraca", f"{v['nome']} está com {v['nivel']}%. Hora de carregar.")
            elif v["carregando"] or v["nivel"] > cfg["alerta"] + 5:
                self.avisados_fraca.discard(chave)
            if cfg["aviso_cheio"] and v["carregando"] and v["nivel"] >= 100:
                if chave not in self.avisados_cheio:
                    self.avisados_cheio.add(chave)
                    avisa("Carga completa", f"{v['nome']} está com 100%. Já pode tirar da tomada.")
            elif not v["carregando"]:
                self.avisados_cheio.discard(chave)

    def rapido(self):
        p = wt.POINT()
        user32.GetCursorPos(ctypes.byref(p))
        achou = None
        for f in self.faixas.values():
            if f.visivel:
                para_frente(f.hwnd)
                if not f.arrastando and achou is None:
                    item = f.item_em(p.x, p.y)
                    if item:
                        achou = (f, item[0], item[1])
        if achou:
            self.dica.mostra(*achou)
        else:
            self.dica.esconde()

    def menu(self, faixa):
        self.dica.esconde()
        m = user32.CreatePopupMenu()
        cfg = nucleo.config()
        for it in itens_visiveis(dict(cfg, mostrar_ate=100)):
            prev = nucleo.previsao(it["chave"])
            texto = f"{it['nome']}: {it['nivel']}%" + (" (carregando)" if it["carregando"] else "")
            user32.AppendMenuW(m, MF_STRING | MF_GRAYED, 0, texto + (f"  ·  {prev}" if prev else ""))
        user32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        if self.nova_versao:
            user32.AppendMenuW(m, MF_STRING, 5, f"Versão nova {self.nova_versao[0]}: abrir no GitHub")
        user32.AppendMenuW(m, MF_STRING, 4, "Ajustes…")
        user32.AppendMenuW(m, MF_STRING | (MF_CHECKED if inicia_com_windows() else 0), 1, "Iniciar com o Windows")
        user32.AppendMenuW(m, MF_STRING, 2, "Voltar para a posição padrão")
        user32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(m, MF_STRING | MF_GRAYED, 0, f"{APP} {VERSAO}")
        user32.AppendMenuW(m, MF_STRING, 3, "Sair")
        p = wt.POINT()
        user32.GetCursorPos(ctypes.byref(p))
        user32.SetForegroundWindow(faixa.hwnd)
        cmd = user32.TrackPopupMenu(m, TPM_RETURNCMD | TPM_RIGHTBUTTON, p.x, p.y, 0, faixa.hwnd, None)
        user32.DestroyMenu(m)
        if cmd == 1:
            alterna_inicio()
        elif cmd == 2:
            margens = cfg["margens"]
            if faixa.id is None:
                margens = {}                       # pela bandeja: todas as telas
            else:
                margens.pop(faixa.id, None)
            nucleo.muda_config(margens=margens)
            self.tick()
        elif cmd == 3:
            user32.PostMessageW(self.ctrl, WM_CLOSE, 0, 0)
        elif cmd == 4:
            ajustes.abre()
        elif cmd == 5 and self.nova_versao:
            os.startfile(self.nova_versao[1])

    def mensagem(self, hwnd, msg, wp, lp):
        if msg == WM_TIMER:
            try:
                self.rapido() if wp == 2 else self.tick()
            except Exception:
                pass
            return 0
        if msg == WM_BANDEJA:
            if lp in (WM_RBUTTONUP, 0x202):        # botão direito ou esquerdo no ícone da bandeja
                self.menu(_PseudoFaixa(self.ctrl))
            return 0
        if msg == WM_AVISO:
            self.bandeja.mostra_fila()
            return 0
        if msg == self.msg_barra_criada:
            self.bandeja.adiciona()
            return 0
        if msg == WM_CLOSE:
            self.bandeja.remove()
            for f in list(self.faixas.values()):
                f.destroi()
            user32.DestroyWindow(self.dica.hwnd)
            user32.DestroyWindow(self.ctrl)
            user32.PostQuitMessage(0)
            return 0
        return None


def principal():
    kernel32.CreateMutexW(None, False, "BateriaPerifericos_unica")
    if kernel32.GetLastError() == 183:          # já está aberto
        return
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # nítido em qualquer escala
    except Exception:
        pass
    # se "Iniciar com o Windows" está ligado mas aponta para outro lugar (ex.: versão antiga), corrige
    if inicia_com_windows():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, comando_inicio())
        except OSError:
            pass
    registra_avisos()
    # o atalho do Menu Iniciar dá nome e ícone às notificações: cria se ainda não existir
    if not os.path.exists(os.path.join(atalho.MENU_INICIAR, "Bateria dos Periféricos.lnk")):
        try:
            import criar_atalho
            criar_atalho.cria_atalhos()
        except Exception:
            pass
    for alvo in leitores.LEITORES:
        threading.Thread(target=alvo, daemon=True).start()
    app = App()
    threading.Thread(target=procura_versao, args=(app,), daemon=True).start()
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    nucleo.parar.set()
    nucleo.salva()


if __name__ == "__main__":
    principal()
