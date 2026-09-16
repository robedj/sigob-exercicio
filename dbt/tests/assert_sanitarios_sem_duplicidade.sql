select id_predio, data_referencia, tipo_sanitario, count(*) as ocorrencias
from {{ ref('stg_sanitarios') }}
group by 1, 2, 3
having count(*) <> 1
