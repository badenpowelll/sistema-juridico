"""Vetorizador local e determinístico para a busca por similaridade ("local-termos-v1").

Não é IA nem modelo de linguagem: cada trecho vira um vetor de 384 posições pelo método de *feature hashing* dos termos
(palavras e pares de palavras, sem acento, sem palavras vazias), com peso 1 + log(frequência) e norma 1. Dois textos
que usam os mesmos termos ficam próximos; sinônimos não. É suficiente para achar o trecho certo da lei ou do documento
e roda sem enviar dado a ninguém. Na Fase 8 um provedor de embeddings aprovado pode reindexar os trechos (a coluna
`vetorizador` diz qual gerou cada vetor) sem mudar o esquema.
"""
from __future__ import annotations

import hashlib
import math
import re

from app.modelos import DIMENSAO_VETOR
from app.servicos.identificadores import normalizar_texto

NOME = "local-termos-v1"
DESCRICAO = "Busca por semelhança de termos, calculada no próprio servidor (sem IA)"

PALAVRAS_VAZIAS = frozenset("""
a o e é de do da dos das em no na nos nas um uma uns umas por pelo pela pelos pelas para pra com sem sob sobre
ao aos à às que se ou como mais menos mas não nao já ja seu sua seus suas lhe lhes ele ela eles elas isso isto
esse essa este esta aquele aquela entre até ate quando onde qual quais cujo cuja ser foi são sao há ha ter tem
""".split())

_PALAVRA = re.compile(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*")


def termos(texto: str) -> list[str]:
    """Termos normalizados (sem acento, minúsculos). Números como 8.906/94 ficam inteiros."""
    return [p for p in _PALAVRA.findall(normalizar_texto(texto)) if p not in PALAVRAS_VAZIAS and (len(p) > 1 or p.isdigit())]


def _posicao(termo: str) -> tuple[int, float]:
    h = hashlib.blake2b(termo.encode(), digest_size=8).digest()
    n = int.from_bytes(h, "big")
    return n % DIMENSAO_VETOR, (1.0 if (n >> 63) & 1 else -1.0)


def vetorizar(texto: str) -> list[float] | None:
    """Vetor de norma 1, ou None quando o texto não tem nenhum termo útil."""
    ts = termos(texto)
    if not ts:
        return None
    contagem: dict[str, int] = {}
    for t in ts:
        contagem[t] = contagem.get(t, 0) + 1
    for a, b in zip(ts, ts[1:]):
        k = a + " " + b
        contagem[k] = contagem.get(k, 0) + 1
    v = [0.0] * DIMENSAO_VETOR
    for t, n in contagem.items():
        i, s = _posicao(t)
        v[i] += s * (1.0 + math.log(n)) * (0.7 if " " in t else 1.0)
    norma = math.sqrt(sum(x * x for x in v))
    if norma == 0:
        return None
    return [x / norma for x in v]


def fatiar(texto: str, tamanho: int = 1200, sobreposicao: int = 200, maximo: int = 2000) -> list[str]:
    """Divide o texto em trechos de até `tamanho` caracteres, respeitando parágrafos, com sobreposição."""
    texto = re.sub(r"[ \t]+", " ", texto or "").strip()
    if not texto:
        return []
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n|\n(?=(?:Art\.|§|[IVXLC]+ ?[-–]|Parágrafo))", texto) if p.strip()]
    trechos: list[str] = []
    atual = ""
    for p in paragrafos:
        while len(p) > tamanho:  # parágrafo enorme: corta em pedaços
            corte = p.rfind(" ", 0, tamanho)
            corte = corte if corte > tamanho // 2 else tamanho
            if atual:
                trechos.append(atual)
                atual = ""
            trechos.append(p[:corte].strip())
            p = p[max(corte - sobreposicao, 1):].strip()
        if len(atual) + len(p) + 1 > tamanho and atual:
            trechos.append(atual)
            atual = atual[-sobreposicao:].split(" ", 1)[-1] + "\n" + p if sobreposicao else p
        else:
            atual = (atual + "\n" + p).strip()
        if len(trechos) >= maximo:
            break
    if atual and len(trechos) < maximo:
        trechos.append(atual)
    return trechos[:maximo]
