"""Executa, em ordem, as consultas de um arquivo SQL e imprime os resultados."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("arquivo", type=Path, help="Arquivo SQL a executar")
    args = parser.parse_args()

    if not args.arquivo.is_file():
        raise SystemExit(f"Arquivo não encontrado: {args.arquivo}")

    conteudo = args.arquivo.read_text(encoding="utf-8")
    with duckdb.connect() as conexao:
        # O parser do próprio DuckDB respeita ponto e vírgula dentro de comentários
        # e literais, ao contrário de uma divisão textual simples.
        instrucoes = conexao.extract_statements(conteudo)
        for indice, instrucao in enumerate(instrucoes, start=1):
            print(f"\n--- consulta {indice} ---")
            resultado = conexao.execute(instrucao.query).fetchdf()
            print(resultado.to_string(index=False))


if __name__ == "__main__":
    main()
