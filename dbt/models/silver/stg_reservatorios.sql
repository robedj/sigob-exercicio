{{ config(location='../data/silver/stg_reservatorios.parquet') }}

-- Grão: uma declaração A/B de reservatório por imóvel e vistoria.
-- Uma declaração pode conter várias parcelas (ex.: "2 x 7500 + 10000"). Cada termo
-- reconhecido é calculado e depois somado; texto não reconhecido nunca vira zero.

with declaracoes as (
    select
        v.id_predio,
        v.data_referencia,
        upper(json_extract_string(item.value, '$.posicao')) as posicao,
        nullif(trim(json_extract_string(item.value, '$.capacidade_declarada')), '')
            as capacidade_original,
        nullif(trim(json_extract_string(item.value, '$.material_declarado')), '')
            as material_original
    from {{ ref('stg_vistorias') }} v,
         json_each(v.reservatorios_json) as item
),

termos as (
    select
        d.*,
        unnest(
            regexp_extract_all(
                lower(d.capacidade_original),
                '(?:[0-9]+[[:space:]]*x[[:space:]]*)?[0-9][0-9.]*'
            )
        ) as termo
    from declaracoes d
    where capacidade_original is not null
),

parcelas as (
    select
        *,
        case
            when regexp_matches(termo, 'x')
                then try_cast(regexp_extract(termo, '^([0-9]+)[[:space:]]*x', 1) as bigint)
            else 1
        end as quantidade_parcela,
        try_cast(
            replace(regexp_extract(termo, '([0-9][0-9.]*)$', 1), '.', '')
            as bigint
        ) as capacidade_parcela_litros
    from termos
),

calculado as (
    select
        id_predio,
        data_referencia,
        posicao,
        count(*) as termos_reconhecidos,
        sum(quantidade_parcela * capacidade_parcela_litros) as capacidade_total_litros
    from parcelas
    group by 1, 2, 3
)

select
    d.*,
    c.termos_reconhecidos,
    c.capacidade_total_litros,
    case
        when d.capacidade_original is null then 'SEM_CAPACIDADE_DECLARADA'
        when c.termos_reconhecidos is null then 'NAO_INTERPRETADO'
        else 'INTERPRETADO'
    end as status_interpretacao
from declaracoes d
left join calculado c using (id_predio, data_referencia, posicao)
