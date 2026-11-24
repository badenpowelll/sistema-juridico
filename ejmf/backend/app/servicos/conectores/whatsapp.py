"""WhatsApp Business Cloud API (Meta). Documentação oficial consultada em 2026-11-24:
- envio: POST {api}/{phone_number_id}/messages com {"messaging_product": "whatsapp", "recipient_type": "individual",
  "to": <número>, "type": "text", "text": {"body": ...}} e cabeçalho Authorization: Bearer <token>;
- webhook: GET de verificação com hub.mode=subscribe, hub.verify_token e hub.challenge; POST com o corpo assinado
  em X-Hub-Signature-256 ("sha256=" + HMAC-SHA256 do corpo bruto com o app secret);
- mensagens livres só dentro da janela de atendimento de 24 h aberta pela última mensagem do contato; fora dela,
  apenas modelos (templates) aprovados pela Meta — ainda não implementados aqui.

Nenhuma credencial vem do código: token, phone number id, app secret e verify token chegam por variável de ambiente.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import obter_config
from app.servicos.conectores.base import CredencialAusente, CredencialRecusada, ErroConector, FonteIndisponivel, LimiteTaxa


def configurado() -> bool:
    c = obter_config()
    return bool(c.whatsapp_token and c.whatsapp_phone_number_id and c.whatsapp_app_secret and c.whatsapp_verify_token)


def verificar_assinatura(corpo: bytes, assinatura: str | None, segredo: str | None = None) -> bool:
    segredo = segredo if segredo is not None else obter_config().whatsapp_app_secret
    if not segredo or not assinatura or not assinatura.startswith("sha256="):
        return False
    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, assinatura.removeprefix("sha256="))


def verificar_inscricao(modo: str | None, token: str | None, desafio: str | None) -> str | None:
    """Devolve o hub.challenge quando o verify token confere; senão None."""
    esperado = obter_config().whatsapp_verify_token
    if modo == "subscribe" and esperado and token and hmac.compare_digest(esperado, token) and desafio:
        return desafio
    return None


@dataclass
class Recebida:
    id_externo: str
    de: str
    nome: str | None
    tipo: str
    texto: str
    original: dict


@dataclass
class Status:
    id_externo: str
    situacao: str  # sent | delivered | read | failed
    erro: str | None


def interpretar_webhook(corpo: dict) -> tuple[list[Recebida], list[Status]]:
    """Extrai mensagens recebidas e status de envio do payload do webhook (campo "messages")."""
    msgs, sts = [], []
    if corpo.get("object") != "whatsapp_business_account":
        return msgs, sts
    for entrada in corpo.get("entry") or []:
        for mud in entrada.get("changes") or []:
            if mud.get("field") != "messages":
                continue
            v = mud.get("value") or {}
            nomes = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in v.get("contacts") or []}
            for m in v.get("messages") or []:
                tipo = m.get("type") or "desconhecido"
                if tipo == "text":
                    texto = (m.get("text") or {}).get("body") or ""
                elif tipo == "interactive":
                    i = m.get("interactive") or {}
                    texto = ((i.get("button_reply") or i.get("list_reply") or {}).get("title")) or ""
                elif tipo == "button":
                    texto = (m.get("button") or {}).get("text") or ""
                else:
                    texto = f"[{tipo} recebido]"
                msgs.append(Recebida(id_externo=str(m.get("id")), de=str(m.get("from")), nome=nomes.get(m.get("from")),
                                     tipo=tipo, texto=texto[:4096], original=m))
            for s in v.get("statuses") or []:
                erros = s.get("errors") or []
                sts.append(Status(id_externo=str(s.get("id")), situacao=str(s.get("status")),
                                  erro=(erros[0].get("title") or erros[0].get("message")) if erros else None))
    return msgs, sts


class ConectorWhatsApp:
    def __init__(self, transporte: httpx.BaseTransport | None = None):
        c = obter_config()
        if not configurado():
            raise CredencialAusente("WhatsApp Business: faltam EJMF_WHATSAPP_TOKEN, EJMF_WHATSAPP_PHONE_NUMBER_ID, "
                                    "EJMF_WHATSAPP_APP_SECRET e EJMF_WHATSAPP_VERIFY_TOKEN")
        self._url = f"{c.whatsapp_api_url.rstrip('/')}/{c.whatsapp_phone_number_id}/messages"
        self._token = c.whatsapp_token
        self._cliente = httpx.Client(timeout=c.conectores_timeout_segundos, transport=transporte)

    def enviar_texto(self, para: str, texto: str) -> str:
        corpo: dict[str, Any] = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": para,
                                 "type": "text", "text": {"body": texto[:4096], "preview_url": False}}
        try:
            r = self._cliente.post(self._url, json=corpo, headers={"Authorization": f"Bearer {self._token}"})
        except httpx.TimeoutException as e:
            raise FonteIndisponivel("WhatsApp: tempo esgotado") from e
        except httpx.HTTPError as e:
            raise FonteIndisponivel(f"WhatsApp: falha de rede ({type(e).__name__})") from e
        if r.status_code == 401:
            raise CredencialRecusada("WhatsApp: token recusado (401)")
        if r.status_code == 429:
            raise LimiteTaxa("WhatsApp: limite de envio", float(r.headers.get("retry-after") or 60))
        if r.status_code >= 500:
            raise FonteIndisponivel(f"WhatsApp: erro {r.status_code}")
        if r.status_code >= 400:
            try:
                det = (r.json().get("error") or {}).get("message")
            except ValueError:
                det = None
            erro = ErroConector(f"WhatsApp recusou o envio ({r.status_code}){': ' + det if det else ''}")
            erro.transitorio = False
            raise erro
        try:
            return str(r.json()["messages"][0]["id"])
        except (ValueError, KeyError, IndexError) as e:
            raise FonteIndisponivel("WhatsApp: resposta sem id da mensagem") from e
