"""Geradores de dados 100% sintéticos para testes (nenhum dado real)."""
import itertools
import random

from app.servicos.identificadores import gerar_cnj, gerar_cnpj, gerar_cpf

_seq = itertools.count(random.randint(1, 4_000_000))
_doc = itertools.count(random.randint(100_000_000, 400_000_000))

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Heitor", "Íris", "João", "Lúcia", "Mateus"]
SOBRENOMES = ["Sintético", "Fictício", "de Teste", "Exemplar", "Modelo", "Simulado"]


def numero(segmento: int = 8, tribunal: int = 20, ano: int = 2024, origem: int = 1) -> str:
    return gerar_cnj(next(_seq), ano, segmento, tribunal, origem)


def cpf() -> str:
    return gerar_cpf(next(_doc))


def cnpj() -> str:
    return gerar_cnpj(f"{next(_doc):012d}")


def nome(i: int | None = None) -> str:
    i = next(_seq) if i is None else i
    return f"{NOMES[i % len(NOMES)]} {SOBRENOMES[(i // len(NOMES)) % len(SOBRENOMES)]} {i}"
