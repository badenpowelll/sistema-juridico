"""Interface comum dos conectores de fontes externas (ADR-0007).

Cada conector implementa `verificar_saude()` e `sincronizar(desde, ate, **parametros)`, declara seus limites
e levanta exceções padronizadas. Quem chama (servicos.sincronizacao) cuida de circuito, registro e fila.
"""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


class ErroConector(Exception):
    """Falha ao consultar a fonte. `transitorio` indica se vale tentar de novo mais tarde."""
    transitorio = True


class LimiteTaxa(ErroConector):
    def __init__(self, mensagem: str, espera_segundos: float = 60):
        super().__init__(mensagem)
        self.espera_segundos = espera_segundos


class FonteIndisponivel(ErroConector):
    pass


class CredencialAusente(ErroConector):
    transitorio = False


class CredencialRecusada(ErroConector):
    transitorio = False


@dataclass
class Saude:
    ok: bool
    detalhe: str


@dataclass
class ResultadoSincronizacao:
    itens: list[dict] = field(default_factory=list)
    requisicoes: int = 0
    observacoes: list[str] = field(default_factory=list)


class LimitadorTaxa:
    """Intervalo mínimo entre requisições do mesmo conector, neste processo."""

    def __init__(self, por_minuto: int):
        self.intervalo = 60.0 / max(por_minuto, 1)
        self._ultimo = 0.0
        self._trava = threading.Lock()

    def aguardar(self) -> None:
        with self._trava:
            agora = time.monotonic()
            espera = self._ultimo + self.intervalo - agora
            if espera > 0:
                time.sleep(espera)
            self._ultimo = time.monotonic()


class Conector(ABC):
    codigo: str
    nome: str
    simulado: bool = False
    limites: dict = {}

    @abstractmethod
    def verificar_saude(self) -> Saude: ...

    @abstractmethod
    def sincronizar(self, desde: date, ate: date, **parametros) -> ResultadoSincronizacao: ...


def erro_http(status: int, fonte: str, retry_after: str | None = None) -> ErroConector:
    """Traduz o status HTTP em exceção padronizada, com mensagem para a central de contingência."""
    if status == 429:
        try:
            espera = float(retry_after) if retry_after else 60.0
        except ValueError:
            espera = 60.0
        return LimiteTaxa(f"{fonte}: limite de requisições atingido (HTTP 429); nova tentativa em {int(espera)} s", espera)
    if status in (401,):
        return CredencialRecusada(f"{fonte}: credencial recusada (HTTP 401). A chave pode ter sido trocada pelo CNJ.")
    if status == 403:
        return FonteIndisponivel(f"{fonte}: acesso negado (HTTP 403). A fonte pode estar bloqueando a origem "
                                 "da requisição (ex.: servidor fora do Brasil).")
    if status >= 500:
        return FonteIndisponivel(f"{fonte}: fonte com erro interno (HTTP {status}).")
    return FonteIndisponivel(f"{fonte}: resposta inesperada (HTTP {status}).")
