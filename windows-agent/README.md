# Detector de jogos — Soares Reserva AI (Windows)

Este pequeno agente verifica a janela que está em primeiro plano a cada 8 segundos e atualiza o status compartilhado no site. Ele não lê teclado, tela, arquivos pessoais nem captura áudio.

## Configuração

1. Instale o Python 3 no Windows, marcando **Add Python to PATH** durante a instalação.
2. Copie `agent_config.example.json` para um novo arquivo chamado `agent_config.json`.
3. Abra `agent_config.json` e preencha `agent_token` com a chave privada disponibilizada pelo administrador do Render. Não publique nem compartilhe esse arquivo.
4. Execute `run_agent.bat` ou rode `python soares_activity_agent.py` nesta pasta.
5. Deixe o agente aberto enquanto joga. Para parar, pressione Ctrl+C ou feche a janela.

## Jogos reconhecidos

GTA V, FiveM, RAGE MP, Roblox, VALORANT, Counter-Strike 2, League of Legends, Fortnite, Overwatch, Minecraft, Rocket League, Apex Legends, Elden Ring, Palworld, Dead by Daylight, Among Us, Phasmophobia, Destiny 2, Rainbow Six Siege e PUBG.

A detecção usa o processo da janela ativa. Se um jogo não estiver na lista, ele não será exibido até seu executável ser incluído em `GAMES` no script.
