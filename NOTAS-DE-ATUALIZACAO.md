# Notas de atualização

## 1.2.2 (26/11/2026): correções e melhorias

### Correções
- **Clicar na faixa não a prende mais no lugar:** um clique simples (sem arrastar) gravava a posição, e a faixa parava de acompanhar a setinha `^` quando um ícone novo entrava na bandeja. Agora só grava quando você arrasta de verdade.
- **Avisos que se atropelavam:** dois avisos ao mesmo tempo (ex.: dois periféricos fracos ao ligar o PC) faziam o Windows trocar um pelo outro antes de dar para ler. Agora avisos do mesmo tipo viram um só, e tipos diferentes aparecem um depois do outro.
- **% parada na barra:** se um leitor travasse, a última % ficava na barra para sempre. Agora leitura com mais de 5 min sem atualizar sai da barra.
- **Versão nova:** sem internet logo depois de ligar o PC, o programa só tentava de novo no dia seguinte. Agora tenta de novo em 1 h.
- **Previsão:** não mostra mais "Cheio em ≈ 5 min" quando já está em 100%, e mostra "1 h" em vez de "60 min".
- **Esquecer (Ajustes):** apagava o periférico da lista mas, logo depois de abrir o programa, podia deixar o histórico dele no disco.
- **Logitech:** o código 4 da bateria unificada é erro de carga, não "carga lenta" (não mostra mais o raio por engano).
- **Erros dos leitores:** antes eram engolidos calados; agora cada erro diferente fica anotado uma vez no `erros.log` (ajuda a consertar Logitech e Razer, que ainda não foram testados com aparelho real).

### Melhorias
- **Ícone da bandeja:** ao parar o mouse em cima, mostra a % de todos os periféricos (útil quando a faixa está escondida em tela cheia ou em outra tela).
- **Segundo aviso:** com 5% ("Bateria acabando · vai desligar logo"), além do aviso de bateria fraca.
- **Dica:** troca de cor na hora quando o Windows muda entre claro e escuro.
- **Testes:** 19 (5 novos).

## 1.2.1 (20/11/2026): correções e revisão de código

### Abre junto com o Windows (correção importante)
- O programa não abria sozinho ao ligar o PC. Agora o "Iniciar com o Windows" usa um atalho na pasta Inicializar (aparece em Configurações > Aplicativos > Inicialização) e o programa espera 10 s para a barra de tarefas, o Bluetooth e o iCUE terminarem de carregar. As versões antigas migram sozinhas.
- Novo arquivo `erros.log` (em `%APPDATA%\BateriaPerifericos`): se algo der errado, fica anotado em vez de sumir calado.

### Previsão de duração
- Antes, a previsão recomeçava do zero a cada recarga ou reinício. Agora o programa guarda o ritmo de uso de cada periférico (30 dias de histórico) e a previsão aparece logo ("Restam ≈ 22 h de uso"). O histórico é gravado a cada minuto e quando o Windows desliga.

### Revisão do código (22 pontos)
- **Ajustes não se perdem mais:** várias partes do programa gravavam ao mesmo tempo e, no teste, a maioria das gravações falhava sem aviso. Agora há uma trava única e uma nova tentativa se falhar. Arquivo de ajustes corrompido vira `.corrompido` em vez de ser apagado.
- **Mouse Attack Shark X11:** o leitor não para mais se der erro (reinicia sozinho) e solta a conexão do receptor ao desligar.
- **Razer:** só pergunta para modelos da lista do razer-battery-report (72, incluindo Basilisk V4 Pro e Viper V4 Pro), com a interface e o tempo de espera certos, repete se o aparelho estiver ocupado, confere a resposta e só abre o canal do mouse (nunca o do teclado). Ainda não testado em aparelho real.
- **Logitech:** reconhece "carga completa" e "carga lenta" (o aviso de carga completa agora dispara), aceita aparelhos que só têm o canal curto e verifica se o aparelho está ligado antes de perguntar (acaba a espera de ~7 s com mouse de cabo).
- **HeadsetControl:** nomes com acento não derrubam mais a leitura, e headsets que não informam a % durante a carga mantêm a última.
- **Antivírus:** o atalho de inicialização e o ícone das notificações só são regravados quando mudam (antes, a cada boot).
- **Menos processador:** de ~0,9% para ~0,2% de um núcleo (o receptor do X11 deixou de ser lido 20 vezes por segundo, a faixa só é redesenhada quando muda e não briga mais com janelas do sistema que ficam por cima).
- **Faixa:** nunca sai da barra ao arrastar; some na hora em jogo de tela cheia (usa o aviso oficial do Windows) e não pisca por cima dele; esconde quando a barra está em "ocultar automaticamente".
- **Menu:** fecha ao clicar fora; nomes com "&" aparecem certos.
- **Ajustes:** botão **Esquecer** para periféricos desligados; não fecha mais o programa em casos raros de memória do Tk.
- **Segurança de código:** declarações de tipos que faltavam nas chamadas do Windows (64 bits), recursos de desenho liberados mesmo se der erro e o "uma cópia só" criado antes de tocar no arquivo de registro.
- **Testes:** novo `testes.py` (14 testes com aparelho de mentira e pasta temporária; não toca nos seus dados).

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
