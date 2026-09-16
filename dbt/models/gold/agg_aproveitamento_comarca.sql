{{ config(location='../data/gold/agg_aproveitamento_comarca.parquet') }}

-- Grão: uma comarca e situação patrimonial no snapshot de referência.
-- As duas métricas são calculadas aqui, e não na consulta final.

select
    data_referencia,
    comarca,
    situacao_patrimonial,
    count(*) as imoveis_cadastrados,
    count(indice_aproveitamento_pct) as imoveis_elegiveis,
    round(avg(indice_aproveitamento_pct), 2) as media_indice_individual_pct,
    round(
        100.0 *
        sum(area_construida_m2) filter (where elegivel_indice_aproveitamento) /
        nullif(sum(area_terreno_m2) filter (where elegivel_indice_aproveitamento), 0),
        2
    ) as indice_global_ponderado_pct
from {{ ref('mart_indicadores_imoveis') }}
group by 1, 2, 3
