"""Executa a mesma consulta sobre as versões anterior e atual do Bronze."""

from pathlib import Path

import duckdb
from deltalake import DeltaTable


RAIZ = Path(__file__).resolve().parents[1]
TABELA = RAIZ / "data" / "bronze" / "imoveis"

CONSULTA = """
select
    count(*) filter (
        where regexp_matches(trim(col_01), '^[0-9]+$')
    ) as imoveis_com_id,
    count(*) filter (
        where try_cast(_linha_origem as integer) >= 5
          and not regexp_matches(trim(col_01), '^[0-9]+$')
          and nullif(trim(col_02), '') is not null
    ) as registros_sem_id
from snapshot
"""


def consultar(versao: int) -> tuple[int, int]:
    tabela = DeltaTable(str(TABELA), version=versao).to_pyarrow_table()
    with duckdb.connect() as conexao:
        conexao.register("snapshot", tabela)
        return conexao.execute(CONSULTA).fetchone()


def main() -> None:
    atual = DeltaTable(str(TABELA)).version()
    if atual < 1:
        raise SystemExit("Execute python -m src.pipeline para criar as duas versões.")

    for versao in (0, atual):
        com_id, sem_id = consultar(versao)
        rotulo = "anterior" if versao == 0 else "atual"
        print(
            f"versão {versao} ({rotulo}): "
            f"{com_id} imóveis com ID; {sem_id} registro sem ID"
        )


if __name__ == "__main__":
    main()
