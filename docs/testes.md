# Plano de testes

Os testes são organizados pelo risco que impedem, não apenas para atingir a quantidade
mínima. A matriz será atualizada com os nomes reais dos testes durante a implementação.

## Testes dbt

| Risco | Modelo/coluna | Teste |
|---|---|---|
| imóvel sem identidade | `stg_imoveis.id_predio` | `not_null` |
| imóvel duplicado | `stg_imoveis.id_predio` | `unique` |
| UF fora do recorte | `stg_imoveis.uf` | `accepted_values` |
| medição duplicada | `stg_patrimonio.id_predio` | `unique` |
| medição órfã | `stg_patrimonio.id_predio` | `relationships` |
| situação desconhecida | `stg_patrimonio.situacao_patrimonial` | `accepted_values` |
| sanitário órfão | `stg_sanitarios.id_predio` | `relationships` |
| reservatório órfão | `stg_reservatorios.id_predio` | `relationships` |
| dimensão duplicada | `dim_imovel.imovel_sk` | `not_null` + `unique` |
| localidade duplicada | `dim_localidade.localidade_sk` | `not_null` + `unique` |
| fato sem imóvel | `fato_imovel_snapshot.imovel_sk` | `not_null` + `relationships` |
| fato sem localidade | `fato_imovel_snapshot.localidade_sk` | `not_null` + `relationships` |
| fan-out da fato | chaves do grão | teste singular de unicidade composta |
| medida negativa | áreas/quantidades/capacidade | teste singular |
| divisão inválida | indicadores derivados | teste singular |
| inválido desaparecido | `quarentena_imoveis` | teste de contagem/motivo esperado |

Serão usados pelo menos `not_null`, `unique`, `accepted_values` e `relationships`, além
de testes singulares. Avisos só serão usados para regras de qualidade que não invalidam
a execução; integridade do grão será erro.

## Testes Python

- cada ingestão cria uma tabela Delta;
- Bronze preserva a quantidade de registros físicos/lógicos definida por formato;
- Bronze preserva texto e nulos sem conversão de negócio;
- metadados técnicos estão presentes;
- duas versões Delta são reconstruídas na ordem esperada;
- time travel retorna resultados diferentes e reproduzíveis;
- rerun não corrompe o snapshot atual;
- pipeline pode partir de diretórios gerados vazios.

## Validações manuais de reconciliação

Uma amostra pequena será calculada à mão:

- um imóvel simples com áreas preenchidas;
- um imóvel com índice superior a 100%;
- um PID sem medição;
- o imóvel sem ID enviado à quarentena;
- um reservatório simples (`2 x 7500`);
- uma expressão composta de reservatório.

## Comandos de aceite

```bash
python -m src.pipeline
pytest
cd dbt
dbt deps
dbt build
dbt docs generate
```

Antes da entrega, os mesmos comandos serão executados em clone limpo.

