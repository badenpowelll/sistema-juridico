"""Fase 10: notificações no celular (Web Push com VAPID e aes128gcm) e voz no assistente.

A rede é sempre simulada (httpx.MockTransport). O teste faz o papel do navegador: decifra o corpo com a chave privada do
aparelho (RFC 8291) e confere a assinatura VAPID (RFC 8292) com a chave pública do servidor.
"""
import base64
import json

import httpx
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select, update

from app.core.config import obter_config
from app.modelos import AssinaturaPush, Tarefa
from app.servicos import fila, notificacoes, push
from app.servicos.semente import obter_escritorio

ENDPOINT = "https://fcm.googleapis.com/fcm/send/sintetico-"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _de(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class Aparelho:
    """Navegador sintético: par de chaves P-256 e segredo de autenticação, como o PushManager gera."""

    def __init__(self):
        self.priv = ec.generate_private_key(ec.SECP256R1())
        self.pub = self.priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.auth = bytes(range(16))

    def chaves(self) -> dict:
        return {"p256dh": _b64(self.pub), "auth": _b64(self.auth)}

    def decifrar(self, corpo: bytes) -> bytes:
        sal, rs, idlen = corpo[:16], int.from_bytes(corpo[16:20], "big"), corpo[20]
        as_pub = corpo[21:21 + idlen]
        assert rs == 4096 and idlen == 65
        ecdh = self.priv.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
        hk = lambda s, k, i, n: HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=i).derive(k)  # noqa: E731
        ikm = hk(self.auth, ecdh, b"WebPush: info\x00" + self.pub + as_pub, 32)
        cek = hk(sal, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = hk(sal, ikm, b"Content-Encoding: nonce\x00", 12)
        claro = AESGCM(cek).decrypt(nonce, corpo[21 + idlen:], None)
        assert claro.endswith(b"\x02")
        return claro[:-1]


@pytest.fixture
def vapid(monkeypatch, db):
    # aparelhos e envios de testes anteriores não contam aqui
    from datetime import datetime, timezone
    db.execute(update(AssinaturaPush).where(AssinaturaPush.revogada_em.is_(None)).values(revogada_em=datetime.now(timezone.utc)))
    db.execute(update(Tarefa).where(Tarefa.tipo == "push.enviar", Tarefa.estado == "pendente").values(estado="falhou"))
    db.commit()
    k = push.gerar_chaves()
    monkeypatch.setenv("EJMF_VAPID_CHAVE_PUBLICA", k["publica"])
    monkeypatch.setenv("EJMF_VAPID_CHAVE_PRIVADA", k["privada"])
    monkeypatch.setenv("EJMF_URL_PUBLICA", "https://ejmf.exemplo.invalid")
    obter_config.cache_clear()
    recebidos: list[httpx.Request] = []
    resposta = {"status": 201}

    def servico(req: httpx.Request) -> httpx.Response:
        recebidos.append(req)
        return httpx.Response(resposta["status"], headers={"Retry-After": "30"})
    push.TRANSPORTE["push"] = httpx.MockTransport(servico)
    yield {"chaves": k, "recebidos": recebidos, "resposta": resposta}
    push.TRANSPORTE["push"] = None
    obter_config.cache_clear()


def _assinar(c, aparelho, sufixo="a", **kw):
    return c.post("/api/v1/aparelhos/push", json={"endpoint": ENDPOINT + sufixo, "keys": aparelho.chaves(),
                                                  "dispositivo": "Celular sintético", **kw})


def _processar(db):
    n = 0
    while (t := fila.pegar(db)) is not None:
        fila.executar(db, t)
        n += 1
    return n


def test_sem_chaves_fica_aguardando_credenciais(admin):
    c, _ = admin
    r = c.get("/api/v1/aparelhos/push").json()
    assert r["disponivel"] is False and r["estado"] == "aguardando_credenciais" and r["chave_publica"] is None
    assert _assinar(c, Aparelho()).status_code == 409


def test_cifra_assina_e_envia_so_aviso_generico(db, admin, vapid):
    c, u = admin
    ap = Aparelho()
    a = _assinar(c, ap)
    assert a.status_code == 201, a.text
    assert a.json()["este_aparelho"] is True and a.json()["servico"] == "fcm.googleapis.com"
    # endereços fora dos serviços de push são recusados (evita o servidor virar ponte para outros endereços)
    for ruim in ("https://exemplo.invalid/push", "http://fcm.googleapis.com/x", "https://fcm.googleapis.com:8443/x",
                 "https://usuario:senha@fcm.googleapis.com/x", "https://fcm.googleapis.com.exemplo.invalid/x"):
        assert c.post("/api/v1/aparelhos/push", json={"endpoint": ruim, "keys": ap.chaves()}).status_code == 422, ruim
    ruim = {**ap.chaves(), "p256dh": _b64(b"\x04" + bytes(40))}
    assert c.post("/api/v1/aparelhos/push", json={"endpoint": ENDPOINT + "z", "keys": ruim}).status_code in (422,)

    esc = obter_escritorio(db)
    n = notificacoes.notificar(db, esc.id, "financeiro:ler", "Honorário do cliente Fulano Sintético vencido: R$ 1.234,00",
                               texto="Processo 0000000-00.2025.8.20.0001", link="/painel/financeiro", nivel="alerta",
                               chave="teste-push-1")
    db.commit()
    assert n >= 1
    assert _processar(db) >= 1
    req = vapid["recebidos"][-1]
    assert str(req.url) == ENDPOINT + "a" and req.headers["Content-Encoding"] == "aes128gcm" and req.headers["TTL"] == "86400"
    assert req.headers["Urgency"] == "high"
    # o navegador consegue abrir, e só há o aviso genérico: nada de cliente, processo ou valor
    claro = json.loads(ap.decifrar(req.content))
    assert claro == {"titulo": "Alerta no EJMF", "texto": "Abra o sistema para ver.", "link": "/painel", "nivel": "alerta"}
    assert b"Fulano" not in req.content and "Fulano" not in json.dumps(claro)
    # VAPID: JWT ES256 com aud do serviço, sub do escritório e chave pública do servidor
    t, k = [p.split("=", 1)[1] for p in req.headers["Authorization"].removeprefix("vapid ").split(", ")]
    assert k == vapid["chaves"]["publica"]
    cab, corpo, sig = t.split(".")
    dados = json.loads(_de(corpo))
    assert dados["aud"] == "https://fcm.googleapis.com" and dados["sub"] == "https://ejmf.exemplo.invalid"
    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _de(k))
    s = _de(sig)
    pub.verify(encode_dss_signature(int.from_bytes(s[:32], "big"), int.from_bytes(s[32:], "big")),
               f"{cab}.{corpo}".encode(), ec.ECDSA(hashes.SHA256()))
    with pytest.raises(InvalidSignature):
        pub.verify(encode_dss_signature(1, 1), b"x", ec.ECDSA(hashes.SHA256()))
    # a mesma notificação não é enviada duas vezes (chave na fila)
    notificacoes.notificar(db, esc.id, "financeiro:ler", "Outro título", chave="teste-push-1")
    db.commit()
    assert _processar(db) == 0


def test_so_urgentes_410_e_sessao_encerrada(db, admin, app_cliente, vapid):
    c, u = admin
    esc = obter_escritorio(db)
    ap = Aparelho()
    aid = _assinar(c, ap, "b", so_urgentes=True).json()["id"]
    notificacoes.notificar(db, esc.id, "financeiro:ler", "Aviso comum", nivel="info", chave="teste-push-2")
    db.commit()
    assert _processar(db) == 0  # aparelho só quer urgentes
    assert c.patch(f"/api/v1/aparelhos/push/{aid}", json={"so_urgentes": False}).status_code == 200
    # o serviço diz que o navegador cancelou: a assinatura acaba
    vapid["resposta"]["status"] = 410
    assert c.post(f"/api/v1/aparelhos/push/{aid}/teste").json() == {"enviado": False, "status": 410}
    assert db.get(AssinaturaPush, __import__("uuid").UUID(aid)).revogada_em is not None
    assert c.get("/api/v1/aparelhos/push").json()["aparelhos"] == []
    # 500 tenta de novo mais tarde; 429 respeita o Retry-After
    vapid["resposta"]["status"] = 201
    aid = _assinar(c, ap, "b").json()["id"]
    vapid["resposta"]["status"] = 503
    notificacoes.notificar(db, esc.id, "financeiro:ler", "Aviso", nivel="info", chave="teste-push-3")
    db.commit()
    _processar(db)
    t = db.execute(select(Tarefa).where(Tarefa.chave.like("push:%"), Tarefa.estado == "pendente")).scalars().all()
    assert t and t[-1].tentativas == 1
    # sair do sistema encerra as notificações daquele aparelho
    vapid["resposta"]["status"] = 201
    assert c.post("/api/v1/auth/sair").status_code == 200
    db.expire_all()
    assert db.get(AssinaturaPush, __import__("uuid").UUID(aid)).motivo_revogacao == "Sessão encerrada"


def test_cada_um_ve_so_os_proprios_aparelhos(db, admin, operador, vapid):
    c, _ = admin
    o, _ = operador
    aid = _assinar(c, Aparelho(), "c").json()["id"]
    assert o.get("/api/v1/aparelhos/push").json()["aparelhos"] == []
    assert o.delete(f"/api/v1/aparelhos/push/{aid}").status_code == 404
    assert o.post(f"/api/v1/aparelhos/push/{aid}/teste").status_code == 404
    assert c.delete(f"/api/v1/aparelhos/push/{aid}").status_code == 200
    assert c.delete(f"/api/v1/aparelhos/push/{aid}").status_code == 404
    # campo a mais é recusado
    assert c.post("/api/v1/aparelhos/push", json={"endpoint": ENDPOINT + "d", "keys": Aparelho().chaves(), "x": 1}).status_code == 422


def test_cli_gera_chaves_validas(capsys):
    from app import cli
    assert cli.main(["gerar-vapid"]) == 0
    saida = capsys.readouterr().out
    pub = next(x.split("=", 1)[1] for x in saida.splitlines() if x.startswith("EJMF_VAPID_CHAVE_PUBLICA="))
    assert len(_de(pub)) == 65 and _de(pub)[0] == 4


def test_voz_desligada_por_padrao_e_so_o_advogado_liga(admin, operador):
    c, _ = admin
    o, _ = operador
    h = c.get("/api/v1/assistente").json()["voz"]
    assert h["permitida"] is False and h["pode_alterar"] is True and "Google" in h["aviso"]
    assert c.post("/api/v1/assistente", json={"texto": "Publicações pendentes", "canal": "voz"}).status_code == 409
    assert o.put("/api/v1/assistente/voz", json={"permitida": True}).status_code == 403
    assert c.put("/api/v1/configuracoes/voz.reconhecimento_navegador", json={"valor": True}).status_code in (404, 409)
    assert c.put("/api/v1/assistente/voz", json={"permitida": True}).json()["permitida"] is True
    r = c.post("/api/v1/assistente", json={"texto": "Publicações pendentes", "canal": "voz"})
    assert r.status_code == 201 and r.json()["canal"] == "voz" and r.json()["tipo"] == "consulta"
    # por voz continua valendo a recusa do que altera dados
    r = c.post("/api/v1/assistente", json={"texto": "Cancelar a audiência de amanhã", "canal": "voz"})
    assert r.json()["tipo"] == "recusado"
