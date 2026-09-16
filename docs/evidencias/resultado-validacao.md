# Evidência da validação integral

- Data: 16/09/2026
- Python: 3.10.12
- dbt-core: 1.11.15
- dbt-duckdb: 1.11.0
- DuckDB: 1.5.5
- Delta Lake (`deltalake`): 1.6.3

## Método

Foi criado um clone local isolado do repositório. Nesse clone, `scripts/zerar.py`
removeu Bronze, Silver, Gold e o catálogo; `data/raw/` permaneceu intacto. Toda a
jornada abaixo foi reconstruída sem `docs-sigob/`, `estrategia.md` ou ajustes manuais.
A instalação usada passou também em `pip check`, sem dependências quebradas.

## Ingestão e testes Python

```text
imoveis: versão Delta atual 1
patrimonio: versão Delta atual 0
infraestrutura_predial: versão Delta atual 0
6 passed
```

## dbt build

```text
Found 15 models, 54 data tests, 3 sources
PASS=69 WARN=0 ERROR=0 SKIP=0 TOTAL=69
```

## Resposta geral

| Data | Cadastrados | Com medição | Elegíveis | Média individual | Índice global |
|---|---:|---:|---:|---:|---:|
| 17/08/2026 | 102 | 79 | 60 | 37,49% | 35,85% |

## Time travel

Mesma consulta aplicada às duas versões:

```text
versão 0 (anterior): 101 imóveis com ID; 1 registro sem ID
versão 1 (atual): 102 imóveis com ID; 1 registro sem ID
```

## Linhagem

`dbt docs generate` concluiu e produziu `target/catalog.json`. Os artefatos gerados não
são versionados; podem ser reconstruídos pelos comandos do README.

## Consultas de consumo e qualidade

`consultas/resposta.sql` foi executada somente contra a Gold e devolveu os valores da
tabela acima, além do recorte por comarca e situação patrimonial.
`consultas/qualidade.sql` confirmou 102 imóveis, 76 com área construída, 60 com área de
terreno e uma ocorrência na quarentena com o motivo
`ID_PREDIO_AUSENTE_OU_INVALIDO`.
