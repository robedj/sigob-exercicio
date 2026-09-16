{{ config(location='../data/gold/dim_tempo.parquet') }}

-- Grão: uma data de referência presente nos snapshots de imóveis.

select distinct
    cast(strftime(data_referencia, '%Y%m%d') as integer) as data_sk,
    data_referencia as data,
    year(data_referencia) as ano,
    month(data_referencia) as mes,
    quarter(data_referencia) as trimestre
from {{ ref('stg_imoveis') }}
