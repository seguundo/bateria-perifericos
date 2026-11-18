# Bateria dos Periféricos: guia para o Claude

Programa para Windows 11 que mostra, numa faixa fixa sobre a barra de tarefas (à esquerda da setinha `^` da bandeja), um ícone e a porcentagem da bateria de cada periférico sem fio. Tudo fica em um arquivo: `bateria.py`.

**Quem usa isto provavelmente não é programador.** Fale em linguagem simples, faça você mesmo as instalações e os testes e entregue o atalho pronto.

**Não gere .exe com PyInstaller**: antivírus (Kaspersky e outros) marcam como trojan e apagam, por ser um .exe sem assinatura que lê um receptor USB e abre com o Windows. O programa roda pelo `pythonw.exe` (o Python, que é assinado) a partir de um atalho criado por `criar_atalho.py`.

## Tarefa típica: "adapta para os meus periféricos"

1. **Descubra o que está conectado** (PowerShell):
   - Bluetooth com bateria: já funciona sozinho, sem mudar nada (controle Xbox, fones, mouses e teclados BLE etc.).
   - Receptores USB 2.4G: liste as interfaces HID com VID/PID:
     `Get-PnpDevice -PresentOnly | ? InstanceId -match '^(HID|USB)\\VID_' | select InstanceId, Class, FriendlyName`
     e veja `DEVPKEY_Device_BusReportedDeviceDesc` para achar o nome real ("2.4G Wireless Device", "USB Receiver"...).
   - Apps das marcas abertos (G HUB, iCUE, Synapse, SteelSeries GG, NGenuity...): `Get-Process`.
   - Pergunte o **modelo exato** de cada periférico ao usuário.
2. **Escolha a fonte da bateria de cada um**, da mais fácil para a mais difícil:
   - **Bluetooth:** já coberto por `le_bluetooth()`. Se o ícone sair errado, ajuste `tipo_bt()`.
   - **Corsair:** já coberto por `le_corsair()` via iCUE SDK (`cuesdk`). O iCUE precisa estar aberto e o aparelho ligado; desligado devolve `CE_InvalidOperation`.
   - **Logitech (Lightspeed/Unifying):** protocolo HID++ 2.0, feature `0x1000`/`0x1001`/`0x1004` (battery), direto no receptor (VID 046D). Ou o WebSocket local do G HUB. Procure projetos abertos (ex.: LGSTrayBattery) e copie o protocolo.
   - **Razer:** relatório de feature de 90 bytes (comando `0x07 0x80`), como no OpenRazer.
   - **SteelSeries, HyperX e outras:** procure no GitHub/GitLab "<marca> <modelo> battery hidraw" ou projetos do Linux (OpenRazer, Solaar, HeadsetControl). **HeadsetControl** cobre muitos headsets (SteelSeries, HyperX, Logitech, Corsair) e serve de referência.
   - **Marcas chinesas (Attack Shark, VXE, ATK, Redragon...):** o receptor costuma mandar quadros sozinho numa interface "vendor". Abra todas as coleções HID daquele VID:PID com `hid` (hidapi) em modo não bloqueante, leia por uns 15 s e procure um byte que bata com a % que o app oficial mostra (veja `le_x11()` como modelo).
3. **Implemente um leitor** no mesmo padrão: uma função em thread que chama `atualiza(chave, nome, tipo, nivel, carregando)` quando lê e `some(chave)` quando o aparelho desliga ou some. `tipo` é `headset`, `mouse`, `controle`, `teclado` ou `bluetooth` (define o ícone; para um tipo novo, acrescente em `GLIFO` e `ORDEM`). Registre a função na lista de `principal()`. Apague os leitores que a pessoa não usa.
4. **Nunca envie comandos de escrita a um aparelho sem saber o que fazem** (pode mudar DPI, macros ou firmware). Prefira ler o que ele já manda sozinho ou repetir um comando conhecido de um projeto aberto.
5. **Teste** rodando os leitores sem a interface (importe `bateria`, inicie as threads e imprima `estado` depois de ~25 s). Depois rode `python bateria.py` e fotografe a barra com `PIL.ImageGrab` para conferir.
6. **Crie o atalho:** `python criar_atalho.py`. Ele cria `icone.ico` e o atalho "Bateria Perifericos" na pasta e no Menu Iniciar (abre `bateria.py` com o `pythonw.exe`). "Iniciar com o Windows", no menu do programa, grava esse mesmo comando em `HKCU\...\Run` e se corrige sozinho se o caminho mudar.

## Como funciona

- **Leitores** (threads) gravam no dicionário `estado`, protegido por `trava`.
- **`Faixa`**: janela Win32 em camadas (`WS_EX_LAYERED`, sempre por cima, sem foco) do tamanho da altura da barra. A imagem é desenhada com Pillow e enviada com `UpdateLayeredWindow` (alfa por pixel; fundo com alfa 1 para dar para clicar e arrastar).
  - Ícones: fonte **Segoe Fluent Icons** do Windows (`SegoeIcons.ttf`): fone `E7F6`, mouse `E962`, controle `E7FC`, Bluetooth `E702`, raio `E945`, teclado `E765`.
  - Texto em Segoe UI. A cor segue o tema claro/escuro da barra e fica vermelha em 15% ou menos.
  - Posição: ancorada à esquerda de `TrayNotifyWnd`. Arrastar move só na horizontal, e a posição fica salva em `%APPDATA%\BateriaPerifericos\config.json`.
  - Botão direito abre o menu (lista, "Iniciar com o Windows" via `HKCU\...\Run`, posição padrão, Sair).
  - A faixa se esconde quando um app está em tela cheia e reaparece a cada 1 s (o tick também reafirma "sempre por cima").
- **Bluetooth:** o Windows guarda a última bateria mesmo com o aparelho desligado. Por isso só vale com `{83DA6326-97A6-4088-9453-A1923F573B29} 15` = True (conectado). A bateria em si é `{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2`.
- **Attack Shark X11** (receptor `1D57:FA60`, interface 2): sem enviar nada, o receptor manda a cada ~2 s o quadro `03 ?? 40 ST NN` (ST `01` = bateria, `03` = carregando; NN = %). Mais de 30 s sem quadro = mouse dormindo/desligado.
- Uma instância por vez (mutex `BateriaPerifericos_unica`). Depois de mudar o código, feche pelo menu (Sair) e abra de novo pelo atalho.

## Dependências

`pip install -r requirements.txt` (Python 3.12 testado).
