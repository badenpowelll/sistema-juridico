"""Assinatura eletrônica pelo Documenso: preparar, autorizar o envio e acompanhar pelo webhook.

O EJMF nunca assina por ninguém nem simula assinatura. Sem a chave da API configurada, a integração fica em
"aguardando credenciais" e o envio é recusado; o pedido continua preparado e pode ser enviado depois.
"""
from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Assinatura, Atendimento, Integracao, Minuta, Tarefa, Usuario, VersaoDocumento
from app.servicos import armazenamento, auditoria, fila
from app.servicos.conectores import documenso
from app.servicos.conectores.base import CredencialAusente, CredencialRecusada

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SITUACOES = {"preparada": "Preparada", "enviando": "Enviando", "enviada": "Enviada", "parcial": "Assinada em parte",
             "concluida": "Concluída", "recusada": "Recusada", "cancelada": "Cancelada", "falha": "Falha no envio"}
EVENTOS = {"DOCUMENT_SENT": "enviado", "DOCUMENT_OPENED": "aberto", "DOCUMENT_SIGNED": "assinado",
           "DOCUMENT_RECIPIENT_COMPLETED": "participante_concluiu", "DOCUMENT_COMPLETED": "concluido",
           "DOCUMENT_REJECTED": "recusado", "DOCUMENT_CANCELLED": "cancelado"}
TRANSPORTE: dict = {}  # testes injetam httpx.MockTransport aqui


class ErroAssinatura(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _integracao(db: Session, esc_id: uuid.UUID) -> Integracao | None:
    return db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id, Integracao.codigo == "assinatura")).scalar()


def _pdf_da_minuta(db: Session, m: Minuta) -> VersaoDocumento:
    if m.documento_id is None:
        raise ErroAssinatura("A minuta aprovada não tem documento gerado")
    v = db.execute(select(VersaoDocumento).where(VersaoDocumento.documento_id == m.documento_id,
                                                 VersaoDocumento.tipo_mime == "application/pdf",
                                                 VersaoDocumento.caminho.is_not(None))
                   .order_by(VersaoDocumento.numero.desc()).limit(1)).scalar()
    if v is None:
        raise ErroAssinatura("O documento aprovado não está em PDF (a conversão não estava disponível): "
                             "a assinatura eletrônica exige PDF", 422)
    return v


def _validar_participantes(participantes: list[dict]) -> list[dict]:
    if not participantes:
        raise ErroAssinatura("Inclua pelo menos um participante", 422)
    if len(participantes) > 10:
        raise ErroAssinatura("No máximo 10 participantes por envio", 422)
    vistos, saida = set(), []
    for n, p in enumerate(participantes, start=1):
        nome, email = (p.get("nome") or "").strip(), (p.get("email") or "").strip().lower()
        papel = p.get("papel") or "assinar"
        if len(nome) < 3:
            raise ErroAssinatura(f"Participante {n}: informe o nome completo", 422)
        if not RE_EMAIL.match(email):
            raise ErroAssinatura(f"Participante {n}: e-mail inválido", 422)
        if papel not in documenso.PAPEIS:
            raise ErroAssinatura(f"Participante {n}: papel inválido", 422)
        if email in vistos:
            raise ErroAssinatura(f"Participante {n}: e-mail repetido", 422)
        vistos.add(email)
        saida.append({"nome": nome[:200], "email": email, "papel": papel, "ordem": int(p.get("ordem") or n),
                      "situacao": "aguardando", "assinado_em": None})
    if not any(p["papel"] == "assinar" for p in saida):
        raise ErroAssinatura("Inclua pelo menos um participante que assina", 422)
    return saida


def preparar(db: Session, ator: auditoria.Ator, m: Minuta, usuario: Usuario, participantes: list[dict],
             mensagem: str | None) -> Assinatura:
    """Monta o pedido (sem enviar). Só para minuta aprovada pelo advogado e já em PDF."""
    if m.situacao != "aprovada":
        raise ErroAssinatura("Só uma minuta aprovada pode ir para assinatura")
    _pdf_da_minuta(db, m)
    ativa = db.execute(select(Assinatura).where(Assinatura.minuta_id == m.id, Assinatura.situacao.in_(
        ("preparada", "enviando", "enviada", "parcial")))).scalar()
    if ativa is not None:
        raise ErroAssinatura("Já existe um pedido de assinatura em andamento para esta minuta")
    a = Assinatura(escritorio_id=m.escritorio_id, minuta_id=m.id, documento_id=m.documento_id,
                   participantes=_validar_participantes(participantes), mensagem=(mensagem or "").strip()[:2000] or None,
                   preparada_por=usuario.id, eventos=[{"evento": "preparada", "em": agora().isoformat()}])
    db.add(a)
    db.flush()
    auditoria.registrar(db, ator, "assinatura.preparar", entidade="assinatura", entidade_id=a.id,
                        alteracoes={"minuta_id": str(m.id), "participantes": len(a.participantes)})
    return a


def cancelar_preparo(db: Session, ator: auditoria.Ator, a: Assinatura) -> Assinatura:
    if a.situacao not in ("preparada", "falha"):
        raise ErroAssinatura("Depois de enviado, o pedido só pode ser cancelado no Documenso")
    a.situacao = "cancelada"
    a.eventos = [*a.eventos, {"evento": "cancelada_no_ejmf", "em": agora().isoformat()}]
    auditoria.registrar(db, ator, "assinatura.cancelar", entidade="assinatura", entidade_id=a.id)
    return a


def enviar(db: Session, ator: auditoria.Ator, a: Assinatura, usuario: Usuario) -> Assinatura:
    """Autorização do envio (permissão assinaturas:enviar, conferida na rota). O envio roda na fila."""
    if a.situacao not in ("preparada", "falha"):
        raise ErroAssinatura("Este pedido já foi enviado")
    if not documenso.configurado():
        raise ErroAssinatura("Assinatura eletrônica aguardando credenciais: configure a chave do Documenso "
                             "(EJMF_DOCUMENSO_TOKEN) para enviar")
    a.situacao, a.autorizada_por, a.erro = "enviando", usuario.id, None
    a.eventos = [*a.eventos, {"evento": "envio_autorizado", "em": agora().isoformat(), "por": usuario.nome}]
    fila.enfileirar(db, a.escritorio_id, "assinatura.enviar", f"assinatura:{a.id}:{len(a.eventos)}",
                    {"assinatura_id": str(a.id)}, max_tentativas=3, criada_por=str(usuario.id))
    auditoria.registrar(db, ator, "assinatura.autorizar_envio", entidade="assinatura", entidade_id=a.id,
                        alteracoes={"participantes": [p["email"] for p in a.participantes]})
    return a


def _paginas(dados: bytes) -> int:
    try:
        from pypdf import PdfReader
        return max(1, len(PdfReader(io.BytesIO(dados), strict=False).pages))
    except Exception:
        return 1


@fila.executor("assinatura.enviar")
def _tarefa_enviar(db: Session, t: Tarefa) -> dict:
    a = db.get(Assinatura, uuid.UUID(t.parametros["assinatura_id"]))
    if a is None or a.situacao != "enviando":
        return {"ignorada": True}
    m = db.get(Minuta, a.minuta_id)
    integ = _integracao(db, a.escritorio_id)
    sistema = auditoria.Ator("sistema", None, "Envio para assinatura", a.escritorio_id)
    try:
        v = _pdf_da_minuta(db, m)
        pdf = armazenamento.caminho(v.caminho).read_bytes()
        con = documenso.ConectorDocumenso(transporte=TRANSPORTE.get("documenso"))
        if not a.id_externo:  # numa nova tentativa não cria um segundo envelope
            a.id_externo = con.criar_envelope(titulo=m.titulo, pdf=pdf, nome_arquivo=v.nome_arquivo or "documento.pdf",
                                              participantes=a.participantes, paginas=_paginas(pdf), id_externo=str(a.id),
                                              assunto=f"Assinatura: {m.titulo}", mensagem=a.mensagem)
            db.commit()
        con.distribuir(a.id_externo)
    except (CredencialAusente, CredencialRecusada) as e:
        a.situacao, a.erro = "falha", str(e)
        if integ:
            integ.estado, integ.ultimo_erro = "aguardando_credenciais", str(e)
        db.commit()
        raise
    except Exception as e:
        if t.tentativas >= t.max_tentativas or not getattr(e, "transitorio", True):
            a.situacao = "falha"
        a.erro = str(e)[:500]
        if integ:
            integ.ultimo_erro, integ.ultima_execucao_em = str(e)[:500], agora()
        db.commit()
        raise
    a.situacao, a.enviada_em, a.erro = "enviada", agora(), None
    a.participantes = [{**p, "situacao": "enviado"} for p in a.participantes]
    a.eventos = [*a.eventos, {"evento": "enviado", "em": agora().isoformat()}]
    if integ:
        integ.ultima_execucao_em = integ.ultimo_sucesso_em = agora()
        integ.ultimo_erro = None
        if integ.estado in ("aguardando_credenciais", "nao_iniciada", "em_desenvolvimento"):
            integ.estado = "ambiente_testes"
    auditoria.registrar(db, sistema, "assinatura.enviada", entidade="assinatura", entidade_id=a.id, origem="worker",
                        alteracoes={"id_externo": a.id_externo})
    if m.atendimento_id:
        at = db.get(Atendimento, m.atendimento_id)
        if at is not None and at.etapa == "contrato_preparado":
            from app.servicos import atendimentos
            atendimentos._etapa(db, sistema, at, "assinatura_pendente", motivo="Enviado para assinatura eletrônica")
    return {"id_externo": a.id_externo}


def _localizar(db: Session, esc_id: uuid.UUID, carga: dict) -> Assinatura | None:
    externo = carga.get("externalId")
    if externo:
        try:
            a = db.get(Assinatura, uuid.UUID(str(externo)))
        except ValueError:
            a = None
        if a is not None and a.escritorio_id == esc_id:
            return a
    for chave in ("envelopeId", "id"):
        if carga.get(chave) is not None:
            a = db.execute(select(Assinatura).where(Assinatura.escritorio_id == esc_id, Assinatura.provedor == "documenso",
                                                    Assinatura.id_externo == str(carga[chave]))).scalar()
            if a is not None:
                return a
    return None


def receber_webhook(db: Session, esc_id: uuid.UUID, dados: dict) -> Assinatura | None:
    """Aplica um evento do Documenso. O segredo já foi conferido na rota. Eventos desconhecidos são ignorados."""
    integ = _integracao(db, esc_id)
    if integ:
        integ.ultima_execucao_em = agora()
        if integ.estado == "aguardando_credenciais" and documenso.configurado():
            integ.estado = "ambiente_testes"
    evento = str(dados.get("event") or "")
    carga = dados.get("payload") if isinstance(dados.get("payload"), dict) else {}
    if evento not in EVENTOS:
        return None
    a = _localizar(db, esc_id, carga)
    if a is None:
        return None
    por_email = {str(r.get("email") or "").lower(): r for r in carga.get("recipients") or [] if isinstance(r, dict)}
    partes = []
    for p in a.participantes:
        r = por_email.get(p["email"])
        if r:
            st = str(r.get("signingStatus") or "").upper()
            if st == "SIGNED":
                p = {**p, "situacao": "assinou", "assinado_em": r.get("signedAt") or p.get("assinado_em")}
            elif st == "REJECTED":
                p = {**p, "situacao": "recusou"}
            elif str(r.get("readStatus") or "").upper() == "OPENED" and p.get("situacao") in ("aguardando", "enviado"):
                p = {**p, "situacao": "abriu"}
        partes.append(p)
    a.participantes = partes
    a.eventos = [*a.eventos, {"evento": EVENTOS[evento], "em": agora().isoformat(),
                              "data_provedor": dados.get("createdAt")}][-200:]
    antes = a.situacao
    if evento == "DOCUMENT_COMPLETED":
        a.situacao, a.concluida_em = "concluida", agora()
    elif evento == "DOCUMENT_REJECTED":
        a.situacao = "recusada"
    elif evento == "DOCUMENT_CANCELLED":
        a.situacao = "cancelada"
    elif a.situacao in ("enviando", "enviada", "parcial"):
        assinaram = sum(1 for p in partes if p["situacao"] == "assinou")
        a.situacao = "parcial" if assinaram else "enviada"
    auditoria.registrar(db, auditoria.Ator("sistema", None, "Documenso", esc_id), "assinatura.evento",
                        entidade="assinatura", entidade_id=a.id, origem="webhook",
                        alteracoes={"evento": evento, "situacao": [antes, a.situacao]})
    if a.situacao != antes and a.situacao in ("concluida", "recusada", "cancelada"):
        from app.servicos import notificacoes
        m = db.get(Minuta, a.minuta_id)
        texto = {"concluida": "Todos assinaram. Baixe o documento assinado no Documenso e anexe-o como nova versão.",
                 "recusada": "Um participante recusou a assinatura.", "cancelada": "O envelope foi cancelado no Documenso."}
        notificacoes.notificar(db, esc_id, "assinaturas:enviar", f"Assinatura {SITUACOES[a.situacao].lower()}: {m.titulo}",
                               texto=texto[a.situacao], link=f"/painel/minutas/{m.id}",
                               nivel="alerta" if a.situacao != "concluida" else "info", chave=f"assinatura:{a.id}:{a.situacao}")
    return a


def listar(db: Session, m: Minuta) -> list[Assinatura]:
    return list(db.execute(select(Assinatura).where(Assinatura.minuta_id == m.id).order_by(Assinatura.criado_em.desc())).scalars())


def como_json(a: Assinatura, nomes: dict | None = None) -> dict:
    nomes = nomes or {}
    return {"id": str(a.id), "minuta_id": str(a.minuta_id), "documento_id": str(a.documento_id) if a.documento_id else None,
            "provedor": a.provedor, "id_externo": a.id_externo, "situacao": a.situacao,
            "situacao_rotulo": SITUACOES.get(a.situacao, a.situacao), "participantes": a.participantes,
            "eventos": a.eventos, "mensagem": a.mensagem, "preparada_por": nomes.get(a.preparada_por),
            "autorizada_por": nomes.get(a.autorizada_por), "enviada_em": a.enviada_em, "concluida_em": a.concluida_em,
            "erro": a.erro, "criado_em": a.criado_em}


def disponivel() -> dict:
    return {"configurado": documenso.configurado(), "provedor": "Documenso",
            "aviso": None if documenso.configurado() else
            "Assinatura eletrônica aguardando credenciais: a chave do Documenso não está configurada neste servidor."}

