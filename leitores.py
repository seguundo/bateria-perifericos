"""Leitores de bateria, um por marca/tecnologia. Cada um roda numa thread própria.

Para acrescentar uma marca: escreva uma função que, em loop até nucleo.espera() devolver True,
chame nucleo.atualiza(chave, nome, tipo, nivel, carregando, origem) quando ler e nucleo.some(chave)
quando o aparelho desligar; depois coloque a função na lista LEITORES no fim do arquivo.

Regra de ouro: só mande para um aparelho comandos conhecidos de projetos abertos. Comando
errado pode mudar DPI, macros ou até firmware.
"""
import ctypes
import json
import os
import subprocess
import time
import uuid
from ctypes import wintypes as wt

import hid

import nucleo
from nucleo import atualiza, espera, some, some_todos

SEM_JANELA = subprocess.CREATE_NO_WINDOW


def _abre(caminho):
    h = hid.device()
    h.open_path(caminho)
    return h


def _fecha(*handles):
    for h in handles:
        try:
            h.close()
        except Exception:
            pass


# =====================================================================================
# Attack Shark X11 (receptor 1D57:FA60, interface 2)
# Sem enviar nada, o receptor manda a cada ~2 s o quadro 03 ?? 40 ST NN
# (ST 01 = na bateria, 03 = carregando; NN = %). Protocolo: Attack-Shark-Battery-KDE (MIT).
# =====================================================================================
X11_DORMINDO = 30


def le_attack_shark():
    while not nucleo.parar.is_set():
        abertos = []
        try:
            for d in hid.enumerate(0x1D57, 0xFA60):
                # só o canal do fabricante (usage page 0x0A), nunca o de teclado/mídia/mouse:
                # o programa não precisa (nem deve) ver teclas
                if d["interface_number"] == 2 and (d["usage_page"] == 0x0A or d["usage_page"] >= 0xFF00):
                    try:
                        h = _abre(d["path"])
                        h.set_nonblocking(1)
                        abertos.append(h)
                    except Exception:
                        pass
            ultimo = 0
            while abertos and not nucleo.parar.is_set():
                for h in list(abertos):
                    try:
                        r = h.read(64)
                    except Exception:
                        abertos.remove(h)
                        continue
                    if r and len(r) >= 5 and r[0] == 0x03 and r[2] == 0x40 and r[4] <= 100 and r[3] in (1, 3):
                        atualiza("x11", "Mouse Attack Shark X11", "mouse", r[4], r[3] == 3, "receptor 2,4 GHz")
                        ultimo = time.time()
                if ultimo and time.time() - ultimo > X11_DORMINDO:
                    some("x11")
                    ultimo = 0
                time.sleep(0.05)
        finally:
            _fecha(*abertos)
        some("x11")
        if espera(10):           # receptor fora do USB: tenta de novo daqui a pouco
            return


# =====================================================================================
# Corsair: iCUE SDK oficial (o iCUE precisa estar aberto; aparelho desligado não informa)
# =====================================================================================
def le_corsair():
    try:
        from cuesdk import (CueSdk, CorsairDeviceFilter, CorsairDeviceType,
                            CorsairDevicePropertyId, CorsairError)
    except Exception:
        return
    sdk = CueSdk()
    sdk.connect(lambda e: None)
    if espera(4):                 # o iCUE leva alguns segundos para aceitar a conexão
        return
    tipos = {CorsairDeviceType.CDT_Headset: "headset", CorsairDeviceType.CDT_Mouse: "mouse",
             CorsairDeviceType.CDT_Keyboard: "teclado"}
    while True:
        vistos = set()
        try:
            devs, _ = sdk.get_devices(CorsairDeviceFilter(device_type_mask=CorsairDeviceType.CDT_All))
            for d in devs or []:
                prop, e = sdk.read_device_property(d.device_id, CorsairDevicePropertyId.CDPI_BatteryLevel, 0)
                if e == CorsairError.CE_Success and prop is not None:
                    chave = "cue" + d.device_id
                    atualiza(chave, f"Corsair {d.model.title()}", tipos.get(d.type, "bluetooth"),
                             int(prop.value), False, "iCUE")
                    vistos.add(chave)
        except Exception:
            pass
        some_todos("cue", vistos)
        if espera(60):
            return


# =====================================================================================
# Bluetooth: o que o próprio Windows sabe, lido pela SetupAPI (sem PowerShell).
# Bateria = {104EA319-...} 2. Só vale com o aparelho conectado ({83DA6326-...} 15),
# porque o Windows guarda a última bateria mesmo com ele desligado.
# =====================================================================================
class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def de(cls, texto):
        u = uuid.UUID(texto)
        g = cls(u.time_low, u.time_mid, u.time_hi_version)
        g.Data4[:] = list(u.bytes[8:])
        return g


class _DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_ulong)]


class _SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("ClassGuid", _GUID), ("DevInst", wt.DWORD), ("Reserved", ctypes.c_void_p)]


_setupapi = ctypes.windll.setupapi
_setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
_setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(_GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]
_setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.POINTER(_SP_DEVINFO_DATA)]
_setupapi.SetupDiGetDevicePropertyW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_SP_DEVINFO_DATA),
                                                 ctypes.POINTER(_DEVPROPKEY), ctypes.POINTER(ctypes.c_ulong),
                                                 ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
_setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_SP_DEVINFO_DATA),
                                                   wt.LPWSTR, wt.DWORD, ctypes.POINTER(wt.DWORD)]
_setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

CLASSE_BLUETOOTH = _GUID.de("e0cbf06c-cd8b-4647-bb8a-263b43f0f974")
P_BATERIA = _DEVPROPKEY(_GUID.de("104EA319-6EE2-4701-BD47-8DDBF425BBE5"), 2)
P_CONECTADO = _DEVPROPKEY(_GUID.de("83DA6326-97A6-4088-9453-A1923F573B29"), 15)
P_NOME = _DEVPROPKEY(_GUID.de("a45c254e-df1c-4efd-8020-67d146a850e0"), 14)


def _propriedade(lista, info, chave):
    tipo, tam = ctypes.c_ulong(), wt.DWORD()
    buf = ctypes.create_string_buffer(512)
    if not _setupapi.SetupDiGetDevicePropertyW(lista, ctypes.byref(info), ctypes.byref(chave), ctypes.byref(tipo),
                                               buf, 512, ctypes.byref(tam), 0):
        return None
    if tipo.value == 0x12:                                   # texto
        return ctypes.wstring_at(buf)
    if tipo.value in (0x03, 0x11):                           # byte / verdadeiro-falso (0xFF = sim)
        return buf.raw[0]
    return None


def bluetooth_com_bateria():
    """[(id, nome, %)] dos aparelhos Bluetooth conectados que informam bateria ao Windows."""
    lista = _setupapi.SetupDiGetClassDevsW(ctypes.byref(CLASSE_BLUETOOTH), None, None, 0x2)  # só presentes
    if not lista or lista == ctypes.c_void_p(-1).value:
        return []
    saida = []
    try:
        i = 0
        while True:
            info = _SP_DEVINFO_DATA(cbSize=ctypes.sizeof(_SP_DEVINFO_DATA))
            if not _setupapi.SetupDiEnumDeviceInfo(lista, i, ctypes.byref(info)):
                break
            i += 1
            nivel = _propriedade(lista, info, P_BATERIA)
            if nivel is None or nivel > 100 or not _propriedade(lista, info, P_CONECTADO):
                continue
            ident = ctypes.create_unicode_buffer(400)
            _setupapi.SetupDiGetDeviceInstanceIdW(lista, ctypes.byref(info), ident, 400, None)
            saida.append((ident.value, _propriedade(lista, info, P_NOME) or "Bluetooth", nivel))
    finally:
        _setupapi.SetupDiDestroyDeviceInfoList(lista)
    return saida


def tipo_pelo_nome(nome):
    n = nome.lower()
    if any(p in n for p in ("controller", "gamepad", "xbox", "dualsense", "dualshock", "controle", "joy-con")):
        return "controle"
    if any(p in n for p in ("headset", "headphone", "fone", "buds", "airpods", "audio", "earbuds")):
        return "headset"
    if "mouse" in n:
        return "mouse"
    if "keyboard" in n or "teclado" in n:
        return "teclado"
    return "bluetooth"


def le_bluetooth():
    while True:
        vistos = set()
        try:
            for ident, nome, nivel in bluetooth_com_bateria():
                chave = "bt" + ident
                atualiza(chave, nome, tipo_pelo_nome(nome), nivel, False, "Bluetooth")
                vistos.add(chave)
        except Exception:
            pass
        some_todos("bt", vistos)
        if espera(10):           # leitura nativa é leve: confere a cada 10 s
            return


# =====================================================================================
# Logitech: HID++ 2.0 direto no receptor (Lightspeed, Unifying, Bolt) ou no cabo, sem G HUB.
# Só consultas de leitura, as mesmas que o Solaar e o logitray usam.
# Mensagem longa: 11 <aparelho> <índice da função> <função<<4 | swid> <16 bytes>
# =====================================================================================
SWID = 0x0A
TIPOS_LOGI = {0: "teclado", 3: "mouse", 4: "mouse", 5: "mouse", 8: "headset", 11: "controle", 12: "controle"}
TENSAO = [(4186, 100), (4067, 90), (3989, 80), (3922, 70), (3859, 60), (3811, 50), (3778, 40),
          (3751, 30), (3717, 20), (3671, 10), (3646, 5), (3579, 2), (3500, 0)]


def _hidpp(longo, curto, aparelho, indice, funcao, params=b"", espera_s=0.4):
    pedido = (funcao << 4) | SWID
    longo.write(bytes([0x11, aparelho, indice, pedido]) + bytes(params).ljust(16, b"\0"))
    fim = time.time() + espera_s
    while time.time() < fim:
        for h in (longo, curto):
            if h is None:
                continue
            r = h.read(20, 20)
            if not r or len(r) < 4 or r[1] != aparelho:
                continue
            if r[2] == 0xFF and r[3] == indice and r[4] == pedido:        # erro HID++ 2.0
                return None
            if r[2] == 0x8F and r[3] == indice:                            # erro HID++ 1.0 (não conectado)
                return None
            if r[2] == indice and r[3] == pedido:
                return bytes(r[4:])
    return None


def _indice(longo, curto, aparelho, recurso):
    r = _hidpp(longo, curto, aparelho, 0x00, 0, bytes([recurso >> 8, recurso & 0xFF]))
    return r[0] if r and r[0] else None


def _nome_logi(longo, curto, aparelho, idx):
    r = _hidpp(longo, curto, aparelho, idx, 0)
    if not r:
        return None
    tamanho, nome = r[0], b""
    while len(nome) < tamanho:
        parte = _hidpp(longo, curto, aparelho, idx, 1, bytes([len(nome)]))
        if not parte:
            break
        nome += parte[: tamanho - len(nome)]
    return nome.decode("utf-8", "ignore").strip("\0 ") or None


def _bateria_logi(longo, curto, aparelho, recursos):
    if recursos.get(0x1004):                       # Unified Battery
        r = _hidpp(longo, curto, aparelho, recursos[0x1004], 1)
        if r:
            nivel = r[0] or {8: 100, 4: 60, 2: 20, 1: 5}.get(r[1] & 0x0F, 0)
            return nivel, r[2] in (1, 2)
    if recursos.get(0x1000):                       # Battery Level Status
        r = _hidpp(longo, curto, aparelho, recursos[0x1000], 0)
        if r:
            return r[0], r[2] in (1, 2)
    if recursos.get(0x1001):                       # Battery Voltage
        r = _hidpp(longo, curto, aparelho, recursos[0x1001], 0)
        if r:
            mv = (r[0] << 8) | r[1]
            nivel = 0
            for (v1, p1), (v2, p2) in zip(TENSAO, TENSAO[1:]):
                if mv >= v2:
                    nivel = p2 + (p1 - p2) * min(1, (mv - v2) / (v1 - v2))
                    break
            return round(nivel), bool(r[2] & 0x80)
    return None


def le_logitech():
    cache = {}      # (caminho, aparelho) -> dict(nome, tipo, recursos) ; None = não responde
    while True:
        vistos = set()
        try:
            grupos = {}
            for d in hid.enumerate(0x046D, 0):
                if d["usage_page"] == 0xFF00 and d["usage"] in (1, 2):
                    chave_usb = (d["product_id"], d["serial_number"], d["interface_number"])
                    grupos.setdefault(chave_usb, {})[d["usage"]] = d["path"]
            for (pid, _, _), caminhos in grupos.items():
                if 2 not in caminhos:
                    continue
                longo = curto = None
                try:
                    longo = _abre(caminhos[2])
                    if 1 in caminhos:
                        try:
                            curto = _abre(caminhos[1])
                        except Exception:
                            curto = None
                    for aparelho in (0xFF, 1, 2, 3, 4, 5, 6):
                        ck = (caminhos[2], aparelho)
                        info = cache.get(ck)
                        if info is None and ck in cache and time.time() - cache.get(("t",) + ck, 0) < 300:
                            continue              # não respondeu há pouco: tenta de novo em 5 min
                        if info is None:
                            recursos = {f: _indice(longo, curto, aparelho, f) for f in (0x1004, 0x1000, 0x1001)}
                            if not any(recursos.values()):
                                cache[ck] = None
                                cache[("t",) + ck] = time.time()
                                continue
                            idx_nome = _indice(longo, curto, aparelho, 0x0005)
                            nome = _nome_logi(longo, curto, aparelho, idx_nome) if idx_nome else None
                            tipo_r = _hidpp(longo, curto, aparelho, idx_nome, 2) if idx_nome else None
                            tipo = TIPOS_LOGI.get(tipo_r[0], "mouse") if tipo_r else "mouse"
                            info = dict(nome="Logitech " + (nome or "sem fio"), tipo=tipo, recursos=recursos)
                            cache[ck] = info
                        leitura = _bateria_logi(longo, curto, aparelho, info["recursos"])
                        if leitura is None:
                            cache[ck] = None                 # desligou: redescobre quando voltar
                            cache[("t",) + ck] = 0
                            continue
                        chave = f"logi{pid:04x}-{aparelho}"
                        atualiza(chave, info["nome"], info["tipo"], leitura[0], leitura[1], "receptor Logitech")
                        vistos.add(chave)
                except Exception:
                    pass
                finally:
                    _fecha(longo, curto)
        except Exception:
            pass
        some_todos("logi", vistos)
        if espera(60):
            return


# =====================================================================================
# Razer: relatório de 90 bytes (classe 0x07: 0x80 = bateria 0-255, 0x84 = carregando),
# o mesmo do OpenRazer e do razer-battery-report. Mouses e teclados sem fio.
# =====================================================================================
TRANSACOES_RAZER = (0x1F, 0x3F, 0xFF, 0x9F)


def _razer(h, transacao, classe, comando):
    pacote = bytearray(90)
    pacote[1], pacote[5], pacote[6], pacote[7] = transacao, 0x02, classe, comando
    crc = 0
    for b in pacote[2:88]:
        crc ^= b
    pacote[88] = crc
    h.send_feature_report(bytes([0x00]) + bytes(pacote))
    time.sleep(0.06)
    r = bytes(h.get_feature_report(0x00, 91))
    if len(r) == 91:
        r = r[1:]
    if len(r) >= 90 and r[6] == classe and r[7] == comando:
        return r
    return None


def le_razer():
    transacao_por_pid = {}
    while True:
        vistos = set()
        try:
            feitos = set()
            for d in hid.enumerate(0x1532, 0):
                pid = d["product_id"]
                if pid in feitos or d["interface_number"] not in (0, -1):
                    continue
                h = None
                try:
                    h = _abre(d["path"])
                    for t in ([transacao_por_pid[pid]] if pid in transacao_por_pid else TRANSACOES_RAZER):
                        r = _razer(h, t, 0x07, 0x80)
                        if r is None:
                            continue
                        feitos.add(pid)
                        if r[0] != 0x02:          # 0x04 = aparelho dormindo/desligado
                            break
                        transacao_por_pid[pid] = t
                        nivel = round(r[9] * 100 / 255)
                        c = _razer(h, t, 0x07, 0x84)
                        carregando = bool(c and c[0] == 0x02 and c[9])
                        nome = (d.get("product_string") or "Razer").strip()
                        chave = f"rz{pid:04x}"
                        atualiza(chave, nome if nome.lower().startswith("razer") else "Razer " + nome,
                                 tipo_pelo_nome(nome) if tipo_pelo_nome(nome) != "bluetooth" else "mouse",
                                 nivel, carregando, "Razer")
                        vistos.add(chave)
                        break
                except Exception:
                    pass
                finally:
                    _fecha(h)
        except Exception:
            pass
        some_todos("rz", vistos)
        if espera(60):
            return


# =====================================================================================
# HeadsetControl (github.com/Sapd/HeadsetControl): headsets SteelSeries, HyperX, Logitech,
# Corsair, Roccat... Precisa do headsetcontrol.exe nesta pasta (ou na pasta "headsetcontrol"),
# baixado do GitHub oficial. Sem ele, este leitor fica parado.
# =====================================================================================
def _acha_headsetcontrol():
    # só procura na pasta do programa (nunca no PATH): roda apenas o .exe que você mesmo colocou aqui
    base = os.path.dirname(os.path.abspath(__file__))
    for c in (os.path.join(base, "headsetcontrol.exe"), os.path.join(base, "headsetcontrol", "headsetcontrol.exe")):
        if os.path.isfile(c):
            return c
    return None


def interpreta_headsetcontrol(texto):
    """Lê a saída JSON do 'headsetcontrol -b -o json'. Devolve lista de (chave, nome, nivel, carregando, vendor)."""
    dados = json.loads(texto)
    saida = []
    for d in dados.get("devices", []):
        bat = d.get("battery") or {}
        status = bat.get("status", "")
        if status not in ("BATTERY_AVAILABLE", "BATTERY_CHARGING"):
            continue
        nivel = bat.get("level", -1)
        if not isinstance(nivel, int) or nivel < 0:
            continue
        nome = (d.get("device") or d.get("product") or "Headset").strip()
        chave = f"hc{d.get('id_vendor', '')}{d.get('id_product', '')}"
        saida.append((chave, nome, nivel, status == "BATTERY_CHARGING", str(d.get("id_vendor", "")).lower()))
    return saida


def le_headsetcontrol():
    exe = _acha_headsetcontrol()
    if not exe:
        return
    while True:
        vistos = set()
        try:
            r = subprocess.run([exe, "-b", "-o", "json"], capture_output=True, text=True, timeout=20,
                               creationflags=SEM_JANELA)
            for chave, nome, nivel, carregando, vendor in interpreta_headsetcontrol(r.stdout):
                # Corsair já vem pelo iCUE quando ele está aberto: não mostra duas vezes
                if vendor in ("0x1b1c", "1b1c") and any(k.startswith("cue") for k in nucleo.instantaneo()):
                    continue
                atualiza(chave, nome, "headset", nivel, carregando, "HeadsetControl")
                vistos.add(chave)
        except Exception:
            pass
        some_todos("hc", vistos)
        if espera(60):
            return


LEITORES = [le_attack_shark, le_corsair, le_bluetooth, le_logitech, le_razer, le_headsetcontrol]
