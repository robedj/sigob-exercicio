"""Orquestra a ingestão Raw → Bronze Delta.

Execução a partir da raiz:

    python -m src.pipeline
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src import ingest


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Iniciando ingestão da PoC de Imóveis do SIGOB")

    etapas = [
        ("imoveis", ingest.ingest_imoveis),
        ("patrimonio", ingest.ingest_patrimonio),
        ("infraestrutura_predial", ingest.ingest_infraestrutura),
    ]
    for nome, etapa in etapas:
        etapa()
        logger.info("%s: versão Delta atual %d", nome, ingest.versao_atual(nome))

    # O dbt-duckdb grava modelos externos, mas não cria o diretório-pai do arquivo.
    # Preparar apenas a estrutura física é responsabilidade operacional do pipeline;
    # nenhuma regra ou transformação de dados acontece aqui.
    for camada in ("silver", "gold"):
        (Path(ingest.PROJECT_ROOT) / "data" / camada).mkdir(parents=True, exist_ok=True)

    logger.info("Ingestão concluída; Bronze disponível em data/bronze")


if __name__ == "__main__":
    main()
