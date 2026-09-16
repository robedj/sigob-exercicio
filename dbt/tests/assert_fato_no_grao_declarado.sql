-- Falha se um imóvel/data aparecer mais de uma vez na fato.
select imovel_sk, data_referencia_sk, count(*) as ocorrencias
from {{ ref('fato_imovel_snapshot') }}
group by 1, 2
having count(*) <> 1
