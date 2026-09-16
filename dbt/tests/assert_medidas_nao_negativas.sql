-- Áreas e quantidades negativas indicam erro de origem ou de parsing.
select *
from {{ ref('fato_imovel_snapshot') }}
where area_construida_m2 < 0
   or area_terreno_m2 < 0
   or area_arquivo_m2 < 0
   or sanitarios_total < 0
   or capacidade_total_litros < 0
