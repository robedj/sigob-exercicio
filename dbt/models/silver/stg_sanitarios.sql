{{ config(location='../data/silver/stg_sanitarios.parquet') }}

-- Grão: um tipo de sanitário declarado por imóvel e vistoria.

select
    v.id_predio,
    v.data_referencia,
    upper(json_extract_string(item.value, '$.tipo')) as tipo_sanitario,
    nullif(json_extract_string(item.value, '$.quantidade_declarada'), '')
        as quantidade_original,
    try_cast(
        nullif(json_extract_string(item.value, '$.quantidade_declarada'), '')
        as integer
    ) as quantidade
from {{ ref('stg_vistorias') }} v,
     json_each(v.sanitarios_json) as item
