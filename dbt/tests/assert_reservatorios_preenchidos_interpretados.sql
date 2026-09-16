-- Capacidade preenchida não pode passar silenciosamente sem interpretação.
select *
from {{ ref('stg_reservatorios') }}
where capacidade_original is not null
  and status_interpretacao <> 'INTERPRETADO'
