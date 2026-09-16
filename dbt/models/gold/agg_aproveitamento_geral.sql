{{ config(location='../data/gold/agg_aproveitamento_geral.parquet') }}

-- Grão: uma data de referência, com a resposta geral e sua cobertura.

select
    data_referencia,
    count(*) as imoveis_cadastrados,
    count(*) filter (where tem_medicao_patrimonial) as imoveis_com_medicao_patrimonial,
    count(indice_aproveitamento_pct) as imoveis_elegiveis,
    round(avg(indice_aproveitamento_pct), 2) as media_indice_individual_pct,
    round(
        100.0 *
        sum(area_construida_m2) filter (where elegivel_indice_aproveitamento) /
        nullif(sum(area_terreno_m2) filter (where elegivel_indice_aproveitamento), 0),
        2
    ) as indice_global_ponderado_pct
from {{ ref('mart_indicadores_imoveis') }}
group by 1
