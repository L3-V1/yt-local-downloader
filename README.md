# YouTube Local Downloader

Miniaplicacao web local em FastAPI para pesquisar videos publicos do YouTube e iniciar downloads locais autorizados com `yt-dlp`.

## Requisitos

- Windows
- Python 3.11+ instalado
- Node.js 22+ ou Deno instalado para compatibilidade atual com YouTube no `yt-dlp`
- Acesso a internet para pesquisar videos publicos e baixar dependencias

## Estrutura do projeto

```text
.
|-- main.py
|-- requirements.txt
|-- src/
|   |-- controllers/
|   |-- routes/
|   |-- services/
|   `-- templates/
|-- downloads/
`-- tests/
```

## 1. Criar e ativar o ambiente virtual

No PowerShell, dentro da raiz do projeto:

```powershell
python -m venv .env
.\.env\Scripts\Activate.ps1
```

Se a pasta `.env` ja existir, basta ativar:

```powershell
.\.env\Scripts\Activate.ps1
```

## 2. Instalar as dependencias

Com o ambiente virtual ativo:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Observacoes:

- O projeto usa `yt-dlp[default]`, que instala o pacote complementar `yt-dlp-ejs`.
- Para YouTube, o `yt-dlp` tambem precisa de um runtime JavaScript suportado. Neste projeto, `node` e usado automaticamente quando estiver disponivel no `PATH`.

## 3. Rodar a aplicacao

Ainda na raiz do projeto:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

Ou, se preferir usar a configuracao padrao do projeto:

```powershell
python main.py
```

Depois abra no navegador:

```text
http://localhost:5000
```

## 4. Como usar

1. Acesse a pagina inicial.
2. Digite um termo de pesquisa ou cole uma URL publica do YouTube.
3. Clique em `Pesquisar`.
4. Escolha um resultado publico/autorizado.
5. Clique em `Baixar Video`.
6. Acompanhe o status em `Historico de Downloads`.
7. Consulte a `Biblioteca de Videos` para reproduzir, transferir, renomear ou excluir arquivos locais.

Os arquivos baixados sao salvos na pasta local `downloads/`.

## 5. Rodar os testes

```powershell
python -m pytest -q
```

## 6. Executar com Docker

O arquivo `docker-compose.yml` esta configurado para usar uma imagem ja criada localmente.

Primeiro, gere a imagem:

```powershell
docker build -t youtube-local-downloader:latest .
```

Depois suba o conteiner:

```powershell
docker compose up -d
```

A aplicacao ficara disponivel em:

```text
http://localhost:5000
```

Os videos baixados ficam persistidos no volume `downloads_data`.

Para encerrar:

```powershell
docker compose down
```

## 7. Observacoes importantes

- O projeto foi pensado para uso local em `http://localhost:5000`.
- Se o `uvicorn` for executado sem `--port`, ele continuara usando a porta padrao dele, que e `8000`.
- Nao ha autenticacao, login, cookies ou tokens.
- O download deve ser usado apenas para conteudos publicos e autorizados.
- O sistema nao tenta contornar DRM, paywall, login ou restricoes de acesso.
