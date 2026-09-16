-- O snapshot entregue possui exatamente o imóvel em construção sem ID oficial.
select quantidade
from (
    select count(*) as quantidade
    from {{ ref('quarentena_imoveis') }}
)
where quantidade <> 1
