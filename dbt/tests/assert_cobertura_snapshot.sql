-- Contrato de regressão do recorte versionado entregue.
select *
from {{ ref('agg_aproveitamento_geral') }}
where imoveis_cadastrados <> 102
   or imoveis_com_medicao_patrimonial <> 79
   or imoveis_elegiveis <> 60
