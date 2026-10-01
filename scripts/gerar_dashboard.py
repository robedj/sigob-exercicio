"""Gera o dashboard da camada de consumo.

Último passo do ciclo: executar depois de `dbt build`.

O dashboard não recalcula a fórmula do índice e não corrige dado. Ele lê as
medidas já calculadas e testadas na Gold (`indice_aproveitamento_pct`,
`area_construida_m2`, `area_terreno_m2`) e apenas filtra, agrega e exibe.

Saída: data/gold/dashboard.html (arquivo único, abre no navegador, sem servidor).
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
GOLD = RAIZ / "data" / "gold"
SILVER = RAIZ / "data" / "silver"
DESTINO = GOLD / "dashboard.html"

TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SIGOB Imóveis — Aproveitamento construtivo</title>
<style>
  :root {
    --ink: #1b1a17; --ink-2: #4a463f; --ink-3: #7d776c;
    --surface: #faf8f5; --card: #ffffff; --linha: #e6e1d8;
    --marca: #8a6a2f; --marca-fraca: #e8dcc4; --alerta: #8c4a2f;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ink: #f2efe9; --ink-2: #c4bdb0; --ink-3: #908a7e;
      --surface: #16150f; --card: #211f18; --linha: #38352b;
      --marca: #d8ad5c; --marca-fraca: #4a3d22; --alerta: #d98c66;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 28px 20px 56px;
    background: var(--surface); color: var(--ink);
    font: 14px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .wrap { max-width: 1120px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: -.01em; }
  .sub { color: var(--ink-3); margin: 0 0 24px; font-size: 13px; }
  .filtros {
    display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end;
    padding: 16px; background: var(--card); border: 1px solid var(--linha);
    border-radius: 10px; margin-bottom: 20px;
  }
  .campo { display: flex; flex-direction: column; gap: 5px; }
  .campo label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-3); }
  select {
    min-width: 210px; padding: 8px 10px; font: inherit; color: var(--ink);
    background: var(--surface); border: 1px solid var(--linha); border-radius: 7px;
  }
  button {
    padding: 8px 14px; font: inherit; color: var(--ink-2); cursor: pointer;
    background: var(--surface); border: 1px solid var(--linha); border-radius: 7px;
  }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); gap: 12px; margin-bottom: 22px; }
  .kpi { padding: 14px 16px; background: var(--card); border: 1px solid var(--linha); border-radius: 10px; }
  .kpi .rotulo { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-3); }
  .kpi .valor { font-size: 27px; font-variant-numeric: tabular-nums; margin-top: 5px; letter-spacing: -.02em; }
  .kpi .nota { font-size: 11px; color: var(--ink-3); margin-top: 2px; }
  .painel { padding: 18px; background: var(--card); border: 1px solid var(--linha); border-radius: 10px; margin-bottom: 20px; }
  .painel h2 { font-size: 14px; margin: 0 0 3px; }
  .painel .ajuda { font-size: 12px; color: var(--ink-3); margin: 0 0 16px; }
  .barras { display: flex; flex-direction: column; gap: 9px; }
  .barra { display: grid; grid-template-columns: 185px 1fr 74px; gap: 11px; align-items: center; }
  .barra .nome { font-size: 12px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .trilha { height: 13px; background: var(--marca-fraca); border-radius: 3px; position: relative; }
  .preenche { height: 100%; background: var(--marca); border-radius: 0 4px 4px 0; min-width: 2px; }
  .barra .num { font-size: 12px; text-align: right; font-variant-numeric: tabular-nums; color: var(--ink-2); }
  .barra:hover .nome, .barra:hover .num { color: var(--ink); }
  .ref100 { position: absolute; top: -3px; bottom: -3px; width: 1px; background: var(--ink-3); opacity: .55; }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th, td { padding: 7px 9px; text-align: left; border-bottom: 1px solid var(--linha); }
  th { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--ink-3); font-weight: 600; }
  td.n { text-align: right; font-variant-numeric: tabular-nums; }
  .tabela-rolagem { overflow-x: auto; max-height: 430px; overflow-y: auto; }
  .vazio { color: var(--ink-3); font-size: 13px; padding: 14px 0; }
  .aviso { font-size: 12px; color: var(--alerta); }
  footer { color: var(--ink-3); font-size: 11.5px; margin-top: 26px; line-height: 1.7; }
  @media (max-width: 560px) { .barra { grid-template-columns: 110px 1fr 62px; } }
</style>
</head>
<body>
<div class="wrap">

  <h1>Aproveitamento construtivo dos imóveis do TJMS</h1>
  <p class="sub">Camada de consumo (Gold) · data de referência __DATA_REF__ · as medidas vêm calculadas e testadas do dbt; este painel apenas filtra e agrega.</p>

  <div class="filtros">
    <div class="campo">
      <label for="f-comarca">Comarca</label>
      <select id="f-comarca"></select>
    </div>
    <div class="campo">
      <label for="f-situacao">Situação patrimonial</label>
      <select id="f-situacao"></select>
    </div>
    <button id="limpar" type="button">Limpar filtros</button>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="painel">
    <h2>Índice de aproveitamento por comarca</h2>
    <p class="ajuda">Razão global da comarca: soma das áreas construídas ÷ soma das áreas de terreno. A linha vertical marca 100%; acima disso a área construída soma mais de um pavimento.</p>
    <div class="barras" id="barras"></div>
  </div>

  <div class="painel">
    <h2>Imóveis no recorte</h2>
    <p class="ajuda">Medida ausente aparece como “—”, nunca como zero.</p>
    <div class="tabela-rolagem">
      <table>
        <thead><tr>
          <th>ID</th><th>Nome oficial</th><th>Comarca</th><th>Situação</th>
          <th class="n">Constr. (m²)</th><th class="n">Terreno (m²)</th><th class="n">Índice</th>
        </tr></thead>
        <tbody id="corpo"></tbody>
      </table>
    </div>
  </div>

  <div class="painel">
    <h2>Quarentena</h2>
    <p class="ajuda">Registro de negócio sem ID oficial. Não entra na estrela e não é descartado: fica isolado com origem, linha e motivo.</p>
    <div class="tabela-rolagem">
      <table>
        <thead><tr><th>Arquivo</th><th class="n">Linha</th><th>Nome original</th><th>Comarca</th><th>Motivo</th></tr></thead>
        <tbody id="corpo-quarentena"></tbody>
      </table>
    </div>
  </div>

  <footer>
    Fonte: <code>data/gold/mart_indicadores_imoveis.parquet</code> e <code>data/silver/quarentena_imoveis.parquet</code>.<br>
    Gerado por <code>scripts/gerar_dashboard.py</code> ao final do ciclo, depois de <code>dbt build</code>.
  </footer>

</div>

<script>
const IMOVEIS = __IMOVEIS__;
const QUARENTENA = __QUARENTENA__;

const fmt = (v, d = 2) => v === null || v === undefined
  ? "—"
  : v.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
const inteiro = (v) => v.toLocaleString("pt-BR");

const selComarca = document.getElementById("f-comarca");
const selSituacao = document.getElementById("f-situacao");

function popular(sel, valores, rotuloTodos) {
  sel.innerHTML = "";
  const todos = document.createElement("option");
  todos.value = "__TODOS__";
  todos.textContent = rotuloTodos;
  sel.appendChild(todos);
  valores.forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    sel.appendChild(o);
  });
}

const unicos = (campo) => [...new Set(IMOVEIS.map((i) => i[campo]))].sort((a, b) => a.localeCompare(b, "pt-BR"));

popular(selComarca, unicos("comarca"), "Todas as comarcas (" + unicos("comarca").length + ")");
popular(selSituacao, unicos("situacao_patrimonial"), "Todas as situações");

function filtrar() {
  const c = selComarca.value;
  const s = selSituacao.value;
  return IMOVEIS.filter((i) =>
    (c === "__TODOS__" || i.comarca === c) &&
    (s === "__TODOS__" || i.situacao_patrimonial === s));
}

function kpis(linhas) {
  const elegiveis = linhas.filter((i) => i.elegivel);
  const comMedicao = linhas.filter((i) => i.tem_medicao);
  const somaC = elegiveis.reduce((a, i) => a + i.area_construida, 0);
  const somaT = elegiveis.reduce((a, i) => a + i.area_terreno, 0);
  const media = elegiveis.length
    ? elegiveis.reduce((a, i) => a + i.indice, 0) / elegiveis.length
    : null;
  const global = somaT > 0 ? (100 * somaC) / somaT : null;
  const cobertura = linhas.length ? (100 * elegiveis.length) / linhas.length : null;

  const cartoes = [
    ["Imóveis no recorte", inteiro(linhas.length), "identificados no cadastro"],
    ["Com medição patrimonial", inteiro(comMedicao.length), "possuem registro no patrimônio"],
    ["Elegíveis ao índice", inteiro(elegiveis.length), "têm as duas áreas necessárias"],
    ["Média dos índices", media === null ? "—" : fmt(media) + "%", "cada imóvel pesa igual"],
    ["Índice global", global === null ? "—" : fmt(global) + "%", "ponderado pelo tamanho do terreno"],
    ["Cobertura elegível", cobertura === null ? "—" : fmt(cobertura, 1) + "%", "elegíveis ÷ imóveis do recorte"],
  ];

  document.getElementById("kpis").innerHTML = cartoes.map(([r, v, n]) => `
    <div class="kpi">
      <div class="rotulo">${r}</div>
      <div class="valor">${v}</div>
      <div class="nota">${n}</div>
    </div>`).join("");
}

function barras(linhas) {
  const porComarca = new Map();
  linhas.filter((i) => i.elegivel).forEach((i) => {
    const atual = porComarca.get(i.comarca) || { c: 0, t: 0, n: 0 };
    atual.c += i.area_construida;
    atual.t += i.area_terreno;
    atual.n += 1;
    porComarca.set(i.comarca, atual);
  });

  const dados = [...porComarca.entries()]
    .map(([comarca, v]) => ({ comarca, pct: (100 * v.c) / v.t, n: v.n }))
    .sort((a, b) => b.pct - a.pct);

  const alvo = document.getElementById("barras");
  if (!dados.length) {
    alvo.innerHTML = '<p class="vazio">Nenhum imóvel elegível neste recorte: faltam área construída ou área de terreno. Por isso não exibimos valor zero.</p>';
    return;
  }

  const maximo = Math.max(...dados.map((d) => d.pct), 100);
  alvo.innerHTML = dados.map((d) => `
    <div class="barra" title="${d.comarca}: ${fmt(d.pct)}% — ${d.n} imóvel(is) elegível(is)">
      <div class="nome">${d.comarca}</div>
      <div class="trilha">
        <div class="preenche" style="width:${(100 * d.pct) / maximo}%"></div>
        <div class="ref100" style="left:${(100 * 100) / maximo}%"></div>
      </div>
      <div class="num">${fmt(d.pct, 1)}%</div>
    </div>`).join("");
}

function tabela(linhas) {
  const ordenadas = [...linhas].sort((a, b) =>
    (b.indice ?? -1) - (a.indice ?? -1) || a.id - b.id);
  document.getElementById("corpo").innerHTML = ordenadas.map((i) => `
    <tr>
      <td class="n">${i.id}</td>
      <td>${i.nome}</td>
      <td>${i.comarca}</td>
      <td>${i.situacao_patrimonial}</td>
      <td class="n">${fmt(i.area_construida)}</td>
      <td class="n">${fmt(i.area_terreno)}</td>
      <td class="n">${i.indice === null ? "—" : fmt(i.indice) + "%"}</td>
    </tr>`).join("");
}

document.getElementById("corpo-quarentena").innerHTML = QUARENTENA.length
  ? QUARENTENA.map((q) => `
      <tr>
        <td>${q.arquivo}</td>
        <td class="n">${q.linha}</td>
        <td>${q.nome}</td>
        <td>${q.comarca}</td>
        <td class="aviso">${q.motivo}</td>
      </tr>`).join("")
  : '<tr><td colspan="5" class="vazio">Nenhum registro em quarentena.</td></tr>';

function render() {
  const linhas = filtrar();
  kpis(linhas);
  barras(linhas);
  tabela(linhas);
}

selComarca.addEventListener("change", render);
selSituacao.addEventListener("change", render);
document.getElementById("limpar").addEventListener("click", () => {
  selComarca.value = "__TODOS__";
  selSituacao.value = "__TODOS__";
  render();
});

render();
</script>
</body>
</html>
"""


def _consultar(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cursor = con.sql(sql)
    colunas = [d[0] for d in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def gerar() -> Path:
    mart = GOLD / "mart_indicadores_imoveis.parquet"
    quarentena = SILVER / "quarentena_imoveis.parquet"

    if not mart.exists():
        raise SystemExit(
            f"{mart} não encontrado. Execute 'python -m src.pipeline' e depois 'dbt build'."
        )

    con = duckdb.connect()

    imoveis = _consultar(
        con,
        f"""
        select
            id_predio                         as id,
            nome_oficial                      as nome,
            comarca,
            situacao_patrimonial,
            area_construida_m2                as area_construida,
            area_terreno_m2                   as area_terreno,
            indice_aproveitamento_pct         as indice,
            elegivel_indice_aproveitamento    as elegivel,
            tem_medicao_patrimonial           as tem_medicao
        from '{mart.as_posix()}'
        order by id_predio
        """,
    )

    data_ref = con.sql(
        f"select max(data_referencia) from '{mart.as_posix()}'"
    ).fetchone()[0]

    linhas_quarentena: list[dict] = []
    if quarentena.exists():
        linhas_quarentena = _consultar(
            con,
            f"""
            select
                _arquivo_origem        as arquivo,
                linha_origem           as linha,
                nome_original          as nome,
                comarca_original       as comarca,
                motivo_quarentena      as motivo
            from '{quarentena.as_posix()}'
            order by linha_origem
            """,
        )

    con.close()

    html = (
        TEMPLATE.replace("__DATA_REF__", data_ref.strftime("%d/%m/%Y"))
        .replace("__IMOVEIS__", json.dumps(imoveis, ensure_ascii=False, default=float))
        .replace("__QUARENTENA__", json.dumps(linhas_quarentena, ensure_ascii=False, default=str))
    )

    DESTINO.write_text(html, encoding="utf-8")
    return DESTINO


if __name__ == "__main__":
    destino = gerar()
    print(f"[INFO] Dashboard gerado em {destino.relative_to(RAIZ)}")
    print("[INFO] Abra com: xdg-open data/gold/dashboard.html")
