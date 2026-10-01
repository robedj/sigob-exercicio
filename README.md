# PoC de Engenharia de Dados — Imóveis do SIGOB

Pipeline completo da disciplina de Gestão e Governança de Dados, aplicado a um recorte
do domínio de Imóveis do SIGOB/TJMS.

```text
CSV + JSON → Python → Bronze Delta → dbt/DuckDB → Silver → Gold → resposta
```

## Pergunta de negócio

> Qual é o índice de aproveitamento construtivo dos imóveis geridos pelo TJMS e como ele
> varia por comarca e situação patrimonial?

A métrica não existe pronta nas fontes:

```text
índice individual (%) = área construída / área do terreno × 100
```

O pipeline também distingue dois números que parecem iguais, mas não são:

- **37,49%** — média aritmética dos índices dos imóveis elegíveis;
- **35,85%** — razão global entre a soma das áreas construídas e a soma dos terrenos.

Cobertura da resposta: 102 imóveis identificados, 79 com medição patrimonial e 60 com as
duas áreas necessárias. Registros sem medição continuam visíveis; não viram zero.

A resposta é materializada em dois lugares, ambos gerados pelo pipeline:

- `consultas/resposta.sql` — SQL sobre a Gold, sem regra de negócio no `WHERE`;
- `data/gold/dashboard.html` — painel com filtros de comarca e situação patrimonial,
  gerado por `python scripts/gerar_dashboard.py` ao final do ciclo.

## Execução em clone limpo

Requisitos: Python 3.10 ou superior, Git e acesso à internet na primeira execução para
instalar dependências e a extensão oficial Delta do DuckDB.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --no-cache-dir -r requirements.txt
cp .env.example .env

python -m src.pipeline
cd dbt
dbt build
cd ..

python scripts/executar_sql.py consultas/resposta.sql
python scripts/gerar_dashboard.py
```

O último comando publica `data/gold/dashboard.html`, que responde à pergunta do início
com filtros de comarca e situação patrimonial. Abra com `xdg-open data/gold/dashboard.html`.

Resultado esperado do `dbt build`:

```text
PASS=69 WARN=0 ERROR=0 SKIP=0 TOTAL=69
```

São 15 modelos e 54 testes de dados. Separadamente, os testes do código de ingestão são:

```bash
pytest
# 6 passed
```

## Time travel do Delta Lake

O Cadastro Mestre possui duas versões reais do processo de consolidação:

- versão 0: antes da classificação da Casa da Mulher como PID 223;
- versão 1: snapshot atual, após a decisão R-11.

```bash
python scripts/demonstrar_time_travel.py
```

Saída esperada:

```text
versão 0 (anterior): 101 imóveis com ID; 1 registro sem ID
versão 1 (atual): 102 imóveis com ID; 1 registro sem ID
```

A consulta é idêntica nas duas versões; somente o snapshot muda.

## Reprocessar desde o zero

```bash
python scripts/zerar.py
python -m src.pipeline
cd dbt && dbt build && cd ..
python scripts/gerar_dashboard.py
```

O `dbt build` depende das pastas criadas por `python -m src.pipeline`; execute os dois na
ordem acima. `zerar.py` remove exclusivamente Bronze, Silver, Gold, catálogo DuckDB e artefatos do
dbt. As fontes de `data/raw/`, o código e os documentos são preservados.

## Linhagem

```bash
cd dbt
dbt docs generate
dbt docs serve
```

A DAG nasce dos `source()` e `ref()` usados pelos modelos. Uma visão comentada está em
[`docs/arquitetura.md`](docs/arquitetura.md).

## Fontes

| Fonte | Formato | Grão |
|---|---|---|
| Cadastro Mestre — dois snapshots | CSV `;` | uma linha por imóvel cadastrado |
| Patrimônio | CSV `;` | uma medição por imóvel |
| Infraestrutura predial | JSON hierárquico | uma vistoria por imóvel, com coleções |

As fontes entregáveis estão em `data/raw/` e não contêm dados pessoais. A pasta local
`docs-sigob/` serviu apenas para preparar o recorte, é ignorada pelo Git e não é
necessária para executar o projeto.

## O que cada camada faz

| Camada | Responsabilidade |
|---|---|
| Raw | arquivos recebidos/versionados, sem alteração pelo pipeline |
| Bronze | preservação em Delta, com hash, origem, linha e instante de ingestão |
| Silver | estrutura, tipagem, reconciliação, parsing e quarentena |
| Intermediate | redução de coleções 1:N ao grão imóvel/data |
| Gold | estrela, métricas oficiais, cobertura e tabelas de resposta |

A ingestão preserva inclusive títulos de planilha, cabeçalhos, decimal brasileiro e o
imóvel sem ID. Essas interpretações só acontecem no dbt.

## Modelo de consumo

O grão de `fato_imovel_snapshot` é:

> uma linha por imóvel e data de referência.

As coleções de sanitários e reservatórios são agregadas antes da fato. O teste
`assert_fato_no_grao_declarado` impede fan-out silencioso.

As dimensões são:

- `dim_imovel`;
- `dim_localidade`;
- `dim_tempo`.

Para consumo direto, `mart_indicadores_imoveis` reúne fato e dimensões, enquanto
`agg_aproveitamento_geral` e `agg_aproveitamento_comarca` armazenam as respostas prontas.

## Dashboard

```bash
python scripts/gerar_dashboard.py
xdg-open data/gold/dashboard.html
```

Arquivo único, sem servidor e sem dependência além das já declaradas. Ele cobre a jornada
inteira, em seis abas:

| Aba | Conteúdo |
|---|---|
| Resposta | KPIs, filtros de comarca e situação, índice por comarca e detalhe por imóvel |
| Etapas do pipeline | Raw, defeitos preservados, versões Delta, time travel, modelos por camada, fan-out evitado e onde cada coisa é calculada |
| Linhagem | DAG desenhada a partir do `manifest.json` real, e o que alimenta ou não a resposta |
| Registros incompletos | por que 42 dos 102 ficam fora do índice, imóvel por imóvel, e a quarentena |
| Qualidade | 54 testes dbt por tipo, os 9 singulares com status e os 6 testes de ingestão |
| Execução | `run_results.json` real: recursos, status, tempos e ambiente |

O painel não recalcula a fórmula e não corrige dado: lê as medidas já calculadas e testadas
na Gold e apenas filtra, agrega e exibe.

## Qualidade e exceções

Algumas decisões protegidas por testes:

- ID de imóvel obrigatório e único;
- relacionamentos de Patrimônio/Infraestrutura com o Cadastro Mestre;
- domínios aceitos para UF, propriedade, situação, sanitário e reservatório;
- áreas e quantidades não negativas;
- fórmula exata do índice;
- 102 linhas na fato, uma por imóvel, sem multiplicação por coleções;
- imóvel sem ID preservado em quarentena;
- todas as 82 capacidades preenchidas interpretadas;
- resposta e cobertura esperadas para os snapshots versionados.

Detalhes: [`docs/testes.md`](docs/testes.md) e
[`docs/fontes-e-qualidade.md`](docs/fontes-e-qualidade.md).

## Estrutura

```text
.
├── data/
│   ├── raw/                 # CSV e JSON versionados
│   ├── bronze/              # Delta Lake, incluindo _delta_log
│   ├── silver/              # Parquet gerado pelo dbt
│   └── gold/                # Parquet gerado pelo dbt + dashboard.html
├── src/                     # ingestão Python
├── dbt/                     # transformações, testes e documentação
├── consultas/               # resposta e auditoria de cobertura
├── scripts/                 # time travel, dashboard, reset e preparação
├── tests/                   # testes Python
├── DECISOES.md              # quatro decisões exigidas
└── docs/                    # ADRs, arquitetura, testes e apresentação
```

## Documentação

- [`DECISOES.md`](DECISOES.md) — decisões obrigatórias;
- [`docs/README.md`](docs/README.md) — índice;
- [`docs/adr/`](docs/adr/) — registros arquiteturais;
- [`docs/apresentacao.md`](docs/apresentacao.md) — roteiro de 20 minutos.
