"""Conector do DataJud — API Pública do CNJ (metadados e andamentos de processos públicos).

POST {base}/api_publica_<alias>/_search com `Authorization: APIKey <chave>` (chave pública divulgada pelo CNJ,
lida só da variável DATAJUD_API_KEY). Consulta em lote por tribunal com `terms` em numeroProcesso.
DataJud não traz processos sigilosos e **não é canal de intimação**: os andamentos entram como movimentação.
"""
from __future__ import annotations

from datetime import date

import httpx

from app.servicos.conectores.base import (
    Conector, CredencialAusente, ErroConector, FonteIndisponivel, LimitadorTaxa, ResultadoSincronizacao, Saude, erro_http,
)

LOTE = 100
_SEM_INDICE = {"STF", "CNJ"}
_LIMITADOR = LimitadorTaxa(por_minuto=60)


def alias(sigla: str | None) -> str | None:
    """Sigla do tribunal -> índice do DataJud (ex.: TJRN -> api_publica_tjrn; TRE-RN -> api_publica_tre-rn)."""
    if not sigla or sigla.upper() in _SEM_INDICE:
        return None
    return "api_publica_" + sigla.lower()


def normalizar_hit(src: dict) -> dict:
    movs = []
    for m in src.get("movimentos") or []:
        compl = "; ".join(f"{c.get('nome')}: {c.get('descricao')}" for c in m.get("complementosTabelados") or []
                          if isinstance(c, dict) and c.get("nome"))
        movs.append({"codigo": m.get("codigo"), "nome": m.get("nome") or "Movimento sem nome",
                     "data_hora": m.get("dataHora"), "complemento": compl or None})
    return {
        "numero_processo": src.get("numeroProcesso"),
        "classe": (src.get("classe") or {}).get("nome"),
        "orgao": (src.get("orgaoJulgador") or {}).get("nome"),
        "grau": src.get("grau"),
        "data_ajuizamento": src.get("dataAjuizamento"),
        "atualizado_em": src.get("dataHoraUltimaAtualizacao"),
        "assuntos": [a.get("nome") for a in src.get("assuntos") or [] if isinstance(a, dict) and a.get("nome")],
        "movimentos": movs,
    }


class ConectorDataJud(Conector):
    codigo = "datajud"
    nome = "DataJud — API Pública (CNJ)"
    limites = {"requisicoes_por_minuto": 60, "processos_por_requisicao": LOTE}

    def __init__(self, base_url: str, chave: str | None, timeout: float = 30.0,
                 transporte: httpx.BaseTransport | None = None, limitador: LimitadorTaxa | None = _LIMITADOR):
        self.base_url = base_url.rstrip("/")
        self.chave = chave
        self._cliente = httpx.Client(timeout=timeout, transport=transporte)
        self._limitador = limitador

    def _buscar(self, indice: str, corpo: dict) -> dict:
        if not self.chave:
            raise CredencialAusente("DataJud: informe a chave pública do CNJ na variável DATAJUD_API_KEY")
        if self._limitador:
            self._limitador.aguardar()
        try:
            r = self._cliente.post(f"{self.base_url}/{indice}/_search", json=corpo,
                                   headers={"Authorization": f"APIKey {self.chave}", "Content-Type": "application/json"})
        except httpx.TimeoutException as e:
            raise FonteIndisponivel("DataJud: tempo de resposta esgotado") from e
        except httpx.HTTPError as e:
            raise FonteIndisponivel(f"DataJud: falha de conexão ({e.__class__.__name__})") from e
        if r.status_code == 404:
            raise FonteIndisponivel(f"DataJud: índice {indice} não existe")
        if r.status_code != 200:
            raise erro_http(r.status_code, "DataJud", r.headers.get("retry-after"))
        return r.json()

    def verificar_saude(self) -> Saude:
        try:
            dados = self._buscar("api_publica_tjrn", {"size": 0, "query": {"match_all": {}}})
        except ErroConector as e:
            return Saude(False, str(e))
        total = ((dados.get("hits") or {}).get("total") or {}).get("value")
        return Saude(True, f"Respondeu; índice do TJRN com {total} processo(s)")

    def sincronizar(self, desde: date, ate: date, *, processos: dict[str, list[str]] | None = None, **_) -> ResultadoSincronizacao:
        """`processos`: sigla do tribunal -> lista de números (20 dígitos). Devolve um item por processo encontrado."""
        res = ResultadoSincronizacao()
        for sigla, numeros in (processos or {}).items():
            indice = alias(sigla)
            if indice is None:
                res.observacoes.append(f"{sigla}: sem índice público no DataJud")
                continue
            for i in range(0, len(numeros), LOTE):
                lote = numeros[i:i + LOTE]
                dados = self._buscar(indice, {"size": len(lote) * 3, "query": {"terms": {"numeroProcesso": lote}}})
                res.requisicoes += 1
                por_numero: dict[str, dict] = {}
                for h in (dados.get("hits") or {}).get("hits") or []:
                    item = normalizar_hit(h.get("_source") or {})
                    n = item["numero_processo"]
                    if n in por_numero:  # mesmo processo em graus diferentes: junta os movimentos
                        por_numero[n]["movimentos"] += item["movimentos"]
                    else:
                        por_numero[n] = item
                res.itens.extend(por_numero.values())
        return res
