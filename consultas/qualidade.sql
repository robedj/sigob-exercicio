-- Cobertura e exceções que acompanham a resposta gerencial.

select
    count(*) as total_imoveis,
    count(area_construida_m2) as com_area_construida,
    count(area_terreno_m2) as com_area_terreno,
    count(indice_aproveitamento_pct) as elegiveis_indice,
    count(sanitarios_total) as com_sanitarios_completos,
    count(capacidade_total_litros) as com_reservacao_informada
from 'data/gold/mart_indicadores_imoveis.parquet';

select *
from 'data/silver/quarentena_imoveis.parquet'
order by arquivo_origem, linha_origem;
