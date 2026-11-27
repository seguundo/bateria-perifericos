"""Estado compartilhado: periféricos lidos, configuração, histórico e previsão de duração."""
import copy
import json
import os
import sys
import threading
import time
import traceback

APP = "Bateria dos Periféricos"
VERSAO = "1.3.0"
ORDEM_TIPO = {"headset": 0, "mouse": 1, "teclado": 2, "controle": 3, "bluetooth": 4}
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
    "aviso_noite": True,         # "carregue antes de parar": avisa se não aguenta o uso de amanhã
    "hora_noite": 22,            # a partir de que hora esse aviso aparece
    "som_critico": True,         # som quando a bateria está acabando (ajuda em tela cheia)
    "noite_avisada": {},         # chave -> dia em que o aviso da noite já saiu
    "procurar_versao": True,
    "ocultos": [],               # chaves dos periféricos escondidos
    "ordem": [],                 # chaves na ordem escolhida
    "margens": {},               # barra -> distância até a borda direita
    "conhecidos": {},            # chave -> {nome, tipo}: todos os periféricos já vistos
}

trava = threading.RLock()
_trava_disco = threading.Lock()     # só uma gravação por vez (relógio, Ajustes e aviso de versão salvam)
estado = {}            # chave -> dict(nome, tipo, nivel, carregando, visto, origem)
parar = threading.Event()
_cfg = None
_cfg_sujo = False
_hist = None
_hist_sujo = False


# ---------- configuração ----------
def _le_json(caminho, padrao):
    """Lê um JSON do tipo esperado. Se estiver corrompido, guarda uma cópia (.corrompido) em vez de apagar."""
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, type(padrao)):
            return dados
        raise ValueError("tipo inesperado")
    except FileNotFoundError:
        return padrao
    except Exception:
        try:
            os.replace(caminho, caminho + ".corrompido")
        except OSError:
            pass
        return padrao


def _grava_json(caminho, dados):
    """Grava com segurança (arquivo temporário + troca). Devolve True se deu certo."""
    try:
        os.makedirs(PASTA_DADOS, exist_ok=True)
        tmp = caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
        os.replace(tmp, caminho)
        return True
    except Exception:
        return False


def _carrega():
    global _cfg
    if _cfg is None:
        _cfg = _le_json(CONFIG, {})
        if "margem_direita" in _cfg:                       # versão 1.0 guardava uma margem só
            _cfg.setdefault("margens", {})["principal"] = _cfg.pop("margem_direita")
    return _cfg


def config():
    """Cópia da configuração atual (com os valores padrão preenchidos). Pode ser alterada à vontade."""
    with trava:
        return copy.deepcopy({**PADRAO, **_carrega()})


def muda_config(**valores):
    global _cfg_sujo
    with trava:
        _carrega().update(valores)
        _cfg_sujo = True
    salva()


def salva():
    """Grava no disco o que mudou (config e histórico). Se a gravação falhar, tenta de novo na próxima."""
    global _cfg_sujo, _hist_sujo
    with _trava_disco:
        with trava:
            cfg = copy.deepcopy(_cfg) if _cfg_sujo and _cfg is not None else None
            hist = copy.deepcopy(_hist) if _hist_sujo and _hist is not None else None
            _cfg_sujo = _hist_sujo = False
        falhou_cfg = cfg is not None and not _grava_json(CONFIG, cfg)
        falhou_hist = hist is not None and not _grava_json(HISTORICO, hist)
        if falhou_cfg or falhou_hist:
            with trava:
                _cfg_sujo = _cfg_sujo or falhou_cfg
                _hist_sujo = _hist_sujo or falhou_hist


# ---------- leituras ----------
SONECA = 30 * 60      # aparelho dormindo continua na barra (apagado) por este tempo


def atualiza(chave, nome, tipo, nivel, carregando=False, origem=""):
    """Os leitores chamam isto a cada leitura. tipo: headset, mouse, teclado, controle ou bluetooth."""
    global _cfg_sujo
    nivel = max(0, min(100, int(nivel)))
    with trava:
        estado[chave] = dict(nome=nome, tipo=tipo, nivel=nivel, carregando=bool(carregando),
                             visto=time.time(), origem=origem)
        conhecidos = _carrega().setdefault("conhecidos", {})
        if conhecidos.get(chave) != {"nome": nome, "tipo": tipo}:
            conhecidos[chave] = {"nome": nome, "tipo": tipo}
            _cfg_sujo = True
        _registra(chave, nivel, bool(carregando))


def esquece(chave):
    """Tira um periférico da lista dos Ajustes (e do histórico). Se ele voltar a ligar, aparece de novo."""
    global _cfg_sujo, _hist_sujo
    global _hist
    with trava:
        if _hist is None:                       # ainda não leu o histórico: lê agora para apagar de verdade
            _hist = _le_json(HISTORICO, {})
        cfg = _carrega()
        cfg.get("conhecidos", {}).pop(chave, None)
        for lista in ("ordem", "ocultos"):
            if chave in cfg.get(lista, []):
                cfg[lista] = [k for k in cfg[lista] if k != chave]
        if _hist and _hist.pop(chave, None) is not None:
            _hist_sujo = True
        _cfg_sujo = True
    salva()


def dorme(chave):
    """O aparelho parou de mandar leituras (dormindo ou desligado): guarda a última % por um tempo."""
    with trava:
        v = estado.get(chave)
        if v and not v.get("dormindo"):
            v.update(dormindo=True, dormiu=time.time())


def some(chave):
    """O periférico desligou ou sumiu."""
    with trava:
        estado.pop(chave, None)


def some_todos(prefixo, menos=()):
    with trava:
        for k in [k for k in estado if k.startswith(prefixo) and k not in menos]:
            estado.pop(k, None)


def expira(segundos):
    """Tira da barra leituras velhas (leitor travado ou aparelho que sumiu sem avisar)."""
    agora = time.time()
    with trava:
        for k, v in list(estado.items()):
            velho = agora - v["dormiu"] > SONECA if v.get("dormindo") else agora - v["visto"] > segundos
            if velho:
                estado.pop(k, None)


_erros_vistos = set()


def erro(onde):
    """Anota no erros.log (uma vez por erro diferente) o erro que acabou de acontecer num leitor."""
    tipo, valor, _ = sys.exc_info()
    assinatura = (onde, type(valor).__name__, str(valor))
    if assinatura in _erros_vistos or sys.stderr is None:
        return
    _erros_vistos.add(assinatura)
    try:
        sys.stderr.write(f"\n[{time.strftime('%d/%m/%Y %H:%M:%S')}] erro em {onde}:\n{traceback.format_exc()}")
    except Exception:
        pass


def espera(segundos):
    """Dorme, mas acorda na hora se o programa for fechado. Devolve True se é para parar."""
    return parar.wait(segundos)


class DetectaCarga:
    """Deduz que está carregando quando o aparelho não informa (ex.: Corsair pelo iCUE).

    A % de alguns headsets oscila até ±7 entre uma leitura e outra, por isso compara a mediana
    das últimas leituras com a menor mediana recente: só uma subida firme conta.
    """
    JANELA = 40 * 60      # quanto tempo para trás é comparado
    SUBIDA = 8            # pontos de subida (na mediana) para considerar que está carregando
    QUEDA = 5             # pontos de queda desde o pico para considerar que saiu da tomada
    PARADO = 25 * 60      # sem subir por este tempo (abaixo de 95%) = não está mais carregando
    LACUNA = 3 * 60       # sumiu por mais que isto: começa do zero

    def __init__(self):
        self.leituras = []        # (hora, %)
        self.medianas = []        # (hora, mediana das últimas 5)
        self.carregando = False
        self.pico = self.hora_pico = 0

    def le(self, nivel, agora=None):
        agora = time.time() if agora is None else agora
        if self.leituras and agora - self.leituras[-1][0] > self.LACUNA:
            self.__init__()
        self.leituras = self.leituras[-4:] + [(agora, nivel)]
        if len(self.leituras) < 5:
            return self.carregando
        mediana = sorted(n for _, n in self.leituras)[2]
        self.medianas = [(t, m) for t, m in self.medianas if agora - t <= self.JANELA] + [(agora, mediana)]
        if not self.carregando:
            if mediana - min(m for _, m in self.medianas) >= self.SUBIDA:
                self.carregando, self.pico, self.hora_pico = True, mediana, agora
        else:
            if mediana > self.pico:
                self.pico, self.hora_pico = mediana, agora
            if self.pico - mediana >= self.QUEDA or (self.pico < 95 and agora - self.hora_pico > self.PARADO):
                self.carregando = False
                self.medianas = [(agora, mediana)]
        return self.carregando


def instantaneo():
    with trava:
        return {k: dict(v) for k, v in estado.items()}


# ---------- histórico e previsão ----------
DIAS_HISTORICO = 30


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


LACUNA = 30 * 60      # mais de 30 min sem ponto = programa fechado / PC desligado: não conta esse tempo


def ritmo(pontos, carregando):
    """% por hora de uso, somando todos os trechos do histórico (todas as cargas, não só a atual).

    Corta o histórico em trechos: na troca carregando/na bateria, quando a % anda no sentido
    contrário (outra carga) e nas lacunas em que o programa estava fechado. Devolve (ritmo, horas)
    ou (None, horas) se ainda há pouco dado.
    """
    sinal = 1 if carregando else -1
    trechos, atual = [], []
    for p in pontos:
        if bool(p[2]) != carregando:
            atual and trechos.append(atual)
            atual = []
            continue
        if atual:
            dt = p[0] - atual[-1][0]
            salto = (p[1] - atual[-1][1]) * -sinal        # andou no sentido contrário
            if dt > LACUNA or salto >= 8:                 # PC desligado ou outra carga
                trechos.append(atual)
                atual = []
        atual.append(p)
    atual and trechos.append(atual)

    variacao, horas = 0.0, 0.0          # variacao = quanto a % andou no total (em pontos percentuais)
    for t in trechos:
        dur = (t[-1][0] - t[0][0]) / 3600
        if len(t) < 3 or dur < 1 / 6:
            continue
        # tendência (mínimos quadrados): as oscilações de ±2–4% que alguns aparelhos têm se anulam
        xs = [(p[0] - t[0][0]) / 3600 for p in t]
        ys = [p[1] for p in t]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        den = sum((x - mx) ** 2 for x in xs)
        if not den:
            continue
        inclinacao = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den * sinal
        if inclinacao <= 0:
            continue
        variacao += inclinacao * dur
        horas += dur
    minimo_h = 0.25 if carregando else 1
    if horas >= minimo_h and variacao >= 3:
        return variacao / horas, horas
    return None, horas


def previsao(chave):
    """Texto como 'Restam ≈ 2 dias de uso' ou 'Cheio em ≈ 40 min', ou None se ainda não dá para prever.

    Usa o ritmo médio aprendido em todo o histórico (até 30 dias), então a previsão continua
    valendo depois de recarregar o periférico ou reiniciar o PC.
    """
    with trava:
        pontos = list((_hist or {}).get(chave, []))
        atual = estado.get(chave)
    if not atual or len(pontos) < 2:
        return None
    carregando = atual["carregando"]
    if (carregando and atual["nivel"] >= 100) or (not carregando and atual["nivel"] <= 0):
        return None
    por_hora, _ = ritmo(pontos, carregando)
    if not por_hora:
        return None
    if carregando:
        return f"Cheio em ≈ {_duracao((100 - atual['nivel']) / por_hora)}"
    falta = atual["nivel"] / por_hora
    por_dia = horas_por_dia(pontos)
    if not por_dia:
        return f"Restam ≈ {_duracao(falta)} de uso"
    texto = f"{round(falta)} h" if falta >= 36 else _duracao(falta)
    dias = round(falta / por_dia)
    extra = f" (uns {dias} dias)" if dias >= 2 else ""
    return f"Restam ≈ {texto} de uso{extra}"


def horas_por_dia(pontos, agora=None):
    """Quantas horas por dia o aparelho costuma ser usado (média dos dias completos com uso).
    Devolve None com menos de 3 dias de dados."""
    hoje = time.localtime(agora)[:3]
    dias = {}
    for a, b in zip(pontos, pontos[1:]):
        dt = b[0] - a[0]
        dia = time.localtime(a[0])[:3]
        if not a[2] and not b[2] and 0 < dt <= LACUNA and dia != hoje:
            dias[dia] = dias.get(dia, 0) + dt / 3600
    usados = [h for h in dias.values() if h >= 0.5]
    return sum(usados) / len(usados) if len(usados) >= 3 else None


def historico(chave):
    with trava:
        return list((_hist or {}).get(chave, []))


def ultima_recarga(pontos):
    """(hora, %) em que terminou a recarga mais recente do histórico, ou None."""
    fim = None
    for a, b in zip(pontos, pontos[1:]):
        if b[2]:
            fim = (b[0], b[1])
        elif b[1] - a[1] >= 12:               # subiu de uma vez: carregou com o programa sem ver
            fim = (b[0], b[1])
    if fim is None and pontos and pontos[-1][2]:
        fim = (pontos[-1][0], pontos[-1][1])
    return fim


# ---------- aviso "carregue antes de parar" ----------
DURA_NOITE = 4        # o aviso vale da hora escolhida até 4 h depois


def dia_da_noite(hora, agora=None):
    """Se estamos no horário do aviso, devolve a data em que esse horário começou; senão None."""
    agora = time.time() if agora is None else agora
    passou = (time.localtime(agora).tm_hour - hora) % 24
    if passou >= DURA_NOITE:
        return None
    return time.strftime("%Y-%m-%d", time.localtime(agora - passou * 3600))


def nao_aguenta_amanha(chave, alerta):
    """Texto do aviso se a bateria não deve durar o uso de amanhã (com 20% de folga), senão None.
    Sem ritmo aprendido ainda, usa a % (até 10 pontos acima do alerta de bateria fraca)."""
    with trava:
        v = dict(estado.get(chave) or {})
    if not v or v["carregando"]:
        return None
    pontos = historico(chave)
    por_hora = ritmo(pontos, False)[0] if len(pontos) >= 2 else None
    if not por_hora:
        return f"{v['nome']} está com {v['nivel']}%." if v["nivel"] <= alerta + 10 else None
    resta = v["nivel"] / por_hora
    por_dia = horas_por_dia(pontos) or 8
    if resta >= por_dia * 1.2:
        return None
    return f"{v['nome']}: {v['nivel']}%, cerca de {_duracao(resta)} de uso."


def _duracao(horas):
    minutos = max(5, round(horas * 60 / 5) * 5)
    if minutos < 60:
        return f"{minutos} min"
    if horas < 36:
        return f"{round(horas)} h"
    return f"{round(horas / 24)} dias"
