# Roteiro da apresentação — 20 minutos

## Objetivo da apresentação

Demonstrar que o número final é confiável porque cada decisão pode ser rastreada da Gold
até as fontes, inclusive quando o dado é inválido ou incompleto.

## 0–4 min — pergunta e fontes

**Integrante 1**

1. Apresentar a pergunta principal e os dois significados possíveis de “índice médio”.
2. Mostrar CSV cadastral/patrimonial e JSON hierárquico de infraestrutura.
3. Exibir três defeitos: decimal brasileiro, imóvel sem ID e reservatório em texto.
4. Explicar por que vazio não significa zero e por que valor acima de 100% pode ser
   legítimo.

## 4–12 min — pipeline ao vivo

**Integrantes 1 e 2**

1. Começar com pastas geradas vazias usando o script seguro de limpeza.
2. Rodar `python -m src.pipeline`.
3. Mostrar Raw preservado e Bronze Delta com `_delta_log`.
4. Rodar `dbt build`.
5. Mostrar a criação de Silver e Gold e o resumo dos testes.
6. Abrir a quarentena e as flags de cobertura.

Mensagem principal: a ingestão não corrigiu nada; as decisões aparecem nos modelos dbt.

## 12–16 min — DAG, Delta e decisões

**Integrante 2**

1. Abrir a DAG do `dbt docs`.
2. Apontar os diferentes grãos e onde ocorre a agregação antes da fato.
3. Rodar a mesma consulta nas versões 0 e 1 do Delta.
4. Explicar a correção que mudou o resultado.
5. Apresentar duas decisões: separação do `Tipo de Imóvel` e quarentena do imóvel sem ID.

## 16–20 min — resposta

**Integrante 3**

1. Abrir `consultas/resposta.sql` e destacar que lê somente a Gold.
2. Executar a consulta.
3. Informar número, recortes e cobertura: total cadastrado, elegíveis e não elegíveis.
4. Diferenciar média individual de índice global ponderado.
5. Concluir com a implicação gerencial e a limitação do dado.

## Plano de contingência

- manter a última saída validada da execução em `docs/evidencias/`;
- saber abrir os Parquet diretamente com DuckDB;
- se `dbt docs serve` falhar, abrir os artefatos já gerados ou o diagrama Mermaid;
- se uma etapa falhar, explicar qual contrato/teste a protege e continuar com os dados
  da última execução válida;
- nunca esconder teste falhando: dizer se é falha de código, ambiente ou qualidade.

## Checklist de ensaio

- todos falam e sabem executar sua parte;
- time travel leva menos de dois minutos;
- o número final foi conferido por outra pessoa do grupo;
- zoom e fonte do terminal são legíveis;
- ambiente foi instalado do zero pelo menos uma vez;
- não aparecem caminhos locais, credenciais ou `docs-sigob/` na apresentação;
- perguntas prováveis têm resposta: grão, fonte oficial, nulos, >100%, Delta e fan-out.
