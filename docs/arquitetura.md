# Arquitetura e linhagem

## Jornada do dado

```mermaid
flowchart LR
    C1["Cadastro Mestre<br/>2 snapshots CSV"]
    C2["Patrimônio<br/>CSV"]
    J["Infraestrutura<br/>JSON hierárquico"]

    P["Ingestão Python<br/>sem regra de negócio"]

    B1[("Bronze Delta<br/>imóveis v0/v1")]
    B2[("Bronze Delta<br/>patrimônio")]
    B3[("Bronze Delta<br/>infraestrutura")]

    S["Silver dbt<br/>tipar · reconciliar · quarentenar"]
    I["Intermediate<br/>agregar coleções ao grão"]
    G["Gold<br/>estrela + marts"]
    R["Resposta<br/>37,49% · 35,85%"]

    C1 --> P
    C2 --> P
    J --> P
    P --> B1
    P --> B2
    P --> B3
    B1 --> S
    B2 --> S
    B3 --> S
    S --> I --> G --> R
```

## DAG lógica

```mermaid
flowchart LR
    BI[bronze.imoveis] --> SI[stg_imoveis]
    BI --> Q[quarentena_imoveis]
    BP[bronze.patrimonio] --> SP[stg_patrimonio]
    BJ[bronze.infraestrutura] --> SV[stg_vistorias]
    SV --> SS[stg_sanitarios] --> IS[int_sanitarios_por_imovel]
    SV --> SR[stg_reservatorios] --> IR[int_reservatorios_por_imovel]

    SI --> DI[dim_imovel]
    SI --> DL[dim_localidade]
    SI --> DT[dim_tempo]
    DI --> F[fato_imovel_snapshot]
    DL --> F
    DT --> F
    SP --> F
    IS --> F
    IR --> F
    F --> M[mart_indicadores_imoveis]
    M --> AG[agg_aproveitamento_geral]
    M --> AC[agg_aproveitamento_comarca]
```

O grafo oficial da execução é o gerado por `dbt docs`. Este desenho é uma explicação
manual e deve ser conferido contra o `manifest.json` quando a DAG mudar.

## Estrela da Gold

```mermaid
erDiagram
    DIM_IMOVEL ||--o{ FATO_IMOVEL_SNAPSHOT : identifica
    DIM_LOCALIDADE ||--o{ FATO_IMOVEL_SNAPSHOT : localiza
    DIM_TEMPO ||--o{ FATO_IMOVEL_SNAPSHOT : referencia

    DIM_IMOVEL {
        varchar imovel_sk PK
        integer id_predio UK
        varchar nome_oficial
        varchar propriedade
        varchar categoria_funcional
        varchar responsavel_manutencao
    }
    DIM_LOCALIDADE {
        varchar localidade_sk PK
        varchar comarca
        varchar cidade
        varchar uf
    }
    DIM_TEMPO {
        integer data_sk PK
        date data
        integer ano
        integer mes
        integer trimestre
    }
    FATO_IMOVEL_SNAPSHOT {
        varchar imovel_sk FK
        varchar localidade_sk FK
        integer data_referencia_sk FK
        decimal area_construida_m2
        decimal area_terreno_m2
        decimal indice_aproveitamento_pct
        integer sanitarios_total
        bigint capacidade_total_litros
    }
```
