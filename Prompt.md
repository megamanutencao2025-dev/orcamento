Crie um aplicativo para auxiliar um eletricista autônomo na criação e controle de orçamentos elétricos.

Esta é a ETAPA 1 do projeto.

Nesta etapa, desenvolver:

1. Orçamentos
2. Novo Orçamento
3. Cadastros
4. Configurações
5. Exportações em PDF

Não criar ainda o módulo de ferramentas/análises. Esse módulo será criado na Etapa 2.

Objetivo do app:
Criar uma ferramenta operacional para montar orçamentos elétricos, calcular custos internos, montar proposta para cliente e gerar lista de materiais para o cliente comprar.

O app deve separar claramente:

1. Controle interno do eletricista.
2. Proposta enviada ao cliente.
3. Lista de materiais para o cliente comprar.

O resumo financeiro completo é interno e não deve ser exposto ao cliente.

Não sugerir paleta de cores específica.
Usar visual limpo, profissional, compacto e operacional, parecido com sistema interno/ERP leve.
A tela Novo Orçamento deve ser densa, com pouco espaço vazio, fontes menores, inputs compactos, listas compactas e tabelas simples.

Menu principal:

* Orçamentos
* Novo Orçamento
* Cadastros
* Configurações

Página: Orçamentos

Criar uma página para listar todos os orçamentos salvos.

Deve mostrar:

* número do orçamento
* cliente
* data
* validade
* status
* total final
* ações

Ações:

* visualizar
* editar
* excluir
* exportar proposta para cliente
* exportar lista de materiais
* exportar relatório interno

Adicionar:

* busca por cliente ou número
* filtro por status

Status:

* Rascunho
* Enviado
* Aprovado
* Recusado

Página: Novo Orçamento

Essa página é de uso interno, não é uma proposta para cliente.
Ela deve ser compacta e rápida para lançar dados.

Seções da página:

1. Dados do orçamento
2. Materiais fornecidos/cobrados
3. Lista de materiais para o cliente comprar
4. Insumos internos
5. Serviços
6. Custos e modelo financeiro
7. Resumo financeiro interno
8. Observações internas
9. Observações para cliente

Dados do orçamento:

* número
* data
* validade
* status
* nome do cliente
* telefone do cliente
* endereço da obra

Materiais fornecidos/cobrados:
São materiais que o eletricista vai fornecer e cobrar.

Campos para adicionar:

* material cadastrado
* quantidade
* unidade
* preço unitário
* fornecedor
* botão adicionar

Ao adicionar, montar uma tabela compacta com:

* material
* unidade
* quantidade
* preço unitário
* subtotal
* remover

Regra:
subtotal = quantidade x preço unitário

Esses materiais entram no cálculo financeiro.

Lista de materiais para o cliente comprar:
Essa lista é separada e independente dos materiais fornecidos pelo eletricista.

Finalidade:
Criar uma lista para enviar ao cliente comprar.

Campos para adicionar:

* descrição do material
* quantidade
* unidade
* observação opcional
* botão adicionar

Também pode permitir selecionar um material cadastrado apenas como referência, mas o item final deve ser independente.

Ao adicionar, montar uma tabela compacta com:

* descrição
* quantidade
* unidade
* observação
* remover

Regra:
Essa lista NÃO entra no cálculo financeiro.
Essa lista NÃO soma no total do orçamento.
Essa lista deve aparecer na proposta para cliente e no PDF de lista de materiais.

Insumos internos:
São materiais de uso do eletricista.

Exemplos:

* fita isolante
* terminais
* conectores
* abraçadeiras
* buchas
* parafusos
* pequenos consumíveis

Campos para adicionar:

* material cadastrado
* quantidade
* unidade
* preço unitário
* botão adicionar

Ao adicionar, montar tabela compacta:

* insumo
* unidade
* quantidade
* preço unitário
* subtotal
* remover

Regra:
Insumos internos entram no custo interno.
Insumos internos não devem aparecer detalhados na proposta do cliente.

Serviços:
Ao adicionar um serviço, o usuário deve selecionar:

* serviço cadastrado
* quantidade
* preço unitário
* dificuldade opcional
* trabalho em altura opcional
* botão adicionar

A dificuldade e o trabalho em altura devem ser aplicados por item de serviço.

Tabela compacta de serviços:

* serviço
* quantidade
* preço unitário
* dificuldade
* altura
* acréscimos
* total
* remover

Regra por serviço:
subtotal base = quantidade x preço unitário
valor dificuldade = subtotal base x percentual dificuldade / 100
valor altura = subtotal base x percentual altura / 100
subtotal final = subtotal base + valor dificuldade + valor altura

Se não selecionar dificuldade, usar 0%.
Se não selecionar trabalho em altura, usar 0%.

Custos e modelo financeiro:

Separar em três blocos compactos:

Bloco 1: Deslocamento
Campos:

* veículo
* distância em km
* custo deslocamento calculado automaticamente

Regra:
custo deslocamento = distância km / km por litro do veículo x preço combustível

Se não houver veículo selecionado, custo deslocamento = 0.

Bloco 2: Outros custos
Não usar campo fixo de descrição e valor.

Criar lista dinâmica com botão:

* Adicionar custo

Ao clicar em + Adicionar custo, mostrar uma linha compacta com:

* descrição
* valor
* salvar
* cancelar

Após salvar:

* adicionar o item na lista
* recalcular total de outros custos

Cada item deve ter:

* descrição
* valor
* botão remover

Regra:
total outros custos = soma dos itens adicionados

Bloco 3: Mão de obra e percentuais
Campos:

* método de cálculo da mão de obra
* tempo estimado em horas
* valor hora
* percentual para ferramentas
* percentual para empresa
* percentual de lucro líquido

Métodos de cálculo da mão de obra:

1. Por serviços lançados
2. Por tempo estimado x valor hora

Se método = serviços lançados:
valor mão de obra = total final dos serviços

Se método = tempo:
valor mão de obra = tempo estimado x valor hora

Modelo financeiro interno:

Calcular:
subtotal materiais fornecidos = soma dos materiais fornecidos/cobrados
subtotal insumos internos = soma dos insumos internos
subtotal serviços base = soma dos serviços sem acréscimos
total acréscimo dificuldade = soma dos acréscimos de dificuldade
total acréscimo altura = soma dos acréscimos de altura
subtotal serviços final = soma dos serviços com acréscimos
outros custos total = soma dos outros custos
custos diretos = materiais fornecidos + insumos internos + deslocamento + outros custos
valor mão de obra = conforme método escolhido
reserva ferramentas = valor mão de obra x percentual ferramentas / 100
subtotal operacional = custos diretos + valor mão de obra + reserva ferramentas
reserva empresa = subtotal operacional x percentual empresa / 100
subtotal antes do lucro = subtotal operacional + reserva empresa
lucro líquido = subtotal antes do lucro x percentual lucro líquido / 100
total final = subtotal antes do lucro + lucro líquido

Regra importante:
Mão de obra não é lucro.
Lucro líquido é apenas o que sobra depois de custos, mão de obra, ferramentas e reserva da empresa.

Resumo financeiro interno:
Mostrar em formato compacto, sem vários cards grandes.

Mostrar:

* materiais fornecidos
* insumos internos
* lista de materiais para cliente comprar, apenas informativo e sem somar
* serviços base
* acréscimo por dificuldade
* acréscimo por altura
* total dos serviços
* método de mão de obra
* valor da mão de obra
* deslocamento
* outros custos
* custos diretos
* reserva para ferramentas
* reserva da empresa
* lucro líquido
* total final

Adicionar aviso:
“Resumo financeiro interno. Não será exibido na proposta do cliente.”

Cadastros:

Criar página Cadastros com abas ou seções internas:

1. Materiais
2. Serviços
3. Veículos
4. Dificuldades
5. Trabalho em Altura

Não criar páginas separadas para esses cadastros no menu principal.

Cadastro de Materiais:
Campos:

* nome
* unidade de medida
* preço unitário
* fornecedor
* tipo de uso

Tipo de uso:

* Material fornecido/cobrado
* Insumo interno
* Referência para lista do cliente

Explicação:
Material fornecido/cobrado:
Material que o eletricista fornece e cobra.

Insumo interno:
Material de uso do eletricista, como fita, terminais, conectores, abraçadeiras, buchas e parafusos.

Referência para lista do cliente:
Material usado apenas como referência para montar lista de compra do cliente.

Cadastro de Serviços:
Campos:

* nome do serviço
* unidade
* preço unitário
* descrição opcional

Cadastro de Veículos:
Campos:

* nome/modelo
* km por litro
* preço do combustível

Cadastro de Dificuldades:
Campos:

* nome
* percentual
* descrição opcional

Exemplos:

* Fácil — 0%
* Média — 10%
* Difícil — 20%
* Muito difícil — 35%

Cadastro de Trabalho em Altura:
Campos:

* nome
* percentual
* descrição opcional

Exemplos:

* Sem altura — 0%
* Escada baixa — 10%
* Escada alta — 15%
* Andaime — 20%
* Plataforma elevatória — 30%

Configurações:

Criar página Configurações com:

* nome do eletricista
* telefone
* e-mail
* cidade
* validade padrão do orçamento em dias
* valor hora padrão
* percentual padrão para ferramentas
* percentual padrão para empresa
* percentual padrão de lucro líquido
* mostrar deslocamento na proposta do cliente: sim/não
* observação padrão para cliente
* observação padrão interna

Essas configurações devem preencher novos orçamentos automaticamente.

Exportações:

Criar três exportações diferentes.

1. Exportar proposta para cliente

A proposta para cliente deve mostrar:

* dados do eletricista
* número do orçamento
* data
* validade
* nome do cliente
* telefone do cliente, se existir
* endereço da obra
* valor da mão de obra
* valor dos materiais fornecidos pelo eletricista
* deslocamento, somente se estiver habilitado nas configurações
* total da proposta
* lista de materiais para o cliente comprar
* observações para cliente
* rodapé simples

A proposta para cliente NÃO deve mostrar:

* valor hora
* tempo estimado
* reserva para ferramentas
* reserva da empresa
* lucro líquido
* insumos internos detalhados
* outros custos internos
* custos diretos
* subtotal operacional
* subtotal antes do lucro
* dificuldade detalhada
* altura detalhada
* distribuição interna do valor
* resumo financeiro completo

2. Exportar lista de materiais

Deve mostrar somente:

* dados do eletricista
* número do orçamento
* data
* cliente
* endereço da obra
* título: Lista de materiais para compra
* descrição do material
* quantidade
* unidade
* observação
* rodapé simples

Não mostrar preços por padrão.

3. Exportar relatório interno

Esse documento é somente para controle do eletricista.

Deve mostrar:

* dados do orçamento
* materiais fornecidos
* materiais para cliente comprar
* insumos internos
* serviços
* deslocamento
* outros custos
* cálculo de mão de obra
* reserva para ferramentas
* reserva da empresa
* lucro líquido
* distribuição do valor
* total final

Deixar claro no título:
Relatório interno

Entidades necessárias no Base44:

Criar entidades para:

* Materiais
* Serviços
* Veículos
* Dificuldades
* TrabalhoAltura
* Orçamentos
* Configurações

A entidade Orçamentos deve guardar todos os dados do orçamento, incluindo:

* dados do cliente
* status
* materiais fornecidos
* lista de materiais para cliente comprar
* insumos internos
* serviços
* outros custos
* deslocamento
* método de mão de obra
* percentuais financeiros
* totais calculados
* observações internas
* observações para cliente

Validações:

* Não permitir salvar orçamento sem nome do cliente.
* Não permitir salvar orçamento completamente vazio.
* Não permitir quantidade menor ou igual a zero.
* Não permitir preço negativo.
* Não permitir percentual negativo.
* Não permitir km por litro menor ou igual a zero no cadastro de veículo.
* Não permitir custo negativo.
* Mostrar mensagens amigáveis.

Layout:
A tela Novo Orçamento deve ser compacta.

Requisitos visuais:

* fontes menores
* inputs baixos
* cards com pouco espaçamento interno
* tabelas compactas
* botões pequenos
* empty states discretos
* sem áreas vazias grandes
* sem cards grandes para cada item financeiro
* o resumo financeiro deve ser uma lista/tabela compacta
* somente o total final deve ter destaque maior

No desktop:

* aproveitar a largura horizontal
* usar linhas compactas para adicionar itens
* usar tabelas compactas

No mobile:

* empilhar campos
* manter leitura simples
* usar cards compactos quando tabela ficar ruim

Critérios de aceite:
Ao final da Etapa 1, o app deve permitir:

* cadastrar materiais
* cadastrar serviços
* cadastrar veículos
* cadastrar dificuldades
* cadastrar trabalho em altura
* configurar dados padrão
* criar orçamento
* adicionar materiais fornecidos
* adicionar lista de materiais para o cliente comprar
* adicionar insumos internos
* adicionar serviços com dificuldade e altura
* adicionar outros custos por botão +
* remover itens adicionados
* calcular deslocamento
* calcular mão de obra por serviço ou por tempo
* calcular reserva para ferramentas
* calcular reserva da empresa
* calcular lucro líquido
* mostrar resumo financeiro interno
* salvar orçamento
* listar orçamentos
* visualizar orçamento
* editar orçamento
* excluir orçamento
* exportar proposta para cliente
* exportar lista de materiais
* exportar relatório interno



Agora implemente a ETAPA 2 do app de orçamentos elétricos.

A Etapa 1 já deve existir com:

* Orçamentos
* Novo Orçamento
* Cadastros
* Configurações
* Proposta para cliente
* Lista de materiais
* Relatório interno

Nesta Etapa 2, criar um novo módulo no menu principal:

Ferramentas

Dentro de Ferramentas, criar a ferramenta:

Análise de produtividade e preço real

Objetivo:
Permitir que o eletricista registre serviços já executados, informando valor total cobrado, custos, materiais, deslocamento, outros custos, serviços realizados, quantidades e tempo gasto. O sistema deve calcular produtividade, valor da hora real, tempo por unidade e preço unitário sugerido para cada serviço.

Esse módulo serve para aprender com serviços já executados e melhorar os preços cadastrados no app.

Página: Ferramentas

Criar uma página com:

* título Ferramentas
* card ou aba Análise de produtividade e preço real
* histórico de análises salvas

Ferramenta: Análise de produtividade e preço real

Campos principais:

* nome da análise/referência
* data
* cliente ou descrição da obra
* valor total cobrado
* valor de materiais
* valor de deslocamento
* outros custos
* valor base de mão de obra calculado
* observações

Regra:
valor base de mão de obra = valor total cobrado - valor de materiais - valor de deslocamento - outros custos

Itens executados:

Permitir adicionar várias tarefas/serviços executados.

Campos por item:

* serviço cadastrado, opcional
* nome do serviço
* unidade
* quantidade executada
* tempo gasto em horas
* quantidade de pessoas
* horas-homem calculadas
* dificuldade opcional
* trabalho em altura opcional
* observações

Regra por item:
horas-homem = tempo gasto em horas x quantidade de pessoas

Depois de adicionar os itens, calcular:

horas-homem total = soma das horas-homem de todos os itens

valor hora real = valor base de mão de obra / horas-homem total

Para cada item:
valor calculado do serviço = horas-homem do item x valor hora real

valor unitário sugerido = valor calculado do serviço / quantidade executada

produtividade = quantidade executada / horas-homem do item

tempo por unidade = horas-homem do item / quantidade executada

Exemplo:
Se foram executados:

* 90 metros de eletroduto em 6 horas com 1 pessoa
* 90 metros de cabo em 4 horas com 1 pessoa
* 23 lâmpadas em 5 horas com 2 pessoas

O sistema deve calcular:

* horas-homem de cada tarefa
* total de horas-homem
* valor hora real
* produtividade de cada serviço
* tempo por unidade
* preço unitário sugerido

Resumo da análise:

Mostrar:

* valor total cobrado
* materiais descontados
* deslocamento descontado
* outros custos descontados
* valor base de mão de obra
* horas-homem totais
* valor hora real

Tabela de resultados:

Mostrar por item:

* serviço
* quantidade
* unidade
* tempo gasto
* pessoas
* horas-homem
* produtividade
* tempo por unidade
* valor calculado
* valor unitário sugerido

Ações:

* salvar análise
* excluir análise
* visualizar análise salva
* aplicar preço sugerido ao cadastro de serviço

Aplicar preço sugerido ao cadastro de serviço:

Se o item estiver vinculado a um serviço cadastrado, permitir botão:
Aplicar preço sugerido

Ao clicar:

* pedir confirmação
* atualizar o preço unitário do serviço cadastrado com o valor unitário sugerido

Também salvar no serviço, se possível:

* último preço sugerido
* última produtividade calculada
* último tempo por unidade
* data da última análise

Histórico de análises:

A página Ferramentas deve mostrar histórico de análises salvas com:

* data
* nome da análise
* cliente/obra
* valor total cobrado
* valor base de mão de obra
* horas-homem totais
* valor hora real
* quantidade de itens analisados
* botão visualizar
* botão excluir

Entidades necessárias:

Criar entidade:
AnalisesProdutividade

A entidade deve guardar:

* nome da análise
* data
* cliente/obra
* valor total cobrado
* valor de materiais
* valor de deslocamento
* outros custos
* valor base de mão de obra
* itens executados
* horas-homem total
* valor hora real
* observações
* data de criação
* data de atualização

Cada item executado deve conter:

* serviço vinculado, opcional
* nome do serviço
* unidade
* quantidade executada
* tempo gasto
* quantidade de pessoas
* horas-homem
* dificuldade
* altura
* valor calculado
* valor unitário sugerido
* produtividade
* tempo por unidade
* observações

Validações:

* Não permitir análise sem nome.
* Não permitir valor total cobrado menor ou igual a zero.
* Não permitir quantidade executada menor ou igual a zero.
* Não permitir tempo menor ou igual a zero.
* Não permitir quantidade de pessoas menor ou igual a zero.
* Não permitir salvar análise sem pelo menos um item executado.
* Não permitir calcular se horas-homem total for zero.

Layout:
Manter visual compacto e operacional, igual ao restante do app.

A tela deve ser parecida com uma ferramenta de análise interna, não uma proposta para cliente.

Usar:

* formulários compactos
* tabelas compactas
* resumo em lista/tabela
* botões claros
* pouco espaço vazio
* fontes menores
* inputs baixos

Não sugerir paleta de cores específica.

Importante:

* Não alterar as regras já existentes da Etapa 1.
* Não quebrar orçamentos.
* Não quebrar cadastros.
* Não quebrar PDFs.
* Não misturar essa ferramenta com proposta para cliente.
* Essa ferramenta é apenas para análise interna.

Critérios de aceite:
Ao final da Etapa 2, o app deve permitir:

* abrir o módulo Ferramentas
* criar análise de produtividade
* informar valor total cobrado e custos
* adicionar serviços executados
* informar quantidade, tempo e pessoas por serviço
* calcular horas-homem
* calcular valor hora real
* calcular produtividade
* calcular tempo por unidade
* calcular preço unitário sugerido
* salvar análise
* visualizar histórico de análises
* excluir análise
* aplicar preço sugerido ao cadastro de serviço
