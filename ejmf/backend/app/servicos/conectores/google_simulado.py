"""Servidor simulado do Google Calendar (dados fictícios, sempre marcados).

Implementa o subconjunto da API v3 que o conector usa (events.list com syncToken/pageToken/showDeleted,
insert, patch e delete) sobre um dicionário que quem chama persiste. Serve para o adaptador
"Simulado — Google Agenda" e para os testes, que podem editar eventos "do lado do Google".
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

PREFIXO = "[SIMULADO — dado fictício]"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def novo_estado(semear: bool = True, fuso: str = "America/Fortaleza") -> dict:
    estado = {"seq": 0, "eventos": {}, "expirar_token": False}
    if semear:
        hoje = datetime.now(ZoneInfo(fuso)).replace(hour=0, minute=0, second=0, microsecond=0)
        for dias, h, dur, titulo in ((1, 9, 60, "Reunião externa"), (2, 14, 90, "Compromisso particular do advogado")):
            ini = hoje + timedelta(days=dias, hours=h)
            criar_externo(estado, f"{PREFIXO} {titulo}", ini, ini + timedelta(minutes=dur))
    return estado


def _gravar(estado: dict, ev: dict) -> dict:
    estado["seq"] += 1
    ev["_seq"] = estado["seq"]
    ev["updated"] = _agora()
    ev["etag"] = f'"{estado["seq"]}"'
    estado["eventos"][ev["id"]] = ev
    return ev


def criar_externo(estado: dict, titulo: str, inicio: datetime, fim: datetime, *, visibilidade: str | None = None) -> dict:
    ev = {"id": "ext" + uuid.uuid4().hex[:20], "status": "confirmed", "summary": titulo,
          "start": {"dateTime": inicio.isoformat()}, "end": {"dateTime": fim.isoformat()}}
    if visibilidade:
        ev["visibility"] = visibilidade
    return _gravar(estado, ev)


def editar(estado: dict, event_id: str, **campos) -> dict:
    """Altera um evento como se fosse pelo app do Google."""
    ev = {**estado["eventos"][event_id], **campos}
    return _gravar(estado, ev)


def _publico(ev: dict) -> dict:
    return {k: v for k, v in ev.items() if not k.startswith("_")}


def transporte(estado: dict) -> httpx.MockTransport:
    def h(req: httpx.Request) -> httpx.Response:
        partes = req.url.path.split("/events")
        resto = partes[1].strip("/") if len(partes) > 1 else ""
        if req.method == "GET" and not resto:
            p = req.url.params
            token = p.get("syncToken")
            if token and estado.get("expirar_token"):
                estado["expirar_token"] = False
                return httpx.Response(410, json={"error": {"code": 410, "message": "Sync token is no longer valid"}})
            desde = int(token) if token else 0
            itens = sorted((e for e in estado["eventos"].values() if e["_seq"] > desde), key=lambda e: e["_seq"])
            if not token:
                itens = [e for e in itens if e.get("status") != "cancelled"]
            pagina, tam = int(p.get("pageToken") or 0), int(p.get("maxResults") or 250)
            fatia = itens[pagina:pagina + tam]
            corpo = {"items": [_publico(e) for e in fatia]}
            if pagina + tam < len(itens):
                corpo["nextPageToken"] = str(pagina + tam)
            else:
                corpo["nextSyncToken"] = str(estado["seq"])
            return httpx.Response(200, json=corpo)
        if req.method == "POST" and not resto:
            ev = json.loads(req.content)
            ev["id"] = "sim" + uuid.uuid4().hex[:20]
            ev.setdefault("status", "confirmed")
            return httpx.Response(200, json=_publico(_gravar(estado, ev)))
        ev = estado["eventos"].get(resto)
        if ev is None or (ev.get("status") == "cancelled" and req.method != "GET"):
            return httpx.Response(404 if ev is None else 410, json={"error": {"code": 404}})
        if req.method == "PATCH":
            return httpx.Response(200, json=_publico(editar(estado, resto, **json.loads(req.content))))
        if req.method == "DELETE":
            editar(estado, resto, status="cancelled")
            return httpx.Response(204)
        return httpx.Response(200, json=_publico(ev))
    return httpx.MockTransport(h)
