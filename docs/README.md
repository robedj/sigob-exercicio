# Documentação da entrega

Este diretório reúne as evidências de arquitetura, qualidade e apresentação da PoC dos
Imóveis do SIGOB.

## Leitura recomendada

1. [`../DECISOES.md`](../DECISOES.md) — as quatro decisões exigidas pela disciplina;
2. [`fontes-e-qualidade.md`](fontes-e-qualidade.md) — fontes, perfis e defeitos;
3. [`arquitetura.md`](arquitetura.md) — jornada, DAG e estrela;
4. [`testes.md`](testes.md) — matriz de riscos, testes dbt e testes Python;
5. [`apresentacao.md`](apresentacao.md) — roteiro da apresentação de 20 minutos;
6. [`evidencias/resultado-validacao.md`](evidencias/resultado-validacao.md) — última
   execução integral conferida;
7. [`adr/`](adr/) — registros das decisões arquiteturais.

## ADRs

- [ADR-0001 — Medallion e Delta no Bronze](adr/0001-medallion-e-delta-no-bronze.md)
- [ADR-0002 — Grão e modelo de consumo](adr/0002-grao-e-modelo-de-consumo.md)
- [ADR-0003 — Precedência e separação de conceitos](adr/0003-precedencia-e-separacao-de-conceitos.md)
- [ADR-0004 — Quarentena e ausência de medição](adr/0004-quarentena-e-ausencia-de-medicao.md)

Os números publicados foram conferidos pela execução integral registrada em
[`evidencias/resultado-validacao.md`](evidencias/resultado-validacao.md).
