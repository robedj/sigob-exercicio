-- Garante que a definição da métrica não se desvie da decisão documentada.
select *
from {{ ref('fato_imovel_snapshot') }}
where elegivel_indice_aproveitamento
  and abs(
      indice_aproveitamento_pct -
      round(100.0 * area_construida_m2 / area_terreno_m2, 4)
  ) > 0.0001
