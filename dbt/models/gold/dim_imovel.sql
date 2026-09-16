{{ config(location='../data/gold/dim_imovel.parquet') }}

-- Grão: uma linha por imóvel identificado no snapshot cadastral atual.

select
    md5(cast(id_predio as varchar)) as imovel_sk,
    id_predio,
    nome_oficial,
    tipo_imovel,
    propriedade,
    categoria_funcional,
    classificacao_original,
    responsavel_manutencao
from {{ ref('stg_imoveis') }}
