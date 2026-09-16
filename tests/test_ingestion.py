"""Testes do código de ingestão, distintos dos testes de dados do dbt."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from deltalake import DeltaTable

from src import ingest


def _limpar_tabela_delta(caminho: Path) -> None:
    """Remove somente uma tabela criada dentro do tmp_path do pytest."""
    if not caminho.exists():
        return
    for item in sorted(caminho.rglob("*"), reverse=True):
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            item.rmdir()
    caminho.rmdir()


def test_csv_bruto_preserva_todas_as_linhas():
    caminho = ingest.DATA_RAW_PATH / "imoveis" / "2026-08-17.csv"
    tabela = ingest._tabela_csv_bruta(caminho, "2026-08-17")
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        quantidade_origem = len(list(csv.reader(arquivo, delimiter=";")))
    assert len(tabela) == quantidade_origem
    assert tabela.column("col_01")[0].as_py().startswith("CADASTRO_MESTRE")


def test_csv_bruto_nao_promove_cabecalho():
    caminho = ingest.DATA_RAW_PATH / "patrimonio.csv"
    tabela = ingest._tabela_csv_bruta(caminho, "2026-08-17")
    assert tabela.column("col_01")[3].as_py() == "ID Prédio"
    assert tabela.column("_linha_origem")[3].as_py() == "4"


def test_json_bruto_preserva_documento_completo():
    caminho = ingest.DATA_RAW_PATH / "infraestrutura_predial.json"
    tabela = ingest._tabela_json_bruta(caminho, "2026-08-17")
    preservado = tabela.column("conteudo_json")[0].as_py()
    assert preservado == caminho.read_text(encoding="utf-8")
    assert len(json.loads(preservado)["vistorias"]) == 79


def test_metadados_tecnicos_estao_presentes():
    caminho = ingest.DATA_RAW_PATH / "patrimonio.csv"
    tabela = ingest._tabela_csv_bruta(caminho, "2026-08-17")
    for coluna in [
        "_arquivo_origem",
        "_versao_fonte",
        "_ingerido_em",
        "_hash_arquivo",
        "_linha_origem",
    ]:
        assert coluna in tabela.column_names


def test_imoveis_registra_duas_versoes_e_time_travel(tmp_path, monkeypatch):
    bronze = tmp_path / "bronze"
    monkeypatch.setattr(ingest, "DATA_BRONZE_PATH", bronze)

    ingest.ingest_imoveis()

    caminho = bronze / "imoveis"
    atual = DeltaTable(str(caminho))
    anterior = DeltaTable(str(caminho), version=0)
    assert atual.version() == 1
    assert atual.to_pyarrow_table().num_rows == 107
    assert anterior.to_pyarrow_table().num_rows == 106


def test_rerun_de_imoveis_nao_cria_versoes_artificiais(tmp_path, monkeypatch):
    bronze = tmp_path / "bronze"
    monkeypatch.setattr(ingest, "DATA_BRONZE_PATH", bronze)

    ingest.ingest_imoveis()
    ingest.ingest_imoveis()

    assert DeltaTable(str(bronze / "imoveis")).version() == 1
