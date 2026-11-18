# Bateria dos Periféricos: guia para o Claude

Programa para Windows 11 que mostra, numa faixa fixa sobre a barra de tarefas (à esquerda da setinha `^` da bandeja, e à esquerda do relógio nas outras telas), o ícone e a % de bateria de cada periférico sem fio. Tem dica ao passar o mouse, previsão de duração, avisos, ajustes e aviso de versão nova.

**Quem usa isto provavelmente não é programador.** Fale em linguagem simples, faça você mesmo as instalações e os testes, e entregue o atalho pronto.

## Regras de segurança (não quebre)

- **Não gere `.exe`** (PyInstaller, Nuitka...): antivírus como o Kaspersky marcam como trojan e apagam. O programa roda pelo `pythonw.exe` a partir do atalho criado por `criar_atalho.py`.
- **Não use PowerShell, cmd ou janelas escondidas.** Antivírus vigiam programas que abrem PowerShell escondido. Use a API do Windows via `ctypes` (veja a leitura do Bluetooth com SetupAPI em `leitores.py` e o atalho via COM em `atalho.py`).
- **Não leia canais HID de teclado, mouse ou mídia** (usage page 0x01, 0x07, 0x0C): parece keylogger. Só canais do fabricante (0xFF00+, 0x0A...).
- **Nunca envie a um aparelho comandos que não venham de um projeto aberto conhecido** (pode mudar DPI, macros ou firmware). Prefira ler o que ele manda sozinho.
- **Nada de baixar e executar coisas da internet.** A única rede é a consulta diária a `api.github.com/repos/<REPO>/releases/latest`.
- Antes de entregar, escaneie a pasta com o antivírus da pessoa (Kaspersky: `avp.com SCAN "<pasta>" /i0`; Defender: `MpCmdRun.exe -Scan -ScanType 3 -File "<pasta>"`).

## Arquivos

| Arquivo | O que tem |
|---|---|
| `leitores.py` | **Um leitor por marca. É aqui que se adapta para novos periféricos.** |
| `nucleo.py` | Estado compartilhado (`atualiza`, `some`), configuração (`config`, `muda_config`), histórico e `previsao()`. `VERSAO` e `REPO` ficam aqui. |
| `bateria.py` | Faixa na barra (uma por tela), dica, menu, ícone na bandeja, avisos, versão nova, Iniciar com o Windows. |
| `ajustes.py` | Janela de Ajustes (tkinter + tema `sv-ttk` no estilo Windows 11, claro/escuro, barra de título escura via DWM; thread própria). |
| `icone.py` | Ícone do programa: pilha desenhada pixel a pixel em 16–24 px, mouse em 32 px ou mais. |
| `atalho.py` / `criar_atalho.py` | Atalho na pasta e no Menu Iniciar, com AppUserModelID (nome e ícone nas notificações). |

## Tarefa típica: "adapta para os meus periféricos"

1. **Descubra o que está conectado.** Pergunte o **modelo exato** de cada periférico. Liste os HID com Python: `hid.enumerate()` (VID, PID, interface, usage_page, produto).
2. **Veja se já funciona** rodando os leitores sem interface (importe `nucleo` e `leitores`, inicie as funções de `LEITORES` em threads e imprima `nucleo.instantaneo()` depois de ~25 s). Já cobertos: Bluetooth com bateria no Windows, Logitech HID++ (receptor ou cabo), Razer (classe 0x07), Corsair via iCUE, HeadsetControl (precisa do `headsetcontrol.exe` na pasta; baixe do GitHub oficial `Sapd/HeadsetControl/releases`, com o OK da pessoa) e Attack Shark X11.
   - **Logitech e Razer foram escritos a partir dos protocolos do Solaar/OpenRazer e não foram testados com aparelhos reais.** Se a pessoa tiver um, teste e corrija.
3. **Marca que falta:** procure no GitHub/GitLab "<marca> <modelo> battery hidraw" ou nos projetos Linux (OpenRazer, Solaar, HeadsetControl, libratbag). **Marcas chinesas** (Attack Shark, VXE, ATK, Redragon...): o receptor costuma mandar quadros sozinho num canal do fabricante. Abra só as coleções de usage page do fabricante, leia por ~15 s e procure um byte igual à % do app oficial (modelo: `le_attack_shark`).
4. **Implemente** em `leitores.py`: uma função em loop que chama `atualiza(chave, nome, tipo, nivel, carregando, origem)` quando lê, `some(chave)` / `some_todos(prefixo, vistos)` quando o aparelho some, e `if espera(segundos): return` entre leituras. `tipo`: `headset`, `mouse`, `teclado`, `controle` ou `bluetooth` (define o ícone). Coloque a função em `LEITORES`. Apague os leitores de marcas que a pessoa não usa, se ela quiser.
5. **Teste na barra:** feche o programa (menu → Sair), rode `python bateria.py` e fotografe a barra com `PIL.ImageGrab` (`all_screens=True` para ver as outras telas).
6. **Atalho:** `python criar_atalho.py`.
7. Se a pessoa fizer um fork, troque `REPO` em `nucleo.py` para o repositório dela (aviso de versão nova). Ao lançar versão: aumente `VERSAO`, escreva as **Notas de atualização** (`NOTAS-DE-ATUALIZACAO.md`) e crie a release `vX.Y.Z` no GitHub com essas notas.

## Como funciona

- **Faixa:** janela Win32 em camadas (sempre por cima, sem foco, `UpdateLayeredWindow` com alfa por pixel; fundo com alfa 1 para dar para clicar e arrastar). Desenho com Pillow. Texto em **Segoe UI Variable** 12 px (`SegUIVar.ttf`, variação Regular; mesmo corpo do relógio). Bateria fraca: ícone + número vermelhos (#FF6E64 escuro / #C42B1C claro). Carregando: raio cheio desenhado como polígono (7×11 px). Ícones da fonte **Segoe Fluent Icons** (`SegoeIcons.ttf`: fone `E7F6`, mouse `E962`, controle `E7FC`, teclado `E765`, Bluetooth `E702`). Uma faixa por barra (`Shell_TrayWnd` e cada `Shell_SecondaryTrayWnd`).
- **Posição:** na tela principal, à esquerda de `TrayNotifyWnd`. Nas outras, 90 px (×escala) da borda direita (antes do relógio). Arrastar mexe só na horizontal; fica salvo em `margens[<id da barra>]`.
- **Tela cheia:** a faixa daquela tela se esconde depois de 2 s seguidos. Ignora janelas camufladas (DWM) e dos processos do shell (explorer, TextInputHost...), que ocupam a tela inteira de forma invisível.
- **Relógios:** 1 s (redesenha, avisos, salva a cada 5 min) e 200 ms (dica e "trazer para a frente": clicar na barra a joga por cima da faixa).
- **Avisos:** `Shell_NotifyIcon` com `NIF_INFO`, no ícone da bandeja. O nome e o ícone vêm do atalho do Menu Iniciar com AppUserModelID `BateriaPerifericos.App` (criado sozinho se faltar).
- **Dados:** `%APPDATA%\BateriaPerifericos\config.json` (ajustes, posições, periféricos conhecidos) e `historico.json` (14 dias; um ponto quando a % muda ou a cada 10 min).
- **Previsão:** pega o trecho atual (descarregando ou carregando) do histórico; precisa de ≥ 1 h (descarga) ou 15 min (carga) e ≥ 3 pontos de variação.
- **Bluetooth:** SetupAPI, classe Bluetooth, bateria `{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2`, conectado `{83DA6326-97A6-4088-9453-A1923F573B29} 15`.
- **Attack Shark X11** (`1D57:FA60`, interface 2, usage page 0x0A): o receptor manda sozinho a cada ~2 s `03 ?? 40 ST NN` (ST `01` bateria, `03` carregando; NN = %). Mais de 30 s sem quadro = dormindo.
- **Logitech HID++ 2.0:** mensagem longa `11 <aparelho> <índice> <função<<4|0A> ...` na coleção FF00/usage 2. Aparelhos 0xFF (cabo/direto) e 1–6 (receptor). Recursos 0x1004 (Unified Battery, função 1), 0x1000 (função 0), 0x1001 (tensão → %), nome 0x0005.
- **Razer:** relatório de recurso de 90 bytes, transação 0x1F/0x3F/0xFF/0x9F, classe 0x07, comando 0x80 (bateria 0–255) e 0x84 (carregando); resposta com status 0x02 = OK.
- Uma instância por vez (mutex `BateriaPerifericos_unica`).

## Dependências

`pip install -r requirements.txt` (Python 3.12 testado).
