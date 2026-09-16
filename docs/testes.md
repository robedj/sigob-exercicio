# Plano de testes

Os testes são organizados pelo risco que impedem, não apenas para atingir a quantidade
mínima. A execução atual possui 54 testes dbt e 6 testes Python.

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

São usados `not_null`, `unique`, `accepted_values` e `relationships`, além de testes
singulares. A integridade do grão é tratada como erro.

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

Uma amostra pequena foi conferida diretamente contra as fontes:

- ID 3: `815,62 / 6.480,00 × 100 = 12,5867%`;
- ID 1: `23.364,50 / 7.045,36 × 100 = 331,6296%`, mantido porque múltiplos
  pavimentos podem superar 100%;
- ID 200: permanece cadastrado, mas com áreas e índice nulos;
- o imóvel sem ID aparece uma vez em `quarentena_imoveis`;
- ID 2: `2 × 10.000 + 30.000 = 50.000` litros;
- ID 1: `1 × 20.000 + 2 × 10.000 + 3 × 30.000 = 130.000` litros.

## Comandos de aceite

```bash
python -m src.pipeline
pytest
cd dbt
dbt build
dbt docs generate
```

Os mesmos comandos são executados na validação em clone limpo.

O resultado da última validação está em
[`evidencias/resultado-validacao.md`](evidencias/resultado-validacao.md).
