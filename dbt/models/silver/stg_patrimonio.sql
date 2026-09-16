{{ config(location='../data/silver/stg_patrimonio.parquet') }}

-- Grão: uma medição patrimonial por imóvel no levantamento de referência.

with origem as (
    select * from {{ source('bronze', 'patrimonio') }}
),

registros as (
    select
        try_cast(trim(col_01) as integer) as id_predio,
        nullif(trim(col_02), '') as nome_na_fonte,
        case lower(trim(col_03))
            when 'próprio' then 'PROPRIO'
            when 'cedido' then 'CEDIDO'
            when 'alugado' then 'ALUGADO'
            else 'NAO_INFORMADO'
        end as situacao_patrimonial,
        nullif(trim(col_04), '') as area_construida_original,
        nullif(trim(col_05), '') as area_terreno_original,
        nullif(trim(col_06), '') as area_arquivo_original,
        nullif(trim(col_07), '') as observacao_fonte,
        try_cast(_versao_fonte as date) as data_referencia,
        _arquivo_origem,
        try_cast(_linha_origem as integer) as linha_origem
    from origem
    where regexp_matches(trim(col_01), '^[0-9]+$')
)

select
    *,
    -- Ponto e vírgula têm papéis diferentes no formato brasileiro. try_cast mantém uma
    -- falha como NULL, permitindo que testes a detectem sem abortar toda a transformação.
    try_cast(replace(replace(area_construida_original, '.', ''), ',', '.') as decimal(18, 2))
        as area_construida_m2,
    try_cast(replace(replace(area_terreno_original, '.', ''), ',', '.') as decimal(18, 2))
        as area_terreno_m2,
    try_cast(replace(replace(area_arquivo_original, '.', ''), ',', '.') as decimal(18, 2))
        as area_arquivo_m2
from registros
