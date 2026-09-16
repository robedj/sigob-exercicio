"""Ingestão das fontes Raw para o Bronze Delta Lake.

Contrato da camada:

- preservar todas as linhas e valores como chegaram;
- acrescentar somente metadados técnicos;
- não tipar medidas nem aplicar regra de negócio;
- registrar os snapshots cadastrais em ordem para permitir time travel.

Os CSVs possuem títulos e notas antes do cabeçalho. Eles são lidos sem ``header`` e
essas linhas continuam no Bronze. Identificá-las é responsabilidade da Silver.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATA_RAW_PATH = PROJECT_ROOT / os.getenv("DATA_RAW_PATH", "data/raw")
DATA_BRONZE_PATH = PROJECT_ROOT / os.getenv("DATA_BRONZE_PATH", "data/bronze")

logger = logging.getLogger(__name__)


def _hash_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _metadados(caminho: Path, versao: str, quantidade: int) -> dict[str, list[str]]:
    instante = datetime.now(timezone.utc).isoformat()
    hash_arquivo = _hash_arquivo(caminho)
    return {
        "_arquivo_origem": [caminho.relative_to(DATA_RAW_PATH).as_posix()] * quantidade,
        "_versao_fonte": [versao] * quantidade,
        "_ingerido_em": [instante] * quantidade,
        "_hash_arquivo": [hash_arquivo] * quantidade,
    }


def _tabela_csv_bruta(caminho: Path, versao: str) -> pa.Table:
    """Lê o CSV fisicamente, sem promover cabeçalho nem interpretar valores."""
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.reader(arquivo, delimiter=";"))

    largura = max(map(len, linhas), default=0)
    dados: dict[str, list[str]] = {
        f"col_{indice:02d}": [
            linha[indice - 1] if len(linha) >= indice else "" for linha in linhas
        ]
        for indice in range(1, largura + 1)
    }
    dados["_linha_origem"] = [str(indice) for indice in range(1, len(linhas) + 1)]
    dados.update(_metadados(caminho, versao, len(linhas)))
    return pa.table(dados)


def _tabela_json_bruta(caminho: Path, versao: str) -> pa.Table:
    """Preserva o documento JSON completo; a abertura das coleções ocorre na Silver."""
    conteudo = caminho.read_text(encoding="utf-8")
    dados: dict[str, list[str]] = {"conteudo_json": [conteudo]}
    dados.update(_metadados(caminho, versao, 1))
    return pa.table(dados)


def _versoes_e_hashes(destino: Path) -> dict[str, int]:
    """Retorna os hashes já materializados e a versão Delta em que aparecem."""
    if not (destino / "_delta_log").exists():
        return {}

    atual = DeltaTable(str(destino))
    encontrados: dict[str, int] = {}
    for versao in range(atual.version() + 1):
        tabela = DeltaTable(str(destino), version=versao).to_pyarrow_table(
            columns=["_hash_arquivo"]
        )
        hashes = tabela.column("_hash_arquivo").to_pylist()
        if hashes:
            encontrados[str(hashes[0])] = versao
    return encontrados


def _hash_atual(destino: Path) -> str | None:
    if not (destino / "_delta_log").exists():
        return None
    tabela = DeltaTable(str(destino)).to_pyarrow_table(columns=["_hash_arquivo"])
    hashes = tabela.column("_hash_arquivo").to_pylist()
    return str(hashes[0]) if hashes else None


def _gravar_snapshot(
    tabela: pa.Table,
    destino: Path,
    *,
    hash_arquivo: str,
) -> bool:
    """Grava por overwrite quando o conteúdo ainda não é o snapshot atual."""
    if _hash_atual(destino) == hash_arquivo:
        logger.info("Bronze já está no snapshot %s; escrita ignorada", hash_arquivo[:12])
        return False

    destino.parent.mkdir(parents=True, exist_ok=True)
    write_deltalake(
        str(destino),
        tabela,
        mode="overwrite",
        schema_mode="overwrite",
    )
    logger.info("Snapshot Delta gravado: %s (%d registros)", destino.name, len(tabela))
    return True


def ingest_imoveis() -> None:
    """Grava os snapshots cadastrais em ordem cronológica.

    Em reruns, se os dois hashes já fazem parte do histórico e o snapshot mais recente
    está ativo, nenhuma nova versão é criada.
    """
    arquivos = sorted((DATA_RAW_PATH / "imoveis").glob("*.csv"))
    if len(arquivos) < 2:
        raise FileNotFoundError("São necessários pelo menos dois snapshots de imóveis")

    destino = DATA_BRONZE_PATH / "imoveis"
    esperados = [_hash_arquivo(caminho) for caminho in arquivos]
    existentes = _versoes_e_hashes(destino)
    if all(hash_arquivo in existentes for hash_arquivo in esperados) and _hash_atual(
        destino
    ) == esperados[-1]:
        logger.info("Histórico Delta de imóveis já está atualizado")
        return

    for caminho, hash_arquivo in zip(arquivos, esperados):
        if hash_arquivo in existentes:
            continue
        tabela = _tabela_csv_bruta(caminho, caminho.stem)
        _gravar_snapshot(tabela, destino, hash_arquivo=hash_arquivo)

    # Se o histórico já continha snapshots, mas o atual não era o mais recente, restaura
    # o último arquivo como estado corrente.
    if _hash_atual(destino) != esperados[-1]:
        caminho = arquivos[-1]
        _gravar_snapshot(
            _tabela_csv_bruta(caminho, caminho.stem),
            destino,
            hash_arquivo=esperados[-1],
        )


def ingest_patrimonio() -> None:
    caminho = DATA_RAW_PATH / "patrimonio.csv"
    hash_arquivo = _hash_arquivo(caminho)
    _gravar_snapshot(
        _tabela_csv_bruta(caminho, "2026-08-17"),
        DATA_BRONZE_PATH / "patrimonio",
        hash_arquivo=hash_arquivo,
    )


def ingest_infraestrutura() -> None:
    caminho = DATA_RAW_PATH / "infraestrutura_predial.json"
    hash_arquivo = _hash_arquivo(caminho)
    _gravar_snapshot(
        _tabela_json_bruta(caminho, "2026-08-17"),
        DATA_BRONZE_PATH / "infraestrutura_predial",
        hash_arquivo=hash_arquivo,
    )


def versao_atual(nome_tabela: str) -> int:
    """Versão atual, usada no log e na demonstração."""
    return DeltaTable(str(DATA_BRONZE_PATH / nome_tabela)).version()
