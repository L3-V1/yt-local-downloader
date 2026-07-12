# YouTube Local Downloader

Miniaplicação web local em FastAPI para pesquisar vídeos públicos do YouTube e iniciar downloads locais autorizados com `yt-dlp`.

## Requisitos

- Windows
- Python 3.11+ instalado
- Node.js 22+ ou Deno instalado para compatibilidade atual com YouTube no `yt-dlp`
- Acesso à internet para pesquisar vídeos públicos e baixar dependências

## Estrutura do projeto

```text
.
├─ main.py
├─ requirements.txt
├─ src/
│  ├─ services/
│  └─ templates/
├─ downloads/
└─ tests/
```

## 1. Criar e ativar o ambiente virtual

No PowerShell, dentro da raiz do projeto:

```powershell
python -m venv .env
.\.env\Scripts\Activate.ps1
```

Se a pasta `.env` já existir, basta ativar:

```powershell
.\.env\Scripts\Activate.ps1
```

## 2. Instalar as dependências

Com o ambiente virtual ativo:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Observação:

- O projeto usa `yt-dlp[default]`, que instala o pacote complementar `yt-dlp-ejs`.
- Para YouTube, o `yt-dlp` também precisa de um runtime JavaScript suportado. Neste projeto, `node` é usado automaticamente quando estiver disponível no `PATH`.

## 3. Rodar a aplicação

Ainda na raiz do projeto:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

Ou, se preferir usar a configuração padrão do projeto:

```powershell
python main.py
```

Depois abra no navegador:

```text
http://localhost:5000
```

## 4. Como usar

1. Acesse a página inicial.
2. Digite um termo de pesquisa.
3. Clique em `Pesquisar`.
4. Escolha um resultado público/autorizado.
5. Clique em `Baixar Vídeo`.
6. Acompanhe o status em `Histórico de Downloads`.

Os arquivos baixados são salvos na pasta local `downloads/`.

## 5. Rodar os testes

```powershell
python -m pytest -q
```

## 6. Observações importantes

- O projeto foi pensado para uso local em `http://localhost:5000`.
- Se o `uvicorn` for executado sem `--port`, ele continuará usando a porta padrão dele, que é `8000`.
- Não há autenticação, login, cookies ou tokens.
- O download deve ser usado apenas para conteúdos públicos e autorizados.
- O sistema não tenta contornar DRM, paywall, login ou restrições de acesso.
