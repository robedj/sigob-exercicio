{{ config(location='../data/gold/fato_imovel_snapshot.parquet') }}

-- GRÃO: uma linha por imóvel e data de referência do snapshot cadastral.
-- Patrimônio, sanitários e reservatórios chegam a este modelo já reduzidos ao mesmo
-- grão. Juntar as coleções detalhadas aqui causaria fan-out e corromperia áreas/médias.

with base as (
    select
        i.id_predio,
        i.data_referencia,
        di.imovel_sk,
        dl.localidade_sk,
        dt.data_sk as data_referencia_sk,
        coalesce(p.situacao_patrimonial, 'NAO_INFORMADO') as situacao_patrimonial,
        p.area_construida_m2,
        p.area_terreno_m2,
        p.area_arquivo_m2,
        s.sanitarios_coletivos,
        s.sanitarios_privativos,
        s.sanitarios_total,
        coalesce(s.tem_sanitarios_completos, false) as tem_sanitarios_completos,
        s.vasos,
        s.mictorios,
        s.lavatorios,
        r.capacidade_total_litros,
        coalesce(r.tem_reservacao_informada, false) as tem_reservacao_informada,
        p.id_predio is not null as tem_medicao_patrimonial,
        s.id_predio is not null as tem_vistoria_infraestrutura
    from {{ ref('stg_imoveis') }} i
    join {{ ref('dim_imovel') }} di using (id_predio)
    join {{ ref('dim_localidade') }} dl
      on dl.localidade_sk = md5(
          coalesce(i.comarca_normalizada, '') || '|' ||
          coalesce(i.cidade_normalizada, '') || '|' ||
          coalesce(i.uf, '')
      )
    join {{ ref('dim_tempo') }} dt on dt.data = i.data_referencia
    left join {{ ref('stg_patrimonio') }} p
      on p.id_predio = i.id_predio
     and p.data_referencia = i.data_referencia
    left join {{ ref('int_sanitarios_por_imovel') }} s
      on s.id_predio = i.id_predio
     and s.data_referencia = i.data_referencia
    left join {{ ref('int_reservatorios_por_imovel') }} r
      on r.id_predio = i.id_predio
     and r.data_referencia = i.data_referencia
)

select
    *,
    area_construida_m2 is not null
        and area_terreno_m2 is not null
        and area_terreno_m2 > 0 as elegivel_indice_aproveitamento,
    case
        when area_construida_m2 is not null
         and area_terreno_m2 is not null
         and area_terreno_m2 > 0
        then round(100.0 * area_construida_m2 / area_terreno_m2, 4)
    end as indice_aproveitamento_pct,
    case
        when sanitarios_total is not null
         and area_construida_m2 > 0
        then round(1000.0 * sanitarios_total / area_construida_m2, 4)
    end as densidade_sanitaria_por_1000_m2,
    case
        when capacidade_total_litros is not null
         and area_construida_m2 > 0
        then round(capacidade_total_litros / area_construida_m2, 4)
    end as reserva_litros_por_m2
from base
