

## Nome do estilo

Usar esse modelo nesse projeto

Na terminologia comum de design de interfaces, ele pertence à família
**Modern SaaS Dashboard** ou **Clean Admin Dashboard**: uma interface
minimalista, orientada por cartões, com navegação lateral, bordas discretas,
sombras suaves e cores semânticas. Também pode ser descrito como
**Flat Design 2.0**, porque adiciona profundidade moderada ao flat design.

Os dois modos oficiais são:

- **Cloud Light**: superfícies brancas sobre um fundo cinza-azulado claro.
- **Midnight Navy**: superfícies azul-marinho profundas com contraste frio.

O estilo não é neumorfismo, porque os componentes não parecem extrudados do
fundo, e não é predominantemente glassmorphism, porque transparência e desfoque
não são a base da composição. A topbar possui apenas um tratamento translúcido
discreto. O conjunto usa uma forma leve de **Soft UI**, mas preserva bordas,
contraste e hierarquia típicos de produtos SaaS.

## Assinatura visual

- Layout de dashboard com sidebar fixa, topbar e área de conteúdo ampla.
- Cartões modulares com cantos de 9 a 18 px.
- Elevação discreta; bordas ajudam a separar superfícies nos dois temas.
- Paleta fria e neutra, com azul como cor primária.
- Verde, amarelo e vermelho reservados para estados semânticos.
- Tipografia sans-serif limpa, compacta e orientada à leitura de dados.
- Transições rápidas, entre 150 e 220 ms.
- Mesmos componentes e mesma hierarquia nos dois modos; apenas os tokens mudam.
- Responsividade progressiva: sidebar recolhível, grades fluidas e tabelas
  adaptadas para telas menores.

## Paleta dos modos

Os valores abaixo são a fonte oficial dos temas em
`static/css/variables.css`.

| Token | Cloud Light | Midnight Navy | Uso |
|---|---:|---:|---|
| `--color-bg` | `#f5f7fb` | `#0b1420` | Fundo geral |
| `--color-surface` | `#ffffff` | `#111d2a` | Cartões e painéis |
| `--color-surface-raised` | `#ffffff` | `#142230` | Superfícies elevadas |
| `--color-surface-muted` | `#f8fafc` | `#0e1925` | Áreas internas suaves |
| `--color-surface-hover` | `#f0f5ff` | `#192b3d` | Hover e seleção |
| `--color-sidebar` | `#ffffff` | `#0d1824` | Navegação lateral |
| `--color-text` | `#172033` | `#f4f7fb` | Texto principal |
| `--color-text-soft` | `#526078` | `#bdc8d6` | Texto secundário |
| `--color-text-muted` | `#7a879c` | `#8997aa` | Metadados e ajuda |
| `--color-border` | `#e3e8f1` | `#223246` | Bordas padrão |
| `--color-border-strong` | `#d5dce8` | `#31455d` | Bordas enfatizadas |
| `--color-primary` | `#1768e5` | `#3d83f5` | Ação principal |
| `--color-primary-hover` | `#0e55c5` | `#66a0ff` | Hover primário |
| `--color-primary-soft` | `#eaf2ff` | `#142d4f` | Fundo primário suave |
| `--color-primary-contrast` | `#ffffff` | `#ffffff` | Texto sobre o primário |
| `--color-success` | `#119c6b` | `#35d39a` | Sucesso e disponibilidade |
| `--color-success-soft` | `#e6f7f0` | `#12382f` | Fundo de sucesso |
| `--color-warning` | `#dc8b08` | `#ffc34d` | Atenção |
| `--color-warning-soft` | `#fff6df` | `#3c3019` | Fundo de atenção |
| `--color-danger` | `#dc3f4d` | `#ff6673` | Erro e exclusão |
| `--color-danger-hover` | `#c12c39` | `#ff8791` | Hover destrutivo |
| `--color-danger-soft` | `#fff0f1` | `#42232b` | Fundo de erro |
| `--color-info` | `#2f74d0` | `#6ca8ff` | Informação |
| `--color-info-soft` | `#edf5ff` | `#18314f` | Fundo informativo |

### Sombras

O modo claro usa sombras azul-acinzentadas com opacidade baixa. O modo escuro
usa sombras pretas mais densas para manter a leitura da profundidade:

| Token | Cloud Light | Midnight Navy |
|---|---|---|
| `--shadow-xs` | `0 1px 2px rgb(28 39 58 / 5%)` | `0 1px 2px rgb(0 0 0 / 18%)` |
| `--shadow-sm` | `0 4px 14px rgb(28 39 58 / 7%)` | `0 5px 18px rgb(0 0 0 / 20%)` |
| `--shadow-md` | `0 14px 40px rgb(28 39 58 / 12%)` | `0 18px 50px rgb(0 0 0 / 32%)` |
| `--shadow-focus` | azul a 18% | azul claro a 25% |

## Tokens compartilhados

### Tipografia

```css
--font-sans: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont,
             "Segoe UI", sans-serif;
```

Não há troca de fonte entre os temas. Peso, tamanho e hierarquia também devem
permanecer iguais para evitar mudança de layout ao alternar o modo.

`Inter` é declarada como primeira opção, mas não é baixada pelo projeto. Se ela
não estiver instalada no dispositivo, o navegador usa a fonte nativa do sistema.

### Raios

| Token | Valor |
|---|---:|
| `--radius-xs` | `6px` |
| `--radius-sm` | `9px` |
| `--radius-md` | `13px` |
| `--radius-lg` | `18px` |
| `--radius-pill` | `999px` |

### Espaçamentos

A escala usa múltiplos de 4 px: `4`, `8`, `12`, `16`, `20`, `24`, `32`,
`40` e `48` px, disponíveis de `--space-1` a `--space-12`.

### Movimento

- `--transition-fast`: `150ms ease`
- `--transition-base`: `220ms ease`
- `prefers-reduced-motion: reduce` desativa movimentos não essenciais.

### Estrutura e breakpoints

- Sidebar: `248px`.
- Topbar desktop: `82px`; mobile: aproximadamente `72px`.
- Largura máxima do conteúdo: `1440px`.
- A sidebar se transforma em drawer abaixo de `960px`.
- Topbar e ações são compactadas abaixo de `700px`.
- Cada tela possui breakpoints complementares entre `1200px` e `420px`,
  definidos no seu próprio CSS.

## Como a troca de tema funciona

1. O atributo `data-theme` é aplicado ao elemento `<html>`.
2. Antes do CSS ser renderizado, `templates/base.html` consulta
   `localStorage["pricewise-theme"]`.
3. Sem preferência salva, é usado `prefers-color-scheme` do sistema operacional.
4. Sem preferência reconhecível do sistema, o modo inicial é `light`.
5. `static/js/app.js` expõe `PriceTracker.setTheme("light" | "dark")`.
6. A escolha é persistida novamente no `localStorage`.
7. O botão recebe `aria-pressed` e um rótulo acessível atualizado.
8. A metatag `theme-color` acompanha o fundo do modo ativo.
9. O evento `pricewise:themechange` permite redesenhar elementos dependentes do
   tema, como o gráfico de histórico.

Exemplo para alterar o modo por código:

```javascript
window.PriceTracker.setTheme("dark");
window.PriceTracker.setTheme("light");
```

## Regras para novos componentes

1. Usar tokens semânticos; não duplicar um componente inteiro para cada tema.
2. Não usar branco, preto ou cores de estado diretamente no componente.
3. Usar `--color-surface` para o plano principal e
   `--color-surface-muted` para agrupamentos internos.
4. Separar superfícies com `--color-border`; sombra é apoio, não substituição.
5. Usar azul apenas para ação, foco, navegação ativa e informação relevante.
6. Usar verde, amarelo e vermelho somente com significado de estado.
7. Nunca transmitir um estado apenas pela cor: manter texto, ícone ou rótulo.
8. Preservar foco visível com `--shadow-focus`.
9. Testar contraste, hover, foco, disabled e loading nos dois modos.
10. Manter dimensões e espaçamentos idênticos ao alternar o tema.

Exemplo:

```css
.new-card {
    color: var(--color-text);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-xs);
    transition:
        border-color var(--transition-fast),
        box-shadow var(--transition-fast);
}

.new-card:hover {
    border-color: var(--color-border-strong);
    box-shadow: var(--shadow-sm);
}
```

## Quando adicionar um token

Um novo token deve representar uma intenção reutilizável, não uma tela
específica. Para adicioná-lo:

1. Definir o valor padrão em `:root`.
2. Definir o equivalente em `:root[data-theme="dark"]`.
3. Usar um nome semântico, como `--color-chart-grid`.
4. Verificar contraste nos dois modos.
5. Atualizar a tabela deste documento.

## Compatibilidade técnica

- `color-mix()` é usado para variações semânticas de borda e brilho.
- `backdrop-filter` produz a translucidez sutil da topbar quando disponível.
- Navegadores sem `backdrop-filter` mantêm um fundo funcional, mas sem desfoque.
- Gradientes com valores fixos existem somente em detalhes da marca e
  ilustrações; componentes novos devem preferir tokens.

## Limitações atuais dos modos

- A interface oferece `light` e `dark`, mas não um terceiro estado permanente
  “seguir o sistema”.
- Alterações do tema do sistema depois que a página já abriu não são observadas
  automaticamente.
- Mudanças feitas em outra aba não são sincronizadas pelo evento `storage`.
- Não há testes automatizados exclusivos para o sistema de temas; a validação é
  visual e funcional.
- Alguns textos discretos e cores semânticas não atingem contraste WCAG AA para
  texto pequeno em todas as combinações. Na auditoria atual, merecem atenção:
  texto muted claro sobre branco, warning claro sobre fundo suave, success claro
  sobre fundo suave e branco sobre o azul primário do modo escuro.
- Por isso, cores suaves devem apoiar — nunca substituir — texto, ícone e
  hierarquia.

## Checklist de qualidade

- Tema salvo continua ativo após recarregar a página.
- Primeira visita respeita a preferência do sistema.
- Não há flash perceptível do tema incorreto.
- Texto principal, secundário e muted permanecem legíveis.
- Todos os controles exibem foco de teclado.
- Estados success, warning, danger e info têm texto ou ícone de apoio.
- Textos pequenos são conferidos com uma ferramenta de contraste antes de uma
  declaração formal de conformidade WCAG.
- Gráficos são redesenhados depois de `pricewise:themechange`.
- Light e dark funcionam em desktop e mobile.
- Não surge rolagem horizontal em 390 px.
- A interface respeita `prefers-reduced-motion`.

## Arquivos responsáveis

- `static/css/variables.css`: tokens dos dois modos.
- `static/css/global.css`: estrutura global e comportamento responsivo.
- `apps/products/static/products/css/components.css`: componentes reutilizáveis.
- `templates/base.html`: inicialização antecipada e botão de tema.
- `static/js/app.js`: troca, persistência, acessibilidade e evento de tema.
