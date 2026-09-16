# Fontes e qualidade dos dados

## Recorte

A PoC usa somente o domínio de Imóveis. Usuários, Terceirizados, Documentos/S3,
hierarquia organizacional, obras e projetos ficam fora do pipeline. Eles foram lidos
para evitar misturar responsabilidades, mas não são necessários para responder à
pergunta escolhida.

`docs-sigob/` é referência local ignorada pelo Git. As fontes necessárias ao clone limpo
serão preparadas e versionadas em `data/raw/`, sem dados pessoais.

## Inventário observado

| Conjunto local | Linhas úteis | Observação |
|---|---:|---|
| Cadastro Mestre | 103 | 102 IDs válidos e 1 imóvel sem ID |
| Patrimônio | 79 | 60 áreas de terreno e 76 áreas construídas preenchidas |
| Sanitários | 79 | quantidades inteiras, com vazios e zeros distintos |
| Reservatórios | 79 | capacidades em texto semiestruturado |

Entre os 102 imóveis identificados, 23 PIDs (IDs 200–222) não aparecem no levantamento
patrimonial. Isso é uma limitação de cobertura, não uma licença para preencher zero.

## Defeitos e decisões esperadas

| Defeito/ambiguidade | Camada | Tratamento |
|---|---|---|
| linhas de título e nota antes do cabeçalho | Silver | identificar estrutura sem perder o Bronze |
| BOM, `;` e decimal brasileiro | Silver | normalização e `try_cast` |
| imóvel sem ID | Silver | quarentena |
| texto composto em `Tipo de Imóvel` | Silver | mapa explícito de conceitos |
| nomes repetidos entre fontes | Silver | cadastro mestre prevalece; join por ID |
| PIDs sem medição | Gold | manter imóvel, medidas nulas e flag de cobertura |
| reservatório `2 x 7500` | Silver | quantidade × capacidade |
| múltiplas parcelas na mesma célula | Silver | abrir parcelas reconhecidas; quarentenar resto |
| vazio versus zero | Silver/Gold | preservar semânticas diferentes |
| coleções 1:N | Gold | agregar antes de juntar à fato |

## Perfil preliminar da métrica principal

Dos 79 registros patrimoniais, 60 têm área construída e área de terreno suficientes para
o índice. A exploração inicial encontrou:

- média simples dos índices individuais: 37,49%;
- mediana: 21,78%;
- razão entre a soma das áreas: 35,85%;
- imóveis com mais de 100% existem e podem representar vários pavimentos.

Esses números são hipóteses de conferência. O valor da entrega será o produzido pela
Gold, após os testes.

## Rastreabilidade

Cada registro Bronze terá arquivo, versão, instante, hash e posição de origem. A Silver
manterá colunas brutas relevantes ao lado das normalizadas quando uma decisão puder ser
auditada.

