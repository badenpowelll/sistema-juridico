"""Documenso (assinatura eletrônica), API v2. Documentação oficial consultada em 2026-11-24 (docs.documenso.com):
- criação: POST {api}/envelope/create, multipart com o campo "payload" (JSON: type "DOCUMENT", title, externalId,
  recipients com email, name, role e fields; meta com subject e message) e o PDF em "files"; resposta {"id": ...};
- envio aos participantes: POST {api}/envelope/distribute com {"envelopeId": ...};
- autenticação: cabeçalho Authorization com a chave da API;
- webhook: o segredo configurado chega no cabeçalho X-Documenso-Secret; eventos DOCUMENT_SENT, DOCUMENT_OPENED,
  DOCUMENT_SIGNED, DOCUMENT_RECIPIENT_COMPLETED, DOCUMENT_COMPLETED, DOCUMENT_REJECTED e DOCUMENT_CANCELLED, com
  payload.envelopeId e payload.recipients[].signingStatus.

O EJMF prepara e acompanha; quem assina é cada participante, no Documenso. Não há adaptador simulado.
"""
from __future__ import annotations

import hmac
import json
from typing import Any

import httpx

from app.core.config import obter_config
from app.servicos.conectores.base import CredencialAusente, CredencialRecusada, ErroConector, FonteIndisponivel, LimiteTaxa

PAPEIS = {"assinar": "SIGNER", "aprovar": "APPROVER", "receber_copia": "CC", "visualizar": "VIEWER"}


def configurado() -> bool:
    return bool(obter_config().documenso_token)


def verificar_segredo(recebido: str | None) -> bool:
    esperado = obter_config().documenso_webhook_secret
    if not esperado or not recebido:
        return False  # sem segredo configurado, nenhum webhook é aceito
    return hmac.compare_digest(esperado.encode(), recebido.encode())


def campos_assinatura(participantes: list[dict], paginas: int) -> list[list[dict]]:
    """Posição padrão dos campos: assinatura e data no pé da última página, dois por linha (percentuais da página)."""
    saida, i = [], 0
    for p in participantes:
        if PAPEIS.get(p["papel"]) != "SIGNER":
            saida.append([])
            continue
        x, y = 8 + (i % 2) * 47, 78 - (i // 2) * 10
        saida.append([{"identifier": 0, "type": "SIGNATURE", "page": paginas, "positionX": x, "positionY": y, "width": 38, "height": 6},
                      {"identifier": 0, "type": "DATE", "page": paginas, "positionX": x, "positionY": y + 6.5, "width": 20, "height": 2.5}])
        i += 1
    return saida


class ConectorDocumenso:
    def __init__(self, transporte: httpx.BaseTransport | None = None):
        c = obter_config()
        if not configurado():
            raise CredencialAusente("Documenso: falta EJMF_DOCUMENSO_TOKEN")
        self._base = c.documenso_url.rstrip("/")
        self._token = c.documenso_token
        self._cliente = httpx.Client(timeout=max(c.conectores_timeout_segundos, 60), transport=transporte)

    def _verificar(self, r: httpx.Response, acao: str) -> Any:
        if r.status_code == 401:
            raise CredencialRecusada("Documenso: chave da API recusada (401)")
        if r.status_code == 429:
            raise LimiteTaxa("Documenso: limite de requisições", float(r.headers.get("retry-after") or 60))
        if r.status_code >= 500:
            raise FonteIndisponivel(f"Documenso: erro {r.status_code} ao {acao}")
        if r.status_code >= 400:
            try:
                det = r.json().get("message")
            except ValueError:
                det = None
            erro = ErroConector(f"Documenso recusou ao {acao} ({r.status_code}){': ' + str(det)[:300] if det else ''}")
            erro.transitorio = False
            raise erro
        try:
            return r.json()
        except ValueError as e:
            raise FonteIndisponivel(f"Documenso: resposta inválida ao {acao}") from e

    def _post(self, caminho: str, acao: str, **kw) -> Any:
        try:
            r = self._cliente.post(f"{self._base}{caminho}", headers={"Authorization": self._token}, **kw)
        except httpx.TimeoutException as e:
            raise FonteIndisponivel(f"Documenso: tempo esgotado ao {acao}") from e
        except httpx.HTTPError as e:
            raise FonteIndisponivel(f"Documenso: falha de rede ao {acao} ({type(e).__name__})") from e
        return self._verificar(r, acao)

    def criar_envelope(self, *, titulo: str, pdf: bytes, nome_arquivo: str, participantes: list[dict], paginas: int,
                       id_externo: str, assunto: str | None, mensagem: str | None) -> str:
        campos = campos_assinatura(participantes, paginas)
        payload = {
            "type": "DOCUMENT", "title": titulo[:250], "externalId": id_externo,
            "recipients": [{"email": p["email"], "name": p["nome"], "role": PAPEIS[p["papel"]],
                            "signingOrder": p.get("ordem") or n + 1, **({"fields": campos[n]} if campos[n] else {})}
                           for n, p in enumerate(participantes)],
            "meta": {"subject": (assunto or titulo)[:250], "message": (mensagem or "")[:2000], "timezone": "America/Fortaleza",
                     "language": "pt", "distributionMethod": "EMAIL"},
        }
        dados = self._post("/envelope/create", "criar o envelope", data={"payload": json.dumps(payload)},
                           files=[("files", (nome_arquivo, pdf, "application/pdf"))])
        if not isinstance(dados, dict) or not dados.get("id"):
            raise FonteIndisponivel("Documenso: envelope criado sem id na resposta")
        return str(dados["id"])

    def distribuir(self, envelope_id: str) -> list[dict]:
        dados = self._post("/envelope/distribute", "enviar aos participantes", json={"envelopeId": envelope_id})
        return list((dados or {}).get("recipients") or [])
