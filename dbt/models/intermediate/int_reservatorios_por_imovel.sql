-- Grão: uma linha por imóvel e data de vistoria.
-- A ausência das duas capacidades permanece NULL. Zero só é somado quando foi declarado
-- explicitamente. Qualquer expressão não interpretada invalida o total do imóvel.

select
    id_predio,
    data_referencia,
    count(*) filter (where capacidade_original is not null)
        as declaracoes_capacidade,
    count(*) filter (
        where capacidade_original is not null
          and status_interpretacao <> 'INTERPRETADO'
    ) as declaracoes_nao_interpretadas,
    case
        when count(*) filter (where capacidade_original is not null) = 0 then null
        when count(*) filter (
            where capacidade_original is not null
              and status_interpretacao <> 'INTERPRETADO'
        ) > 0 then null
        else sum(capacidade_total_litros)
    end as capacidade_total_litros,
    count(*) filter (where capacidade_original is not null) > 0
        as tem_reservacao_informada
from {{ ref('stg_reservatorios') }}
group by 1, 2
