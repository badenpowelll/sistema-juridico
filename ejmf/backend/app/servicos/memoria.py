"""Memória permanente do escritório: decisões, orientações, preferências e fatos confirmados.

Regras:
- só o que uma pessoa registra (ou confirma) vale como memória; sugestão de IA ou extraída de documento fica
  "a confirmar", fora da pesquisa, até alguém conferir — resposta de IA nunca vira fato sozinha;
- correção não apaga: cria uma memória nova e a anterior fica "substituída", com o vínculo;
- exclusão controlada: exige permissão e motivo, apaga o conteúdo e mantém só o registro de que existiu (auditoria);
- memória de cliente ou processo só aparece no escopo desse cliente ou processo.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modelos import Cliente, Departamento, Memoria, Parte, Processo, Usuario
from app.servicos import auditoria, conhecimento, notificacoes

ROTULOS_TIPO = {"decisao": "Decisão", "orientacao": "Orientação", "preferencia": "Preferência", "fato": "Fato confirmado"}
ROTULOS_SITUACAO = {"a_confirmar": "A confirmar", "confirmada": "Confirmada", "substituida": "Substituída",
                    "excluida": "Excluída"}


class ErroMemoria(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _validar(db: Session, esc_id: uuid.UUID, d: dict) -> None:
    if "tipo" in d and d["tipo"] not in ROTULOS_TIPO:
        raise ErroMemoria("Tipo inválido", 422)
    for modelo, k, rot in ((Cliente, "cliente_id", "Cliente"), (Processo, "processo_id", "Processo"),
                           (Departamento, "departamento_id", "Departamento")):
        if d.get(k):
            o = db.get(modelo, d[k])
            if o is None or o.escritorio_id != esc_id:
                raise ErroMemoria(f"{rot} não encontrado", 404)
    if d.get("processo_id") and d.get("cliente_id"):
        if not db.execute(select(Parte.id).where(Parte.processo_id == d["processo_id"],
                                                         Parte.cliente_id == d["cliente_id"])).first():
            raise ErroMemoria("O cliente não é parte desse processo", 422)
    if len((d.get("titulo") or "x" * 3).strip()) < 3 or ("texto" in d and len((d["texto"] or "").strip()) < 5):
        raise ErroMemoria("Escreva o título e o texto da memória", 422)


def obter(db: Session, esc_id: uuid.UUID, mid: uuid.UUID) -> Memoria:
    m = db.get(Memoria, mid)
    if m is None or m.escritorio_id != esc_id:
        raise ErroMemoria("Memória não encontrada", 404)
    return m


def registrar(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario | None, dados: dict,
              origem: str = "pessoa") -> Memoria:
    if origem not in ("pessoa", "documento", "sugestao_ia"):
        raise ErroMemoria("Origem inválida", 422)
    _validar(db, esc_id, dados)
    confirmada = origem == "pessoa" and usuario is not None
    m = Memoria(escritorio_id=esc_id, origem=origem, criado_por=usuario.id if usuario else None,
                situacao="confirmada" if confirmada else "a_confirmar",
                confirmada_por=usuario.id if confirmada else None, confirmada_em=agora() if confirmada else None,
                **{k: (v.strip() if isinstance(v, str) else v) for k, v in dados.items()})
    db.add(m)
    db.flush()
    conhecimento.sincronizar_memoria(db, m)
    auditoria.registrar(db, ator, "memoria.registrar", entidade="memoria", entidade_id=m.id,
                        alteracoes={"tipo": m.tipo, "origem": origem, "situacao": m.situacao,
                                    "cliente_id": str(m.cliente_id) if m.cliente_id else None})
    if not confirmada:
        notificacoes.notificar(db, esc_id, "memoria:confirmar", f"Memória a confirmar: {m.titulo}",
                               texto="Sugerida automaticamente. Só vale depois de conferida por uma pessoa.",
                               link=f"/painel/memoria?id={m.id}", chave=f"memoria:{m.id}")
    return m


def confirmar(db: Session, ator: auditoria.Ator, m: Memoria, usuario: Usuario, texto: str | None = None) -> Memoria:
    if m.situacao != "a_confirmar":
        raise ErroMemoria("Esta memória não está aguardando confirmação", 409)
    if texto is not None:
        if len(texto.strip()) < 5:
            raise ErroMemoria("Texto curto demais", 422)
        m.texto = texto.strip()
    m.situacao, m.confirmada_por, m.confirmada_em = "confirmada", usuario.id, agora()
    conhecimento.sincronizar_memoria(db, m)
    auditoria.registrar(db, ator, "memoria.confirmar", entidade="memoria", entidade_id=m.id,
                        alteracoes={"editada": texto is not None})
    return m


def corrigir(db: Session, ator: auditoria.Ator, m: Memoria, usuario: Usuario, titulo: str | None, texto: str,
             motivo: str) -> Memoria:
    if m.situacao != "confirmada":
        raise ErroMemoria("Só memória confirmada pode ser corrigida", 409)
    if len((motivo or "").strip()) < 5:
        raise ErroMemoria("Explique a correção", 422)
    nova = registrar(db, ator, m.escritorio_id, usuario,
                     {"tipo": m.tipo, "titulo": (titulo or m.titulo), "texto": texto, "cliente_id": m.cliente_id,
                      "processo_id": m.processo_id, "departamento_id": m.departamento_id,
                      "referencia": f"Correção de memória anterior: {motivo.strip()}"[:500]})
    m.situacao, m.substituida_por = "substituida", nova.id
    conhecimento.sincronizar_memoria(db, m)
    auditoria.registrar(db, ator, "memoria.corrigir", entidade="memoria", entidade_id=m.id,
                        alteracoes={"nova": str(nova.id), "motivo": motivo.strip()})
    return nova


def excluir(db: Session, ator: auditoria.Ator, m: Memoria, motivo: str) -> Memoria:
    if m.situacao == "excluida":
        raise ErroMemoria("Memória já excluída", 409)
    if len((motivo or "").strip()) < 5:
        raise ErroMemoria("Informe o motivo da exclusão", 422)
    m.situacao, m.motivo_exclusao = "excluida", motivo.strip()
    m.titulo, m.texto, m.referencia = "(memória excluída)", f"Conteúdo excluído em {agora():%d/%m/%Y}.", None
    conhecimento.sincronizar_memoria(db, m)
    auditoria.registrar(db, ator, "memoria.excluir", entidade="memoria", entidade_id=m.id,
                        alteracoes={"motivo": motivo.strip()})
    return m


def listar(db: Session, esc_id: uuid.UUID, *, cliente_id: uuid.UUID | None = None, processo_id: uuid.UUID | None = None,
           situacao: str | None = None, tipo: str | None = None, q: str | None = None, so_gerais: bool = False) -> list[Memoria]:
    conds = [Memoria.escritorio_id == esc_id]
    if situacao:
        conds.append(Memoria.situacao == situacao)
    else:
        conds.append(Memoria.situacao.in_(("confirmada", "a_confirmar")))
    if tipo:
        conds.append(Memoria.tipo == tipo)
    if processo_id:
        conds.append(Memoria.processo_id == processo_id)
    elif cliente_id:
        conds.append(Memoria.cliente_id == cliente_id)
    elif so_gerais:
        conds.append(Memoria.cliente_id.is_(None))
        conds.append(Memoria.processo_id.is_(None))
    if q and q.strip():
        t = f"%{q.strip()}%"
        conds.append(or_(Memoria.titulo.ilike(t), Memoria.texto.ilike(t)))
    return list(db.execute(select(Memoria).where(*conds).order_by(Memoria.atualizado_em.desc()).limit(500)).scalars())


def como_json(m: Memoria, nomes: dict | None = None) -> dict:
    nomes = nomes or {}
    return {"id": str(m.id), "tipo": m.tipo, "tipo_rotulo": ROTULOS_TIPO.get(m.tipo, m.tipo), "titulo": m.titulo,
            "texto": m.texto, "cliente_id": str(m.cliente_id) if m.cliente_id else None,
            "processo_id": str(m.processo_id) if m.processo_id else None,
            "departamento_id": str(m.departamento_id) if m.departamento_id else None, "origem": m.origem,
            "referencia": m.referencia, "situacao": m.situacao, "situacao_rotulo": ROTULOS_SITUACAO.get(m.situacao),
            "confirmada_por": nomes.get(m.confirmada_por), "confirmada_em": m.confirmada_em,
            "substituida_por": str(m.substituida_por) if m.substituida_por else None,
            "motivo_exclusao": m.motivo_exclusao, "criado_por": nomes.get(m.criado_por), "criado_em": m.criado_em,
            "atualizado_em": m.atualizado_em}


def exportar(db: Session, esc_id: uuid.UUID, cliente_id: uuid.UUID | None = None) -> dict:
    """Exporta as memórias confirmadas (do cliente ou só as gerais do escritório) com histórico de correções."""
    conds = [Memoria.escritorio_id == esc_id, Memoria.situacao.in_(("confirmada", "substituida"))]
    conds.append(Memoria.cliente_id == cliente_id if cliente_id else Memoria.cliente_id.is_(None))
    ms = db.execute(select(Memoria).where(*conds).order_by(Memoria.criado_em)).scalars().all()
    nomes = dict(db.execute(select(Usuario.id, Usuario.nome).where(Usuario.escritorio_id == esc_id)).all())
    return {"gerado_em": agora().isoformat(), "cliente_id": str(cliente_id) if cliente_id else None,
            "formato": "ejmf-memoria-v1", "memorias": [como_json(m, nomes) for m in ms]}
