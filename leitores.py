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
                        abertos.append(_abre(d["path"]))
                    except Exception:
                        pass
            ultimo = 0
            while abertos and not nucleo.parar.is_set():
                espera_ms = max(50, 500 // len(abertos))       # o quadro chega a cada ~2 s: espera em vez de girar
                for h in list(abertos):
                    try:
                        r = h.read(64, espera_ms)
                    except Exception:
                        abertos.remove(h)
                        _fecha(h)                              # receptor desligado: solta o handle
                        continue
                    if r and len(r) >= 5 and r[0] == 0x03 and r[2] == 0x40 and r[4] <= 100 and r[3] in (1, 3):
                        atualiza("x11", "Mouse Attack Shark X11", "mouse", r[4], r[3] == 3, "receptor 2,4 GHz")
                        ultimo = time.time()
                if ultimo and time.time() - ultimo > X11_DORMINDO:
                    nucleo.dorme("x11")          # fica apagado na barra com a última %
                    ultimo = 0
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
    cargas = {}                   # o iCUE não diz se está carregando: deduz pela subida da %
    while True:
        vistos = set()
        try:
            devs, _ = sdk.get_devices(CorsairDeviceFilter(device_type_mask=CorsairDeviceType.CDT_All))
            for d in devs or []:
                prop, e = sdk.read_device_property(d.device_id, CorsairDevicePropertyId.CDPI_BatteryLevel, 0)
                if e == CorsairError.CE_Success and prop is not None:
                    chave = "cue" + d.device_id
                    nivel = int(prop.value)
                    carregando = cargas.setdefault(chave, nucleo.DetectaCarga()).le(nivel)
                    atualiza(chave, f"Corsair {d.model.title()}", tipos.get(d.type, "bluetooth"),
                             nivel, carregando, "iCUE")
                    vistos.add(chave)
        except Exception:
            nucleo.erro("Corsair")
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
            nucleo.erro("Bluetooth")
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
    if longo is not None:                       # mensagem longa: 11 <aparelho> <índice> <função> + 16 bytes
        pacote = bytes([0x11, aparelho, indice, pedido]) + bytes(params).ljust(16, b"\0")
        escritor = longo
    else:                                       # aparelho só com canal curto: 10 <aparelho> <índice> <função> + 3 bytes
        pacote = bytes([0x10, aparelho, indice, pedido]) + bytes(params)[:3].ljust(3, b"\0")
        escritor = curto
    escritor.write(pacote)
    fim = time.time() + espera_s
    while time.time() < fim:
        for h in (longo, curto):
            if h is None:
                continue
            r = h.read(20, 20)
            if not r or len(r) < 5 or r[1] != aparelho:
                continue
            if r[2] == 0xFF and r[3] == indice and r[4] == pedido:        # erro HID++ 2.0
                return None
            if r[2] == 0x8F and r[3] == indice:                            # erro HID++ 1.0 (não conectado)
                return None
            if r[2] == indice and r[3] == pedido:
                return bytes(r[4:])
    return None


def _ping(longo, curto, aparelho):
    """O aparelho está ligado e fala HID++ 2.0? (mesma pergunta do Solaar: raiz, função 1, resposta em ~100 ms)."""
    return _hidpp(longo, curto, aparelho, 0x00, 1, b"\x00\x00\x5a", 0.15) is not None


def _carga(status, unificada=False):
    """(carregando, cheio) pelo código de status do HID++ (tabelas do Solaar).
    0x1000: 0 descarregando, 1 carregando, 2 quase cheio, 3 completa, 4 carga lenta, 5+ erro.
    0x1004: 0 descarregando, 1 carregando, 2 carga lenta, 3 completa, 4+ erro."""
    if unificada:
        return status in (1, 2), status == 3
    return status in (1, 2, 4), status == 3


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
            carregando, cheio = _carga(r[2], unificada=True)
            return (100 if cheio else nivel), carregando or cheio
    if recursos.get(0x1000):                       # Battery Level Status
        r = _hidpp(longo, curto, aparelho, recursos[0x1000], 0)
        if r:
            carregando, cheio = _carga(r[2])
            return (100 if cheio else r[0]), carregando or cheio
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
                if d["usage_page"] == 0xFF00 and d["usage"] in (1, 2):   # canais HID++ do fabricante (nunca teclas)
                    chave_usb = (d["product_id"], d["serial_number"], d["interface_number"])
                    grupos.setdefault(chave_usb, {})[d["usage"]] = d["path"]
            for (pid, _, _), caminhos in grupos.items():
                longo = curto = None
                try:
                    if 2 in caminhos:
                        longo = _abre(caminhos[2])
                    if 1 in caminhos:
                        try:
                            curto = _abre(caminhos[1])
                        except Exception:
                            curto = None
                    if longo is None and curto is None:
                        continue
                    base = caminhos.get(2) or caminhos.get(1)
                    for aparelho in (0xFF, 1, 2, 3, 4, 5, 6):
                        ck = (base, aparelho)
                        info = cache.get(ck)
                        if info is None and ck in cache and time.time() - cache.get(("t",) + ck, 0) < 300:
                            continue              # não respondeu há pouco: tenta de novo em 5 min
                        if info is None:
                            if not _ping(longo, curto, aparelho):      # desligado ou vazio: não gasta tempo
                                cache[ck] = None
                                cache[("t",) + ck] = time.time()
                                continue
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
                    nucleo.erro(f"Logitech {pid:04x}")
                finally:
                    _fecha(longo, curto)
        except Exception:
            nucleo.erro("Logitech")
        some_todos("logi", vistos)
        if espera(60):
            return


# =====================================================================================
# Razer: relatório de recurso de 90 bytes (classe 0x07: 0x80 = bateria 0-255, 0x84 = carregando),
# o mesmo do OpenRazer. A tabela PID -> (transação, interface, espera) vem do catálogo do
# razer-battery-report (xzeldon, licença MIT, a partir do OpenRazer). Só pergunta para modelos
# da tabela: nada de adivinhar IDs. Mouses sem fio. NÃO TESTADO em aparelho real.
# =====================================================================================
RAZER = {}


def _grupo(tid, interface, espera_ms, *pids):
    for p in pids:
        RAZER[p] = (tid, interface, espera_ms)


_grupo(0xFF, 0, 0.6, 0x001F, 0x0024, 0x0025, 0x0032, 0x003E, 0x003F, 0x0044, 0x0045)
_grupo(0x3F, 0, 0.6, 0x0059, 0x005A)
_grupo(0x1F, 0, 0.6, 0x008F)
_grupo(0x1F, 0, 400, 0x0062, 0x0094, 0x0095)                        # Atheris, Orochi V2: respondem devagar
_grupo(0x3F, 0, 31, 0x0072, 0x0073)
_grupo(0xFF, 0, 31, 0x0083)
_grupo(0xFF, 0, 59.9, 0x007A, 0x007B)
_grupo(0x3F, 0, 59.9, 0x007C, 0x007D)
_grupo(0x1F, 0, 59.9, 0x009E, 0x009F, 0x00B3, 0x00B8, 0x00C1, 0x00DF)
_grupo(0x1F, 3, 59.9, 0x00E2, 0x00E3, 0x00E5, 0x00E6)                # Basilisk V4 Pro, Viper V4 Pro: interface 3
_grupo(0x1F, 0, 31, 0x006F, 0x0070, 0x0077, 0x0080, 0x0086, 0x0088, 0x0090, 0x009A, 0x009C, 0x00A5, 0x00A6,
       0x00A7, 0x00A8, 0x00AA, 0x00AB, 0x00AF, 0x00B0, 0x00B4, 0x00B6, 0x00B7, 0x00B9, 0x00BE, 0x00BF, 0x00C0,
       0x00C2, 0x00C3, 0x00C4, 0x00C5, 0x00C7, 0x00C8, 0x00CC, 0x00CD, 0x00D0, 0x00D1, 0x00D3, 0x00D4, 0x00D6,
       0x00D7, 0x00DA, 0x00DB, 0x00DE)

RAZER_TENTATIVAS, RAZER_PAUSA = 5, 0.01          # como o OpenRazer: até 5 tentativas, 10 ms entre elas


def _crc_razer(pacote):
    crc = 0
    for b in pacote[2:88]:
        crc ^= b
    return crc


def _razer(h, tid, espera_ms, classe, comando):
    """Uma pergunta ao aparelho. Devolve o relatório de resposta (status 0x02) ou None.

    Repete se estiver ocupado (0x01) ou sem resposta (0x04); para na hora se não suporta (0x05)
    ou falhou (0x03). Confere o CRC e se a resposta é mesmo desta pergunta.
    """
    pacote = bytearray(90)
    pacote[1], pacote[5], pacote[6], pacote[7] = tid, 0x02, classe, comando
    pacote[88] = _crc_razer(pacote)
    for tentativa in range(RAZER_TENTATIVAS):
        if tentativa:
            time.sleep(RAZER_PAUSA)
        h.send_feature_report(bytes([0x00]) + bytes(pacote))
        time.sleep(espera_ms / 1000)
        r = bytes(h.get_feature_report(0x00, 91))
        if len(r) != 91:
            continue
        r = r[1:]
        if r[88] != _crc_razer(r) or r[2:4] != pacote[2:4] or r[6] != classe or r[7] != comando:
            continue                                  # resposta de outra coisa: tenta de novo
        if r[0] == 0x02:
            return r
        if r[0] in (0x03, 0x05):                      # falhou / não suportado: repetir não adianta
            return None
    return None


def le_razer():
    while True:
        vistos = set()
        try:
            feitos = set()
            for d in hid.enumerate(0x1532, 0):
                pid = d["product_id"]
                if pid in feitos or pid not in RAZER:
                    continue
                tid, interface, espera_ms = RAZER[pid]
                if d["interface_number"] not in ((interface,) if interface else (0, -1)):
                    continue
                # só a coleção do mouse (página 1, uso 2) ou do fabricante: nunca a de teclado nem a de mídia
                if not ((d["usage_page"] == 0x01 and d["usage"] == 0x02) or d["usage_page"] >= 0xFF00):
                    continue
                h = None
                try:
                    h = _abre(d["path"])
                    r = _razer(h, tid, espera_ms, 0x07, 0x80)
                    if r is None:                     # dormindo/desligado ou esta coleção não responde
                        continue
                    feitos.add(pid)
                    nivel = round(r[9] * 100 / 255)
                    c = _razer(h, tid, espera_ms, 0x07, 0x84)
                    carregando = bool(c and c[9])
                    nome = (d.get("product_string") or "Razer").strip()
                    chave = f"rz{pid:04x}"
                    atualiza(chave, nome if nome.lower().startswith("razer") else "Razer " + nome,
                             tipo_pelo_nome(nome) if tipo_pelo_nome(nome) != "bluetooth" else "mouse",
                             nivel, carregando, "Razer")
                    vistos.add(chave)
                except Exception:
                    nucleo.erro(f"Razer {pid:04x}")
                finally:
                    _fecha(h)
        except Exception:
            nucleo.erro("Razer")
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
        if not isinstance(nivel, int):
            continue
        if nivel < 0:
            if status != "BATTERY_CHARGING":
                continue
            nivel = None                     # carregando e o headset não diz quanto: o chamador reaproveita o último
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
            r = subprocess.run([exe, "-b", "-o", "json"], capture_output=True, encoding="utf-8", errors="replace",
                               timeout=20, creationflags=SEM_JANELA)
            for chave, nome, nivel, carregando, vendor in interpreta_headsetcontrol(r.stdout or ""):
                # Corsair já vem pelo iCUE quando ele está aberto: não mostra duas vezes
                if vendor in ("0x1b1c", "1b1c") and any(k.startswith("cue") for k in nucleo.instantaneo()):
                    continue
                if nivel is None:
                    anterior = nucleo.instantaneo().get(chave)
                    if not anterior:
                        continue
                    nivel = anterior["nivel"]
                atualiza(chave, nome, "headset", nivel, carregando, "HeadsetControl")
                vistos.add(chave)
        except Exception:
            nucleo.erro("HeadsetControl")
        some_todos("hc", vistos)
        if espera(60):
            return


def _resiliente(leitor):
    """Se um leitor der erro, anota no erros.log e tenta de novo (30 s, depois 1, 2, 4, 8 e 10 min)."""
    def roda():
        pausa = 30
        while not nucleo.parar.is_set():
            try:
                leitor()
                return                       # terminou de propósito (sem SDK, sem headsetcontrol, programa fechando)
            except Exception:
                nucleo.erro(f"leitor {leitor.__name__} (vai tentar de novo em {pausa} s)")
                if espera(pausa):
                    return
                pausa = min(600, pausa * 2)
    roda.__name__ = leitor.__name__
    return roda


LEITORES = [_resiliente(f) for f in (le_attack_shark, le_corsair, le_bluetooth, le_logitech, le_razer,
                                     le_headsetcontrol)]
