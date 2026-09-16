{{ config(location='../data/silver/stg_vistorias.parquet') }}

-- Grão: uma vistoria de infraestrutura por imóvel e data de referência.
-- O JSON é aberto somente nesta camada; o Bronze mantém o documento completo.

with origem as (
    select * from {{ source('bronze', 'infraestrutura_predial') }}
),

aberto as (
    select item.value as vistoria_json
    from origem,
         json_each(json_extract(conteudo_json, '$.vistorias')) as item
)

select
    try_cast(json_extract_string(vistoria_json, '$.id_predio') as integer) as id_predio,
    nullif(trim(json_extract_string(vistoria_json, '$.nome_na_fonte')), '') as nome_na_fonte,
    try_cast(json_extract_string(vistoria_json, '$.data_referencia') as date) as data_referencia,
    cast(json_extract(vistoria_json, '$.sanitarios') as varchar) as sanitarios_json,
    cast(json_extract(vistoria_json, '$.reservatorios') as varchar) as reservatorios_json,
    try_cast(nullif(json_extract_string(vistoria_json, '$.loucas.vasos_declarados'), '') as integer)
        as vasos,
    try_cast(nullif(json_extract_string(vistoria_json, '$.loucas.mictorios_declarados'), '') as integer)
        as mictorios,
    try_cast(nullif(json_extract_string(vistoria_json, '$.loucas.lavatorios_declarados'), '') as integer)
        as lavatorios
from aberto
