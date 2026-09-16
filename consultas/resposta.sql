-- RESPOSTA PRINCIPAL
-- Lê somente modelos Gold. Conversão, quarentena, elegibilidade e fórmulas já foram
-- resolvidas e testadas no pipeline; não existe regra de negócio escondida no WHERE.

-- 1. Número geral e cobertura
select
    data_referencia,
    imoveis_cadastrados,
    imoveis_com_medicao_patrimonial,
    imoveis_elegiveis,
    media_indice_individual_pct,
    indice_global_ponderado_pct
from 'data/gold/agg_aproveitamento_geral.parquet';

-- 2. Os mesmos indicadores por comarca e situação patrimonial
select
    data_referencia,
    comarca,
    situacao_patrimonial,
    imoveis_cadastrados,
    imoveis_elegiveis,
    media_indice_individual_pct,
    indice_global_ponderado_pct
from 'data/gold/agg_aproveitamento_comarca.parquet'
order by comarca, situacao_patrimonial;
