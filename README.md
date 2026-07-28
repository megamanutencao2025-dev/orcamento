# Gestor Elétrico

Aplicação Django para cadastro de produtos, composição de custos, criação de
orçamentos e emissão de propostas em PDF.

O projeto pode operar de duas formas:

- localmente, com SQLite e Waitress, pela rede local ou Tailscale;
- online, com Render, PostgreSQL no Neon e Gunicorn.

## Executar localmente

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

## Rede local e Tailscale

```powershell
.\scripts\Start-NetworkServer.ps1
```

O inicializador usa a porta `8010`, configura os hosts detectados, exige login e
mantém o modo HTTP local separado das configurações HTTPS da nuvem.

Para encerrar somente os processos desse servidor:

```powershell
.\scripts\Stop-NetworkServer.ps1
```

Veja [Acesso pela rede](docs/acesso-rede.md).

## Render + Neon

O repositório contém:

- `render.yaml`, com o Web Service gratuito e as variáveis necessárias;
- `scripts/render-build.sh`, com dependências, arquivos estáticos e migrations;
- suporte a `DATABASE_URL` para PostgreSQL sem remover o SQLite local;
- `/health/`, que valida a aplicação e a conexão com o banco;
- migração protegida de SQLite para Neon, com backup e comparação dos dados.

O procedimento completo está em
[Implantação no Render + Neon](docs/deploy-render-neon.md).

## Testes

```powershell
.\.venv\Scripts\python.exe manage.py test
.\scripts\Test-MigrationRoundTrip.ps1
```

O segundo comando ensaia a exportação e a restauração em um banco descartável,
sem alterar o SQLite principal.

Depois da publicação, tarefas seguras de backup, verificação e troca de senha
no Neon ficam disponíveis em:

```powershell
.\scripts\Manage-Neon.ps1 -Action Check
.\scripts\Manage-Neon.ps1 -Action Backup
```

## Organização

- `core/`: painel, configurações e comandos operacionais;
- `cadastros/`: materiais, categorias, unidades, serviços e adicionais;
- `orcamentos/`: itens, cálculos comerciais e PDFs;
- `ferramentas/`: análises internas de produtividade;
- `templates/` e `static/`: interface HTML, CSS e JavaScript;
- `database/`: SQLite local, nunca enviado ao Git;
- `scripts/`: execução local, migração e implantação;
- `docs/`: arquitetura e procedimentos.
