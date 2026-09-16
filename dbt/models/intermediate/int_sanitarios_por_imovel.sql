-- Grão: uma linha por imóvel e data de vistoria.
-- O total só existe quando coletivo e privativo foram ambos informados; somar uma parte
-- e tratar a outra como zero criaria uma medida aparentemente completa.

with pivotado as (
    select
        id_predio,
        data_referencia,
        max(case when tipo_sanitario = 'COLETIVO' then quantidade end)
            as sanitarios_coletivos,
        max(case when tipo_sanitario = 'PRIVATIVO' then quantidade end)
            as sanitarios_privativos
    from {{ ref('stg_sanitarios') }}
    group by 1, 2
)

select
    p.*,
    case
        when p.sanitarios_coletivos is not null
         and p.sanitarios_privativos is not null
        then p.sanitarios_coletivos + p.sanitarios_privativos
    end as sanitarios_total,
    p.sanitarios_coletivos is not null
        and p.sanitarios_privativos is not null as tem_sanitarios_completos,
    v.vasos,
    v.mictorios,
    v.lavatorios
from pivotado p
join {{ ref('stg_vistorias') }} v using (id_predio, data_referencia)
