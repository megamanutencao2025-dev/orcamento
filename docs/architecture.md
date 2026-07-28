# Arquitetura

## Contextos da aplicação

O projeto usa Django 5.2 com uma aplicação por contexto de negócio:

- `core`: painel, configuração única e comandos operacionais;
- `cadastros`: materiais, categorias, unidades, serviços, veículos e adicionais;
- `orcamentos`: agregado de orçamento, itens, cálculos e documentos;
- `ferramentas`: análises internas de produtividade e preço real.

HTML semântico, CSS e JavaScript permanecem em `templates/` e `static/`. As
regras de negócio ficam no backend e são cobertas por testes.

## Persistência

O mesmo código aceita dois bancos:

- SQLite, por padrão, para execução local;
- PostgreSQL/Neon quando `DATABASE_URL` está definida.

No Neon, o runtime usa conexão agrupada e desabilita cursores de servidor para
compatibilidade com o PgBouncer em modo transacional. Migrations e
administração usam uma conexão direta separada.

SQLite e Neon não implementam sincronização bidirecional. Depois de uma
migração, apenas um deles deve ser tratado como fonte oficial.

## Execução

- Desenvolvimento: servidor Django.
- Rede local/Tailscale: Waitress em HTTP, com hosts explícitos.
- Internet: Gunicorn no Render, atrás do proxy HTTPS.
- Estáticos: WhiteNoise.
- PDFs: gerados em memória.
- Imagens de produtos: referências por URL externa.

As configurações HTTPS só são ativadas por `DJANGO_HTTPS_MODE`, preservando o
servidor HTTP da rede local.

## Regras de cálculo

As regras não ficam nos templates nem dependem do JavaScript:

- `orcamentos/services.py` calcula e persiste os totais internos;
- `orcamentos/composicao_comercial.py` transforma custos internos em linhas
  comerciais para o cliente;
- `ferramentas/services.py` calcula métricas de produtividade.

Todos os valores financeiros usam `Decimal`.

## Composição comercial da proposta

O resumo interno e os preços apresentados ao cliente são estruturas separadas:

- materiais fornecidos mantêm seu preço comercial;
- insumos, outros custos, reservas e lucro são incorporados à linha de mão de
  obra e serviços;
- materiais que o cliente comprará ficam fora do total;
- a geração do PDF é bloqueada se as linhas comerciais não fecharem exatamente
  com o total final;
- o modo preço global omite os subtotais e mostra somente o total da proposta.

## Implantação e operação

`render.yaml` descreve o serviço online. `scripts/render-build.sh` instala
dependências, coleta estáticos, aplica migrations pela conexão direta e executa
as verificações de produção.

`scripts/Migrate-SqliteToNeon.ps1` faz a transferência inicial com:

- backup externo;
- validação de integridade;
- bloqueio de banco ocupado;
- fixture temporária em UTF-8;
- comparação determinística antes/depois;
- limpeza dos arquivos temporários.

O procedimento operacional está em
[deploy-render-neon.md](deploy-render-neon.md).
