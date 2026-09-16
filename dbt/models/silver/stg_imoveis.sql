{{ config(location='../data/silver/stg_imoveis.parquet') }}

-- Grão: uma linha por imóvel com ID oficial no snapshot cadastral atual.
-- O Bronze preserva títulos, cabeçalho e o registro sem ID. A Silver seleciona somente
-- registros identificáveis; o restante é encaminhado a quarentena_imoveis.

with origem as (
    select * from {{ source('bronze', 'imoveis') }}
),

registros as (
    select
        try_cast(trim(col_01) as integer)                         as id_predio,
        nullif(trim(col_02), '')                                  as nome_oficial,
        nullif(trim(col_03), '')                                  as classificacao_original,
        nullif(trim(col_04), '')                                  as responsavel_manutencao,
        nullif(trim(col_05), '')                                  as comarca,
        nullif(trim(col_06), '')                                  as logradouro,
        nullif(trim(col_07), '')                                  as numero,
        nullif(trim(col_08), '')                                  as cidade,
        upper(nullif(trim(col_09), ''))                           as uf,
        nullif(trim(col_10), '')                                  as cep,
        nullif(trim(col_11), '')                                  as telefone,
        nullif(trim(col_12), '')                                  as observacao,
        try_cast(_versao_fonte as date)                           as data_referencia,
        _arquivo_origem,
        try_cast(_linha_origem as integer)                        as linha_origem
    from origem
    where regexp_matches(trim(col_01), '^[0-9]+$')
)

select
    *,
    -- A fonte chama este campo de "Tipo", mas mistura propriedade, ocupação e PID.
    -- A PoC separa os conceitos e não inventa um tipo físico ausente.
    case
        when upper(classificacao_original) like 'PRÓPRIO%' then 'PROPRIO'
        when upper(classificacao_original) like 'PID%' then 'CEDIDO'
        else 'NAO_INFORMADO'
    end                                                             as propriedade,
    case
        when upper(classificacao_original) like 'PID%' then 'PID'
        when upper(classificacao_original) like '%PRÉDIO AVULSO%' then 'PREDIO_AVULSO'
        else 'IMOVEL_INSTITUCIONAL'
    end                                                             as categoria_funcional,
    'NAO_INFORMADO'                                                  as tipo_imovel,
    upper(comarca)                                                   as comarca_normalizada,
    upper(cidade)                                                    as cidade_normalizada
from registros
