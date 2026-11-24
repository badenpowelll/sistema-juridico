"""Conector do DJEN — Plataforma de Comunicações Processuais do CNJ (consulta pública, sem autenticação).

GET {base}/comunicacao?numeroOab=&ufOab=&dataDisponibilizacaoInicio=&dataDisponibilizacaoFim=&pagina=&itensPorPagina=
Resposta: {"status", "message", "count", "items": [...]}. Cada item traz id, hash (certidão), datas, tribunal,
órgão, classe, tipo de comunicação, texto, destinatários e advogados. O item original é preservado sem alteração.
A API recusa origem fora do Brasil (HTTP 403) e limita a taxa (HTTP 429).
"""
from __future__ import annotations

import re
from datetime import date, datetime

import httpx

from app.servicos.conectores.base import (
    Conector, ErroConector, FonteIndisponivel, LimitadorTaxa, ResultadoSincronizacao, Saude, erro_http,
)

ITENS_POR_PAGINA = 100
MAX_PAGINAS = 50  # 5.000 comunicações por OAB e janela; acima disso a janela é dividida pelo chamador
_LIMITADOR = LimitadorTaxa(por_minuto=30)


def _data(valor) -> date | None:
    if not valor:
        return None
    v = str(valor).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _advogados(lista) -> list[dict]:
    saida = []
    for a in lista or []:
        a = a.get("advogado", a) if isinstance(a, dict) else {}
        if a:
            saida.append({"nome": a.get("nome"), "numero_oab": str(a.get("numero_oab") or "") or None,
                          "uf_oab": a.get("uf_oab")})
    return saida


def normalizar_item(item: dict) -> dict:
    """Converte uma comunicação do DJEN no formato de captura do EJMF. Não descarta nada: `original` vai junto."""
    numero = re.sub(r"\D", "", str(item.get("numero_processo") or item.get("numeroprocessocommascara") or ""))
    return {
        "id_externo": str(item["id"]) if item.get("id") is not None else None,
        "hash_certidao": item.get("hash"),
        "tipo_original": item.get("tipoComunicacao"),
        "numero_processo": numero if len(numero) == 20 else None,
        "numero_formatado": item.get("numeroprocessocommascara"),
        "tribunal_sigla": item.get("siglaTribunal"),
        "orgao": item.get("nomeOrgao"),
        "classe": item.get("nomeClasse"),
        "tipo_documento": item.get("tipoDocumento"),
        "texto": item.get("texto") or "",
        "destinatarios": [{"nome": d.get("nome"), "polo": d.get("polo")} for d in item.get("destinatarios") or []
                          if isinstance(d, dict)],
        "advogados": _advogados(item.get("destinatarioadvogados")),
        "link": item.get("link"),
        "disponibilizado_em": _data(item.get("data_disponibilizacao") or item.get("datadisponibilizacao")),
        "original": item,
    }


def oab_para_consulta(numero: str) -> str:
    """'12.114' -> '12114' (a API recebe só os dígitos e eventual letra de inscrição suplementar)."""
    return re.sub(r"[^0-9A-Za-z]", "", numero or "").upper()


class ConectorDJEN(Conector):
    codigo = "djen"
    nome = "DJEN — Comunicações processuais (CNJ)"
    limites = {"requisicoes_por_minuto": 30, "itens_por_pagina": ITENS_POR_PAGINA, "paginas_por_consulta": MAX_PAGINAS}

    def __init__(self, base_url: str, timeout: float = 30.0, transporte: httpx.BaseTransport | None = None,
                 limitador: LimitadorTaxa | None = _LIMITADOR):
        self.base_url = base_url.rstrip("/")
        self._cliente = httpx.Client(timeout=timeout, transport=transporte,
                                     headers={"Accept": "application/json", "User-Agent": "EJMF/0.3 (monitor de publicacoes)"})
        self._limitador = limitador

    def _get(self, caminho: str, params: dict) -> dict:
        if self._limitador:
            self._limitador.aguardar()
        try:
            r = self._cliente.get(f"{self.base_url}{caminho}", params=params)
        except httpx.TimeoutException as e:
            raise FonteIndisponivel(f"DJEN: tempo de resposta esgotado ({e.__class__.__name__})") from e
        except httpx.HTTPError as e:
            raise FonteIndisponivel(f"DJEN: falha de conexão ({e.__class__.__name__})") from e
        if r.status_code != 200:
            raise erro_http(r.status_code, "DJEN", r.headers.get("retry-after"))
        try:
            return r.json()
        except ValueError as e:
            raise FonteIndisponivel("DJEN: resposta não é JSON (a fonte pode estar fora do ar ou bloqueando)") from e

    def verificar_saude(self) -> Saude:
        hoje = date.today().isoformat()
        try:
            dados = self._get("/comunicacao", {"siglaTribunal": "TJRN", "dataDisponibilizacaoInicio": hoje,
                                               "dataDisponibilizacaoFim": hoje, "itensPorPagina": 5, "pagina": 1})
        except ErroConector as e:
            return Saude(False, str(e))
        return Saude(True, f"Respondeu; {dados.get('count', 0)} comunicação(ões) hoje no TJRN")

    def sincronizar(self, desde: date, ate: date, *, oabs: list[tuple[str, str]] = (), **_) -> ResultadoSincronizacao:
        res = ResultadoSincronizacao()
        vistos: set[str] = set()
        for numero, uf in oabs:
            pagina, recebidos = 1, 0
            while pagina <= MAX_PAGINAS:
                dados = self._get("/comunicacao", {
                    "numeroOab": oab_para_consulta(numero), "ufOab": uf.upper(),
                    "dataDisponibilizacaoInicio": desde.isoformat(), "dataDisponibilizacaoFim": ate.isoformat(),
                    "pagina": pagina, "itensPorPagina": ITENS_POR_PAGINA})
                res.requisicoes += 1
                itens = dados.get("items") or []
                for it in itens:
                    chave = str(it.get("id") or it.get("hash"))
                    if chave not in vistos:  # a mesma comunicação pode vir para duas grafias da OAB
                        vistos.add(chave)
                        res.itens.append(normalizar_item(it))
                recebidos += len(itens)
                total = int(dados.get("count") or 0)
                if not itens or recebidos >= total:
                    break
                pagina += 1
            else:
                res.observacoes.append(f"OAB {numero}/{uf}: mais de {MAX_PAGINAS * ITENS_POR_PAGINA} itens na janela; "
                                       "divida o período.")
        return res
