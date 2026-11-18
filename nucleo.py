"""Estado compartilhado: periféricos lidos, configuração, histórico e previsão de duração."""
import json
import os
import threading
import time

APP = "Bateria dos Periféricos"
VERSAO = "1.2.0"
REPO = "seguundo/bateria-perifericos"          # onde procurar versão nova (troque se fizer um fork)
PASTA_DADOS = os.path.join(os.environ.get("APPDATA", "."), "BateriaPerifericos")
CONFIG = os.path.join(PASTA_DADOS, "config.json")
HISTORICO = os.path.join(PASTA_DADOS, "historico.json")

PADRAO = {
    "monitores": "todos",        # "todos" ou "principal"
    "tamanho": 1.0,              # 0.85 pequeno, 1.0 normal, 1.2 grande
    "mostrar_ate": 100,          # só mostra periféricos com bateria <= isto (100 = sempre)
    "alerta": 15,                # % de bateria fraca (número vermelho + aviso)
    "aviso_fraca": True,
    "aviso_cheio": True,         # avisa quando terminar de carregar
    "procurar_versao": True,
    "ocultos": [],               # chaves dos periféricos escondidos
    "ordem": [],                 # chaves na ordem escolhida
    "margens": {},               # barra -> distância até a borda direita
    "conhecidos": {},            # chave -> {nome, tipo}: todos os periféricos já vistos
}

trava = threading.RLock()
estado = {}            # chave -> dict(nome, tipo, nivel, carregando, visto, origem)
parar = threading.Event()
_cfg = None
_cfg_sujo = False
_hist = None
_hist_sujo = False


# ---------- configuração ----------
def _le_json(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


def _grava_json(caminho, dados):
    try:
        os.makedirs(PASTA_DADOS, exist_ok=True)
        tmp = caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
        os.replace(tmp, caminho)
    except Exception:
        pass


def config():
    """Cópia da configuração atual (com os valores padrão preenchidos)."""
    global _cfg
    with trava:
        if _cfg is None:
            _cfg = _le_json(CONFIG, {})
            if "margem_direita" in _cfg:                       # versão 1.0 guardava uma margem só
                _cfg.setdefault("margens", {})["principal"] = _cfg.pop("margem_direita")
        return {**PADRAO, **json.loads(json.dumps(_cfg))}


def muda_config(**valores):
    global _cfg_sujo
    with trava:
        config()
        _cfg.update(valores)
        _cfg_sujo = True
    salva()


def salva():
    """Grava no disco o que mudou (config e histórico)."""
    global _cfg_sujo, _hist_sujo
    with trava:
        cfg = json.loads(json.dumps(_cfg)) if _cfg_sujo and _cfg is not None else None
        hist = json.loads(json.dumps(_hist)) if _hist_sujo and _hist is not None else None
        _cfg_sujo = _hist_sujo = False
    if cfg is not None:
        _grava_json(CONFIG, cfg)
    if hist is not None:
        _grava_json(HISTORICO, hist)


# ---------- leituras ----------
def atualiza(chave, nome, tipo, nivel, carregando=False, origem=""):
    """Os leitores chamam isto a cada leitura. tipo: headset, mouse, teclado, controle ou bluetooth."""
    global _cfg_sujo
    nivel = max(0, min(100, int(nivel)))
    with trava:
        estado[chave] = dict(nome=nome, tipo=tipo, nivel=nivel, carregando=bool(carregando),
                             visto=time.time(), origem=origem)
        config()
        if _cfg.setdefault("conhecidos", {}).get(chave) != {"nome": nome, "tipo": tipo}:
            _cfg["conhecidos"][chave] = {"nome": nome, "tipo": tipo}
            _cfg_sujo = True
        _registra(chave, nivel, bool(carregando))


def some(chave):
    """O periférico desligou ou sumiu."""
    with trava:
        estado.pop(chave, None)


def some_todos(prefixo, menos=()):
    with trava:
        for k in [k for k in estado if k.startswith(prefixo) and k not in menos]:
            estado.pop(k, None)


def espera(segundos):
    """Dorme, mas acorda na hora se o programa for fechado. Devolve True se é para parar."""
    return parar.wait(segundos)


def instantaneo():
    with trava:
        return {k: dict(v) for k, v in estado.items()}


# ---------- histórico e previsão ----------
DIAS_HISTORICO = 14


def _registra(chave, nivel, carregando):
    global _hist, _hist_sujo
    if _hist is None:
        _hist = _le_json(HISTORICO, {})
    pontos = _hist.setdefault(chave, [])
    agora = int(time.time())
    if pontos:
        t, n, c = pontos[-1]
        if n == nivel and bool(c) == carregando and agora - t < 600:   # igual e recente: não repete
            return
    pontos.append([agora, nivel, 1 if carregando else 0])
    limite = agora - DIAS_HISTORICO * 86400
    while pontos and pontos[0][0] < limite:
        pontos.pop(0)
    _hist_sujo = True


def previsao(chave):
    """Texto como 'Restam ≈ 2 dias' ou 'Cheio em ≈ 40 min', ou None se ainda não dá para prever."""
    with trava:
        pontos = list((_hist or {}).get(chave, []))
        atual = estado.get(chave)
    if not atual or len(pontos) < 2:
        return None
    carregando = atual["carregando"]
    # pega o trecho atual (descarregando ou carregando) andando para trás no histórico
    trecho = [pontos[-1]]
    for p in reversed(pontos[:-1]):
        anterior = trecho[-1]
        if bool(p[2]) != carregando:
            break
        if anterior[0] - p[0] > 6 * 3600 and carregando:     # carga não fica 6 h parada
            break
        if not carregando and p[1] < anterior[1] - 1:        # bateria subiu: começou outro ciclo
            break
        if carregando and p[1] > anterior[1] + 1:
            break
        trecho.append(p)
    inicio, fim = trecho[-1], trecho[0]
    horas = (fim[0] - inicio[0]) / 3600
    variacao = (inicio[1] - fim[1]) if not carregando else (fim[1] - inicio[1])
    if horas < (0.25 if carregando else 1) or variacao < 3:
        return None
    por_hora = variacao / horas
    falta = (atual["nivel"] if not carregando else 100 - atual["nivel"]) / por_hora
    texto = _duracao(falta)
    return f"Cheio em ≈ {texto}" if carregando else f"Restam ≈ {texto}"


def _duracao(horas):
    if horas < 1:
        return f"{max(5, round(horas * 60 / 5) * 5)} min"
    if horas < 36:
        return f"{round(horas)} h"
    return f"{round(horas / 24)} dias"
