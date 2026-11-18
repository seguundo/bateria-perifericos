# Notas de atualização

## 1.2.0 (18/11/2026): acabamento visual

Ajustes da revisão visual, para o programa parecer de fábrica do Windows 11.

### Barra
- **Número do mesmo tamanho do relógio:** a % agora usa a mesma fonte do relógio (Segoe UI Variable, 12 px). Antes ela saía uns 25% maior.
- **Raio de "carregando" legível:** um raio cheio e maior, um pouco afastado do número. O de antes era fino e parecia sujeira na tela.
- **Bateria fraca mais visível:** o bloco inteiro fica vermelho (ícone + número), não só o número. Assim funciona também para quem não distingue bem o vermelho.
- **Segunda tela:** o espaço até o relógio ficou igual ao da tela principal até a setinha `^`.

### Dica ao passar o mouse
- Mesma fonte do Windows. Cada linha começa com maiúscula ("Previsão: …", "Via iCUE · lido agora").
- Previsão escrita como "Restam ≈ 2 dias" e "Cheio em ≈ 40 min".
- Bateria fraca: a linha da % fica vermelha, combinando com a barra.
- "2.4G" virou "2,4 GHz".

### Janela de Ajustes
- **Visual do Windows 11** (tema Sun Valley), escura quando o Windows está no escuro, com a barra de título escura também.
- Ícone do programa no título (antes aparecia a pena do Python).
- Títulos de seção separados das instruções, que ficam em cinza menor; "desligado" em cinza ao lado do nome.
- **Salvar** em destaque como botão principal; Enter salva e Esc cancela.
- As setas de ordem ficam desativadas no primeiro e no último item.

### Ícone do programa
- Desenho próprio para os tamanhos pequenos (16, 20 e 24 px): uma pilha com carga verde, que lê bem na bandeja. O mouse ficou só nos tamanhos grandes, agora com uma borda clara para não sumir na barra escura.

### Para quem já usava
- Rode `pip install -r requirements.txt` de novo (entrou o tema `sv-ttk`, só Python, sem `.exe`) e `python criar_atalho.py` para atualizar o ícone do atalho.

## 1.1.0 (18/11/2026)

### Novidades
- **Dica ao passar o mouse:** pare o mouse em cima de um ícone para ver o nome do periférico, se está na bateria ou carregando, a previsão de duração e de onde veio a leitura.
- **Previsão de duração:** o programa aprende o ritmo de uso de cada periférico e mostra quanto ainda falta ("≈ 2 dias restantes") ou quando termina a carga ("cheio em ≈ 40 min"). A previsão começa a aparecer depois de ~1 hora de uso.
- **Avisos do Windows:** notificação quando a bateria fica fraca (15%, ajustável) e quando termina de carregar.
- **Segunda tela:** os ícones aparecem na barra de tarefas de todos os monitores (ou só na principal, se preferir). Cada tela guarda a sua posição.
- **Janela de Ajustes** (botão direito → Ajustes…): em quais telas mostrar, tamanho dos ícones, mostrar só quando a bateria estiver baixa, % do aviso, quais periféricos aparecem e em que ordem.
- **Aviso de versão nova:** uma vez por dia o programa confere se saiu versão nova no GitHub e avisa (dá para desligar nos Ajustes).
- **Ícone na bandeja:** o menu também abre pelo ícone do programa na bandeja do Windows (útil quando nenhum periférico está ligado).

### Mais marcas
- **Logitech** (Lightspeed, Unifying, Bolt ou cabo): leitura direta do receptor, sem precisar do G HUB.
- **Razer:** mouses e teclados sem fio, direto pelo USB.
- **HeadsetControl:** dezenas de headsets SteelSeries, HyperX, Logitech, Corsair e Roccat. Basta colocar o `headsetcontrol.exe` (do [GitHub oficial](https://github.com/Sapd/HeadsetControl/releases)) na pasta do programa.
- Ícone de **teclado** para teclados sem fio.

### Segurança
- **Sem PowerShell:** o Bluetooth agora é lido direto pelo Windows, e os avisos usam a função oficial de notificações. Antes o programa abria o PowerShell escondido, comportamento que antivírus vigiam.
- **Mouse Attack Shark:** o programa escuta só o canal da bateria do receptor, nunca o de teclas.
- **HeadsetControl:** só roda o `.exe` que estiver na pasta do programa, nunca um encontrado em outro lugar do PC.
- Os atalhos são criados pela função nativa do Windows (sem PowerShell) e dão nome e ícone próprios às notificações.
- Verificado no Kaspersky: nenhuma detecção.

### Correções
- Os ícones não somem mais ao abrir ou fechar a setinha `^` da bandeja.
- Controle Bluetooth desligado some da barra (o Windows guardava a última bateria).
- Bluetooth conferido a cada 10 s (antes, 20 s).
- Um jogo em tela cheia numa tela não esconde os ícones da outra.

### Para quem já usava
- O programa agora tem 5 arquivos (`bateria.py`, `leitores.py`, `nucleo.py`, `ajustes.py`, `atalho.py`). Rode `python criar_atalho.py` de novo para criar o atalho novo, **Bateria dos Periféricos**.
- Sua posição dos ícones é mantida.

## 1.0.0 (18/11/2026)
- Primeira versão: ícone e % de cada periférico sem fio fixos na barra de tarefas, ao lado da setinha `^`.
- Mouse Attack Shark X11 (direto do receptor), headsets Corsair (iCUE) e aparelhos Bluetooth.
- Arrastar para mudar de lugar, menu no botão direito, Iniciar com o Windows, some em tela cheia.
