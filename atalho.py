"""Cria atalhos do Windows pela API nativa (COM via ctypes, sem PowerShell).

O atalho do Menu Iniciar leva o "AppUserModelID" do programa: é assim que o Windows mostra
o nome "Bateria dos Periféricos" e o ícone certo nas notificações.
"""
import ctypes
import os
import uuid
from ctypes import wintypes as wt

AUMID = "BateriaPerifericos.App"
MENU_INICIAR = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def de(cls, texto):
        u = uuid.UUID(texto)
        g = cls(u.time_low, u.time_mid, u.time_hi_version)
        g.Data4[:] = list(u.bytes[8:])
        return g


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wt.DWORD)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("pwszVal", ctypes.c_wchar_p), ("extra", ctypes.c_void_p)]


CLSID_ShellLink = GUID.de("00021401-0000-0000-C000-000000000046")
IID_IShellLinkW = GUID.de("000214F9-0000-0000-C000-000000000046")
IID_IPropertyStore = GUID.de("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
IID_IPersistFile = GUID.de("0000010b-0000-0000-C000-000000000046")
PKEY_AUMID = PROPERTYKEY(GUID.de("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5)

ole32 = ctypes.windll.ole32
ole32.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, wt.DWORD, ctypes.POINTER(GUID),
                                   ctypes.POINTER(ctypes.c_void_p)]


def _metodo(obj, indice, *tipos):
    vtable = ctypes.cast(ctypes.cast(obj, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    return ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *tipos)(vtable[indice])


def _chama(obj, indice, tipos, *args):
    return _metodo(obj, indice, *tipos)(obj, *args)


def _interface(obj, iid):
    saida = ctypes.c_void_p()
    _chama(obj, 0, (ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)), ctypes.byref(iid), ctypes.byref(saida))
    return saida


def _solta(obj):
    if obj:
        _metodo(obj, 2)(obj)


def cria(destino, alvo, argumentos="", pasta="", icone="", descricao="", aumid=None):
    ole32.CoInitialize(None)
    link = ctypes.c_void_p()
    ole32.CoCreateInstance(ctypes.byref(CLSID_ShellLink), None, 1, ctypes.byref(IID_IShellLinkW), ctypes.byref(link))
    loja = arquivo = None
    try:
        _chama(link, 20, (wt.LPCWSTR,), alvo)                     # SetPath
        _chama(link, 11, (wt.LPCWSTR,), argumentos)               # SetArguments
        _chama(link, 9, (wt.LPCWSTR,), pasta)                     # SetWorkingDirectory
        _chama(link, 7, (wt.LPCWSTR,), descricao)                 # SetDescription
        if icone:
            _chama(link, 17, (wt.LPCWSTR, ctypes.c_int), icone, 0)  # SetIconLocation
        if aumid:
            loja = _interface(link, IID_IPropertyStore)
            valor = PROPVARIANT(vt=31, pwszVal=aumid)               # VT_LPWSTR
            _chama(loja, 6, (ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT)),
                   ctypes.byref(PKEY_AUMID), ctypes.byref(valor))   # SetValue
            _chama(loja, 7, ())                                      # Commit
        arquivo = _interface(link, IID_IPersistFile)
        _chama(arquivo, 6, (wt.LPCWSTR, wt.BOOL), destino, True)    # Save
    finally:
        _solta(arquivo)
        _solta(loja)
        _solta(link)
