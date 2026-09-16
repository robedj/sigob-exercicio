"""Remove somente artefatos gerados para permitir a demonstração desde o zero.

Raw, código e documentação nunca são removidos. Os alvos são explícitos e precisam estar
dentro da raiz deste projeto.
"""

from pathlib import Path
import shutil


RAIZ = Path(__file__).resolve().parents[1]
ALVOS = [
    RAIZ / "data" / "bronze",
    RAIZ / "data" / "silver",
    RAIZ / "data" / "gold",
    RAIZ / "data" / "analytics.duckdb",
    RAIZ / "dbt" / "target",
    RAIZ / "dbt" / "logs",
]


def main() -> None:
    for alvo in ALVOS:
        alvo.resolve().relative_to(RAIZ.resolve())
        if alvo.is_dir():
            shutil.rmtree(alvo)
            print(f"removido diretório gerado: {alvo.relative_to(RAIZ)}")
        elif alvo.exists():
            alvo.unlink()
            print(f"removido arquivo gerado: {alvo.relative_to(RAIZ)}")
    print("Projeto pronto para reconstrução; data/raw foi preservado.")


if __name__ == "__main__":
    main()
