select id_predio, data_referencia, posicao, count(*) as ocorrencias
from {{ ref('stg_reservatorios') }}
group by 1, 2, 3
having count(*) <> 1
