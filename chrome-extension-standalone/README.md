# YouTube Local Downloader Helper V2

Extensão do Chrome para baixar experimentalmente o vídeo atual do YouTube sem depender da aplicação local.

## Funcionalidades

- detecta o vídeo aberto na aba atual do YouTube;
- permite escolher formato e qualidade do download;
- consulta uma API experimental de terceiros configurável;
- inicia o download no Chrome com seletor de diretório (`saveAs`).

## Instalação

1. Abra `chrome://extensions`.
2. Ative o `Modo do desenvolvedor`.
3. Clique em `Carregar sem compactação`.
4. Selecione a pasta `chrome-extension-v2`.

## Observações importantes

- O modo atual é experimental e depende de uma API de terceiros.
- A instância pública `https://api.cobalt.tools/` não é destinada a integração de terceiros e pode falhar por proteção anti-bot.
- Para uso mais estável, substitua o endpoint por uma instância própria compatível com a API do Cobalt.
- O `manifest` permite endpoints `http` e `https` porque o endereço da API é configurável nesta versão experimental.
- O vídeo precisa estar aberto em uma aba suportada do YouTube.
