# Apresentação completa — PoC de Imóveis do SIGOB

Roteiro integral para uma apresentação de 20 minutos, incluindo o texto dos slides,
a fala sugerida, os comandos da demonstração e as respostas para perguntas prováveis.

> Esta apresentação trata exclusivamente do domínio de **Imóveis do SIGOB/TJMS**. Não
> misturar decisões, métricas ou fontes de outros estudos de caso.

## Como transformar este roteiro em slides

- usar formato 16:9 e no máximo quatro pontos visuais por slide;
- copiar a seção **Texto no slide** para o PowerPoint, Google Slides ou Canva;
- colocar a seção **Fala sugerida** nas notas do apresentador;
- usar bronze, cinza e dourado para identificar as camadas Bronze, Silver e Gold;
- substituir blocos de código extensos por capturas legíveis do repositório ou terminal;
- deixar o navegador preparado para a DAG e dois terminais abertos para a demonstração.

## Divisão sugerida entre os integrantes

| Tempo | Responsável | Conteúdo |
|---|---|---|
| 0–4 min | Edvaldo | problema, pergunta, métrica, fontes e defeitos |
| 4–8 min | Rodrigo | limpeza segura, ingestão e preservação Bronze/Delta |
| 8–12 min | Wellington | transformações, modelo de consumo e testes dbt |
| 12–16 min | Rodrigo | DAG, time travel e decisões de governança |
| 16–20 min | Edvaldo | consulta, resposta, interpretação gerencial e limitações |

Os nomes podem ser trocados, mas todos precisam falar e cada integrante deve saber
explicar a pergunta, o grão, a quarentena e a diferença entre as duas métricas finais.

---

## Slide 1 — Capa

**Tempo:** 0:00–0:20
**Responsável:** Edvaldo

### Texto no slide

> **SIGOB Imóveis**
> Do dado bruto a um indicador gerencial confiável

`CSV + JSON → Python → Delta Lake → dbt → Gold → resposta`

Equipe: Edvaldo, Rodrigo e Wellington

Curso: Residência TJMS — Especialização em Engenharia de Software Inteligente
Disciplina: Gestão e Governança de Dados

### Visual sugerido

Uma seta horizontal com as seis etapas da jornada e as cores Bronze, Silver e Gold.

### Fala sugerida

“Nosso projeto aplica a jornada completa da disciplina ao domínio de imóveis do SIGOB.
Nós partimos de arquivos institucionais com estruturas e qualidades diferentes,
preservamos o que chegou, transformamos com regras explícitas e terminamos com uma
resposta gerencial acompanhada de cobertura, testes e linhagem.”

---

## Slide 2 — A pergunta de negócio

**Tempo:** 0:20–1:10
**Responsável:** Edvaldo

### Texto no slide

> **Qual é o índice de aproveitamento construtivo dos imóveis geridos pelo TJMS e como
> ele varia por comarca e situação patrimonial?**

Recortes exigidos:

- comarca;
- situação patrimonial: próprio, cedido, alugado ou não informado.

### Visual sugerido

Um cartão com a pergunta e dois filtros laterais: “Comarca” e “Situação patrimonial”.

### Fala sugerida

“Escolhemos uma pergunta que um gestor do patrimônio poderia fazer. Ela não pede apenas
uma contagem cadastral: precisa relacionar área construída e área de terreno. Também
possui dois ângulos explícitos de análise, comarca e situação patrimonial. O objetivo não
é declarar que um índice alto é bom ou ruim, mas entregar uma base comparável e
rastreável para a gestão do portfólio.”

---

## Slide 3 — Uma métrica realmente derivada

**Tempo:** 1:10–2:00
**Responsável:** Edvaldo

### Texto no slide

```text
índice individual (%) = área construída / área do terreno × 100
```

Dois resultados diferentes:

- **37,49%** — média dos índices individuais;
- **35,85%** — razão entre as somas das áreas.

### Visual sugerido

Apresentar a fórmula no centro e dois cartões abaixo, um para cada resultado.

### Fala sugerida

“Essa medida não existe pronta em nenhuma fonte. Ela é calculada na Gold para cada
imóvel elegível. Também tratamos uma pegadinha comum: média dos percentuais individuais
e razão entre as somas não são sinônimos. A média individual dá o mesmo peso a cada
imóvel. O índice global dá mais peso aos imóveis com terrenos maiores. Por isso
publicamos os dois números com nomes diferentes, em vez de escolher silenciosamente um
deles.”

---

## Slide 4 — Fontes e defeitos preservados

**Tempo:** 2:00–4:00
**Responsável:** Edvaldo

### Texto no slide

| Fonte | Formato | Grão |
|---|---|---|
| Cadastro Mestre — 2 snapshots | CSV | um imóvel cadastrado |
| Patrimônio | CSV | uma medição por imóvel |
| Infraestrutura predial | JSON hierárquico | uma vistoria com coleções |

Defeitos e ambiguidades:

- títulos antes do cabeçalho, BOM, `;` e decimal brasileiro;
- um imóvel sem ID oficial;
- 23 PIDs sem medição patrimonial;
- capacidades como `2 x 10.000 + 30.000`;
- `Tipo de Imóvel` mistura propriedade, ocupação e categoria.

### Visual sugerido

À esquerda, pequenos recortes do CSV e do JSON. À direita, cinco chamadas destacando os
defeitos.

### Fala sugerida

“Temos três fontes semanticamente distintas em dois formatos. O Cadastro Mestre possui
dois snapshots CSV. O levantamento patrimonial também é CSV, mas tem outro grão. A
infraestrutura é JSON hierárquico, com sanitários e reservatórios dentro de cada
vistoria. Os dados não foram ‘embelezados’: preservamos linhas de título, formato
numérico brasileiro, ausência de ID, lacunas de medição e expressões semiestruturadas.
O recorte entregue não possui dados pessoais reais. Esses defeitos são importantes
porque permitem demonstrar onde cada decisão acontece.”

**Transição para a demo:** “Agora vamos apagar somente as camadas geradas e reconstruir
a jornada a partir de `data/raw/`.”

---

## Slide 5 — Arquitetura escolhida

**Tempo:** 4:00–4:45
**Responsável:** Rodrigo

### Texto no slide

```text
Raw → Bronze Delta → Silver dbt → Intermediate → Gold → Resposta
```

- **Raw:** arquivos entregues;
- **Bronze:** preservação e histórico;
- **Silver:** estrutura, tipos e padronização;
- **Intermediate:** redução das coleções ao grão correto;
- **Gold:** estrela, métricas e respostas prontas;
- **Serving:** DuckDB local.

### Visual sugerido

Usar o diagrama de `docs/arquitetura.md`, com cada camada em uma cor.

### Fala sugerida

“Adotamos Medallion porque ela separa captura, interpretação e consumo. Raw guarda os
arquivos entregues. Bronze usa Delta Lake e acrescenta somente metadados técnicos.
Silver é onde o dbt limpa, tipa e padroniza. A camada Intermediate evita fan-out das
coleções. A Gold materializa o modelo estrela e as métricas oficiais. DuckDB permite
executar tudo localmente, sem Spark.”

---

## Slide 6 — Demo: reconstrução e ingestão

**Tempo:** 4:45–6:20
**Responsável:** Rodrigo

### Texto no slide

```bash
python scripts/zerar.py
python -m src.pipeline
```

**Contrato da ingestão:** ler, preservar e registrar metadados — sem regra de negócio.

### Ação ao vivo

No terminal aberto na raiz:

```bash
python scripts/zerar.py
find data -maxdepth 2 -type d | sort
python -m src.pipeline
```

### Saída esperada

```text
imoveis: versão Delta atual 1
patrimonio: versão Delta atual 0
infraestrutura_predial: versão Delta atual 0
```

### Fala sugerida

“O script de limpeza possui alvos explícitos. Ele remove Bronze, Silver, Gold, o catálogo
local e artefatos do dbt, mas preserva `data/raw/`, o código e os documentos. Em seguida,
`python -m src.pipeline` lê os arquivos e reconstrói o Bronze. A ingestão não promove o
cabeçalho do CSV, não converte decimal, não corrige nome e não descarta o imóvel sem ID.
Ela acrescenta apenas origem, versão, instante, hash e posição da linha.”

---

## Slide 7 — Bronze: bruto preservado e versionado

**Tempo:** 6:20–8:00
**Responsável:** Rodrigo

### Texto no slide

Bronze Delta preserva:

- todas as linhas físicas dos CSVs;
- o documento JSON completo;
- `_arquivo_origem`, `_versao_fonte`, `_ingerido_em`;
- `_hash_arquivo` e `_linha_origem`;
- `_delta_log` com duas versões do Cadastro Mestre.

### Ação ao vivo

```bash
find data/bronze -maxdepth 3 -type f | sort
```

Abrir rapidamente `src/ingest.py` e apontar o uso de nomes genéricos `col_01`,
`col_02` e o JSON armazenado integralmente.

### Fala sugerida

“A preservação não significa apenas guardar uma cópia bonita. O Bronze mantém inclusive
as linhas estruturais e o texto original. O Cadastro Mestre é gravado em ordem
cronológica: a primeira entrega cria a versão zero e a entrega seguinte cria a versão
um. O pipeline é idempotente: uma nova execução com os mesmos hashes não cria versões
artificiais.”

---

## Slide 8 — Silver: onde as regras são explícitas

**Tempo:** 8:00–9:30
**Responsável:** Wellington

### Texto no slide

O dbt passa a:

- remover linhas estruturais e tipar IDs/datas;
- converter `23.364,50` em decimal;
- separar propriedade, categoria e tipo físico;
- abrir as coleções do JSON;
- interpretar expressões de reservatórios;
- encaminhar o registro sem ID à quarentena.

### Visual sugerido

Mostrar os modelos `stg_imoveis`, `stg_patrimonio`, `stg_reservatorios` e
`quarentena_imoveis`.

### Fala sugerida

“As regras começam somente na Silver e cada tratamento relevante está comentado com o
motivo. Usamos `try_cast` para que uma conversão ruim vire uma ausência detectável, em
vez de derrubar ou inventar um valor. O JSON é aberto em vistorias, sanitários e
reservatórios. Uma capacidade preenchida que não for interpretada faz um teste falhar;
ela nunca vira zero silenciosamente.”

---

## Slide 9 — Camada de consumo e grão

**Tempo:** 9:30–10:30
**Responsável:** Wellington

### Texto no slide

> **Grão da fato:** uma linha por imóvel e data de referência.

Modelo estrela:

- `dim_imovel`;
- `dim_localidade`;
- `dim_tempo`;
- `fato_imovel_snapshot`.

Consumo direto:

- `mart_indicadores_imoveis`;
- agregados geral e por comarca/situação.

### Fala sugerida

“O grão está declarado no topo do modelo principal. Sanitários e reservatórios são
coleções um-para-muitos; por isso são agregados por imóvel e data antes de chegar à
fato. Sem essa etapa, dois reservatórios poderiam duplicar a área construída e alterar
o resultado sem produzir erro técnico. A estrela foi escolhida para reutilizar imóvel,
localidade e tempo em diferentes análises. O detalhe das coleções permanece na Silver.”

---

## Slide 10 — Demo: dbt build e qualidade

**Tempo:** 10:30–12:00
**Responsável:** Wellington

### Texto no slide

```bash
cd dbt
dbt build
```

Resultado validado:

```text
15 modelos + 54 testes de dados
PASS=69  WARN=0  ERROR=0  SKIP=0
```

- 45 testes declarados em `schema.yml`;
- 9 testes singulares;
- quatro tipos: `not_null`, `unique`, `accepted_values`, `relationships`.

### Ação ao vivo

Executar o build e destacar o resumo final. Se houver tempo, abrir rapidamente
`dbt/models/gold/schema.yml` e `dbt/tests/assert_fato_no_grao_declarado.sql`.

### Fala sugerida

“A atividade exige oito testes e três tipos. Nós temos 45 testes declarativos nos
arquivos `schema.yml`, nove singulares e quatro tipos de teste. Eles protegem identidade,
domínios, relacionamentos, o grão, medidas não negativas, interpretação dos
reservatórios, quarentena, cobertura e os números finais. O build executa 15 modelos e
54 testes, totalizando 69 recursos aprovados sem warning ou erro.”

---

## Slide 11 — Linhagem: da fonte à resposta

**Tempo:** 12:00–13:15
**Responsável:** Rodrigo

### Texto no slide

```bash
dbt docs generate
dbt docs serve --port 8080
```

Na DAG, mostrar:

1. três fontes Bronze;
2. modelos Silver;
3. agregações Intermediate;
4. fato e dimensões Gold;
5. tabelas que respondem à pergunta.

### Ação ao vivo

Gerar a documentação, abrir a DAG no navegador e selecionar
`agg_aproveitamento_geral`. Percorrer os ancestrais até as três fontes.

### Fala sugerida

“A DAG é gerada pelos `source()` e `ref()` reais do projeto, não por um desenho manual.
Partindo da resposta geral, conseguimos voltar ao mart, à fato, às dimensões, aos
modelos Silver e às três tabelas Bronze. A linhagem também evidencia onde as coleções
são agregadas antes do join com a fato.”

---

## Slide 12 — Delta Lake: a mesma consulta em duas versões

**Tempo:** 13:15–14:20
**Responsável:** Rodrigo

### Texto no slide

```bash
python scripts/demonstrar_time_travel.py
```

```text
versão 0: 101 imóveis com ID; 1 registro sem ID
versão 1: 102 imóveis com ID; 1 registro sem ID
```

Mudança: inclusão do PID 223, Casa da Mulher, após esclarecimento da origem do imóvel.

### Fala sugerida

“O script aplica exatamente a mesma consulta à versão zero e à versão atual. Na primeira
entrega havia 101 imóveis identificados. Na segunda, a Casa da Mulher, que funciona em
salas cedidas pela Prefeitura, foi classificada como PID 223 após esclarecimento da
Engenharia. O Fórum da Mulher em construção é outro imóvel e continua sem ID nas duas
versões. Portanto, o time travel mostra uma mudança real de conhecimento, não dois
commits Delta idênticos.”

---

## Slide 13 — Decisões que não poderiam ser copiadas da PoC da aula

**Tempo:** 14:20–16:00
**Responsável:** Rodrigo

### Texto no slide

**Dado ambíguo**

`Tipo de Imóvel` misturava propriedade, ocupação e categoria.

> Regra: separar os conceitos; tipo físico incerto = `NÃO INFORMADO`.

**Registro inválido**

Fórum da Mulher sem ID oficial.

> Regra: quarentenar; não descartar e não inventar ID.

### Fala sugerida

“A arquitetura e o grão já foram mostrados. As outras duas decisões obrigatórias são
específicas do SIGOB. Primeiro, o campo chamado Tipo de Imóvel misturava três conceitos.
O código separa propriedade e categoria, mas não inventa o tipo físico. Essa regra deve
ser validada pelo responsável de negócio do SIGOB. Segundo, o imóvel em construção não
tem chave oficial. Ele não pode entrar na estrela, mas descartá-lo esconderia um
problema. Por isso ele fica na quarentena com origem, linha e motivo. Já um imóvel com
ID válido e sem medição permanece na Gold com medidas nulas, nunca com zero artificial.”

---

## Slide 14 — A consulta final não corrige dados

**Tempo:** 16:00–17:00
**Responsável:** Edvaldo

### Texto no slide

```sql
select
    data_referencia,
    imoveis_cadastrados,
    imoveis_com_medicao_patrimonial,
    imoveis_elegiveis,
    media_indice_individual_pct,
    indice_global_ponderado_pct
from 'data/gold/agg_aproveitamento_geral.parquet';
```

**Zero regra de negócio no `WHERE`. Somente Gold.**

### Ação ao vivo

Na raiz, em outro terminal:

```bash
python scripts/executar_sql.py consultas/resposta.sql
```

### Fala sugerida

“A consulta final lê somente a camada Gold. Ela não converte decimal, não escolhe fonte,
não remove inválido e não recalcula a métrica. Na verdade, a consulta principal nem
possui `WHERE`. A segunda consulta apenas lê o agregado por comarca e situação e ordena
o resultado. Toda regra de negócio está materializada, documentada e testada antes da
camada de resposta.”

---

## Slide 15 — A resposta e sua cobertura

**Tempo:** 17:00–19:00
**Responsável:** Edvaldo

### Texto no slide

| Indicador | Resultado |
|---|---:|
| imóveis identificados | **102** |
| com medição patrimonial | **79** |
| elegíveis ao índice | **60** |
| média dos índices individuais | **37,49%** |
| índice global ponderado | **35,85%** |
| registros em quarentena | **1** |

Exemplos dos recortes:

- Campo Grande / próprio: média **117,42%**, global **95,04%**;
- Dourados / próprio: um elegível com **279,00%**.

### Visual sugerido

Usar cartões para os seis números e um pequeno gráfico por comarca/situação. Não exibir
um ranking como “melhor” ou “pior”.

### Fala sugerida

“O portfólio possui 102 imóveis identificados. Setenta e nove têm algum registro
patrimonial, mas somente 60 possuem as duas áreas necessárias ao indicador. Portanto, a
cobertura elegível é 58,8%. Entre esses imóveis, a média individual é 37,49% e a razão
global das áreas é 35,85%. Os recortes mostram diferenças relevantes, mas índices acima
de 100% não são automaticamente erros: a área construída soma pavimentos e pode superar
a área do terreno. Por isso o resultado precisa ser analisado com o contexto de cada
imóvel.”

---

## Slide 16 — O que o número diz ao gestor

**Tempo:** 19:00–20:00
**Responsável:** Edvaldo

### Texto no slide

**Resposta gerencial**

- o indicador permite comparar o aproveitamento construtivo por comarca e situação;
- o portfólio elegível apresenta índice global de **35,85%**;
- **42 de 102 imóveis** ainda não possuem base completa para o cálculo;
- prioridade de governança: completar e validar as medições patrimoniais.

> Um número confiável não esconde quem ficou fora do cálculo.

### Fala sugerida

“Para o gestor, o índice global informa que, no conjunto elegível, existem cerca de
35,85 metros quadrados de área construída para cada 100 metros quadrados de terreno. Ele
permite comparar recortes e localizar casos que merecem investigação. Mas a principal
limitação também é uma informação gerencial: 42 imóveis ainda não possuem base completa
para o cálculo. O próximo passo não é preencher esses valores com zero; é melhorar o
cadastro e as medições. Concluímos, assim, a jornada do dado bruto até uma resposta cujo
valor, cobertura e regras podem ser auditados.”

**Encerramento:** “Obrigado. Estamos prontos para mostrar qualquer etapa da linhagem ou
responder perguntas.”

---

# Roteiro operacional da demonstração

## Preparação antes da aula

1. Usar um clone separado para a apresentação.
2. Instalar e testar o ambiente com antecedência.
3. Abrir três janelas:
   - Terminal A na raiz do projeto;
   - Terminal B na pasta `dbt/`;
   - navegador em `http://localhost:8080`.
4. Deixar o GitHub e `docs/evidencias/resultado-validacao.md` abertos como contingência.
5. Aumentar o zoom do terminal e ocultar notificações.

## Sequência exata

### Terminal A — raiz

```bash
source .venv/bin/activate
python scripts/zerar.py
find data -maxdepth 2 -type d | sort
python -m src.pipeline
find data/bronze -maxdepth 3 -type f | sort
```

### Terminal B — pasta `dbt/`

```bash
source ../.venv/bin/activate
dbt build
dbt docs generate
dbt docs serve --port 8080
```

### Terminal A — time travel e resposta

```bash
python scripts/demonstrar_time_travel.py
python scripts/executar_sql.py consultas/resposta.sql
python scripts/executar_sql.py consultas/qualidade.sql
```

## O que apontar na consulta de qualidade

```text
102 imóveis
76 com área construída
60 com área de terreno
60 elegíveis
68 com sanitários completos
68 com reservação informada
1 registro em quarentena
```

---

# Matriz de aderência aos nove itens obrigatórios

Esta parte funciona como apêndice. Não precisa ser lida inteira durante os 20 minutos,
mas deve estar disponível para perguntas.

| Requisito | Evidência do projeto |
|---|---|
| 1. Duas fontes em dois formatos | Cadastro/Patrimônio em CSV e Infraestrutura em JSON |
| 2. Ingestão Python sem regra | `src/ingest.py` e `src/pipeline.py` |
| 3. Preservação do bruto | `data/bronze/` em Delta, com conteúdo e metadados técnicos |
| 4. Transformação dbt documentada | modelos Silver comentados e tipados |
| 5. Camada de consumo | estrela com fato no grão imóvel/data e marts Gold |
| 6. Oito testes e três tipos | 45 testes em `schema.yml`, 9 singulares e quatro tipos |
| 7. Linhagem | `dbt docs generate` e DAG navegável |
| 8. Consulta de resposta | `consultas/resposta.sql`, somente Gold e sem regra no `WHERE` |
| 9. Delta com duas versões | Cadastro Mestre nas versões 0 e 1 e script de time travel |

## As quatro decisões obrigatórias

| Decisão | Escolha da equipe | Justificativa curta |
|---|---|---|
| Arquitetura | Raw, Bronze Delta, Silver, Intermediate, Gold e DuckDB | separar captura, interpretação e consumo |
| Grão | um imóvel por data de referência | impedir duplicação das áreas pelas coleções 1:N |
| Dado ambíguo | separar propriedade, categoria e tipo físico | não tratar conceitos diferentes como um único domínio |
| Registro inválido | quarentena | preservar o problema sem contaminar a Gold ou inventar ID |

---

# Perguntas difíceis e respostas preparadas

## “Por que existem dois percentuais finais?”

A média individual dá o mesmo peso a cada imóvel elegível. O índice global divide a
soma das áreas construídas pela soma dos terrenos e, portanto, pondera naturalmente
pelos tamanhos. Eles respondem perguntas diferentes e são publicados separadamente.

## “Como um índice pode ser maior que 100%?”

A área construída é a soma das áreas dos pavimentos. Um prédio de vários andares pode
ter área construída maior que a área do lote. O valor merece análise, mas não pode ser
rejeitado automaticamente.

## “Por que não preencher os dados ausentes com zero?”

Zero afirma que a medida foi realizada e o resultado foi zero. `NULL` afirma que não há
informação suficiente. Trocar ausência por zero reduziria artificialmente os índices e
criaria uma falsa sensação de completude.

## “Por que 103 registros capturados viram 102 imóveis na Gold?”

O snapshot atual contém 102 IDs válidos e um imóvel sem ID. O registro sem chave fica em
quarentena, preservado com origem e motivo. Ele não entra na estrela porque não pode ser
relacionado com segurança.

## “Por que o Delta está somente no Bronze?”

É no ponto de captura que precisamos provar o que chegou em cada versão. Silver e Gold
podem ser reconstruídas a partir do Bronze e usam Parquet para manter a PoC simples. A
decisão atende ao requisito sem ampliar desnecessariamente a superfície técnica.

## “Como vocês garantem que o pipeline reconstrói do zero?”

`scripts/zerar.py` remove exclusivamente as camadas geradas. Em clone isolado, a equipe
executou `python -m src.pipeline`, os 6 testes Python, `dbt build`, `dbt docs generate`,
time travel e as consultas. O resultado foi 69/69 no dbt, sem ajuste manual.

## “A consulta final possui regra de negócio?”

Não. Ela lê agregados Gold prontos. Conversão, reconciliação, elegibilidade, fórmula e
quarentena já foram aplicadas e testadas no dbt. A consulta principal não tem `WHERE`.

## “Quem deveria validar a ambiguidade do Tipo de Imóvel?”

O responsável de negócio do módulo de Imóveis do SIGOB, com apoio da área patrimonial.
A equipe implementou uma regra explícita para a PoC, mas não transformou uma inferência
técnica em verdade definitiva de negócio.

## “Qual é a principal limitação da resposta?”

Somente 60 dos 102 imóveis identificados têm área construída e terreno suficientes para
o índice. O resultado é confiável para o conjunto elegível, mas não representa uma
medição completa de todo o portfólio.

---

# Plano de contingência

- manter a evidência validada aberta em `docs/evidencias/resultado-validacao.md`;
- se a rede falhar, trabalhar somente com o clone e as dependências já instaladas;
- se `dbt docs serve` falhar, usar o diagrama de `docs/arquitetura.md`;
- se a demo falhar depois da limpeza, explicar a etapa e usar a saída validada;
- não esconder teste falhando: identificar se a causa é ambiente, código ou qualidade;
- não improvisar números diferentes dos registrados na Gold;
- reservar pelo menos dois minutos do ensaio para a troca entre slides, terminal e DAG.

## Checklist final do ensaio

- [ ] todos os integrantes falam e conhecem sua transição;
- [ ] a apresentação completa fica entre 18 e 20 minutos;
- [ ] os terminais começam nas pastas corretas;
- [ ] `python scripts/zerar.py` foi testado no clone de apresentação;
- [ ] `dbt docs` abre com zoom legível;
- [ ] o time travel leva menos de um minuto;
- [ ] a consulta final mostra 37,49% e 35,85%;
- [ ] ninguém chama ausência de dado de zero;
- [ ] ninguém chama índice acima de 100% de erro automático;
- [ ] não aparecem credenciais, caminhos privados ou `docs-sigob/` na tela;
- [ ] o grupo consegue explicar os 42 imóveis não elegíveis;
- [ ] existe uma pessoa responsável por controlar o tempo.
