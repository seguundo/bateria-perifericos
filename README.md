# Bateria dos Periféricos

Mostra na barra de tarefas do Windows 11, ao lado da setinha `^`, o ícone e a porcentagem de bateria dos periféricos sem fio: fone, mouse, controle e teclado.

![Ícones na barra de tarefas](docs/barra.png)

- Fica sempre visível na barra, em todas as telas (não escondido no menu da bandeja).
- **Pare o mouse em cima** de um ícone para ver o nome, o estado e a **previsão de duração** ("≈ 2 dias restantes").
- **Avisos do Windows** quando a bateria fica fraca e quando termina de carregar.
- Ícones do próprio Windows 11, que acompanham o tema claro/escuro. Número vermelho na bateria fraca; raiozinho carregando.
- Periférico desligado some sozinho e volta quando liga. Os ícones se escondem em jogos e vídeos em tela cheia.
- Arraste para o lado para mudar de lugar. Botão direito: **Ajustes** (telas, tamanho, quais periféricos e em que ordem, avisos), Iniciar com o Windows, Sair.
- Avisa quando sai versão nova aqui no GitHub.

O que mudou em cada versão: [Notas de atualização](NOTAS-DE-ATUALIZACAO.md).

## Periféricos que funcionam

| Periférico | Como a bateria é lida |
|---|---|
| Qualquer aparelho **Bluetooth** que informe bateria ao Windows (controle Xbox, fones, mouses e teclados BLE) | Direto do Windows |
| **Logitech** (Lightspeed, Unifying, Bolt ou cabo) | HID++ direto no receptor, sem G HUB |
| **Razer** (mouses e teclados sem fio) | Direto pelo USB, sem Synapse |
| Headsets e periféricos **Corsair** | iCUE SDK (o iCUE precisa estar aberto) |
| Headsets **SteelSeries, HyperX, Logitech, Roccat** e outros | [HeadsetControl](https://github.com/Sapd/HeadsetControl): coloque o `headsetcontrol.exe` na pasta do programa |
| Mouse **Attack Shark X11** (receptor 2.4G `1D57:FA60`) | Direto do receptor, sem o app da marca |

Logitech e Razer foram feitos a partir de protocolos de projetos abertos e ainda não foram testados com os aparelhos. Se não funcionar com o seu, abra uma *issue*.

## Instalação

Requer Windows 11 e Python 3.12.

```bash
pip install -r requirements.txt
python criar_atalho.py
```

Abra o atalho **Bateria dos Periféricos** (na pasta e no Menu Iniciar).

## Segurança

- **Sem `.exe`:** antivírus apagam por engano programas Python empacotados como `.exe`. O atalho roda o script pelo `pythonw.exe` do próprio Python, que é assinado digitalmente.
- **Sem PowerShell e sem janelas escondidas:** tudo é feito pelas funções nativas do Windows.
- **Só lê:** não muda configurações dos periféricos. Para Logitech e Razer, envia apenas as perguntas de bateria já usadas por projetos abertos (Solaar, OpenRazer). No receptor Attack Shark, escuta só o canal da bateria, nunca o de teclas.
- **Internet:** só uma consulta por dia à página de versões deste repositório (dá para desligar nos Ajustes). Nada é enviado e nada é baixado automaticamente.
- **Arquivos:** grava apenas em `%APPDATA%\BateriaPerifericos` (ajustes e histórico de bateria) e, se você pedir, na chave "Iniciar com o Windows" do seu usuário. Não precisa de administrador.
- Verificado no Kaspersky (18/11/2026): nenhuma detecção.

## Adaptar para os seus periféricos com o Claude Code

Abra a pasta no Claude Code e peça:

> Adapta esse programa para os meus periféricos: mouse Logitech G Pro X Superlight, headset HyperX Cloud II Wireless. No fim, cria o atalho.

O [`CLAUDE.md`](CLAUDE.md) explica ao Claude como o programa funciona e como descobrir a bateria de cada marca.

## Créditos

- Protocolo do Attack Shark: [Attack Shark Battery KDE](https://gitlab.com/gabriel17166/Attack-Shark-Battery-KDE) (MIT).
- Protocolos Logitech HID++ e Razer: documentados pelos projetos [Solaar](https://github.com/pwr-Solaar/Solaar) e [OpenRazer](https://github.com/openrazer/openrazer).
- Headsets: [HeadsetControl](https://github.com/Sapd/HeadsetControl).
- Ícones: fonte Segoe Fluent Icons, que vem com o Windows 11.
