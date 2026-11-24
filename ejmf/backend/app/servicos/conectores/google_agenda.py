"""Conector do Google Calendar (API v3) e fluxo OAuth 2.0 do escritório.

- Escopo mínimo: `calendar.events.owned` (ver, criar, alterar e excluir eventos nas agendas de que a conta é dona).
- OAuth "authorization code" com PKCE (S256), `access_type=offline` para obter refresh token. Client ID/secret e
  URL de retorno vêm só do ambiente (EJMF_GOOGLE_CLIENT_ID, EJMF_GOOGLE_CLIENT_SECRET, EJMF_GOOGLE_REDIRECT_URI).
- Leitura incremental: events.list com `syncToken`; token expirado responde 410 e exige ressincronização completa.
  `syncToken` não pode ser combinado com timeMin/timeMax/privateExtendedProperty (documentação oficial).
- Eventos criados pelo EJMF levam `extendedProperties.private.ejmf_id`; só esses podem ser alterados ou excluídos.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import httpx

from app.servicos.conectores.base import (
    CredencialAusente, CredencialRecusada, ErroConector, FonteIndisponivel, LimitadorTaxa, LimiteTaxa, erro_http,
)

ESCOPOS = ["https://www.googleapis.com/auth/calendar.events.owned"]
URL_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_REVOGAR = "https://oauth2.googleapis.com/revoke"
URL_API = "https://www.googleapis.com/calendar/v3"
FONTE = "Google Calendar"
_LIMITADOR = LimitadorTaxa(por_minuto=240)


class SyncTokenExpirado(ErroConector):
    """HTTP 410: o token de sincronização expirou; refazer a leitura completa."""


def pkce() -> tuple[str, str]:
    verificador = secrets.token_urlsafe(64)[:96]
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    return verificador, desafio


def _erro(r: httpx.Response) -> ErroConector:
    if r.status_code == 410:
        return SyncTokenExpirado(f"{FONTE}: token de sincronização expirado (HTTP 410)")
    if r.status_code == 401:
        return CredencialRecusada(f"{FONTE}: acesso recusado (HTTP 401). Conecte a conta Google de novo.")
    if r.status_code == 403:
        motivo = ""
        try:
            motivo = (r.json().get("error", {}).get("errors") or [{}])[0].get("reason", "")
        except ValueError:
            pass
        if motivo in ("rateLimitExceeded", "userRateLimitExceeded"):
            return LimiteTaxa(f"{FONTE}: limite de requisições atingido (HTTP 403 {motivo})", 60)
        return CredencialRecusada(f"{FONTE}: permissão negada (HTTP 403{' ' + motivo if motivo else ''}).")
    return erro_http(r.status_code, FONTE, r.headers.get("retry-after"))


class OAuthGoogle:
    def __init__(self, client_id: str | None, client_secret: str | None, redirect_uri: str | None, *,
                 transporte: httpx.BaseTransport | None = None, timeout: float = 30.0):
        self.client_id, self.client_secret, self.redirect_uri = client_id, client_secret, redirect_uri
        self._cliente = httpx.Client(transport=transporte, timeout=timeout)

    @property
    def configurado(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def url_autorizacao(self, estado: str, desafio: str) -> str:
        if not self.configurado:
            raise CredencialAusente("Credenciais OAuth do Google não configuradas (EJMF_GOOGLE_CLIENT_ID, "
                                    "EJMF_GOOGLE_CLIENT_SECRET, EJMF_GOOGLE_REDIRECT_URI)")
        return URL_AUTORIZACAO + "?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code",
            "scope": " ".join(ESCOPOS), "access_type": "offline", "prompt": "consent", "include_granted_scopes": "false",
            "state": estado, "code_challenge": desafio, "code_challenge_method": "S256"})

    def _token(self, dados: dict) -> dict:
        try:
            r = self._cliente.post(URL_TOKEN, data={**dados, "client_id": self.client_id, "client_secret": self.client_secret})
        except httpx.HTTPError as e:
            raise FonteIndisponivel(f"{FONTE}: falha de rede ao obter token ({type(e).__name__})") from e
        if r.status_code in (400, 401):
            erro = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("error")
            raise CredencialRecusada(f"{FONTE}: autorização recusada ({erro or r.status_code}). Conecte a conta de novo.")
        if r.status_code != 200:
            raise _erro(r)
        t = r.json()
        t["expira_em"] = (datetime.now(timezone.utc) + timedelta(seconds=int(t.get("expires_in", 3600)) - 60)).isoformat()
        return t

    def trocar_codigo(self, codigo: str, verificador: str) -> dict:
        return self._token({"grant_type": "authorization_code", "code": codigo, "redirect_uri": self.redirect_uri,
                            "code_verifier": verificador})

    def renovar(self, refresh_token: str) -> dict:
        t = self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})
        t.setdefault("refresh_token", refresh_token)
        return t

    def revogar(self, token: str) -> bool:
        try:
            return self._cliente.post(URL_REVOGAR, data={"token": token}).status_code == 200
        except httpx.HTTPError:
            return False


class ConectorGoogleAgenda:
    codigo = "google_calendar"
    nome = FONTE
    simulado = False

    def __init__(self, access_token: str, calendario_id: str = "primary", *, base_url: str = URL_API,
                 transporte: httpx.BaseTransport | None = None, timeout: float = 30.0, limitador: LimitadorTaxa | None = _LIMITADOR):
        if not access_token:
            raise CredencialAusente(f"{FONTE}: conta Google não conectada")
        self.calendario_id = calendario_id
        self._base = f"{base_url.rstrip('/')}/calendars/{quote(calendario_id, safe='')}/events"
        self._cliente = httpx.Client(transport=transporte, timeout=timeout,
                                     headers={"Authorization": f"Bearer {access_token}"})
        self._limitador = limitador
        self.requisicoes = 0

    def _req(self, metodo: str, url: str, **kw) -> httpx.Response:
        if self._limitador:
            self._limitador.aguardar()
        self.requisicoes += 1
        try:
            r = self._cliente.request(metodo, url, **kw)
        except httpx.TimeoutException as e:
            raise FonteIndisponivel(f"{FONTE}: tempo de resposta esgotado") from e
        except httpx.HTTPError as e:
            raise FonteIndisponivel(f"{FONTE}: falha de rede ({type(e).__name__})") from e
        if r.status_code >= 400 and not (metodo == "DELETE" and r.status_code in (404, 410)):
            raise _erro(r)
        return r

    def listar_mudancas(self, sync_token: str | None, inicio_completo: datetime) -> tuple[list[dict], str | None]:
        """Devolve (eventos, próximo sync token). Sem token: leitura completa a partir de `inicio_completo`."""
        itens: list[dict] = []
        params: dict = {"maxResults": 250, "singleEvents": "true", "showDeleted": "true"}
        if sync_token:
            params["syncToken"] = sync_token
        else:
            params["timeMin"] = inicio_completo.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        proximo = None
        for _ in range(40):
            dados = self._req("GET", self._base, params=params).json()
            itens.extend(dados.get("items") or [])
            if dados.get("nextPageToken"):
                params = {**params, "pageToken": dados["nextPageToken"]}
                continue
            proximo = dados.get("nextSyncToken")
            break
        return itens, proximo

    def inserir(self, evento: dict) -> dict:
        return self._req("POST", self._base, json=evento).json()

    def atualizar(self, event_id: str, evento: dict) -> dict:
        return self._req("PATCH", f"{self._base}/{event_id}", json=evento).json()

    def remover(self, event_id: str) -> None:
        """Só para eventos criados pelo EJMF (quem chama garante)."""
        self._req("DELETE", f"{self._base}/{event_id}")
