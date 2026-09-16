# Decisões da PoC — Imóveis do SIGOB

Este documento registra as decisões exigidas pela disciplina. As justificativas técnicas
mais extensas ficam nos ADRs em [`docs/adr/`](docs/adr/).

## 1. Arquitetura de armazenamento

Adotamos uma arquitetura Medallion:

- **Raw**: CSV e JSON exatamente como entregues e versionados no repositório;
- **Bronze**: tabelas Delta Lake com metadados técnicos e histórico;
- **Silver**: Parquet produzido pelo dbt, com estrutura, tipos, padronização e
  reconciliação;
- **Gold**: Parquet em modelo estrela, orientado à pergunta de negócio;
- **Serving**: DuckDB para execução local e consulta dos arquivos.

O Medallion foi escolhido porque separa captura de interpretação e torna o refinamento
visível na demonstração. Delta fica no Bronze porque é onde precisamos provar o que
chegou em cada versão. Silver e Gold ficam em Parquet para manter a PoC simples e barata.

Detalhes: [ADR-0001](docs/adr/0001-medallion-e-delta-no-bronze.md).

## 2. Grão e formato da camada de consumo

O modelo principal é `fato_imovel_snapshot`.

> Uma linha representa um imóvel em uma data de referência do levantamento.

Sanitários e reservatórios possuem grãos próprios na Silver. Antes de entrar na fato,
eles são agregados por imóvel e data. Isso impede que dois reservatórios multipliquem a
área construída do imóvel e alterem médias ou totais.

Escolhemos estrela, com dimensões de imóvel, localidade e tempo, porque os atributos de
cadastro serão recortes comuns de várias métricas e porque o modelo permite demonstrar
surrogate keys, integridade por testes e dimensões conformadas. O detalhe operacional
das coleções permanece na Silver.

Detalhes: [ADR-0002](docs/adr/0002-grao-e-modelo-de-consumo.md).

## 3. Dado ambíguo que exigiu escolha

O campo da fonte chamado `Tipo de Imóvel` mistura pelo menos três conceitos:

- propriedade: próprio ou cedido;
- uso/ocupação: ocupado pelo TJMS;
- classificação funcional: PID ou prédio avulso.

Não copiamos esse campo para a Gold como se fosse um único domínio confiável. A Silver
aplica um mapa explícito e versionado para separar `propriedade`, `categoria_funcional`
e `tipo_imovel`.

Quando a fonte não informar o tipo físico com segurança, `tipo_imovel` receberá
`NÃO INFORMADO`. Não assumiremos que todo imóvel próprio é uma edificação. Essa escolha
deve ser confirmada pelo responsável de negócio do SIGOB; o código apenas materializa a
regra adotada pela PoC.

Em divergências de nome, o Cadastro Mestre prevalece. As outras fontes são ligadas pelo
ID oficial e seus nomes são mantidos somente para reconciliação.

Detalhes: [ADR-0003](docs/adr/0003-precedencia-e-separacao-de-conceitos.md).

## 4. Destino do registro inválido

O registro do Fórum da Mulher, Criança, Adolescente e Idoso não possui ID oficial. Ele
não entrará na estrela porque não existe chave confiável para relacioná-lo às medições.
Também não é descartado e não recebe um ID inventado.

Seu destino é `quarentena_imoveis`, com arquivo, linha, conteúdo original e motivo.
Uma consulta de qualidade mostrará a quantidade em quarentena. Assim, o número final não
é contaminado e o problema não desaparece silenciosamente.

Já os PIDs com ID válido e sem medição permanecem no modelo com medidas nulas e flags de
completude. Ausência de informação não é convertida em zero.

Detalhes: [ADR-0004](docs/adr/0004-quarentena-e-ausencia-de-medicao.md).

## 5. Definição da métrica principal

A pergunta principal é:

> Qual é o índice de aproveitamento construtivo dos imóveis geridos pelo TJMS e como ele
> varia por comarca e situação patrimonial?

No grão de imóvel:

```text
índice individual (%) = área construída / área do terreno × 100
```

Na visão agregada são expostos **dois números com nomes distintos**:

- `media_indice_individual_pct`: média aritmética do índice de cada imóvel elegível;
- `indice_global_ponderado_pct`: soma das áreas construídas dividida pela soma das áreas
  de terreno, vezes 100.

Eles respondem perguntas diferentes e não serão apresentados como sinônimos. O
levantamento possui 60 imóveis elegíveis. A Gold produziu 37,49% para a média individual
e 35,85% para o índice global ponderado; testes de regressão conferem esses números e a
cobertura de 102 imóveis cadastrados e 79 com medição patrimonial.

Um valor acima de 100% não é automaticamente inválido, pois a área construída pode
somar vários pavimentos. Divisão por área nula ou zero gera resultado nulo e flag de
incompletude.

## 6. Fontes e formatos

A entrega possui fontes semanticamente distintas em dois formatos:

- CSV: cadastro mestre e medições patrimoniais;
- JSON hierárquico: vistoria de infraestrutura com sanitários e reservatórios.

O JSON não é uma cópia do cadastro. Ele tem outro grão e coleções próprias. O recorte
foi preparado sem dados pessoais, versionado em `data/raw/` e documentado em
[`docs/fontes-e-qualidade.md`](docs/fontes-e-qualidade.md).

`docs-sigob/` é referência local e não faz parte da entrega nem é dependência do
pipeline.

## 7. Regra para a consulta final

A consulta de resposta lerá somente a Gold. Conversão de decimal, parsing de texto,
escolha de fonte, tratamento de inválido e fórmulas de negócio pertencem ao dbt. O SQL
final poderá agrupar e ordenar medidas prontas, mas não corrigirá dados no `WHERE`.
