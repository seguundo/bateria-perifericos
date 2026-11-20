"""Testes rápidos (não tocam no seu programa nem nos seus dados). Rode: python testes.py

Usam uma pasta temporária no lugar do %APPDATA% e aparelhos de mentira, então não precisam de
nenhum periférico. Cobrem a gravação dos ajustes, a previsão de duração, os protocolos
(Razer, Logitech, HeadsetControl) e a leitura de atalhos.
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest

DADOS = tempfile.mkdtemp(prefix="bateria_teste_")
os.environ["APPDATA"] = DADOS                      # antes de importar o programa
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atalho  # noqa: E402
import leitores  # noqa: E402
import nucleo  # noqa: E402


def lejson(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def escreve(caminho, texto):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def zera():
    nucleo._cfg, nucleo._cfg_sujo, nucleo._hist, nucleo._hist_sujo = None, False, None, False
    nucleo.estado.clear()
    for n in os.listdir(nucleo.PASTA_DADOS) if os.path.isdir(nucleo.PASTA_DADOS) else []:
        os.remove(os.path.join(nucleo.PASTA_DADOS, n))


class TestaNucleo(unittest.TestCase):
    def setUp(self):
        zera()

    def test_gravacoes_ao_mesmo_tempo_nao_perdem_nada(self):
        def trabalha(n):
            for i in range(60):
                nucleo.muda_config(contador=n * 1000 + i)
                nucleo.atualiza(f"x{n}", "Teste", "mouse", 50 + (i % 5))
                nucleo.salva()
        fios = [threading.Thread(target=trabalha, args=(n,)) for n in range(4)]
        [f.start() for f in fios]
        [f.join() for f in fios]
        nucleo.salva()
        em_disco = lejson(nucleo.CONFIG)
        self.assertEqual(em_disco["contador"], nucleo.config()["contador"])
        self.assertEqual(set(lejson(nucleo.HISTORICO)), {f"x{n}" for n in range(4)})

    def test_config_devolve_copia_independente(self):
        c = nucleo.config()
        c["margens"]["principal"] = 99
        c["ocultos"].append("x")
        self.assertEqual(nucleo.PADRAO["margens"], {})
        self.assertEqual(nucleo.PADRAO["ocultos"], [])
        self.assertEqual(nucleo.config()["margens"], {})

    def test_json_corrompido_vira_copia_e_volta_ao_padrao(self):
        os.makedirs(nucleo.PASTA_DADOS, exist_ok=True)
        escreve(nucleo.CONFIG, "{ isto não é json")
        self.assertEqual(nucleo.config()["alerta"], nucleo.PADRAO["alerta"])
        self.assertTrue(os.path.exists(nucleo.CONFIG + ".corrompido"))

    def test_json_de_tipo_errado_nao_quebra(self):
        os.makedirs(nucleo.PASTA_DADOS, exist_ok=True)
        escreve(nucleo.CONFIG, "[1, 2, 3]")
        self.assertEqual(nucleo.config()["monitores"], "todos")

    def test_esquece_tira_do_historico_e_da_lista(self):
        nucleo.atualiza("a", "Aparelho A", "mouse", 40)
        nucleo.muda_config(ordem=["a"], ocultos=["a"])
        nucleo.esquece("a")
        cfg = nucleo.config()
        self.assertNotIn("a", cfg["conhecidos"])
        self.assertEqual((cfg["ordem"], cfg["ocultos"]), ([], []))
        self.assertNotIn("a", nucleo._hist)

    def test_ritmo_e_previsao(self):
        agora = int(time.time())
        pontos = [[agora - (10 - i) * 1800, 90 - i * 3, 0] for i in range(11)]        # 6 %/h durante 5 h
        r, horas = nucleo.ritmo(pontos, False)
        self.assertAlmostEqual(r, 6, delta=0.5)
        nucleo._hist = {"t": pontos}
        nucleo.estado["t"] = dict(nome="t", tipo="mouse", nivel=60, carregando=False, visto=agora, origem="")
        self.assertIn("Restam", nucleo.previsao("t"))

    def test_ritmo_ignora_lacuna_e_pouco_dado(self):
        agora = int(time.time())
        self.assertEqual(nucleo.ritmo([[agora - 600, 50, 0], [agora, 49, 0]], False)[0], None)
        lacuna = [[agora - 90000, 90, 0], [agora - 89000, 88, 0], [agora - 100, 50, 0], [agora, 49, 0]]
        self.assertEqual(nucleo.ritmo(lacuna, False)[0], None)         # PC desligado no meio: não conta


class RazerDeMentira:
    """Aparelho Razer simulado: responde 'ocupado' nas primeiras vezes e depois a bateria."""
    def __init__(self, ocupado=2, status_final=0x02, nivel=128):
        self.ocupado, self.status_final, self.nivel, self.ultimo, self.envios = ocupado, status_final, nivel, None, 0

    def send_feature_report(self, dados):
        self.ultimo, self.envios = bytearray(dados[1:]), self.envios + 1

    def get_feature_report(self, _id, tamanho):
        r = bytearray(self.ultimo)
        r[0] = 0x01 if self.envios <= self.ocupado else self.status_final
        r[9] = self.nivel
        r[88] = leitores._crc_razer(r)
        return bytes([0]) + bytes(r)


class TestaLeitores(unittest.TestCase):
    def test_razer_repete_quando_ocupado(self):
        h = RazerDeMentira(ocupado=2)
        r = leitores._razer(h, 0x1F, 0.1, 0x07, 0x80)
        self.assertIsNotNone(r)
        self.assertEqual((h.envios, round(r[9] * 100 / 255)), (3, 50))

    def test_razer_para_quando_nao_suportado(self):
        h = RazerDeMentira(ocupado=0, status_final=0x05)
        self.assertIsNone(leitores._razer(h, 0x1F, 0.1, 0x07, 0x80))
        self.assertEqual(h.envios, 1)

    def test_razer_rejeita_crc_errado(self):
        h = RazerDeMentira(ocupado=0)
        original = h.get_feature_report
        h.get_feature_report = lambda i, t: original(i, t)[:-2] + b"\x00\x00"
        self.assertIsNone(leitores._razer(h, 0x1F, 0.1, 0x07, 0x80))

    def test_tabela_razer(self):
        self.assertEqual(len(leitores.RAZER), 72)
        self.assertEqual(leitores.RAZER[0x00E2], (0x1F, 3, 59.9))      # Basilisk V4 Pro: interface 3
        self.assertEqual(leitores.RAZER[0x0062][2], 400)               # Atheris: resposta lenta
        self.assertNotIn(0x9F, {t for t, _, _ in leitores.RAZER.values()})

    def test_logitech_status_de_carga(self):
        self.assertEqual(leitores._carga(0), (False, False))
        self.assertEqual(leitores._carga(1), (True, False))
        self.assertEqual(leitores._carga(3), (False, True))           # carga completa
        self.assertEqual(leitores._carga(4), (True, False))           # carga lenta

    def test_headsetcontrol(self):
        texto = json.dumps({"devices": [
            {"device": "A", "id_vendor": "0x1038", "id_product": "1",
             "battery": {"status": "BATTERY_CHARGING", "level": -1}},
            {"device": "B", "id_vendor": "0x1", "id_product": "2",
             "battery": {"status": "BATTERY_AVAILABLE", "level": -1}},
            {"device": "C é ç", "id_vendor": "0x2", "id_product": "3",
             "battery": {"status": "BATTERY_AVAILABLE", "level": 55}}]})
        lista = leitores.interpreta_headsetcontrol(texto)
        self.assertEqual([(n, nivel, c) for _, n, nivel, c, _ in lista], [("A", None, True), ("C é ç", 55, False)])


class TestaAtalho(unittest.TestCase):
    def test_cria_e_le(self):
        destino = os.path.join(DADOS, "teste.lnk")
        atalho.cria(destino, sys.executable, '"C:\\pasta com espaço\\x.py" --inicio', DADOS, "", "teste", atalho.AUMID)
        self.assertEqual(atalho.le(destino), (sys.executable, '"C:\\pasta com espaço\\x.py" --inicio'))
        self.assertIsNone(atalho.le(os.path.join(DADOS, "nao-existe.lnk")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
