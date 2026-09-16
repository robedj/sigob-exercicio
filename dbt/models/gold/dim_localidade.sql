{{ config(location='../data/gold/dim_localidade.parquet') }}

-- Grão: uma combinação única de comarca, cidade e UF presente no cadastro atual.

select distinct
    md5(
        coalesce(comarca_normalizada, '') || '|' ||
        coalesce(cidade_normalizada, '') || '|' ||
        coalesce(uf, '')
    ) as localidade_sk,
    comarca_normalizada as comarca,
    cidade_normalizada as cidade,
    uf
from {{ ref('stg_imoveis') }}
