# ADR-0002 — Grão e modelo de consumo

- Status: aceito
- Data: 16/09/2026

## Contexto

Cadastro e patrimônio têm aproximadamente uma linha por imóvel, enquanto a
infraestrutura possui vários sanitários e reservatórios por imóvel. Um join direto entre
esses grãos multiplicaria áreas e produziria totais incorretos sem erro de execução.

## Decisão

O grão da fato principal é um imóvel por data de referência. Coleções são normalizadas
na Silver e agregadas a esse grão antes de chegar à Gold.

A Gold será uma estrela:

- `dim_imovel`;
- `dim_localidade`;
- `dim_tempo`;
- `fato_imovel_snapshot`.

O comentário no topo da fato declarará o grão e as chaves que o garantem. Um teste de
unicidade composta protegerá `imovel_sk + data_referencia_sk`.

## Alternativas consideradas

### Uma tabela larga desde a Silver

É simples para consultar, mas oculta os grãos diferentes e aumenta o risco de fan-out.

### Uma fato por cada coleção

É dimensionalmente válida, mas excessiva para a pergunta principal e para o tempo de
apresentação. O detalhe continua disponível na Silver.

## Consequências

- medidas detalhadas são agregadas antes dos joins;
- dimensões podem ser reutilizadas nos recortes;
- a consulta final fica pequena;
- os testes de relacionamento substituem as FKs que os arquivos não possuem.

