# Extensão para Chrome e Brave

Esta pasta contém uma extensão auxiliar compatível com Chrome e Brave. Ela detecta o vídeo aberto no YouTube e abre o `YouTube Local Downloader` com o link já preenchido no campo de busca.

## Compatibilidade

A extensão usa `Manifest V3` e a API `chrome.*`, que também é suportada pelo Brave por ser baseado em Chromium. Por isso, não foi necessário criar uma versão separada para esse navegador.

## Como carregar no Chrome

1. Abra `chrome://extensions/`.
2. Ative o `Modo do desenvolvedor`.
3. Clique em `Carregar sem compactação`.
4. Selecione a pasta `chrome-extension/`.

## Como carregar no Brave

1. Abra `brave://extensions/`.
2. Ative o `Modo do desenvolvedor`.
3. Clique em `Carregar sem compactação`.
4. Selecione a pasta `chrome-extension/`.

## Como usar

1. Abra um vídeo do YouTube em uma aba do Chrome ou Brave.
2. Clique no ícone da extensão.
3. Confira o link detectado.
4. Se necessário, ajuste o endereço da aplicação local.
5. Clique em `Abrir no app`.

A extensão tentará:

- focar uma aba existente da aplicação local, se ela já estiver aberta
- ou abrir uma nova aba em `http://desenv.local:5000/`

Em ambos os casos, o link do vídeo será enviado como parâmetro `query` para preencher automaticamente o campo de busca da aplicação principal.

## Endereços compatíveis

Por padrão, a extensão já vem configurada para:

- `http://desenv.local:5000/`

Ela também continua compatível com:

- `http://localhost:5000/`

Você pode alterar o endereço diretamente no popup da extensão sempre que precisar.
