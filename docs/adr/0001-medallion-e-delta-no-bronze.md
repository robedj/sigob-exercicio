# ADR-0001 — Medallion e Delta Lake no Bronze

- Status: aceito
- Data: 16/09/2026

## Contexto

A PoC precisa preservar o dado capturado, transformar com dbt, reconstruir tudo do zero
e demonstrar pelo menos duas versões com time travel. Também precisa ser executável
localmente, sem Spark ou servidor de banco.

## Decisão

Usar Raw → Bronze → Silver → Gold. Raw contém as entregas CSV/JSON; Bronze usa Delta
Lake via biblioteca Python `deltalake`; Silver e Gold usam Parquet; DuckDB executa o SQL
do dbt e serve as consultas.

A ingestão registra metadados técnicos, mas não interpreta os valores. Remoção de
cabeçalhos de planilha, conversão de decimal brasileiro e reconciliação pertencem à
Silver.

## Alternativas consideradas

### Somente Parquet

Mais simples, mas não atende sozinho ao requisito de versionamento e time travel.

### Delta em todas as camadas

Possível, porém amplia dependências e superfície de falha sem benefício necessário para
esta PoC. O requisito de histórico está concentrado na preservação.

### Banco relacional local

Entregaria constraints, mas esconderia a separação entre armazenamento e processamento
que a atividade quer demonstrar e não resolveria o time travel pedido.

## Consequências

- o pipeline precisa provar compatibilidade entre as versões fixadas de `deltalake`,
  DuckDB e dbt-duckdb;
- a demo pode comparar a mesma tabela Bronze em duas versões;
- Silver e Gold continuam fáceis de inspecionar como arquivos;
- o README deve explicar claramente como reconstruir o histórico.

