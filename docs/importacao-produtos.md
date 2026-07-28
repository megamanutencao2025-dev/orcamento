# Importação de materiais por URL

O cadastro de materiais possui uma importação assistida. A consulta gera uma
prévia e nunca salva ou atualiza um material automaticamente.

## Lojas suportadas

- Mercado Livre: tenta dados estruturados; quando a plataforma exige
  verificação, mantém o nome derivado da URL e solicita preço manual.
- Amazon Brasil: usa dados estruturados, metadados e campos da página de
  produto.
- Shopee Brasil: usa metadados quando disponíveis; o preço pode exigir
  preenchimento manual.
- Eletrorastro: usa JSON-LD e metadados da página.
- Delupo: usa primeiro o catálogo público VTEX e mantém o HTML como fallback.

Preços de anúncios com variações continuam sujeitos à seleção feita na loja.
Por isso, todo resultado deve ser revisado antes de salvar.

## Segurança

O serviço `cadastros/services/product_import.py`:

- aceita somente HTTP e HTTPS;
- trabalha com uma lista explícita de domínios suportados;
- rejeita credenciais na URL e portas não convencionais;
- resolve e bloqueia endereços privados, locais e reservados;
- revalida cada redirecionamento;
- aplica limite de tempo e tamanho da resposta;
- não executa JavaScript recebido;
- guarda as prévias em cache por cinco minutos.

As imagens são mantidas como URLs externas nesta primeira versão. O navegador
usa `referrerpolicy="no-referrer"` ao exibi-las.

## Categorias

`CategoriaMaterial` é um cadastro independente. O vínculo no material é
opcional para preservar dados antigos, e a exclusão de uma categoria não exclui
seus materiais: eles passam a aparecer como “Sem categoria”.
