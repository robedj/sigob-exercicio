"""Prepara o recorte entregável a partir do material local do SIGOB.

Este script é de preparação do trabalho, não faz parte do pipeline avaliado. O pipeline
usa apenas ``data/raw`` e funciona em clone limpo sem a pasta ``docs-sigob``.

As saídas preservam os valores textuais das planilhas. Nenhuma medida é tipada ou
corrigida aqui. O JSON apenas representa o levantamento de infraestrutura em seu formato
de entrega para a PoC.

Uso:
    python scripts/preparar_fontes.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "docs-sigob" / "imoveis" / "dados-imoveis-tjms"
DESTINO = RAIZ / "data" / "raw"


def _ler_csv(nome: str) -> list[list[str]]:
    caminho = ORIGEM / nome
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.reader(arquivo, delimiter=";"))


def _gravar_csv(caminho: Path, linhas: list[list[str]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";", lineterminator="\n")
        escritor.writerows(linhas)


def _registros(nome: str) -> list[dict[str, str]]:
    linhas = _ler_csv(nome)
    cabecalho = [coluna.strip() for coluna in linhas[3]]
    resultado = []
    for linha in linhas[4:]:
        valores = (linha + [""] * len(cabecalho))[: len(cabecalho)]
        registro = dict(zip(cabecalho, valores))
        if any(valor.strip() for valor in valores):
            resultado.append(registro)
    return resultado


def preparar_imoveis() -> None:
    atual = _ler_csv("Cadastro_Mestre.csv")

    # O snapshot anterior representa o momento antes da decisão R-11: a Casa da Mulher
    # ainda não havia recebido o ID 223 como PID. Todas as demais linhas são idênticas.
    anterior = [linha for linha in atual if not linha or linha[0].strip() != "223"]

    pasta = DESTINO / "imoveis"
    _gravar_csv(pasta / "2026-08-01.csv", anterior)
    _gravar_csv(pasta / "2026-08-17.csv", atual)


def preparar_patrimonio() -> None:
    _gravar_csv(DESTINO / "patrimonio.csv", _ler_csv("PATRIMONIO.csv"))


def preparar_infraestrutura() -> None:
    sanitarios = {
        item["ID Prédio"].strip(): item
        for item in _registros("SANITARIOS.csv")
        if item["ID Prédio"].strip()
    }
    reservatorios = {
        item["ID Prédio"].strip(): item
        for item in _registros("RESERVATORIOS.csv")
        if item["ID Prédio"].strip()
    }

    ids = sorted(set(sanitarios) | set(reservatorios), key=int)
    vistorias = []
    for id_predio in ids:
        san = sanitarios.get(id_predio, {})
        res = reservatorios.get(id_predio, {})
        nome = san.get("Nome Oficial") or res.get("Nome Oficial") or ""

        vistorias.append(
            {
                "id_predio": id_predio,
                "nome_na_fonte": nome,
                "data_referencia": "2026-08-17",
                "sanitarios": [
                    {
                        "tipo": "coletivo",
                        "quantidade_declarada": san.get("Sanitários Coletivos", ""),
                    },
                    {
                        "tipo": "privativo",
                        "quantidade_declarada": san.get("Sanitários Privativos", ""),
                    },
                ],
                "loucas": {
                    "vasos_declarados": san.get("Vasos", ""),
                    "mictorios_declarados": san.get("Mictórios", ""),
                    "lavatorios_declarados": san.get("Lavatórios", ""),
                },
                "reservatorios": [
                    {
                        "posicao": "A",
                        "capacidade_declarada": res.get("Caixa A (litros)", ""),
                        "material_declarado": res.get("Material da Caixa A", ""),
                    },
                    {
                        "posicao": "B",
                        "capacidade_declarada": res.get("Caixa B (litros)", ""),
                        "material_declarado": res.get("Material da Caixa B", ""),
                    },
                ],
            }
        )

    documento = {
        "fonte": "Levantamento de infraestrutura predial TJMS",
        "data_referencia": "2026-08-17",
        "vistorias": vistorias,
    }
    DESTINO.mkdir(parents=True, exist_ok=True)
    caminho = DESTINO / "infraestrutura_predial.json"
    caminho.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if not ORIGEM.exists():
        raise SystemExit(
            "Pasta local docs-sigob não encontrada. "
            "Ela só é necessária para regenerar data/raw."
        )
    preparar_imoveis()
    preparar_patrimonio()
    preparar_infraestrutura()
    print(f"Fontes preparadas em {DESTINO}")


if __name__ == "__main__":
    main()
