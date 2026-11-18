"""Bateria dos Periféricos — faixa fixa na barra de tarefas com o ícone e a % de cada periférico sem fio.

- Mouse Attack Shark X11: lê direto do receptor 2.4G (1D57:FA60, interface 2). O receptor envia
  sozinho, a cada ~2 s, um quadro 03 ?? 40 ST NN (ST 01 = na bateria, 03 = carregando; NN = %).
- Headset Corsair: pelo iCUE (SDK oficial). O iCUE precisa estar aberto e o headset ligado.
- Bluetooth (controle Xbox etc.): pela informação de bateria que o próprio Windows guarda.

A faixa é uma janelinha transparente por cima da barra de tarefas (o Windows 11 não deixa
programas escreverem dentro da barra). Arraste para o lado para mudar de lugar;
botão direito abre o menu.
"""
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import winreg
from ctypes import wintypes as wt

import hid
from PIL import Image, ImageChops, ImageDraw, ImageFont

APP = "Bateria dos Periféricos"
ALERTA = 15            # % que deixa o número vermelho
INTERVALO = 60         # s entre consultas do headset
INTERVALO_BT = 20      # s entre consultas do Bluetooth (ligar/desligar aparece rápido)
X11_DORMINDO = 30      # s sem sinal = mouse dormindo/desligado
CONFIG = os.path.join(os.environ.get("APPDATA", "."), "BateriaPerifericos", "config.json")

# Ícones da fonte do Windows 11 (Segoe Fluent Icons)
G_HEADSET, G_MOUSE, G_CONTROLE, G_BLUETOOTH, G_RAIO, G_TECLADO = "", "", "", "", "", ""
ORDEM = {"headset": 0, "mouse": 1, "teclado": 2, "controle": 3, "bluetooth": 4}
GLIFO = {"headset": G_HEADSET, "mouse": G_MOUSE, "teclado": G_TECLADO, "controle": G_CONTROLE, "bluetooth": G_BLUETOOTH}

estado = {}            # chave -> dict(nome, tipo, nivel, carregando, visto)
trava = threading.Lock()
rodando = True


def atualiza(chave, nome, tipo, nivel, carregando=False):
    with trava:
        estado[chave] = dict(nome=nome, tipo=tipo, nivel=nivel, carregando=carregando, visto=time.time())


def some(chave):
    with trava:
        estado.pop(chave, None)


def espera(s):
    fim = time.time() + s
    while rodando and time.time() < fim:
        time.sleep(0.5)


# ---------- Mouse Attack Shark X11 ----------
def le_x11():
    while rodando:
        abertos = []
        try:
            for d in hid.enumerate(0x1D57, 0xFA60):
                if d["interface_number"] != 2:
                    continue
                try:
                    h = hid.device()
                    h.open_path(d["path"])
                    h.set_nonblocking(1)
                    abertos.append(h)
                except Exception:
                    pass
            while rodando and abertos:
                for h in list(abertos):
                    try:
                        r = h.read(64)
                    except Exception:
                        abertos.remove(h)
                        continue
                    if r and len(r) >= 5 and r[0] == 0x03 and r[2] == 0x40 and r[4] <= 100 and r[3] in (1, 3):
                        atualiza("x11", "Mouse Attack Shark X11", "mouse", r[4], r[3] == 3)
                with trava:
                    v = estado.get("x11")
                if v and time.time() - v["visto"] > X11_DORMINDO:
                    some("x11")
                time.sleep(0.05)
        finally:
            for h in abertos:
                try:
                    h.close()
                except Exception:
                    pass
        some("x11")
        espera(10)   # receptor fora do USB: tenta de novo daqui a pouco


# ---------- Headset Corsair (iCUE) ----------
def le_corsair():
    try:
        from cuesdk import (CueSdk, CorsairDeviceFilter, CorsairDeviceType,
                            CorsairDevicePropertyId, CorsairError)
    except Exception:
        return
    sdk = CueSdk()
    sdk.connect(lambda e: None)
    time.sleep(4)          # o iCUE leva alguns segundos para aceitar a conexão
    tipos = {CorsairDeviceType.CDT_Headset: "headset", CorsairDeviceType.CDT_Mouse: "mouse"}
    while rodando:
        try:
            devs, _ = sdk.get_devices(CorsairDeviceFilter(device_type_mask=CorsairDeviceType.CDT_All))
            vistos = set()
            for d in devs or []:
                prop, e = sdk.read_device_property(d.device_id, CorsairDevicePropertyId.CDPI_BatteryLevel, 0)
                if e == CorsairError.CE_Success and prop is not None:
                    chave = "cue" + d.device_id
                    atualiza(chave, f"Corsair {d.model.title()}", tipos.get(d.type, "bluetooth"), int(prop.value))
                    vistos.add(chave)
            for chave in [k for k in list(estado) if k.startswith("cue") and k not in vistos]:
                some(chave)
        except Exception:
            pass
        espera(INTERVALO)


# ---------- Bluetooth (o que o Windows já sabe) ----------
PS = ("Get-PnpDevice -PresentOnly -Class Bluetooth | ForEach-Object { "
      "$b=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' "
      "-ErrorAction SilentlyContinue).Data; "
      # o Windows guarda a última bateria mesmo com o aparelho desligado: só vale se estiver conectado
      "$c=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName '{83DA6326-97A6-4088-9453-A1923F573B29} 15' "
      "-ErrorAction SilentlyContinue).Data; if ($b -ne $null -and $c -eq $true) { $_.InstanceId + '|' + $_.FriendlyName + '|' + $b } }")


def tipo_bt(nome):
    n = nome.lower()
    if any(p in n for p in ("controller", "gamepad", "xbox", "dualsense", "controle")):
        return "controle"
    if any(p in n for p in ("headset", "headphone", "fone", "buds", "airpods", "audio")):
        return "headset"
    if "mouse" in n:
        return "mouse"
    if "keyboard" in n or "teclado" in n:
        return "teclado"
    return "bluetooth"


def le_bluetooth():
    while rodando:
        try:
            saida = subprocess.run(["powershell", "-NoProfile", "-Command", PS], capture_output=True,
                                   text=True, timeout=40, creationflags=subprocess.CREATE_NO_WINDOW).stdout
            vistos = set()
            for linha in saida.splitlines():
                partes = linha.strip().split("|")
                if len(partes) == 3 and partes[2].isdigit():
                    chave = "bt" + partes[0]
                    atualiza(chave, partes[1], tipo_bt(partes[1]), int(partes[2]))
                    vistos.add(chave)
            for chave in [k for k in list(estado) if k.startswith("bt") and k not in vistos]:
                some(chave)
        except Exception:
            pass
        espera(INTERVALO_BT)


# ---------- Desenho da faixa ----------
def fonte(nomes, tam):
    for f in nomes:
        try:
            return ImageFont.truetype(f, tam)
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


def desenha_faixa(itens, altura, escala):
    """itens: lista de dict(tipo, nivel, carregando). Devolve imagem RGBA (fundo quase transparente)."""
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
        wt_ = medidor.textlength(txt, font=f_txt)
        wr = medidor.textlength(G_RAIO, font=f_raio) + round(2 * escala) if it["carregando"] else 0
        blocos.append((it, txt, wi, wt_, wr))
        largura += wi + gap_icone + wt_ + wr + (gap_item if i < len(itens) - 1 else 0)
    largura = int(largura + pad)

    img = Image.new("RGBA", (max(largura, 1), altura), (0, 0, 0, 1))   # alpha 1: dá para clicar/arrastar
    d = ImageDraw.Draw(img)
    x, meio = pad, altura / 2
    for it, txt, wi, wt_, wr in blocos:
        c = vermelho if (it["nivel"] <= ALERTA and not it["carregando"]) else cor
        d.text((x, meio), GLIFO.get(it["tipo"], G_BLUETOOTH), font=f_icone, fill=cor, anchor="lm")
        x += wi + gap_icone
        d.text((x, meio + round(0.5 * escala)), txt, font=f_txt, fill=c, anchor="lm")
        x += wt_
        if wr:
            x += round(2 * escala)
            d.text((x, meio), G_RAIO, font=f_raio, fill=cor, anchor="lm")
            x += wr - round(2 * escala)
        x += gap_item
    return img


# ---------- Configuração ----------
def le_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salva_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def comando_inicio():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw}" "{os.path.abspath(__file__)}"'


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


# ---------- Janela por cima da barra (Win32) ----------
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
user32.CreatePopupMenu.restype = wt.HMENU
user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID]
user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE),
                                       wt.HDC, ctypes.POINTER(wt.POINT), wt.DWORD, ctypes.c_void_p, wt.DWORD]
user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
kernel32.GetModuleHandleW.restype = wt.HMODULE

WM_DESTROY, WM_TIMER, WM_NCHITTEST, WM_MOVING, WM_EXITSIZEMOVE = 0x0002, 0x0113, 0x0084, 0x0216, 0x0232
WM_NCRBUTTONUP, WM_RBUTTONUP, WM_DPICHANGED = 0x00A5, 0x0205, 0x02E0
HTCAPTION = 2
WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_NOACTIVATE = 0x80000, 0x80, 0x8, 0x08000000
HWND_TOPMOST = wt.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW, SWP_HIDEWINDOW = 0x1, 0x2, 0x10, 0x40, 0x80
ULW_ALPHA = 2
TPM_RETURNCMD, TPM_RIGHTBUTTON = 0x100, 0x2
MF_STRING, MF_CHECKED, MF_SEPARATOR, MF_GRAYED = 0x0, 0x8, 0x800, 0x1


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


PROCESSOS_SISTEMA = {"explorer.exe", "textinputhost.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe",
                      "searchhost.exe", "searchapp.exe", "lockapp.exe", "shellhost.exe", "tabtip.exe"}


def processo(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)      # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        n = wt.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


class Faixa:
    def __init__(self):
        self.cfg = le_config()
        self.margem = self.cfg.get("margem_direita")   # distância da faixa até a borda direita da barra
        self.ultimo = None
        self.tam = (0, 0)
        self.pos = (0, 0)
        self.visivel = False
        self.proc = WNDPROC(self.wndproc)
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=self.proc, hInstance=hinst,
                         hCursor=user32.LoadCursorW(None, 32512), lpszClassName="BateriaPerifericosFaixa")
        user32.RegisterClassExW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE,
                                           "BateriaPerifericosFaixa", APP, WS_POPUP, 0, 0, 1, 1,
                                           None, None, hinst, None)
        self.cheia_seguidas = 0
        user32.SetTimer(self.hwnd, 1, 1000, None)
        user32.SetTimer(self.hwnd, 2, 200, None)   # clicar na barra a joga por cima: volta para a frente rápido
        self.tick()

    # --- barra de tarefas ---
    def barra(self):
        tb = user32.FindWindowW("Shell_TrayWnd", None)
        if not tb:
            return None
        r = wt.RECT()
        user32.GetWindowRect(tb, ctypes.byref(r))
        bandeja = wt.RECT()
        tn = user32.FindWindowExW(tb, None, "TrayNotifyWnd", None)
        if tn:
            user32.GetWindowRect(tn, ctypes.byref(bandeja))
        return tb, r, (bandeja.left if tn and r.left < bandeja.left < r.right else None)

    def escala(self, tb):
        try:
            return user32.GetDpiForWindow(tb) / 96
        except Exception:
            return 1.0

    def tela_cheia(self):
        fg = user32.GetForegroundWindow()
        if not fg or fg == self.hwnd or not user32.IsWindowVisible(fg):
            return False
        nome = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(fg, nome, 64)
        if nome.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            return False
        # janelas invisíveis do próprio Windows (bandeja ^, teclado de toque, Iniciar...) ocupam a tela
        # inteira mas não são jogo/vídeo: ignora as "camufladas" e as dos processos do sistema
        camuflada = wt.DWORD()
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(fg, 14, ctypes.byref(camuflada), 4) == 0 and camuflada.value:
            return False
        if processo(fg) in PROCESSOS_SISTEMA:
            return False
        r = wt.RECT()
        user32.GetWindowRect(fg, ctypes.byref(r))
        mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
        user32.GetMonitorInfoW(user32.MonitorFromWindow(fg, 2), ctypes.byref(mi))
        m = mi.rcMonitor
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom

    # --- desenho ---
    def tick(self):
        info = self.barra()
        with trava:
            itens = sorted(({"tipo": v["tipo"], "nivel": v["nivel"], "carregando": v["carregando"], "nome": v["nome"]}
                            for v in estado.values()), key=lambda i: (ORDEM.get(i["tipo"], 9), i["nome"]))
        self.cheia_seguidas = self.cheia_seguidas + 1 if self.tela_cheia() else 0
        if not info or not itens or self.cheia_seguidas >= 2:   # 2 s seguidos: não some por um piscar
            self.esconde()
            return
        tb, r, bandeja_esq = info
        esc = self.escala(tb)
        altura = r.bottom - r.top
        chave = (tuple((i["tipo"], i["nivel"], i["carregando"]) for i in itens), altura, esc, tema_claro())
        if chave != self.ultimo:
            self.ultimo = chave
            self.img = desenha_faixa(itens, altura, esc)
        w, h = self.img.size
        if self.margem is None:
            ref = bandeja_esq if bandeja_esq else r.right - round(330 * esc)
            self.margem = r.right - ref + round(8 * esc)    # encosta na setinha ^ com uma folga pequena
        x = max(r.left, r.right - self.margem - w)
        self.aplica(x, r.top, w, h)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        self.visivel = True

    def esconde(self):
        if self.visivel:
            user32.ShowWindow(self.hwnd, 0)
            self.visivel = False

    def aplica(self, x, y, w, h):
        a = self.img.split()[3]
        r, g, b = (ImageChops.multiply(c, a) for c in self.img.split()[:3])
        dados = Image.merge("RGBA", (b, g, r, a)).tobytes()
        tela = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(tela)
        bi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h, biPlanes=1,
                              biBitCount=32, biCompression=0)
        bits = ctypes.c_void_p()
        bmp = gdi32.CreateDIBSection(mem, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, dados, len(dados))
        antigo = gdi32.SelectObject(mem, bmp)
        blend = BLENDFUNCTION(0, 0, 255, 1)
        user32.UpdateLayeredWindow(self.hwnd, tela, ctypes.byref(wt.POINT(x, y)), ctypes.byref(wt.SIZE(w, h)),
                                   mem, ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)
        gdi32.SelectObject(mem, antigo)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, tela)
        self.pos, self.tam = (x, y), (w, h)

    # --- menu ---
    def menu(self):
        m = user32.CreatePopupMenu()
        with trava:
            linhas = [f"{v['nome']}: {v['nivel']}%" + (" (carregando)" if v["carregando"] else "")
                      for v in estado.values()]
        for linha in linhas:
            user32.AppendMenuW(m, MF_STRING | MF_GRAYED, 0, linha)
        user32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(m, MF_STRING | (MF_CHECKED if inicia_com_windows() else 0), 1, "Iniciar com o Windows")
        user32.AppendMenuW(m, MF_STRING, 2, "Voltar para a posição padrão")
        user32.AppendMenuW(m, MF_STRING, 3, "Sair")
        p = wt.POINT()
        user32.GetCursorPos(ctypes.byref(p))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(m, TPM_RETURNCMD | TPM_RIGHTBUTTON, p.x, p.y, 0, self.hwnd, None)
        user32.DestroyMenu(m)
        if cmd == 1:
            alterna_inicio()
        elif cmd == 2:
            self.margem = None
            self.cfg.pop("margem_direita", None)
            salva_config(self.cfg)
            self.tick()
        elif cmd == 3:
            user32.DestroyWindow(self.hwnd)

    def wndproc(self, hwnd, msg, wp, lp):
        if msg == WM_TIMER:
            if wp == 2:
                if self.visivel:
                    user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            else:
                self.tick()
            return 0
        if msg == WM_NCHITTEST:
            return HTCAPTION                      # arrastar com o botão esquerdo
        if msg == WM_MOVING:                      # só anda na horizontal
            rc = ctypes.cast(lp, ctypes.POINTER(wt.RECT)).contents
            altura = rc.bottom - rc.top
            rc.top, rc.bottom = self.pos[1], self.pos[1] + altura
            return 1
        if msg == WM_EXITSIZEMOVE:
            info = self.barra()
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if info:
                self.margem = info[1].right - r.right
                self.cfg["margem_direita"] = self.margem
                salva_config(self.cfg)
            self.tick()
            return 0
        if msg in (WM_NCRBUTTONUP, WM_RBUTTONUP):
            self.menu()
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wp, lp)


def principal():
    global rodando
    kernel32.CreateMutexW(None, False, "BateriaPerifericos_unica")
    if kernel32.GetLastError() == 183:          # já está aberto
        return
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # nítido em qualquer escala
    except Exception:
        pass
    # se "Iniciar com o Windows" está ligado mas aponta para outro lugar (ex.: o antigo .exe), corrige
    if inicia_com_windows():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, comando_inicio())
        except OSError:
            pass
    for alvo in (le_x11, le_corsair, le_bluetooth):
        threading.Thread(target=alvo, daemon=True).start()
    Faixa()
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    rodando = False


if __name__ == "__main__":
    principal()
