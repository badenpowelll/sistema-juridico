"""Antivírus dos arquivos recebidos (Fase 11): cliente do clamd (ClamAV) pelo protocolo INSTREAM.

Sem EJMF_CLAMAV_ENDERECO, a varredura fica desligada e a integração aparece "aguardando configuração". Configurado e
fora do ar, o arquivo não é perdido nem aceito às cegas: vai para a quarentena até a equipe liberar. Arquivo
infectado é recusado e não é gravado. O arquivo é enviado ao clamd do próprio servidor; nada sai para fora.
"""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass

from app.core.config import obter_config

TEMPO_S = 30.0
BLOCO = 64 * 1024


@dataclass(frozen=True)
class Resultado:
    situacao: str  # limpo | infectado | indisponivel | desligado
    detalhe: str | None = None


def _conectar(endereco: str) -> socket.socket:
    if endereco.startswith("tcp://"):
        host, _, porta = endereco[6:].rpartition(":")
        s = socket.create_connection((host or "127.0.0.1", int(porta or 3310)), timeout=TEMPO_S)
    else:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(TEMPO_S)
        s.connect(endereco.removeprefix("unix://"))
    return s


def _ler(s: socket.socket) -> str:
    partes = b""
    while not partes.endswith(b"\0"):
        p = s.recv(4096)
        if not p:
            break
        partes += p
    return partes.rstrip(b"\0").decode(errors="replace").strip()


def configurado() -> bool:
    return bool(obter_config().clamav_endereco)


def ping() -> bool:
    end = obter_config().clamav_endereco
    if not end:
        return False
    try:
        with _conectar(end) as s:
            s.sendall(b"zPING\0")
            return _ler(s) == "PONG"
    except OSError:
        return False


def varrer(dados: bytes) -> Resultado:
    end = obter_config().clamav_endereco
    if not end:
        return Resultado("desligado")
    try:
        with _conectar(end) as s:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(dados), BLOCO):
                pedaco = dados[i:i + BLOCO]
                s.sendall(struct.pack(">I", len(pedaco)) + pedaco)
            s.sendall(struct.pack(">I", 0))
            resposta = _ler(s)
    except OSError as e:
        return Resultado("indisponivel", f"Antivírus fora do ar: {e.__class__.__name__}")
    # respostas: "stream: OK", "stream: <assinatura> FOUND", "INSTREAM size limit exceeded. ERROR"
    if resposta.endswith("FOUND"):
        return Resultado("infectado", resposta.removeprefix("stream:").removesuffix("FOUND").strip())
    if resposta.endswith("OK"):
        return Resultado("limpo")
    return Resultado("indisponivel", f"Antivírus não conseguiu verificar: {resposta[:200]}")


def motivo_quarentena(r: Resultado) -> str | None:
    if r.situacao == "indisponivel":
        return f"Varredura de vírus pendente ({r.detalhe}). Libere depois de verificar o arquivo."
    return None
