-- Protege os números conferidos da pergunta principal.
select *
from {{ ref('agg_aproveitamento_geral') }}
where media_indice_individual_pct <> 37.49
   or indice_global_ponderado_pct <> 35.85
