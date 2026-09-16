{{ config(location='../data/silver/quarentena_imoveis.parquet') }}

-- Grão: uma ocorrência cadastral sem chave de negócio confiável.
-- O registro não some e não recebe um ID inventado; permanece auditável fora da Gold.

with origem as (
    select * from {{ source('bronze', 'imoveis') }}
)

select
    _arquivo_origem,
    try_cast(_linha_origem as integer) as linha_origem,
    nullif(trim(col_01), '') as id_predio_original,
    nullif(trim(col_02), '') as nome_original,
    nullif(trim(col_03), '') as classificacao_original,
    nullif(trim(col_05), '') as comarca_original,
    'ID_PREDIO_AUSENTE_OU_INVALIDO' as motivo_quarentena
from origem
where try_cast(_linha_origem as integer) >= 5
  and not regexp_matches(trim(col_01), '^[0-9]+$')
  and nullif(trim(col_02), '') is not null
