# Implantação no Render + Neon

Este guia publica o Gestor Elétrico na internet usando:

- **Render** para executar o Django;
- **Neon** para armazenar os dados em PostgreSQL;
- **GitHub** para entregar o código ao Render.

O resultado usa HTTPS, login obrigatório, arquivos estáticos pelo WhiteNoise e
um banco persistente fora do disco temporário do Render.

## O que já está pronto

| Parte | Preparação |
| --- | --- |
| Django | `DEBUG=False`, hosts do Render e proxy HTTPS |
| Banco | SQLite local ou PostgreSQL conforme `DATABASE_URL` |
| Neon | SSL, conexão agrupada e cursores compatíveis com PgBouncer |
| Servidor | Gunicorn com configuração adequada ao plano gratuito |
| Render | Blueprint versionado em `render.yaml` |
| Estáticos | `collectstatic` e WhiteNoise |
| Disponibilidade | `/health/` testa o processo e o banco |
| Dados atuais | exportação, backup, bloqueio de destino ocupado e validação |
| Segredos | SQLite, backups, fixtures, `.env` e chaves excluídos do Git |

## Visão do funcionamento

```text
Navegador
    │ HTTPS
    ▼
Render / Django ───── DATABASE_URL agrupada (-pooler) ─────► Neon
    │
    └──── deploy automático ◄──── GitHub

Computador local ─── DIRECT_DATABASE_URL ─────────────────► Neon
                     somente migração/administração
```

`DATABASE_URL` é a conexão agrupada usada pelo site. `DIRECT_DATABASE_URL` é a
conexão direta usada por migrations e tarefas administrativas. As duas contêm
senha e nunca devem ser colocadas em arquivo versionado.

## Parte 1 — criar o Neon

Esta etapa depende da sua conta.

1. Acesse [Neon](https://console.neon.tech/) e crie uma conta.
2. Crie um projeto para a aplicação.
3. Escolha a região **AWS US East (N. Virginia)**, próxima do serviço Render
   definido em `render.yaml`.
4. Abra **Connect** no projeto.
5. Com **Connection pooling desativado**, copie a URL direta e guarde-a como
   `DIRECT_DATABASE_URL`.
6. Ative **Connection pooling** e copie a segunda URL, cujo host contém
   `-pooler`. Guarde-a como `DATABASE_URL`.
7. Preserve os parâmetros entregues pelo Neon, especialmente
   `sslmode=require`.

Não envie essas URLs por mensagem, não faça captura de tela com elas e não as
grave no GitHub.

O Neon recomenda a conexão agrupada para aplicações web e a direta para
migrações e ferramentas administrativas:
[documentação de pooling](https://neon.com/docs/connect/connection-pooling).

## Parte 2 — transferir os dados atuais

Faça esta etapa antes de criar o serviço no Render. Assim, o primeiro deploy já
encontrará o administrador e os orçamentos existentes.

1. Encerre a janela do servidor Waitress ou qualquer `runserver`.
2. Confirme que ninguém está cadastrando dados.
3. Abra o PowerShell na pasta do projeto.
4. Execute:

```powershell
.\scripts\Migrate-SqliteToNeon.ps1 -ConfirmLocalServerStopped
```

5. Quando solicitado, cole a **URL direta**, sem `-pooler`. A entrada fica
   oculta.

O script:

1. confirma que a origem é SQLite e verifica sua integridade;
2. cria, pela API nativa do SQLite, um backup consistente fora do projeto;
3. usa essa cópia imutável como origem da exportação em `%TEMP%`, em UTF-8;
4. valida que a URL é direta e pertence ao Neon;
5. bloqueia antes das migrations se o schema já contiver qualquer tabela;
6. aplica as migrations e confirma que só existem os dados iniciais esperados;
7. importa os 32 objetos atuais;
8. reexporta o Neon e compara o hash da fixture integral, além das contagens,
   usuários e valores monetários;
9. confirma a existência do administrador;
10. apaga as fixtures temporárias e remove a URL do processo.

No ensaio local preparado em 28/07/2026, foram preservados:

- 1 usuário administrador;
- 16 unidades de medida;
- 3 categorias, 1 material e 1 serviço;
- 2 orçamentos;
- `ORC-2026-0001`, total de R$ 115,90;
- `OS-002`, total de R$ 630,83.

Se o destino tiver dados ou a comparação falhar, o script interrompe sem apagar
o Neon. Crie outro projeto/branch vazio e repita. Não execute `flush`.

As sessões não são migradas; no site online será necessário entrar novamente
com o mesmo usuário e senha.

## Parte 3 — enviar o código ao GitHub

Esta etapa depende de uma conta e de um repositório GitHub.

O repositório Git local já está inicializado na branch `main`, com os arquivos
de dados excluídos. Não é necessário executar `git init`.

Crie um repositório **privado**, sem adicionar README, `.gitignore` ou licença
pela interface. Depois execute, substituindo a URL:

```powershell
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

Antes do envio, confirme:

```powershell
git status --short
git check-ignore database\db.sqlite3 database\.network-secret
```

Os dois caminhos devem aparecer como ignorados. Backups `*.sqlite3*`, `*.bak`,
fixtures JSON dentro de `database/`, `.env`, mídia local e `staticfiles` também
estão protegidos. As fixtures dos scripts ficam em `%TEMP%` e são apagadas.

## Parte 4 — criar o serviço no Render

1. Acesse o [Dashboard do Render](https://dashboard.render.com/) e crie uma
   conta.
2. Escolha **New > Blueprint**.
3. Conecte a conta GitHub e selecione o repositório.
4. O Render encontrará `render.yaml`.
5. Na criação, preencha:

| Variável | Valor |
| --- | --- |
| `DATABASE_URL` | URL agrupada do Neon, com `-pooler` |
| `DIRECT_DATABASE_URL` | URL direta do Neon, sem `-pooler` |

As outras variáveis são configuradas pelo Blueprint. A chave
`DJANGO_SECRET_KEY` é gerada pelo próprio Render.

6. Confirme a criação e acompanhe o primeiro deploy.

O build instala dependências, coleta os estáticos, aplica migrations pela URL
direta, valida que as duas URLs representam o mesmo banco, confirma o
administrador e executa o checklist de produção. O serviço inicia com Gunicorn
e é monitorado em `/health/`.

Se optar por um banco realmente vazio, sem migrar o usuário atual, adicione
temporariamente estas variáveis no Render:

```text
DJANGO_SUPERUSER_USERNAME=seu_usuario
DJANGO_SUPERUSER_EMAIL=seu_email
DJANGO_SUPERUSER_PASSWORD=uma_senha_forte_com_12_ou_mais_caracteres
```

Faça novo deploy e depois remova `DJANGO_SUPERUSER_PASSWORD`. No fluxo
recomendado, o usuário atual já foi migrado e essas três variáveis não são
necessárias.

## Parte 5 — validação depois do deploy

O Render fornecerá uma URL parecida com:

```text
https://orcamento-eletrico.onrender.com
```

Valide:

- `/health/` responde `status: ok` e `database: available`;
- o login aceita o usuário migrado;
- aparecem 2 orçamentos e o orçamento `OS-002` mantém R$ 630,83;
- um PDF pode ser gerado;
- cadastro manual de material funciona;
- uma importação de produto por URL funciona.

Algumas lojas podem bloquear requisições originadas de datacenters. Portanto,
Mercado Livre, Amazon, Shopee, Eletrorastro e Delupo devem ser testados na URL
do Render, mesmo que funcionem no computador local.

### Domínio próprio opcional

O endereço `*.onrender.com` funciona sem configuração extra. Ao adicionar um
domínio próprio, inclua no painel do Render:

```text
DJANGO_ALLOWED_HOSTS=orcamentos.seudominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://orcamentos.seudominio.com
```

Se houver mais de um host/origem, separe-os por vírgula. Faça novo deploy depois
da alteração.

## Depois do corte

O Neon passa a ser a fonte oficial dos dados. SQLite e Neon não se sincronizam.
Não continue cadastrando no SQLite local depois da migração.

Para os computadores e celulares, use a URL HTTPS do Render. Guarde o backup
SQLite apenas como rollback, sem novas gravações.

Cada `git push` na branch principal inicia um deploy automático. O script de
build reaplica migrations com segurança.

## Limites dos planos gratuitos

Os limites podem mudar; confira as páginas oficiais antes do uso contínuo.

No plano gratuito, o Render:

- suspende o site depois de aproximadamente 15 minutos sem acesso;
- pode levar cerca de um minuto no primeiro acesso depois da suspensão;
- usa disco efêmero, portanto SQLite e uploads locais não são persistentes;
- não oferece shell, SSH, disco persistente ou etapa pre-deploy;
- é indicado pelo próprio Render para hobby e testes, sem garantia de produção.

Veja [Render Free](https://render.com/docs/free) e
[planos de computação](https://render.com/docs/compute-plans).

No plano gratuito, o Neon oferece banco persistente com limites de
armazenamento, computação e tráfego, além de redução automática a zero quando
ocioso. Veja [preços do Neon](https://neon.com/pricing) e
[scale to zero](https://neon.com/docs/introduction/scale-to-zero).

As imagens atuais dos produtos são URLs externas e os PDFs são gerados em
memória, então o disco efêmero não afeta esses recursos hoje. Se futuramente
houver upload real de arquivos, será necessário armazenamento externo.

## Segurança e recuperação

- mantenha o repositório privado;
- ative autenticação em dois fatores no GitHub, Neon e Render;
- use senha exclusiva para o administrador;
- nunca use a URL direta como `DATABASE_URL` do site;
- nunca publique `.env`, banco SQLite, fixture ou backup;
- revise periodicamente usuários e variáveis do Render;
- mantenha backups fora do computador principal.

Crie um backup manual do Neon sem expor a conexão no histórico:

```powershell
.\scripts\Manage-Neon.ps1 -Action Backup
```

Para validar a conexão e o administrador:

```powershell
.\scripts\Manage-Neon.ps1 -Action Check
```

Para recuperar ou alterar a senha sem shell do Render:

```powershell
.\scripts\Manage-Neon.ps1 -Action ChangePassword -Username NOME_DO_USUARIO
```

Nos três casos, o script solicita a URL direta em entrada mascarada, mantém a
conexão apenas no processo atual e a remove ao terminar.

Referências adicionais:

- [Django: checklist de implantação](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Render: Django](https://render.com/docs/deploy-django)
- [Render: variáveis de ambiente](https://render.com/docs/configure-environment-variables)
- [Render: Blueprints](https://render.com/docs/infrastructure-as-code)
- [Django: PostgreSQL](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes)
