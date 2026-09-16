{{ config(location='../data/gold/mart_indicadores_imoveis.parquet') }}

-- Grão: uma linha por imóvel e data, já enriquecida para consumo.
-- Esta tabela larga não redefine regras: apenas apresenta fato e dimensões juntas.

select
    f.*,
    i.id_predio,
    i.nome_oficial,
    i.tipo_imovel,
    i.propriedade,
    i.categoria_funcional,
    i.responsavel_manutencao,
    l.comarca,
    l.cidade,
    l.uf,
    t.data as data_referencia,
    t.ano,
    t.mes,
    t.trimestre
from {{ ref('fato_imovel_snapshot') }} f
join {{ ref('dim_imovel') }} i using (imovel_sk)
join {{ ref('dim_localidade') }} l using (localidade_sk)
join {{ ref('dim_tempo') }} t on t.data_sk = f.data_referencia_sk
