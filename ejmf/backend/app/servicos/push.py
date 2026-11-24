"""Notificações no celular por Web Push (RFC 8030), com VAPID (RFC 8292) e conteúdo cifrado (RFC 8291, aes128gcm).

Implementado com `cryptography`, sem biblioteca nova. Regras (ADR-0014):
- só envia se as chaves VAPID estiverem nas variáveis de ambiente (geradas localmente por `python -m app.cli gerar-vapid`);
- o aparelho só recebe um aviso genérico ("Nova notificação no EJMF"): título, cliente, processo e valores ficam no
  sistema, que pede login para abrir. Nada sigiloso passa pelo serviço de push nem aparece na tela bloqueada;
- só endereços HTTPS dos serviços de push dos navegadores (Google, Mozilla, Apple, Microsoft) são aceitos;
- a assinatura vale enquanto a sessão que a criou estiver aberta; 404/410 do serviço encerram a assinatura.
"""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import AssinaturaPush, Sessao, Tarefa, Usuario
from app.servicos import auditoria, fila
from app.servicos.conectores.base import ErroConector, LimiteTaxa

TRANSPORTE: dict[str, Any] = {"push": None}  # testes trocam por httpx.MockTransport
HOSTS_PERMITIDOS = ("fcm.googleapis.com", "android.googleapis.com", "push.services.mozilla.com",
                    "updates.push.services.mozilla.com", "push.apple.com", "notify.windows.com")
URGENTES = ("alerta", "perigo")
MAX_FALHAS = 5
MAX_POR_USUARIO = 10


class ErroPush(ValueError):
    def __init__(self, mensagem: str, status: int = 422):
        super().__init__(mensagem)
        self.status = status


class FalhaPermanente(ErroConector):
    transitorio = False


# ---------------------------------------------------------------- base64url e chaves

def b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def gerar_chaves() -> dict:
    """Par VAPID novo (P-256). A privada vai só para a variável de ambiente; nunca para o banco ou o Git."""
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"publica": b64(pub), "privada": b64(priv.private_numbers().private_value.to_bytes(32, "big"))}


def _chave_privada() -> ec.EllipticCurvePrivateKey | None:
    cfg = obter_config()
    if not (cfg.vapid_chave_publica and cfg.vapid_chave_privada):
        return None
    return ec.derive_private_key(int.from_bytes(de_b64(cfg.vapid_chave_privada), "big"), ec.SECP256R1())


def disponivel() -> bool:
    try:
        return _chave_privada() is not None
    except ValueError:
        return False


def estado() -> dict:
    cfg = obter_config()
    ok = disponivel()
    return {"disponivel": ok, "chave_publica": cfg.vapid_chave_publica if ok else None,
            "estado": "configurada" if ok else "aguardando_credenciais",
            "aviso": "O aparelho recebe só “Nova notificação no EJMF”; o conteúdo fica no sistema e pede login." if ok else
                     "Notificações no celular aguardam as chaves VAPID (EJMF_VAPID_CHAVE_PUBLICA e EJMF_VAPID_CHAVE_PRIVADA)."}


# ---------------------------------------------------------------- RFC 8292 e 8291

def _jwt(endpoint: str, agora: int | None = None) -> str:
    cfg = obter_config()
    partes = urlsplit(endpoint)
    sub = cfg.vapid_contato or cfg.url_publica
    if not sub.startswith(("mailto:", "https://")):
        sub = "https://" + urlsplit(sub).netloc if urlsplit(sub).netloc else "https://localhost"
    cab = b64(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    corpo = b64(json.dumps({"aud": f"{partes.scheme}://{partes.netloc}", "exp": (agora or int(time.time())) + 12 * 3600,
                            "sub": sub}, separators=(",", ":")).encode())
    assinatura = _chave_privada().sign(f"{cab}.{corpo}".encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(assinatura)
    return f"{cab}.{corpo}.{b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def _hkdf(sal: bytes, ikm: bytes, info: bytes, tamanho: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=tamanho, salt=sal, info=info).derive(ikm)


def cifrar(conteudo: bytes, p256dh: str, auth: str, *, sal: bytes | None = None,
           efemera: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """Corpo aes128gcm de um registro só (RFC 8291 §4 e RFC 8188)."""
    ua_pub = de_b64(p256dh)
    segredo_auth = de_b64(auth)
    if len(ua_pub) != 65 or ua_pub[0] != 4 or len(segredo_auth) != 16:
        raise ErroPush("Chaves do aparelho inválidas")
    efemera = efemera or ec.generate_private_key(ec.SECP256R1())
    as_pub = efemera.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ecdh = efemera.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = _hkdf(segredo_auth, ecdh, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    sal = sal or os.urandom(16)
    cek = _hkdf(sal, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(sal, ikm, b"Content-Encoding: nonce\x00", 12)
    cifrado = AESGCM(cek).encrypt(nonce, conteudo + b"\x02", None)
    return sal + (4096).to_bytes(4, "big") + bytes([len(as_pub)]) + as_pub + cifrado


def validar_endpoint(endpoint: str) -> str:
    p = urlsplit(endpoint)
    host = (p.hostname or "").lower()
    if (p.scheme != "https" or p.username or p.password or p.port not in (None, 443) or len(endpoint) > 1000
            or not any(host == h or host.endswith("." + h) for h in HOSTS_PERMITIDOS)):
        raise ErroPush("Endereço de notificação não reconhecido: só serviços de push dos navegadores")
    return endpoint


# ---------------------------------------------------------------- assinaturas

def assinar(db: Session, ator: auditoria.Ator, usuario: Usuario, sessao: Sessao, endpoint: str, p256dh: str, auth: str,
            dispositivo: str | None, so_urgentes: bool) -> AssinaturaPush:
    if not disponivel():
        raise ErroPush("Notificações no celular ainda não configuradas neste servidor", 409)
    validar_endpoint(endpoint)
    cifrar(b"teste", p256dh, auth)  # recusa chave malformada já no cadastro
    a = db.execute(select(AssinaturaPush).where(AssinaturaPush.endpoint == endpoint)).scalar()
    if a is None:
        ativas = db.execute(select(AssinaturaPush.id).where(AssinaturaPush.usuario_id == usuario.id,
                                                            AssinaturaPush.revogada_em.is_(None))).all()
        if len(ativas) >= MAX_POR_USUARIO:
            raise ErroPush(f"Limite de {MAX_POR_USUARIO} aparelhos: encerre um antes de cadastrar outro", 409)
        a = AssinaturaPush(escritorio_id=usuario.escritorio_id, usuario_id=usuario.id, endpoint=endpoint)
        db.add(a)
    elif a.usuario_id != usuario.id:
        # o mesmo navegador passou a outra pessoa: a assinatura antiga deixa de existir
        a.usuario_id, a.escritorio_id = usuario.id, usuario.escritorio_id
    a.p256dh, a.auth, a.sessao_id = p256dh, auth, sessao.id
    a.dispositivo = (dispositivo or "").strip()[:120] or None
    a.so_urgentes, a.falhas, a.revogada_em, a.motivo_revogacao = so_urgentes, 0, None, None
    db.flush()
    auditoria.registrar(db, ator, "push.assinar", entidade="assinatura_push", entidade_id=a.id,
                        alteracoes={"dispositivo": a.dispositivo, "so_urgentes": so_urgentes, "servico": urlsplit(endpoint).hostname})
    return a


def revogar(db: Session, a: AssinaturaPush, motivo: str) -> None:
    if a.revogada_em is None:
        a.revogada_em, a.motivo_revogacao = datetime.now(timezone.utc), motivo[:200]


def revogar_das_sessoes(db: Session, condicao) -> int:
    """Encerra as assinaturas ligadas às sessões que satisfazem a condição (sessão encerrada = aparelho desligado)."""
    sub = select(Sessao.id).where(condicao)
    return db.execute(update(AssinaturaPush).where(AssinaturaPush.sessao_id.in_(sub), AssinaturaPush.revogada_em.is_(None))
                      .values(revogada_em=datetime.now(timezone.utc), motivo_revogacao="Sessão encerrada")).rowcount or 0


def como_json(a: AssinaturaPush, sessao_atual: uuid.UUID | None = None) -> dict:
    return {"id": str(a.id), "dispositivo": a.dispositivo, "servico": urlsplit(a.endpoint).hostname, "so_urgentes": a.so_urgentes,
            "falhas": a.falhas, "ultimo_envio_em": a.ultimo_envio_em, "criado_em": a.criado_em,
            "este_aparelho": a.sessao_id == sessao_atual if sessao_atual else False}


def _sessao_valida(db: Session, a: AssinaturaPush) -> bool:
    s = db.get(Sessao, a.sessao_id) if a.sessao_id else None
    u = db.get(Usuario, a.usuario_id)
    return bool(s and s.revogada_em is None and s.expira_em > datetime.now(timezone.utc) and u and u.ativo)


# ---------------------------------------------------------------- envio

def avisar(db: Session, usuario_id: uuid.UUID, notificacao_id: uuid.UUID, nivel: str) -> int:
    """Põe na fila um envio por aparelho ativo do usuário. Chamado ao criar a notificação no sistema."""
    if not disponivel():
        return 0
    n = 0
    for a in db.execute(select(AssinaturaPush).where(AssinaturaPush.usuario_id == usuario_id,
                                                     AssinaturaPush.revogada_em.is_(None))).scalars():
        if a.so_urgentes and nivel not in URGENTES:
            continue
        fila.enfileirar(db, a.escritorio_id, "push.enviar", f"push:{notificacao_id}:{a.id}",
                        {"assinatura_id": str(a.id), "nivel": nivel}, max_tentativas=4)
        n += 1
    return n


def conteudo(nivel: str) -> bytes:
    """O que o aparelho recebe: nada além de um aviso genérico e o endereço do sino."""
    titulo = "Alerta no EJMF" if nivel in URGENTES else "Nova notificação no EJMF"
    return json.dumps({"titulo": titulo, "texto": "Abra o sistema para ver.", "link": "/painel", "nivel": nivel},
                      ensure_ascii=False).encode()


def enviar(db: Session, a: AssinaturaPush, nivel: str = "info") -> int:
    if not _sessao_valida(db, a):
        revogar(db, a, "Sessão encerrada")
        return 0
    corpo = cifrar(conteudo(nivel), a.p256dh, a.auth)
    cfg = obter_config()
    cab = {"TTL": "86400", "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
           "Urgency": "high" if nivel in URGENTES else "normal",
           "Authorization": f"vapid t={_jwt(a.endpoint)}, k={cfg.vapid_chave_publica}"}
    try:
        with httpx.Client(timeout=15, transport=TRANSPORTE.get("push"), follow_redirects=False) as c:
            r = c.post(validar_endpoint(a.endpoint), content=corpo, headers=cab)
    except httpx.HTTPError as e:
        raise ErroConector(f"Serviço de push indisponível: {e.__class__.__name__}") from e
    if r.status_code in (200, 201, 202):
        a.falhas, a.ultimo_envio_em = 0, datetime.now(timezone.utc)
        return r.status_code
    if r.status_code in (404, 410):
        revogar(db, a, "O navegador cancelou as notificações")
        return r.status_code
    a.falhas += 1
    if a.falhas >= MAX_FALHAS:
        revogar(db, a, f"{MAX_FALHAS} falhas seguidas")
    db.commit()
    if r.status_code == 429:
        raise LimiteTaxa("Serviço de push pediu para esperar", float(r.headers.get("Retry-After", "60") or 60))
    if r.status_code >= 500:
        raise ErroConector(f"Serviço de push respondeu {r.status_code}")
    raise FalhaPermanente(f"Serviço de push recusou o envio ({r.status_code})")


@fila.executor("push.enviar")
def _executar(db: Session, t: Tarefa) -> dict:
    a = db.get(AssinaturaPush, uuid.UUID(t.parametros["assinatura_id"]))
    if a is None or a.revogada_em is not None:
        return {"enviado": False, "motivo": "assinatura encerrada"}
    st = enviar(db, a, t.parametros.get("nivel", "info"))
    return {"enviado": st in (200, 201, 202), "status": st}
