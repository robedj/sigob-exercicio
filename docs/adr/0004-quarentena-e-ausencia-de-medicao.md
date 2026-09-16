# ADR-0004 — Quarentena e ausência de medição

- Status: aceito
- Data: 16/09/2026

## Contexto

Há um imóvel em construção sem ID oficial. Também existem imóveis com ID válido, como
PIDs, que legitimamente não possuem todas as medições. Descartar ambos mistura dois
problemas diferentes; transformar vazios em zero cria medidas falsas.

## Decisão

- registro sem chave de negócio vai para `quarentena_imoveis`;
- a quarentena preserva origem, linha, conteúdo e motivo;
- nenhum ID é inventado;
- imóvel com ID válido permanece no modelo;
- medição ausente vira `NULL` e uma flag de completude;
- zero permanece zero apenas quando foi explicitamente informado pela fonte.

## Alternativas consideradas

### Descartar silenciosamente

Faria a carga passar, mas perderia um imóvel relevante e esconderia o defeito.

### Gerar ID temporário

Criaria uma chave sem autoridade e poderia colidir com a futura identificação oficial.

### Linha genérica “não informado”

É útil para fatos órfãos, mas aqui esconderia que se trata de um imóvel específico em
construção. A quarentena preserva melhor a pendência.

## Consequências

- a contagem da Gold será menor que a contagem capturada e a diferença será explicada;
- a consulta de qualidade precisa acompanhar a resposta gerencial;
- métricas agregadas devem expor quantidade total e quantidade elegível.

