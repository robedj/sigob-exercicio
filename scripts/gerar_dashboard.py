"""Gera o dashboard da PoC: da fonte bruta até a resposta da pergunta de negócio.

Último passo do ciclo, depois de `dbt build`:

    python -m src.pipeline
    cd dbt && dbt build && cd ..
    python scripts/gerar_dashboard.py

O dashboard não recalcula a fórmula do índice e não corrige dado. Ele lê as
medidas já calculadas e testadas na Gold, os artefatos reais de execução do dbt
(`manifest.json` e `run_results.json`) e o `_delta_log` da Bronze.

Saída: data/gold/dashboard.html — arquivo único, abre no navegador, sem servidor.
"""

from __future__ import annotations

import json
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
BRONZE = RAIZ / "data" / "bronze"
SILVER = RAIZ / "data" / "silver"
GOLD = RAIZ / "data" / "gold"
TARGET = RAIZ / "dbt" / "target"
DESTINO = GOLD / "dashboard.html"

PERGUNTA = (
    "Qual é o índice de aproveitamento construtivo dos imóveis geridos pelo "
    "TJMS e como ele varia por comarca e situação patrimonial?"
)

CAMADAS = {
    "bronze": "Bronze",
    "silver": "Silver",
    "intermediate": "Intermediate",
    "gold": "Gold",
}

DEFEITOS_RAW = [
    ("Título e descrição antes do cabeçalho", "4 linhas estruturais em cada CSV; o cabeçalho real está na linha 4"),
    ("BOM e separador ';'", "arquivos exportados de planilha, não CSV canônico"),
    ("Decimal brasileiro", "23.364,50 chega como texto e só é convertido na Silver"),
    ("Registro sem ID oficial", "Fórum da Mulher, Criança, Adolescente e Idoso — vai para quarentena"),
    ("Campo que mistura conceitos", "'Tipo de Imóvel' junta propriedade, ocupação e categoria funcional"),
    ("Capacidade semiestruturada", "expressões como '2 x 10.000 + 30.000' interpretadas na Silver"),
    ("Safras diferentes na mesma linha", "área construída de 2026 e área de terreno de 2019, conforme o cabeçalho da fonte"),
]

CONSULTA_TIME_TRAVEL = """
select
    count(*) filter (where regexp_matches(trim(col_01), '^[0-9]+$')) as com_id,
    count(*) filter (
        where try_cast(_linha_origem as integer) >= 5
          and not regexp_matches(trim(col_01), '^[0-9]+$')
          and nullif(trim(col_02), '') is not null
    ) as sem_id
from snapshot
"""


# --------------------------------------------------------------------------- #
# Coleta
# --------------------------------------------------------------------------- #
def _linhas(caminho: Path) -> int | None:
    if caminho.suffix.lower() != ".csv":
        return None
    with caminho.open("r", encoding="utf-8-sig") as arquivo:
        return sum(1 for _ in arquivo)


def coletar_raw() -> list[dict]:
    arquivos = sorted(RAW.rglob("*"))
    itens = []
    for caminho in arquivos:
        if not caminho.is_file():
            continue
        itens.append(
            {
                "arquivo": caminho.relative_to(RAW).as_posix(),
                "formato": caminho.suffix.lstrip(".").upper(),
                "bytes": caminho.stat().st_size,
                "linhas_fisicas": _linhas(caminho),
            }
        )
    return itens


def coletar_bronze() -> list[dict]:
    tabelas = []
    for pasta in sorted(p for p in BRONZE.iterdir() if p.is_dir()):
        commits = []
        for log in sorted((pasta / "_delta_log").glob("*.json")):
            versao = int(log.stem)
            for linha in log.read_text(encoding="utf-8").splitlines():
                registro = json.loads(linha)
                info = registro.get("commitInfo")
                if not info:
                    continue
                metricas = info.get("operationMetrics", {})
                commits.append(
                    {
                        "versao": versao,
                        "operacao": info.get("operation", "—"),
                        "modo": info.get("operationParameters", {}).get("mode", "—"),
                        "linhas": int(metricas.get("num_added_rows", 0) or 0),
                        "arquivos_add": int(metricas.get("num_added_files", 0) or 0),
                        "arquivos_rem": int(metricas.get("num_removed_files", 0) or 0),
                    }
                )
        tabelas.append(
            {
                "tabela": pasta.name,
                "versao_atual": max((c["versao"] for c in commits), default=0),
                "commits": commits,
            }
        )
    return tabelas


def coletar_time_travel() -> list[dict]:
    try:
        from deltalake import DeltaTable
    except ImportError:
        return []

    tabela = BRONZE / "imoveis"
    if not tabela.exists():
        return []

    atual = DeltaTable(str(tabela)).version()
    linhas = []
    for versao in sorted({0, atual}):
        pyarrow = DeltaTable(str(tabela), version=versao).to_pyarrow_table()
        with duckdb.connect() as conexao:
            conexao.register("snapshot", pyarrow)
            com_id, sem_id = conexao.execute(CONSULTA_TIME_TRAVEL).fetchone()
        linhas.append(
            {
                "versao": versao,
                "rotulo": "anterior" if versao == 0 else "atual",
                "com_id": com_id,
                "sem_id": sem_id,
                "linhas_fisicas": pyarrow.num_rows,
            }
        )
    return linhas


def _contar(caminho: Path, con: duckdb.DuckDBPyConnection) -> int | None:
    if not caminho.exists():
        return None
    return con.sql(f"select count(*) from '{caminho.as_posix()}'").fetchone()[0]


def coletar_modelos(con: duckdb.DuckDBPyConnection) -> dict[str, list[dict]]:
    descricoes = {
        "stg_imoveis": "Cadastro Mestre interpretado: descarta linhas estruturais, tipa ID e data, separa propriedade/categoria/tipo",
        "stg_patrimonio": "Medições patrimoniais com decimal brasileiro convertido e situação padronizada",
        "stg_vistorias": "Cabeçalho da vistoria extraído do documento JSON",
        "stg_sanitarios": "Coleção de sanitários aberta em linhas (grão: sanitário)",
        "stg_reservatorios": "Coleção de reservatórios aberta em linhas, com capacidade interpretada",
        "quarentena_imoveis": "Registro de negócio sem ID oficial, isolado com origem, linha e motivo",
        "int_sanitarios_por_imovel": "Reduz os sanitários ao grão imóvel/data antes da fato",
        "int_reservatorios_por_imovel": "Reduz os reservatórios ao grão imóvel/data antes da fato",
        "dim_imovel": "Dimensão de imóvel: nome oficial, tipo, propriedade, categoria funcional",
        "dim_localidade": "Dimensão de localidade: comarca, cidade, UF",
        "dim_tempo": "Dimensão de tempo: data de referência do levantamento",
        "fato_imovel_snapshot": "Fato no grão imóvel/data, com medidas e indicadores derivados",
        "mart_indicadores_imoveis": "Fato achatada com as dimensões, para consumo direto",
        "agg_aproveitamento_geral": "Resposta geral da pergunta, com cobertura",
        "agg_aproveitamento_comarca": "Resposta por comarca e situação patrimonial",
    }

    por_camada: dict[str, list[dict]] = {"silver": [], "intermediate": [], "gold": []}
    for camada, pasta in (("silver", SILVER), ("gold", GOLD)):
        for modelo in sorted(descricoes):
            caminho = pasta / f"{modelo}.parquet"
            if not caminho.exists():
                continue
            por_camada[camada].append(
                {
                    "modelo": modelo,
                    "linhas": _contar(caminho, con),
                    "materializacao": "parquet externo",
                    "descricao": descricoes[modelo],
                }
            )

    # Intermediate é view: o grão reduzido é demonstrado a partir da Silver.
    for modelo, origem, rotulo in (
        ("int_sanitarios_por_imovel", "stg_sanitarios", "sanitários"),
        ("int_reservatorios_por_imovel", "stg_reservatorios", "reservatórios"),
    ):
        caminho = SILVER / f"{origem}.parquet"
        if not caminho.exists():
            continue
        detalhe = _contar(caminho, con)
        reduzido = con.sql(
            f"select count(*) from (select distinct id_predio, data_referencia "
            f"from '{caminho.as_posix()}')"
        ).fetchone()[0]
        por_camada["intermediate"].append(
            {
                "modelo": modelo,
                "linhas": reduzido,
                "materializacao": "view",
                "descricao": descricoes[modelo],
                "fanout": {"detalhe": detalhe, "reduzido": reduzido, "rotulo": rotulo},
            }
        )
    return por_camada


def coletar_fanout(con: duckdb.DuckDBPyConnection) -> dict:
    """Mede a explosão que a camada Intermediate evita."""
    sanitarios = SILVER / "stg_sanitarios.parquet"
    reservatorios = SILVER / "stg_reservatorios.parquet"
    if not (sanitarios.exists() and reservatorios.exists()):
        return {}

    linha = con.sql(
        f"""
        with s as (
            select id_predio, data_referencia, count(*) as n
            from '{sanitarios.as_posix()}' group by 1, 2
        ), r as (
            select id_predio, data_referencia, count(*) as n
            from '{reservatorios.as_posix()}' group by 1, 2
        )
        select
            count(*)            as imoveis_com_vistoria,
            sum(s.n)            as linhas_sanitarios,
            sum(r.n)            as linhas_reservatorios,
            sum(s.n * r.n)      as linhas_se_juntasse_direto,
            max(s.n * r.n)      as pior_caso_por_imovel
        from s join r using (id_predio, data_referencia)
        """
    ).fetchone()

    return {
        "imoveis_com_vistoria": int(linha[0]),
        "linhas_sanitarios": int(linha[1]),
        "linhas_reservatorios": int(linha[2]),
        "linhas_se_juntasse_direto": int(linha[3]),
        "pior_caso_por_imovel": int(linha[4]),
    }


def coletar_dag() -> dict:
    manifesto = TARGET / "manifest.json"
    if not manifesto.exists():
        return {"nos": [], "arestas": []}

    dados = json.loads(manifesto.read_text(encoding="utf-8"))
    rotulos: dict[str, dict] = {}

    for uid, no in dados["sources"].items():
        rotulos[uid] = {"id": uid, "nome": no["name"], "camada": "bronze"}
    for uid, no in dados["nodes"].items():
        if no["resource_type"] != "model":
            continue
        pasta = Path(no["original_file_path"]).parent.name
        rotulos[uid] = {
            "id": uid,
            "nome": no["name"],
            "camada": pasta if pasta in CAMADAS else "gold",
        }

    pais = {
        uid: [p for p in parentes if p in rotulos]
        for uid, parentes in dados["parent_map"].items()
        if uid in rotulos
    }

    profundidade: dict[str, int] = {}

    def calcular(uid: str) -> int:
        if uid in profundidade:
            return profundidade[uid]
        parentes = pais.get(uid, [])
        profundidade[uid] = 0 if not parentes else 1 + max(calcular(p) for p in parentes)
        return profundidade[uid]

    for uid in rotulos:
        calcular(uid)

    arestas = [
        {"de": pai, "para": uid} for uid, parentes in pais.items() for pai in parentes
    ]
    nos = [{**rotulos[uid], "nivel": profundidade[uid]} for uid in rotulos]
    nos.sort(key=lambda n: (n["nivel"], n["nome"]))
    return {"nos": nos, "arestas": arestas}


def coletar_uso(dag: dict) -> dict:
    """Separa o que alimenta a resposta final do que é terminal.

    Percorre os ancestrais dos agregados que respondem à pergunta de negócio.
    Um nó terminal não é desperdício: a quarentena existe para isolar o
    registro sem chave, e por isso não deve alimentar a Gold.
    """
    if not dag["nos"]:
        return {}

    pais: dict[str, list[str]] = {}
    for aresta in dag["arestas"]:
        pais.setdefault(aresta["para"], []).append(aresta["de"])

    alvos = [n["id"] for n in dag["nos"] if n["nome"].startswith("agg_")]
    usados: set[str] = set(alvos)

    def subir(uid: str) -> None:
        for pai in pais.get(uid, []):
            if pai not in usados:
                usados.add(pai)
                subir(pai)

    for alvo in alvos:
        subir(alvo)

    por_id = {n["id"]: n for n in dag["nos"]}
    return {
        "usados": sorted(
            ({"nome": por_id[u]["nome"], "camada": por_id[u]["camada"]} for u in usados),
            key=lambda n: (n["camada"], n["nome"]),
        ),
        "terminais": sorted(
            (
                {"nome": n["nome"], "camada": n["camada"]}
                for n in dag["nos"]
                if n["id"] not in usados
            ),
            key=lambda n: n["nome"],
        ),
    }


def coletar_testes() -> dict:
    manifesto = TARGET / "manifest.json"
    resultados = TARGET / "run_results.json"
    if not manifesto.exists():
        return {"por_tipo": [], "singulares": [], "total": 0}

    dados = json.loads(manifesto.read_text(encoding="utf-8"))
    status = {}
    if resultados.exists():
        status = {
            r["unique_id"]: r["status"]
            for r in json.loads(resultados.read_text(encoding="utf-8"))["results"]
        }

    contagem: dict[str, int] = {}
    singulares = []
    for uid, no in dados["nodes"].items():
        if no["resource_type"] != "test":
            continue
        meta = (no.get("test_metadata") or {}).get("name")
        tipo = meta or "singular (SQL próprio)"
        contagem[tipo] = contagem.get(tipo, 0) + 1
        if not meta:
            singulares.append(
                {
                    "nome": no["name"],
                    "status": status.get(uid, "—"),
                    "descricao": (no.get("description") or "").strip(),
                }
            )

    por_tipo = sorted(
        ({"tipo": t, "qtd": q} for t, q in contagem.items()),
        key=lambda x: -x["qtd"],
    )
    return {
        "por_tipo": por_tipo,
        "singulares": sorted(singulares, key=lambda s: s["nome"]),
        "total": sum(contagem.values()),
    }


def coletar_testes_python() -> dict:
    arquivos = sorted((RAIZ / "tests").glob("test_*.py"))
    casos = []
    for arquivo in arquivos:
        for nome in re.findall(r"^def (test_\w+)", arquivo.read_text(encoding="utf-8"), re.M):
            casos.append({"arquivo": arquivo.name, "nome": nome})
    return {"total": len(casos), "casos": casos}


def coletar_execucao() -> dict:
    resultados = TARGET / "run_results.json"
    if not resultados.exists():
        return {}

    dados = json.loads(resultados.read_text(encoding="utf-8"))
    nos = [
        {
            "nome": r["unique_id"].split(".")[-1],
            "tipo": "modelo" if r["unique_id"].startswith("model.") else "teste",
            "status": r["status"],
            "segundos": round(r["execution_time"], 3),
        }
        for r in dados["results"]
    ]
    modelos = [n for n in nos if n["tipo"] == "modelo"]
    testes = [n for n in nos if n["tipo"] == "teste"]
    return {
        "gerado_em": dados["metadata"]["generated_at"],
        "dbt_version": dados["metadata"]["dbt_version"],
        "elapsed": round(dados["elapsed_time"], 2),
        "total": len(nos),
        "modelos": len(modelos),
        "testes": len(testes),
        "sucesso": sum(1 for n in nos if n["status"] in ("success", "pass")),
        "falha": sum(1 for n in nos if n["status"] not in ("success", "pass")),
        "mais_lentos": sorted(nos, key=lambda n: -n["segundos"])[:10],
    }


# --------------------------------------------------------------------------- #
# DAG em SVG
# --------------------------------------------------------------------------- #
def desenhar_dag(dag: dict) -> str:
    nos = dag["nos"]
    if not nos:
        return '<p class="vazio">DAG indisponível: execute dbt build para gerar o manifest.</p>'

    largura_no, altura_no = 172, 36
    gap_x, gap_y = 72, 18
    margem = 22

    niveis: dict[int, list[dict]] = {}
    for no in nos:
        niveis.setdefault(no["nivel"], []).append(no)

    posicoes: dict[str, tuple[float, float]] = {}
    for nivel, grupo in niveis.items():
        for indice, no in enumerate(grupo):
            x = margem + nivel * (largura_no + gap_x)
            y = margem + 34 + indice * (altura_no + gap_y)
            posicoes[no["id"]] = (x, y)

    largura = margem * 2 + (max(niveis) + 1) * largura_no + max(niveis) * gap_x
    altura = margem * 2 + 34 + max(len(g) for g in niveis.values()) * (altura_no + gap_y)

    partes = [
        f'<svg viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}" '
        'role="img" aria-label="Grafo de dependências entre fontes e modelos dbt">'
    ]

    for nivel, grupo in sorted(niveis.items()):
        x = margem + nivel * (largura_no + gap_x)
        partes.append(
            f'<text x="{x}" y="{margem + 10}" class="dag-nivel">nível {nivel}'
            f' · {len(grupo)}</text>'
        )

    for aresta in dag["arestas"]:
        if aresta["de"] not in posicoes or aresta["para"] not in posicoes:
            continue
        x1, y1 = posicoes[aresta["de"]]
        x2, y2 = posicoes[aresta["para"]]
        x1 += largura_no
        y1 += altura_no / 2
        y2 += altura_no / 2
        meio = (x1 + x2) / 2
        partes.append(
            f'<path d="M {x1} {y1} C {meio} {y1}, {meio} {y2}, {x2} {y2}" class="dag-aresta"/>'
        )

    for no in nos:
        x, y = posicoes[no["id"]]
        nome = no["nome"]
        exibido = nome if len(nome) <= 24 else nome[:23] + "…"
        partes.append(
            f'<g class="dag-no camada-{no["camada"]}">'
            f'<title>{nome} — camada {CAMADAS[no["camada"]]} (nível {no["nivel"]})</title>'
            f'<rect x="{x}" y="{y}" width="{largura_no}" height="{altura_no}" rx="7"/>'
            f'<text x="{x + 11}" y="{y + 23}">{exibido}</text>'
            "</g>"
        )

    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------- #
# Dados da resposta
# --------------------------------------------------------------------------- #
def _dicts(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cursor = con.sql(sql)
    colunas = [d[0] for d in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def gerar() -> Path:
    mart = GOLD / "mart_indicadores_imoveis.parquet"
    if not mart.exists():
        raise SystemExit(
            f"{mart} não encontrado. Execute 'python -m src.pipeline' e depois 'dbt build'."
        )

    con = duckdb.connect()
    caminho_mart = mart.as_posix()

    imoveis = _dicts(
        con,
        f"""
        select
            id_predio                      as id,
            nome_oficial                   as nome,
            comarca,
            cidade,
            uf,
            situacao_patrimonial,
            propriedade,
            categoria_funcional,
            tipo_imovel,
            area_construida_m2             as area_construida,
            area_terreno_m2                as area_terreno,
            area_arquivo_m2                as area_arquivo,
            indice_aproveitamento_pct      as indice,
            sanitarios_total,
            densidade_sanitaria_por_1000_m2 as densidade,
            capacidade_total_litros        as litros,
            reserva_litros_por_m2          as reserva,
            elegivel_indice_aproveitamento as elegivel,
            tem_medicao_patrimonial        as tem_medicao,
            tem_vistoria_infraestrutura    as tem_vistoria
        from '{caminho_mart}'
        order by id_predio
        """,
    )

    geral = _dicts(con, f"select * from '{(GOLD / 'agg_aproveitamento_geral.parquet').as_posix()}'")
    comarca = _dicts(
        con,
        f"select * from '{(GOLD / 'agg_aproveitamento_comarca.parquet').as_posix()}' "
        "order by comarca, situacao_patrimonial",
    )

    quarentena = []
    caminho_q = SILVER / "quarentena_imoveis.parquet"
    if caminho_q.exists():
        quarentena = _dicts(
            con,
            f"""
            select _arquivo_origem as arquivo, linha_origem as linha,
                   nome_original as nome, classificacao_original as classificacao,
                   comarca_original as comarca, motivo_quarentena as motivo
            from '{caminho_q.as_posix()}' order by linha_origem
            """,
        )

    data_ref = con.sql(f"select max(data_referencia) from '{caminho_mart}'").fetchone()[0]
    modelos = coletar_modelos(con)
    fanout = coletar_fanout(con)
    con.close()

    contexto = {
        "pergunta": PERGUNTA,
        "data_referencia": data_ref.strftime("%d/%m/%Y"),
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "imoveis": imoveis,
        "geral": geral[0] if geral else {},
        "comarca": comarca,
        "quarentena": quarentena,
        "raw": coletar_raw(),
        "defeitos": [{"titulo": t, "detalhe": d} for t, d in DEFEITOS_RAW],
        "bronze": coletar_bronze(),
        "time_travel": coletar_time_travel(),
        "modelos": modelos,
        "fanout": fanout,
        "testes": coletar_testes(),
        "testes_python": coletar_testes_python(),
        "execucao": coletar_execucao(),
        "ambiente": {
            "python": platform.python_version(),
            "duckdb": duckdb.__version__,
            "plataforma": platform.system(),
        },
    }

    dag = coletar_dag()
    contexto["uso"] = coletar_uso(dag)
    contexto["area_arquivo_preenchida"] = sum(
        1 for i in imoveis if i.get("area_arquivo") is not None
    )

    html = (
        TEMPLATE.replace("__DAG_SVG__", desenhar_dag(dag))
        .replace("__PERGUNTA__", PERGUNTA)
        .replace("__DATA_REF__", contexto["data_referencia"])
        .replace("__GERADO_EM__", contexto["gerado_em"])
        .replace("__CONTEXTO__", json.dumps(contexto, ensure_ascii=False, default=str))
    )

    DESTINO.write_text(html, encoding="utf-8")
    return DESTINO


TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SIGOB Imóveis — do dado bruto à resposta</title>
<style>
  :root {
    --ink:#1b1a17; --ink-2:#4a463f; --ink-3:#7d776c;
    --surface:#faf8f5; --card:#fff; --linha:#e6e1d8; --sutil:#f1ece3;
    --marca:#8a6a2f; --marca-fraca:#e8dcc4;
    --ok:#3f6b45; --ok-fraca:#dfeadf; --atencao:#8c5a2f; --erro:#8c3a2f;
    --bronze:#9c6f3f; --silver:#7b7f86; --inter:#5f6f7a; --gold:#a8872f;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ink:#f2efe9; --ink-2:#c4bdb0; --ink-3:#908a7e;
      --surface:#141309; --card:#201e17; --linha:#38352b; --sutil:#2a271f;
      --marca:#d8ad5c; --marca-fraca:#4a3d22;
      --ok:#7fb288; --ok-fraca:#2a3a2c; --atencao:#d9a066; --erro:#d98c7a;
      --bronze:#c9924f; --silver:#a8adb5; --inter:#8fa3b0; --gold:#d8b95c;
    }
  }
  *{box-sizing:border-box}
  body{margin:0;padding:26px 20px 60px;background:var(--surface);color:var(--ink);
       font:14px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  .wrap{max-width:1180px;margin:0 auto}
  h1{font-size:22px;margin:0 0 6px;letter-spacing:-.015em}
  .pergunta{margin:0 0 6px;padding:13px 16px;background:var(--card);
            border-left:3px solid var(--marca);border-radius:0 8px 8px 0;
            font-size:14.5px;color:var(--ink)}
  .meta{color:var(--ink-3);font-size:12px;margin:8px 0 22px}
  nav{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:22px;border-bottom:1px solid var(--linha);padding-bottom:0}
  nav button{padding:9px 14px;font:inherit;font-size:13px;color:var(--ink-3);cursor:pointer;
             background:none;border:0;border-bottom:2px solid transparent;border-radius:0}
  nav button:hover{color:var(--ink)}
  nav button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--marca);font-weight:600}
  section[hidden]{display:none!important}
  h2{font-size:16px;margin:28px 0 4px;letter-spacing:-.01em}
  h2:first-child{margin-top:0}
  .ajuda{font-size:12.5px;color:var(--ink-3);margin:0 0 15px;max-width:76ch}
  .painel{padding:17px;background:var(--card);border:1px solid var(--linha);border-radius:10px;margin-bottom:18px}
  .filtros{display:flex;flex-wrap:wrap;gap:13px;align-items:flex-end;padding:15px;
           background:var(--card);border:1px solid var(--linha);border-radius:10px;margin-bottom:18px}
  .campo{display:flex;flex-direction:column;gap:5px}
  .campo label{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--ink-3)}
  select,button.acao{padding:8px 11px;font:inherit;color:var(--ink);background:var(--surface);
                     border:1px solid var(--linha);border-radius:7px}
  select{min-width:205px}
  button.acao{cursor:pointer;color:var(--ink-2)}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(162px,1fr));gap:11px;margin-bottom:20px}
  .kpi{padding:13px 15px;background:var(--card);border:1px solid var(--linha);border-radius:10px}
  .kpi .rotulo{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--ink-3)}
  .kpi .valor{font-size:26px;font-variant-numeric:tabular-nums;margin-top:4px;letter-spacing:-.02em}
  .kpi .nota{font-size:11px;color:var(--ink-3);margin-top:2px}
  .kpi.destaque{border-color:var(--marca)}
  .barras{display:flex;flex-direction:column;gap:8px}
  .barra{display:grid;grid-template-columns:200px 1fr 78px;gap:11px;align-items:center}
  .barra .nome{font-size:12px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .trilha{height:13px;background:var(--marca-fraca);border-radius:3px;position:relative}
  .preenche{height:100%;background:var(--marca);border-radius:0 4px 4px 0;min-width:2px}
  .preenche.verde{background:var(--ok)}
  .barra .num{font-size:12px;text-align:right;font-variant-numeric:tabular-nums;color:var(--ink-2)}
  .ref100{position:absolute;top:-3px;bottom:-3px;width:1px;background:var(--ink-3);opacity:.5}
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th,td{padding:7px 9px;text-align:left;border-bottom:1px solid var(--linha);vertical-align:top}
  th{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3);font-weight:600;
     position:sticky;top:0;background:var(--card)}
  td.n{text-align:right;font-variant-numeric:tabular-nums}
  .rolagem{overflow:auto;max-height:440px;border-radius:7px}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;
       background:var(--sutil);padding:1px 5px;border-radius:4px}
  .vazio{color:var(--ink-3);font-size:13px;padding:13px 0;margin:0}
  .selo{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10.5px;
        letter-spacing:.04em;text-transform:uppercase;border:1px solid var(--linha);color:var(--ink-2)}
  .selo.ok{background:var(--ok-fraca);border-color:transparent;color:var(--ok)}
  .selo.aviso{color:var(--atencao)}
  .grade2{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:14px}
  .etapa{padding:15px;background:var(--card);border:1px solid var(--linha);border-radius:10px;
         border-top:3px solid var(--marca)}
  .etapa.bronze{border-top-color:var(--bronze)}
  .etapa.silver{border-top-color:var(--silver)}
  .etapa.intermediate{border-top-color:var(--inter)}
  .etapa.gold{border-top-color:var(--gold)}
  .etapa h3{font-size:13.5px;margin:0 0 3px}
  .etapa .sub{font-size:11.5px;color:var(--ink-3);margin:0 0 11px}
  .lista{list-style:none;padding:0;margin:0;font-size:12.5px}
  .lista li{padding:6px 0;border-top:1px solid var(--linha)}
  .lista li:first-child{border-top:0}
  .lista .quanto{float:right;font-variant-numeric:tabular-nums;color:var(--ink-3);margin-left:10px}
  .dag-rolagem{overflow-x:auto;padding-bottom:8px}
  .dag-aresta{fill:none;stroke:var(--ink-3);stroke-width:1.2;opacity:.45}
  .dag-no rect{fill:var(--sutil);stroke:var(--linha);stroke-width:1}
  .dag-no text{font-size:11.5px;fill:var(--ink)}
  .dag-no.camada-bronze rect{stroke:var(--bronze);stroke-width:1.6}
  .dag-no.camada-silver rect{stroke:var(--silver);stroke-width:1.6}
  .dag-no.camada-intermediate rect{stroke:var(--inter);stroke-width:1.6}
  .dag-no.camada-gold rect{stroke:var(--gold);stroke-width:1.6}
  .dag-nivel{font-size:10.5px;fill:var(--ink-3);letter-spacing:.06em;text-transform:uppercase}
  .legenda{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;font-size:11.5px;color:var(--ink-2)}
  .legenda i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;
             vertical-align:-1px;border:1.6px solid var(--linha);background:var(--sutil)}
  .legenda .lb{border-color:var(--bronze)} .legenda .ls{border-color:var(--silver)}
  .legenda .li{border-color:var(--inter)} .legenda .lg{border-color:var(--gold)}
  footer{color:var(--ink-3);font-size:11.5px;margin-top:30px;line-height:1.8;
         border-top:1px solid var(--linha);padding-top:14px}
  @media (max-width:620px){.barra{grid-template-columns:116px 1fr 64px}}
</style>
</head>
<body>
<div class="wrap">

  <h1>SIGOB Imóveis — do dado bruto à resposta</h1>
  <p class="pergunta"><strong>Pergunta de negócio:</strong> __PERGUNTA__</p>
  <p class="meta">Data de referência do levantamento: __DATA_REF__ · dashboard gerado em __GERADO_EM__ ·
     as medidas vêm calculadas e testadas da Gold; este painel apenas filtra, agrega e exibe.</p>

  <nav role="tablist">
    <button role="tab" data-aba="resposta" aria-selected="true">Resposta</button>
    <button role="tab" data-aba="etapas" aria-selected="false">Etapas do pipeline</button>
    <button role="tab" data-aba="linhagem" aria-selected="false">Linhagem (DAG)</button>
    <button role="tab" data-aba="incompletos" aria-selected="false">Registros incompletos</button>
    <button role="tab" data-aba="qualidade" aria-selected="false">Qualidade</button>
    <button role="tab" data-aba="execucao" aria-selected="false">Execução</button>
  </nav>

  <!-- ---------------------------------------------------------------- -->
  <section id="aba-resposta">
    <div class="filtros">
      <div class="campo"><label for="f-comarca">Comarca</label><select id="f-comarca"></select></div>
      <div class="campo"><label for="f-situacao">Situação patrimonial</label><select id="f-situacao"></select></div>
      <button class="acao" id="limpar" type="button">Limpar filtros</button>
    </div>

    <div class="kpis" id="kpis"></div>

    <div class="painel">
      <h2>Índice de aproveitamento por comarca</h2>
      <p class="ajuda">Razão global da comarca: soma das áreas construídas ÷ soma das áreas de terreno.
         A linha vertical marca 100%; acima dela a área construída soma mais de um pavimento, o que não é erro.</p>
      <div class="barras" id="barras-comarca"></div>
    </div>

    <div class="painel">
      <h2>Cobertura da resposta</h2>
      <p class="ajuda">Quantos imóveis cada etapa da métrica alcança. Cobertura também é resultado.</p>
      <div class="barras" id="barras-cobertura"></div>
    </div>

    <div class="painel">
      <h2>Imóveis no recorte</h2>
      <p class="ajuda">Medida ausente aparece como “—”, nunca como zero.</p>
      <div class="rolagem">
        <table>
          <thead><tr><th>ID</th><th>Nome oficial</th><th>Comarca</th><th>Situação</th>
            <th class="n">Constr. m²</th><th class="n">Terreno m²</th><th class="n">Índice</th>
            <th class="n">Sanit.</th><th class="n">Reserva L/m²</th></tr></thead>
          <tbody id="corpo-imoveis"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ---------------------------------------------------------------- -->
  <section id="aba-etapas" hidden>
    <h2>Raw — os arquivos como foram recebidos</h2>
    <p class="ajuda">Ponto de reprocessamento. O pipeline nunca escreve aqui.</p>
    <div class="painel"><div class="rolagem"><table>
      <thead><tr><th>Arquivo</th><th>Formato</th><th class="n">Bytes</th><th class="n">Linhas físicas</th></tr></thead>
      <tbody id="corpo-raw"></tbody></table></div></div>

    <h2>Defeitos e ambiguidades preservados</h2>
    <p class="ajuda">Nada disso foi corrigido na ingestão. A interpretação começa na Silver.</p>
    <div class="painel"><ul class="lista" id="lista-defeitos"></ul></div>

    <h2>Bronze — preservação em Delta Lake</h2>
    <p class="ajuda">Cópia fiel e consultável, com metadados técnicos de origem, linha, versão, instante e hash.
       Cada gravação é uma transação registrada no <code>_delta_log</code>.</p>
    <div class="painel"><div class="rolagem"><table>
      <thead><tr><th>Tabela</th><th class="n">Versão</th><th>Operação</th><th>Modo</th>
        <th class="n">Linhas</th><th class="n">Arq. +</th><th class="n">Arq. −</th></tr></thead>
      <tbody id="corpo-bronze"></tbody></table></div></div>

    <h2>Time travel — a mesma consulta em duas versões</h2>
    <p class="ajuda">O código da consulta é idêntico; o que muda é a versão da tabela que o Delta reconstrói.</p>
    <div class="painel"><div class="rolagem"><table>
      <thead><tr><th class="n">Versão</th><th>Estado</th><th class="n">Linhas físicas</th>
        <th class="n">Imóveis com ID</th><th class="n">Registro sem ID</th></tr></thead>
      <tbody id="corpo-tt"></tbody></table></div></div>

    <h2>Silver, Intermediate e Gold — modelos dbt</h2>
    <p class="ajuda">Toda regra de negócio está aqui, em modelo versionado. Não há script manual entre camadas.</p>
    <div class="grade2" id="grade-modelos"></div>

    <h2>Por que a camada Intermediate existe</h2>
    <p class="ajuda">Sanitários e reservatórios têm vários registros por vistoria. Juntar as duas coleções
       direto na fato multiplicaria o imóvel e distorceria áreas e médias — sem gerar erro técnico.</p>
    <div class="painel" id="painel-fanout"></div>

    <h2>Onde cada coisa é calculada</h2>
    <p class="ajuda">A regra de negócio começa na Silver e termina na Gold. A ingestão não calcula e a
       camada de resposta não recalcula.</p>
    <div class="painel"><div class="rolagem"><table>
      <thead><tr><th>Etapa</th><th>Calcula métrica?</th><th>O que faz</th><th>Onde no código</th></tr></thead>
      <tbody>
        <tr>
          <td><strong>Ingestão Python</strong></td>
          <td><span class="selo">não</span></td>
          <td>Lê Raw e grava Bronze. Acrescenta só metadados técnicos: arquivo, linha, versão, instante e hash.</td>
          <td><code>src/ingest.py</code><br><code>src/pipeline.py</code></td>
        </tr>
        <tr>
          <td><strong>Silver</strong></td>
          <td><span class="selo">converte, não calcula métrica</span></td>
          <td>Descarta linhas estruturais, tipa ID e data, converte decimal brasileiro
              (<code>23.364,50</code> → <code>23364.50</code>), interpreta capacidade de reservatório,
              separa propriedade/categoria/tipo e isola o registro sem ID.</td>
          <td><code>stg_patrimonio.sql:34-38</code><br><code>stg_imoveis.sql:11,23,27</code></td>
        </tr>
        <tr>
          <td><strong>Intermediate</strong></td>
          <td><span class="selo">agrega coleções</span></td>
          <td>Soma e conta sanitários e reservatórios no grão imóvel/data, antes da junção com a fato.</td>
          <td><code>int_reservatorios_por_imovel.sql:20</code><br><code>int_sanitarios_por_imovel.sql</code></td>
        </tr>
        <tr>
          <td><strong>Gold — fato</strong></td>
          <td><span class="selo ok">sim: indicadores por imóvel</span></td>
          <td>Índice de aproveitamento, densidade sanitária e reserva por m². Também marca a
              elegibilidade: sem área de terreno maior que zero, o resultado é nulo, nunca zero.</td>
          <td><code>fato_imovel_snapshot.sql:59</code> índice<br>
              <code>:64</code> densidade · <code>:69</code> reserva</td>
        </tr>
        <tr>
          <td><strong>Gold — agregados</strong></td>
          <td><span class="selo ok">sim: métricas agregadas</span></td>
          <td>Média dos índices individuais e índice global ponderado, no total e por
              comarca × situação patrimonial.</td>
          <td><code>agg_aproveitamento_geral.sql:10,16</code><br>
              <code>agg_aproveitamento_comarca.sql:12,18</code></td>
        </tr>
        <tr>
          <td><strong>Consulta final e este dashboard</strong></td>
          <td><span class="selo">não</span></td>
          <td>Leem medidas prontas da Gold e apenas filtram, agrupam, ordenam e exibem.
              A consulta principal não tem <code>WHERE</code>.</td>
          <td><code>consultas/resposta.sql</code><br><code>scripts/gerar_dashboard.py</code></td>
        </tr>
      </tbody>
    </table></div></div>
  </section>

  <!-- ---------------------------------------------------------------- -->
  <section id="aba-linhagem" hidden>
    <h2>Grafo de dependências</h2>
    <p class="ajuda">Gerado a partir do <code>manifest.json</code> real do dbt, pelos <code>source()</code> e
       <code>ref()</code> usados nos modelos. <strong>Não é linha do tempo:</strong> cada seta significa
       “preciso deste modelo construído antes”. O nível é a distância máxima até uma fonte.</p>
    <div class="painel">
      <div class="dag-rolagem">__DAG_SVG__</div>
      <div class="legenda">
        <span><i class="lb"></i>Bronze (fonte Delta)</span>
        <span><i class="ls"></i>Silver</span>
        <span><i class="li"></i>Intermediate</span>
        <span><i class="lg"></i>Gold</span>
      </div>
    </div>
    <h2>O que é usado e o que não é usado</h2>
    <p class="ajuda">Calculado percorrendo os ancestrais reais dos agregados que respondem à pergunta.
       Um nó terminal não é desperdício: a quarentena existe justamente para <em>não</em> alimentar a Gold.</p>
    <div class="grade2">
      <div class="etapa gold">
        <h3>Alimentam a resposta final</h3>
        <p class="sub" id="sub-usados"></p>
        <ul class="lista" id="lista-usados"></ul>
      </div>
      <div class="etapa silver">
        <h3>Não alimentam a resposta (terminais)</h3>
        <p class="sub" id="sub-terminais"></p>
        <ul class="lista" id="lista-terminais"></ul>
      </div>
    </div>

    <div class="painel">
      <h2>No nível dos dados</h2>
      <p class="ajuda">O que foi ingerido e preservado, mas não participa da métrica principal.</p>
      <div class="rolagem"><table>
        <thead><tr><th>Item</th><th>Situação</th><th>Por quê</th></tr></thead>
        <tbody id="corpo-uso-dados"></tbody>
      </table></div>
    </div>
  </section>

  <!-- ---------------------------------------------------------------- -->
  <section id="aba-incompletos" hidden>
    <h2>Por que 42 dos 102 imóveis ficam fora do índice</h2>
    <p class="ajuda">Ausência de medição não vira zero. Zero afirmaria que a medição foi feita e deu zero;
       nulo afirma que não há informação suficiente.</p>
    <div class="kpis" id="kpis-lacunas"></div>
    <div class="painel">
      <h2>Onde está a lacuna</h2>
      <div class="barras" id="barras-lacunas"></div>
    </div>

    <h2>Registros incompletos, imóvel por imóvel</h2>
    <p class="ajuda">Cada linha diz exatamente qual informação falta para o imóvel entrar no cálculo.</p>
    <div class="painel"><div class="rolagem"><table>
      <thead><tr><th>ID</th><th>Nome oficial</th><th>Comarca</th><th>Situação</th>
        <th>O que falta</th><th class="n">Constr. m²</th><th class="n">Terreno m²</th></tr></thead>
      <tbody id="corpo-incompletos"></tbody></table></div></div>

    <h2>Quarentena — isolado, não descartado</h2>
    <p class="ajuda">Registro de negócio sem ID oficial. Não entra na estrela porque não há chave confiável,
       e não é apagado: fica preservado com arquivo, linha, conteúdo original e motivo. A ação esperada é
       obter o ID oficial e reprocessar o pipeline.</p>
    <div class="painel"><div class="rolagem"><table>
      <thead><tr><th>Arquivo</th><th class="n">Linha</th><th>Nome original</th>
        <th>Classificação</th><th>Comarca</th><th>Motivo</th></tr></thead>
      <tbody id="corpo-quarentena"></tbody></table></div></div>
  </section>

  <!-- ---------------------------------------------------------------- -->
  <section id="aba-qualidade" hidden>
    <h2>Testes de dados (dbt)</h2>
    <p class="ajuda">Contratos observáveis. Executados no mesmo <code>dbt build</code>: se um teste da Silver
       falha, a Gold não é construída e o dado ruim não propaga.</p>
    <div class="kpis" id="kpis-testes"></div>
    <div class="painel">
      <h2>Testes por tipo</h2>
      <div class="barras" id="barras-testes"></div>
    </div>
    <div class="painel">
      <h2>Testes singulares (SQL próprio)</h2>
      <div class="rolagem"><table>
        <thead><tr><th>Teste</th><th>Status</th></tr></thead>
        <tbody id="corpo-singulares"></tbody></table></div>
    </div>
    <div class="painel">
      <h2>Testes do código de ingestão (pytest)</h2>
      <div class="rolagem"><table>
        <thead><tr><th>Arquivo</th><th>Caso</th></tr></thead>
        <tbody id="corpo-pytest"></tbody></table></div>
    </div>
  </section>

  <!-- ---------------------------------------------------------------- -->
  <section id="aba-execucao" hidden>
    <h2>Última execução do pipeline</h2>
    <p class="ajuda">Lido de <code>dbt/target/run_results.json</code> — é o registro real da execução,
       não um número digitado à mão.</p>
    <div class="kpis" id="kpis-execucao"></div>
    <div class="painel">
      <h2>Recursos mais lentos</h2>
      <div class="barras" id="barras-tempo"></div>
    </div>
    <div class="painel">
      <h2>Ambiente</h2>
      <ul class="lista" id="lista-ambiente"></ul>
    </div>
    <div class="painel">
      <h2>Reprodução em clone limpo</h2>
      <p class="ajuda">As dependências estão fixadas em <code>requirements.txt</code>. Nenhuma camada
         intermediária precisa de edição manual.</p>
      <ul class="lista">
        <li><code>python3 -m venv .venv &amp;&amp; source .venv/bin/activate</code></li>
        <li><code>pip install -r requirements.txt</code></li>
        <li><code>python scripts/zerar.py</code><span class="quanto">remove só o que é gerado</span></li>
        <li><code>python -m src.pipeline</code><span class="quanto">Raw → Bronze Delta</span></li>
        <li><code>cd dbt &amp;&amp; dbt build &amp;&amp; cd ..</code><span class="quanto">Silver → Gold + testes</span></li>
        <li><code>python scripts/gerar_dashboard.py</code><span class="quanto">este dashboard</span></li>
      </ul>
    </div>
  </section>

  <footer>
    Fontes do painel: <code>data/gold/*.parquet</code>, <code>data/silver/quarentena_imoveis.parquet</code>,
    <code>data/bronze/*/_delta_log/</code>, <code>dbt/target/manifest.json</code> e
    <code>dbt/target/run_results.json</code>.<br>
    Gerado por <code>scripts/gerar_dashboard.py</code>, último passo do ciclo, depois de <code>dbt build</code>.
  </footer>

</div>

<script>
const CTX = __CONTEXTO__;

const num = (v, d = 2) => v === null || v === undefined
  ? "—" : Number(v).toLocaleString("pt-BR", {minimumFractionDigits:d, maximumFractionDigits:d});
const int = (v) => v === null || v === undefined ? "—" : Number(v).toLocaleString("pt-BR");
const pct = (v, d = 2) => v === null || v === undefined ? "—" : num(v, d) + "%";
const esc = (s) => String(s ?? "").replace(/[&<>]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

/* ---------------- abas ---------------- */
const abas = [...document.querySelectorAll("nav button")];
abas.forEach((b) => b.addEventListener("click", () => {
  abas.forEach((o) => {
    o.setAttribute("aria-selected", String(o === b));
    document.getElementById("aba-" + o.dataset.aba).hidden = o !== b;
  });
}));

/* ---------------- barras genéricas ---------------- */
function barras(alvo, dados, opcoes = {}) {
  const el = document.getElementById(alvo);
  if (!dados.length) {
    el.innerHTML = '<p class="vazio">' + (opcoes.vazio || "Sem dados neste recorte.") + "</p>";
    return;
  }
  const maximo = Math.max(...dados.map((d) => d.valor), opcoes.minimoEscala || 0) || 1;
  el.innerHTML = dados.map((d) => {
    const ref = opcoes.ref100 && maximo >= 100
      ? '<div class="ref100" style="left:' + (100 * 100 / maximo) + '%"></div>' : "";
    return '<div class="barra" title="' + esc(d.dica || d.nome) + '">'
      + '<div class="nome">' + esc(d.nome) + "</div>"
      + '<div class="trilha"><div class="preenche' + (opcoes.verde ? " verde" : "")
      + '" style="width:' + (100 * d.valor / maximo) + '%"></div>' + ref + "</div>"
      + '<div class="num">' + d.rotulo + "</div></div>";
  }).join("");
}

/* ---------------- aba resposta ---------------- */
const selComarca = document.getElementById("f-comarca");
const selSituacao = document.getElementById("f-situacao");
const unicos = (c) => [...new Set(CTX.imoveis.map((i) => i[c]))].sort((a,b) => String(a).localeCompare(String(b), "pt-BR"));

function popular(sel, valores, rotulo) {
  sel.innerHTML = '<option value="__TODOS__">' + rotulo + "</option>"
    + valores.map((v) => '<option value="' + esc(v) + '">' + esc(v) + "</option>").join("");
}
popular(selComarca, unicos("comarca"), "Todas as comarcas (" + unicos("comarca").length + ")");
popular(selSituacao, unicos("situacao_patrimonial"), "Todas as situações (" + unicos("situacao_patrimonial").length + ")");

const filtrar = () => CTX.imoveis.filter((i) =>
  (selComarca.value === "__TODOS__" || i.comarca === selComarca.value) &&
  (selSituacao.value === "__TODOS__" || i.situacao_patrimonial === selSituacao.value));

function kpis(linhas) {
  const el = linhas.filter((i) => i.elegivel);
  const medicao = linhas.filter((i) => i.tem_medicao);
  const somaC = el.reduce((a, i) => a + Number(i.area_construida), 0);
  const somaT = el.reduce((a, i) => a + Number(i.area_terreno), 0);
  const media = el.length ? el.reduce((a, i) => a + i.indice, 0) / el.length : null;
  const global = somaT > 0 ? 100 * somaC / somaT : null;
  const cobertura = linhas.length ? 100 * el.length / linhas.length : null;

  document.getElementById("kpis").innerHTML = [
    ["Imóveis no recorte", int(linhas.length), "identificados no cadastro", ""],
    ["Com medição patrimonial", int(medicao.length), "possuem registro no patrimônio", ""],
    ["Elegíveis ao índice", int(el.length), "têm as duas áreas necessárias", ""],
    ["Média dos índices", media === null ? "—" : pct(media), "cada imóvel pesa igual", "destaque"],
    ["Índice global", global === null ? "—" : pct(global), "ponderado pelo tamanho do terreno", "destaque"],
    ["Cobertura elegível", cobertura === null ? "—" : pct(cobertura, 1), "elegíveis ÷ imóveis do recorte", ""],
  ].map(([r, v, n, c]) => '<div class="kpi ' + c + '"><div class="rotulo">' + r
    + '</div><div class="valor">' + v + '</div><div class="nota">' + n + "</div></div>").join("");

  barras("barras-cobertura", [
    {nome:"Identificados no cadastro", valor:linhas.length, rotulo:int(linhas.length)},
    {nome:"Com medição patrimonial", valor:medicao.length, rotulo:int(medicao.length)},
    {nome:"Elegíveis ao índice", valor:el.length, rotulo:int(el.length)},
  ], {verde:true});
}

function barrasComarca(linhas) {
  const mapa = new Map();
  linhas.filter((i) => i.elegivel).forEach((i) => {
    const a = mapa.get(i.comarca) || {c:0, t:0, n:0};
    a.c += Number(i.area_construida); a.t += Number(i.area_terreno); a.n += 1;
    mapa.set(i.comarca, a);
  });
  const dados = [...mapa.entries()]
    .map(([nome, v]) => ({nome, valor:100*v.c/v.t, rotulo:num(100*v.c/v.t,1)+"%",
                          dica:nome+": "+num(100*v.c/v.t)+"% — "+v.n+" imóvel(is) elegível(is)"}))
    .sort((a,b) => b.valor - a.valor);
  barras("barras-comarca", dados, {ref100:true,
    vazio:"Nenhum imóvel elegível neste recorte: faltam área construída ou área de terreno. Por isso não exibimos valor zero."});
}

function tabelaImoveis(linhas) {
  const ord = [...linhas].sort((a,b) => (b.indice ?? -1) - (a.indice ?? -1) || a.id - b.id);
  document.getElementById("corpo-imoveis").innerHTML = ord.map((i) => "<tr>"
    + '<td class="n">' + i.id + "</td><td>" + esc(i.nome) + "</td><td>" + esc(i.comarca) + "</td>"
    + "<td>" + esc(i.situacao_patrimonial) + "</td>"
    + '<td class="n">' + num(i.area_construida) + '</td><td class="n">' + num(i.area_terreno) + "</td>"
    + '<td class="n">' + (i.indice === null ? "—" : pct(i.indice)) + "</td>"
    + '<td class="n">' + int(i.sanitarios_total) + '</td><td class="n">' + num(i.reserva) + "</td></tr>").join("");
}

function render() {
  const linhas = filtrar();
  kpis(linhas); barrasComarca(linhas); tabelaImoveis(linhas);
}
selComarca.addEventListener("change", render);
selSituacao.addEventListener("change", render);
document.getElementById("limpar").addEventListener("click", () => {
  selComarca.value = "__TODOS__"; selSituacao.value = "__TODOS__"; render();
});

/* ---------------- aba etapas ---------------- */
document.getElementById("corpo-raw").innerHTML = CTX.raw.map((r) => "<tr><td><code>"
  + esc(r.arquivo) + "</code></td><td>" + esc(r.formato) + '</td><td class="n">' + int(r.bytes)
  + '</td><td class="n">' + (r.linhas_fisicas === null ? "—" : int(r.linhas_fisicas))
  + "</td></tr>").join("");

document.getElementById("lista-defeitos").innerHTML = CTX.defeitos.map((d) =>
  "<li><strong>" + esc(d.titulo) + "</strong><br><span style='color:var(--ink-3)'>"
  + esc(d.detalhe) + "</span></li>").join("");

document.getElementById("corpo-bronze").innerHTML = CTX.bronze.flatMap((t) =>
  t.commits.map((c, idx) => "<tr>"
    + "<td>" + (idx === 0 ? "<code>" + esc(t.tabela) + "</code>" : "") + "</td>"
    + '<td class="n">v' + c.versao + "</td><td>" + esc(c.operacao) + "</td><td>" + esc(c.modo) + "</td>"
    + '<td class="n">' + int(c.linhas) + '</td><td class="n">' + int(c.arquivos_add)
    + '</td><td class="n">' + int(c.arquivos_rem) + "</td></tr>")).join("");

document.getElementById("corpo-tt").innerHTML = CTX.time_travel.length
  ? CTX.time_travel.map((v) => '<tr><td class="n">v' + v.versao + "</td><td>" + esc(v.rotulo)
      + '</td><td class="n">' + int(v.linhas_fisicas) + '</td><td class="n">' + int(v.com_id)
      + '</td><td class="n">' + int(v.sem_id) + "</td></tr>").join("")
  : '<tr><td colspan="5" class="vazio">Execute python -m src.pipeline para gerar as duas versões.</td></tr>';

const ROTULO_CAMADA = {silver:"Silver — interpreta e limpa", intermediate:"Intermediate — corrige o grão", gold:"Gold — métricas e consumo"};
document.getElementById("grade-modelos").innerHTML = ["silver","intermediate","gold"].map((camada) => {
  const itens = CTX.modelos[camada] || [];
  if (!itens.length) return "";
  const corpo = itens.map((m) => {
    const fan = m.fanout
      ? "<br><span style='color:var(--atencao)'>" + int(m.fanout.detalhe) + " linhas de "
        + esc(m.fanout.rotulo) + " → " + int(m.fanout.reduzido)
        + " combinações imóvel/data (evita fan-out)</span>" : "";
    return "<li><code>" + esc(m.modelo) + '</code><span class="quanto">'
      + int(m.linhas) + " linhas</span><br><span style='color:var(--ink-3)'>" + esc(m.descricao)
      + "</span>" + fan + "</li>";
  }).join("");
  return '<div class="etapa ' + camada + '"><h3>' + ROTULO_CAMADA[camada] + "</h3>"
    + '<p class="sub">' + itens.length + " modelo(s) · " + esc(itens[0].materializacao)
    + '</p><ul class="lista">' + corpo + "</ul></div>";
}).join("");

/* ---------------- fan-out ---------------- */
const fo = CTX.fanout || {};
document.getElementById("painel-fanout").innerHTML = Object.keys(fo).length
  ? '<ul class="lista">'
    + "<li>Imóveis com vistoria<span class='quanto'>" + int(fo.imoveis_com_vistoria) + "</span></li>"
    + "<li>Linhas detalhadas de sanitários<span class='quanto'>" + int(fo.linhas_sanitarios) + "</span></li>"
    + "<li>Linhas detalhadas de reservatórios<span class='quanto'>" + int(fo.linhas_reservatorios) + "</span></li>"
    + "<li><strong>Se as duas coleções fossem juntadas direto na fato</strong>"
    + "<span class='quanto' style='color:var(--erro)'>" + int(fo.linhas_se_juntasse_direto)
    + " linhas</span><br><span style='color:var(--ink-3)'>em vez de uma linha por imóvel; "
    + "no pior caso, " + int(fo.pior_caso_por_imovel)
    + " linhas para o mesmo imóvel — as áreas seriam contadas várias vezes</span></li>"
    + "<li><strong>Com a Intermediate, a fato fica no grão declarado</strong>"
    + "<span class='quanto' style='color:var(--ok)'>" + int(CTX.imoveis.length)
    + " linhas</span><br><span style='color:var(--ink-3)'>uma linha por imóvel e data de referência, "
    + "protegido pelo teste <code>assert_fato_no_grao_declarado</code></span></li>"
    + "</ul>"
  : '<p class="vazio">Execute dbt build para medir o fan-out.</p>';

/* ---------------- o que é usado ---------------- */
const uso = CTX.uso || {usados:[], terminais:[]};
const itemUso = (n) => "<li><code>" + esc(n.nome) + '</code><span class="quanto selo">'
  + esc(n.camada) + "</span></li>";
document.getElementById("sub-usados").textContent =
  uso.usados.length + " de " + (uso.usados.length + uso.terminais.length) + " nós do grafo";
document.getElementById("lista-usados").innerHTML = uso.usados.map(itemUso).join("");
document.getElementById("sub-terminais").textContent =
  uso.terminais.length + " nó(s) — isolado é esperado, não é erro";
document.getElementById("lista-terminais").innerHTML = uso.terminais.length
  ? uso.terminais.map(itemUso).join("")
  : '<li class="vazio">Nenhum nó terminal.</li>';

const semVistoria = CTX.imoveis.filter((i) => !i.tem_vistoria).length;
const semMedicao = CTX.imoveis.filter((i) => !i.tem_medicao).length;
const foraIndice = CTX.imoveis.filter((i) => !i.elegivel).length;
document.getElementById("corpo-uso-dados").innerHTML = [
  ["Cadastro Mestre (CSV) + Patrimônio (CSV)",
   '<span class="selo ok">usado na fórmula principal</span>',
   "Fornecem área construída e área de terreno, as duas medidas do índice."],
  ["Infraestrutura predial (JSON)",
   '<span class="selo">usado em indicadores secundários</span>',
   "Produz densidade sanitária e reserva por m². Não participa da fórmula de área construída ÷ terreno."],
  ["Delta v0 do Cadastro Mestre",
   '<span class="selo">não usado no cálculo</span>',
   "A Gold lê a versão corrente. A v0 existe para auditoria e time travel, e não é somada à Gold atual."],
  [int(foraIndice) + " imóveis sem base completa",
   '<span class="selo aviso">fora do índice</span>',
   "Faltam área de terreno ou registro patrimonial. Ficam no modelo com medida nula, nunca zero."],
  [int(CTX.quarentena.length) + " registro em quarentena",
   '<span class="selo aviso">isolado, não descartado</span>',
   "Sem ID oficial não há chave confiável. Preservado com arquivo, linha, conteúdo e motivo."],
  ["Coluna <code>area_arquivo_m2</code> (" + int(CTX.area_arquivo_preenchida) + " preenchidas)",
   '<span class="selo">preservada, não usada</span>',
   "Convertida e disponível na Gold, mas não entra em nenhum indicador desta entrega."],
  [int(semVistoria) + " imóveis sem vistoria e " + int(semMedicao) + " sem medição patrimonial",
   '<span class="selo aviso">cobertura declarada</span>',
   "Permanecem no cadastro e aparecem na contagem; apenas não têm indicador calculável."],
].map(([item, selo, porque]) => "<tr><td>" + item + "</td><td>" + selo + "</td><td>"
  + porque + "</td></tr>").join("");

/* ---------------- aba incompletos ---------------- */
function classificar(i) {
  if (i.elegivel) return null;
  if (!i.tem_medicao) return "Sem registro patrimonial";
  const faltas = [];
  if (i.area_construida === null) faltas.push("área construída");
  if (i.area_terreno === null) faltas.push("área de terreno");
  return faltas.length ? "Falta " + faltas.join(" e ") : "Área de terreno igual a zero";
}

const incompletos = CTX.imoveis.filter((i) => !i.elegivel).map((i) => ({...i, falta: classificar(i)}));
const porMotivo = new Map();
incompletos.forEach((i) => porMotivo.set(i.falta, (porMotivo.get(i.falta) || 0) + 1));

document.getElementById("kpis-lacunas").innerHTML = [
  ["Imóveis identificados", int(CTX.imoveis.length), "no snapshot atual"],
  ["Fora do índice", int(incompletos.length), "não têm base completa"],
  ["Em quarentena", int(CTX.quarentena.length), "sem ID oficial, isolado"],
  ["Cobertura elegível", pct(100 * (CTX.imoveis.length - incompletos.length) / CTX.imoveis.length, 1), "do portfólio identificado"],
].map(([r,v,n]) => '<div class="kpi"><div class="rotulo">' + r + '</div><div class="valor">' + v
  + '</div><div class="nota">' + n + "</div></div>").join("");

barras("barras-lacunas", [...porMotivo.entries()]
  .map(([nome, valor]) => ({nome, valor, rotulo: int(valor)}))
  .sort((a,b) => b.valor - a.valor));

document.getElementById("corpo-incompletos").innerHTML = incompletos
  .sort((a,b) => a.falta.localeCompare(b.falta, "pt-BR") || a.id - b.id)
  .map((i) => "<tr>"
    + '<td class="n">' + i.id + "</td><td>" + esc(i.nome) + "</td><td>" + esc(i.comarca) + "</td>"
    + "<td>" + esc(i.situacao_patrimonial) + '</td><td><span class="selo aviso">' + esc(i.falta) + "</span></td>"
    + '<td class="n">' + num(i.area_construida) + '</td><td class="n">' + num(i.area_terreno)
    + "</td></tr>").join("");

document.getElementById("corpo-quarentena").innerHTML = CTX.quarentena.length
  ? CTX.quarentena.map((q) => "<tr><td><code>" + esc(q.arquivo) + '</code></td><td class="n">'
      + int(q.linha) + "</td><td>" + esc(q.nome) + "</td><td>" + esc(q.classificacao)
      + "</td><td>" + esc(q.comarca) + '</td><td><span class="selo aviso">' + esc(q.motivo)
      + "</span></td></tr>").join("")
  : '<tr><td colspan="6" class="vazio">Nenhum registro em quarentena.</td></tr>';

/* ---------------- aba qualidade ---------------- */
document.getElementById("kpis-testes").innerHTML = [
  ["Testes de dados", int(CTX.testes.total), "executados pelo dbt build"],
  ["Tipos de teste", int(CTX.testes.por_tipo.length), "genéricos e singulares"],
  ["Singulares", int(CTX.testes.singulares.length), "SQL escrito para esta PoC"],
  ["Testes de ingestão", int(CTX.testes_python.total), "pytest sobre src/"],
].map(([r,v,n]) => '<div class="kpi"><div class="rotulo">' + r + '</div><div class="valor">' + v
  + '</div><div class="nota">' + n + "</div></div>").join("");

barras("barras-testes", CTX.testes.por_tipo.map((t) =>
  ({nome:t.tipo, valor:t.qtd, rotulo:int(t.qtd)})), {verde:true});

document.getElementById("corpo-singulares").innerHTML = CTX.testes.singulares.map((t) =>
  "<tr><td><code>" + esc(t.nome) + "</code>"
  + (t.descricao ? "<br><span style='color:var(--ink-3)'>" + esc(t.descricao) + "</span>" : "")
  + '</td><td><span class="selo ' + (t.status === "pass" ? "ok" : "") + '">'
  + esc(t.status) + "</span></td></tr>").join("");

document.getElementById("corpo-pytest").innerHTML = CTX.testes_python.casos.map((c) =>
  "<tr><td><code>" + esc(c.arquivo) + "</code></td><td><code>" + esc(c.nome)
  + "</code></td></tr>").join("");

/* ---------------- aba execução ---------------- */
const ex = CTX.execucao || {};
document.getElementById("kpis-execucao").innerHTML = Object.keys(ex).length ? [
  ["Recursos executados", int(ex.total), ex.modelos + " modelos + " + ex.testes + " testes"],
  ["Sucesso", int(ex.sucesso), "status success/pass"],
  ["Falhas", int(ex.falha), ex.falha === 0 ? "nenhuma" : "verificar run_results"],
  ["Tempo total", num(ex.elapsed, 2) + " s", "do dbt build"],
].map(([r,v,n]) => '<div class="kpi"><div class="rotulo">' + r + '</div><div class="valor">' + v
  + '</div><div class="nota">' + n + "</div></div>").join("")
  : '<p class="vazio">Execute dbt build para registrar uma execução.</p>';

barras("barras-tempo", (ex.mais_lentos || []).map((n) =>
  ({nome:n.nome, valor:n.segundos, rotulo:num(n.segundos,3)+" s", dica:n.nome+" ("+n.tipo+") — "+n.status})));

document.getElementById("lista-ambiente").innerHTML = [
  ["Python", CTX.ambiente.python],
  ["DuckDB", CTX.ambiente.duckdb],
  ["dbt", ex.dbt_version || "—"],
  ["Plataforma", CTX.ambiente.plataforma],
  ["Execução registrada em", ex.gerado_em || "—"],
  ["Data de referência dos dados", CTX.data_referencia],
].map(([r,v]) => "<li>" + r + '<span class="quanto"><code>' + esc(v) + "</code></span></li>").join("");

render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    destino = gerar()
    print(f"[INFO] Dashboard gerado em {destino.relative_to(RAIZ)}")
    print(f"[INFO] Abra com: xdg-open {destino.relative_to(RAIZ)}")
    sys.exit(0)
