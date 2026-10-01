"""Executa a jornada completa em um comando: Raw → Bronze → Silver → Gold → resposta.

    python scripts/executar_tudo.py              # pipeline, dbt build e dashboard
    python scripts/executar_tudo.py --zerar      # apaga as camadas geradas antes
    python scripts/executar_tudo.py --completo   # inclui pytest, time travel e consultas
    python scripts/executar_tudo.py --abrir      # abre o dashboard no navegador

Cada etapa herda a saída no terminal, para a execução ficar visível. No final imprime
um resumo com status e tempo de cada etapa. Qualquer falha interrompe a sequência e
devolve código de saída diferente de zero.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DBT = RAIZ / "dbt"
DASHBOARD = RAIZ / "data" / "gold" / "dashboard.html"

PY = sys.executable
DBT_BIN = Path(PY).parent / "dbt"


class Falha(Exception):
    """Uma etapa terminou com código diferente de zero."""


def _executavel_dbt() -> list[str]:
    if DBT_BIN.exists():
        return [str(DBT_BIN)]
    encontrado = shutil.which("dbt")
    if encontrado:
        return [encontrado]
    raise Falha(
        "dbt não encontrado. Ative o ambiente virtual: source .venv/bin/activate"
    )


def montar_etapas(zerar: bool, completo: bool) -> list[tuple[str, list[str], Path]]:
    etapas: list[tuple[str, list[str], Path]] = []

    if zerar:
        etapas.append(
            ("Limpar camadas geradas", [PY, "scripts/zerar.py"], RAIZ)
        )

    # O pipeline cria data/silver e data/gold; sem ele o dbt build falha.
    etapas.append(("Ingestão Raw → Bronze Delta", [PY, "-m", "src.pipeline"], RAIZ))

    if completo:
        etapas.append(("Testes da ingestão (pytest)", [PY, "-m", "pytest", "-q"], RAIZ))

    etapas.append(("Transformações e testes (dbt build)", _executavel_dbt() + ["build"], DBT))

    if completo:
        etapas.append(
            ("Time travel do Delta", [PY, "scripts/demonstrar_time_travel.py"], RAIZ)
        )
        etapas.append(
            ("Resposta da pergunta", [PY, "scripts/executar_sql.py", "consultas/resposta.sql"], RAIZ)
        )
        etapas.append(
            ("Auditoria de cobertura", [PY, "scripts/executar_sql.py", "consultas/qualidade.sql"], RAIZ)
        )

    etapas.append(("Dashboard da camada de consumo", [PY, "scripts/gerar_dashboard.py"], RAIZ))
    return etapas


def rodar(etapas: list[tuple[str, list[str], Path]]) -> list[dict]:
    resultados: list[dict] = []
    total = len(etapas)

    for indice, (titulo, comando, diretorio) in enumerate(etapas, start=1):
        onde = diretorio.relative_to(RAIZ) if diretorio != RAIZ else Path(".")
        print(f"\n\033[1m[{indice}/{total}] {titulo}\033[0m")
        print(f"      $ {' '.join(comando)}   (em {onde})\n", flush=True)

        inicio = time.perf_counter()
        processo = subprocess.run(comando, cwd=diretorio)
        duracao = time.perf_counter() - inicio

        resultados.append(
            {"titulo": titulo, "codigo": processo.returncode, "segundos": duracao}
        )
        if processo.returncode != 0:
            raise Falha(f"etapa '{titulo}' falhou com código {processo.returncode}")

    return resultados


def resumir(resultados: list[dict], erro: str | None) -> None:
    largura = max(len(r["titulo"]) for r in resultados) if resultados else 30
    print("\n" + "─" * (largura + 22))
    print("Resumo da execução")
    print("─" * (largura + 22))
    for resultado in resultados:
        selo = "ok   " if resultado["codigo"] == 0 else "FALHA"
        print(f"  {selo}  {resultado['titulo']:<{largura}}  {resultado['segundos']:6.2f}s")
    total = sum(r["segundos"] for r in resultados)
    print("─" * (largura + 22))
    print(f"  Total: {total:.2f}s")

    if erro:
        print(f"\n\033[31mInterrompido: {erro}\033[0m")
        return

    print(f"\n\033[32mJornada completa.\033[0m Dashboard em {DASHBOARD.relative_to(RAIZ)}")
    print(f"  Abra com: xdg-open {DASHBOARD.relative_to(RAIZ)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Executa o pipeline inteiro e gera o dashboard."
    )
    parser.add_argument(
        "--zerar",
        action="store_true",
        help="apaga Bronze, Silver, Gold, catálogo e artefatos do dbt antes de começar",
    )
    parser.add_argument(
        "--completo",
        action="store_true",
        help="inclui pytest, time travel e as consultas de resposta e cobertura",
    )
    parser.add_argument(
        "--abrir", action="store_true", help="abre o dashboard no navegador ao final"
    )
    argumentos = parser.parse_args()

    resultados: list[dict] = []
    erro: str | None = None
    try:
        resultados = rodar(montar_etapas(argumentos.zerar, argumentos.completo))
    except Falha as falha:
        erro = str(falha)
    except KeyboardInterrupt:
        erro = "interrompido pelo usuário"

    resumir(resultados, erro)

    if erro:
        return 1

    if argumentos.abrir and shutil.which("xdg-open"):
        subprocess.Popen(
            ["xdg-open", str(DASHBOARD)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
