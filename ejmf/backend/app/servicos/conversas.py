"""Conversas por canal (WhatsApp real ou simulado): recebimento idempotente, envio pela fila e janela de 24 h."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import Cliente, Conversa, Integracao, Mensagem, Tarefa, Usuario
from app.servicos import auditoria, fila, notificacoes, recepcionista
from app.servicos import prazos as svc_prazos
from app.servicos.conectores import whatsapp
from app.servicos.conectores.base import CredencialAusente, CredencialRecusada

CANAIS = ("whatsapp", "whatsapp_simulado")
JANELA = timedelta(hours=24)


class ErroConversa(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _integracao(db: Session, esc_id: uuid.UUID, codigo: str) -> Integracao | None:
    return db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id, Integracao.codigo == codigo)).scalar()


def simulador_disponivel() -> bool:
    return obter_config().conectores_simulados


def _cliente_pelo_telefone(db: Session, esc_id: uuid.UUID, numero: str) -> Cliente | None:
    d = re.sub(r"\D", "", numero)
    if len(d) < 10:
        return None
    nacional = d[2:] if d.startswith("55") and len(d) >= 12 else d
    candidatos = {nacional, nacional[:2] + nacional[3:] if len(nacional) == 11 else nacional[:2] + "9" + nacional[2:]}
    achados = db.execute(select(Cliente).where(Cliente.escritorio_id == esc_id, Cliente.telefone.in_(candidatos))).scalars().all()
    return achados[0] if len(achados) == 1 else None  # ambíguo: não vincula


def receber(db: Session, esc_id: uuid.UUID, canal: str, *, contato_id: str, nome: str | None, texto: str,
            id_externo: str | None, tipo: str = "texto", original: dict | None = None) -> tuple[Conversa, Mensagem | None, list[Mensagem]]:
    """Registra a mensagem do contato e, se a conversa está com a recepcionista, gera as respostas.
    Mensagem repetida (mesmo id externo) é ignorada: o webhook da Meta pode reenviar."""
    if canal not in CANAIS:
        raise ErroConversa("Canal inválido", 422)
    simulado = canal == "whatsapp_simulado"
    if id_externo and db.execute(select(Mensagem.id).where(Mensagem.escritorio_id == esc_id,
                                                           Mensagem.id_externo == id_externo)).first():
        conv = db.execute(select(Conversa).where(Conversa.escritorio_id == esc_id, Conversa.canal == canal,
                                                 Conversa.contato_id == contato_id)).scalar()
        return conv, None, []
    conv = db.execute(select(Conversa).where(Conversa.escritorio_id == esc_id, Conversa.canal == canal,
                                             Conversa.contato_id == contato_id).with_for_update()).scalar()
    if conv is None:
        cli = _cliente_pelo_telefone(db, esc_id, contato_id)
        conv = Conversa(escritorio_id=esc_id, canal=canal, contato_id=contato_id, simulado=simulado,
                        contato_nome=(("[SIMULADO] " if simulado and nome and not nome.startswith("[SIMULADO]") else "") + nome) if nome else None,
                        cliente_id=cli.id if cli else None, contexto={})
        db.add(conv)
        db.flush()
    if conv.estado == "encerrada":
        conv.estado, conv.contexto = "recepcionista", {}
    conv.ultima_entrada_em = conv.ultima_mensagem_em = agora()
    conv.nao_lidas += 1
    entrada = Mensagem(escritorio_id=esc_id, conversa_id=conv.id, direcao="entrada", autor="contato", tipo=tipo,
                       texto=texto or "", id_externo=id_externo, situacao="recebida", original=original)
    db.add(entrada)
    db.flush()
    respostas: list[Mensagem] = []
    ativa = svc_prazos.config(db, esc_id, "recepcionista.ativa", True)
    if conv.estado == "recepcionista" and ativa:
        if tipo != "texto":
            intent, textos = "arquivo", ["Recebi seu arquivo, mas por aqui não consigo guardá-lo com segurança. "
                                         "Envie os documentos pelo link seguro: responda 2 que eu mando o link."]
        else:
            intent, textos = recepcionista.responder(db, conv, texto)
        entrada.intencao = intent
        for t in textos:
            respostas.append(enviar(db, conv, t, autor="recepcionista"))
    else:
        notificacoes.notificar(db, esc_id, "conversas:ler", f"Mensagem de {conv.contato_nome or conv.contato_id}",
                               texto=(texto or "")[:200], link=f"/painel/conversas?c={conv.id}",
                               chave=f"mensagem:{entrada.id}")
    return conv, entrada, respostas


def enviar(db: Session, conv: Conversa, texto: str, *, autor: str, usuario: Usuario | None = None) -> Mensagem:
    texto = (texto or "").strip()
    if not texto:
        raise ErroConversa("Mensagem vazia", 422)
    if conv.canal == "whatsapp" and (conv.ultima_entrada_em is None or conv.ultima_entrada_em < agora() - JANELA):
        raise ErroConversa("Fora da janela de 24 h do WhatsApp: só modelos aprovados pela Meta podem ser enviados "
                           "agora (ainda não configurados). Use outro canal ou aguarde o contato escrever.")
    m = Mensagem(escritorio_id=conv.escritorio_id, conversa_id=conv.id, direcao="saida", autor=autor,
                 usuario_id=usuario.id if usuario else None, texto=texto[:4096],
                 situacao="simulada" if conv.simulado else "pendente")
    db.add(m)
    db.flush()
    conv.ultima_mensagem_em = agora()
    if not conv.simulado:
        fila.enfileirar(db, conv.escritorio_id, "whatsapp.enviar", f"whatsapp:{m.id}", {"mensagem_id": str(m.id)},
                        max_tentativas=4, criada_por=autor)
    return m


@fila.executor("whatsapp.enviar")
def _tarefa_enviar(db: Session, t: Tarefa) -> dict:
    m = db.get(Mensagem, uuid.UUID(t.parametros["mensagem_id"]))
    if m is None or m.situacao not in ("pendente", "falha"):
        return {"ignorada": True}
    conv = db.get(Conversa, m.conversa_id)
    integ = _integracao(db, conv.escritorio_id, "whatsapp")
    try:
        m.id_externo = whatsapp.ConectorWhatsApp(transporte=TRANSPORTE.get("whatsapp")).enviar_texto(conv.contato_id, m.texto)
    except (CredencialAusente, CredencialRecusada) as e:
        m.situacao, m.erro = "falha", str(e)
        if integ:
            integ.estado, integ.ultimo_erro = "aguardando_credenciais", str(e)
        db.commit()
        raise
    except Exception as e:
        m.situacao, m.erro = "falha", str(e)
        db.commit()
        raise
    m.situacao, m.erro = "enviada", None
    if integ:
        integ.ultima_execucao_em = integ.ultimo_sucesso_em = agora()
        integ.ultimo_erro = None
        if integ.estado != "implementada_validada":
            integ.estado = "implementada_validada"  # primeiro envio real aceito pela Meta
    return {"id_externo": m.id_externo}


TRANSPORTE: dict = {}  # testes injetam httpx.MockTransport aqui


def atualizar_status(db: Session, esc_id: uuid.UUID, status: list[whatsapp.Status]) -> int:
    n = 0
    for s in status:
        m = db.execute(select(Mensagem).where(Mensagem.escritorio_id == esc_id, Mensagem.id_externo == s.id_externo)).scalar()
        if m is None:
            continue
        mapa = {"sent": "enviada", "delivered": "entregue", "read": "lida", "failed": "falha"}
        nova = mapa.get(s.situacao)
        ordem = ["pendente", "enviada", "entregue", "lida"]
        if nova == "falha":
            m.situacao, m.erro = "falha", s.erro
        elif nova and (m.situacao not in ordem or ordem.index(nova) > ordem.index(m.situacao)):
            m.situacao = nova
        n += 1
    return n


def webhook_recebido(db: Session, esc_id: uuid.UUID) -> None:
    """Primeiro webhook assinado com as credenciais configuradas: a integração passa a 'em ambiente de testes'."""
    integ = _integracao(db, esc_id, "whatsapp")
    if integ and integ.estado == "aguardando_credenciais" and whatsapp.configurado():
        integ.estado = "ambiente_testes"
    if integ:
        integ.ultima_execucao_em = agora()


def assumir(db: Session, ator: auditoria.Ator, conv: Conversa, usuario: Usuario) -> Conversa:
    conv.estado = "humano"
    conv.contexto = {**(conv.contexto or {}), "aguardando": None, "assumida_por": str(usuario.id)}
    auditoria.registrar(db, ator, "conversa.assumir", entidade="conversa", entidade_id=conv.id)
    return conv


def devolver(db: Session, ator: auditoria.Ator, conv: Conversa) -> Conversa:
    conv.estado, conv.contexto = "recepcionista", {"saudou": True}
    auditoria.registrar(db, ator, "conversa.devolver", entidade="conversa", entidade_id=conv.id)
    return conv


def encerrar(db: Session, ator: auditoria.Ator, conv: Conversa) -> Conversa:
    conv.estado, conv.contexto = "encerrada", {}
    auditoria.registrar(db, ator, "conversa.encerrar", entidade="conversa", entidade_id=conv.id)
    return conv


def nao_lidas(db: Session, esc_id: uuid.UUID) -> int:
    return db.execute(select(func.coalesce(func.sum(Conversa.nao_lidas), 0)).where(
        Conversa.escritorio_id == esc_id, Conversa.estado == "humano")).scalar_one()


def janela_aberta(conv: Conversa) -> bool:
    return conv.simulado or bool(conv.ultima_entrada_em and conv.ultima_entrada_em >= agora() - JANELA)


def conversa_json(conv: Conversa, ultima: Mensagem | None = None) -> dict:
    return {"id": str(conv.id), "canal": conv.canal, "contato_id": conv.contato_id, "contato_nome": conv.contato_nome,
            "cliente_id": str(conv.cliente_id) if conv.cliente_id else None,
            "atendimento_id": str(conv.atendimento_id) if conv.atendimento_id else None, "estado": conv.estado,
            "nao_lidas": conv.nao_lidas, "ultima_mensagem_em": conv.ultima_mensagem_em, "simulado": conv.simulado,
            "janela_aberta": janela_aberta(conv), "motivo_transferencia": (conv.contexto or {}).get("motivo_transferencia"),
            "ultima": mensagem_json(ultima) if ultima else None}


def mensagem_json(m: Mensagem, nomes: dict | None = None) -> dict:
    return {"id": str(m.id), "direcao": m.direcao, "autor": m.autor, "usuario": (nomes or {}).get(m.usuario_id),
            "tipo": m.tipo, "texto": m.texto, "intencao": m.intencao, "situacao": m.situacao, "erro": m.erro,
            "criado_em": m.criado_em}


def listar(db: Session, esc_id: uuid.UUID, estado: str | None = None) -> list[dict]:
    q = select(Conversa).where(Conversa.escritorio_id == esc_id)
    if estado:
        q = q.where(Conversa.estado == estado)
    convs = db.execute(q.order_by(Conversa.ultima_mensagem_em.desc().nulls_last()).limit(200)).scalars().all()
    out = []
    for c in convs:
        ult = db.execute(select(Mensagem).where(Mensagem.conversa_id == c.id).order_by(Mensagem.criado_em.desc()).limit(1)).scalar()
        out.append(conversa_json(c, ult))
    return out

