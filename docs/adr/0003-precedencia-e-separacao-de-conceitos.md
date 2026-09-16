# ADR-0003 — Precedência de fontes e separação de conceitos

- Status: aceito para a PoC; requer validação do negócio para produção
- Data: 16/09/2026

## Contexto

As fontes repetem o nome do imóvel e o campo `Tipo de Imóvel` mistura propriedade,
ocupação e classificação funcional. A especificação consolidada determina que tipo e
propriedade são conceitos independentes e que o Cadastro Mestre fornece o nome oficial.

## Decisão

1. Junções usam `id_predio`, nunca o nome.
2. O nome da Gold vem do Cadastro Mestre.
3. Nomes das outras fontes ficam disponíveis para reconciliação e testes.
4. Um mapa explícito separa `propriedade`, `categoria_funcional` e `tipo_imovel`.
5. Se o tipo físico não puder ser inferido, ele recebe `NÃO INFORMADO`.

## Alternativas consideradas

### Usar o texto mais recente

Não existe data confiável por linha para provar qual texto é mais recente.

### Inferir edificação para todo imóvel próprio

Produziria um valor aparentemente completo, mas inventado. O domínio admite Terreno,
Galpão e outros tipos parametrizáveis.

### Usar o nome como chave

Falha com abreviações, caixa, acentos e mudanças de nomenclatura.

## Consequências

- o mapa passa a ser uma decisão governada e testável;
- a dimensão expõe ausência de tipo em vez de escondê-la;
- alterações futuras no cadastro mestre não quebram relacionamentos por nome.
