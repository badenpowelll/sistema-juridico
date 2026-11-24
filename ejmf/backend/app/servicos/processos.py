"""Processos, partes, movimentações e linha do tempo (prontuário digital)."""
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modelos import (
    POLOS, STATUS_PROCESSO, Auditoria, Cliente, Departamento, Movimentacao, Parte, Processo, Publicacao, Tribunal,
)
from app.servicos import auditoria
from app.servicos.identificadores import NumeroInvalido, analisar_cnj, normalizar_texto
from app.servicos.tribunais import catalogo as catalogo_tribunais

_FORTALEZA = ZoneInfo("America/Fortaleza")

ROTULO_STATUS = {"ativo": "Ativo", "suspenso": "Suspenso", "arquivado": "Arquivado", "encerrado": "Encerrado"}


class ProcessoDuplicado(ValueError):
    def __init__(self, existente: Processo):
        super().__init__(f"O processo {existente.numero_formatado} já está cadastrado")
        self.existente = existente


_SIGLAS = {t["codigo"]: t["sigla"] for t in catalogo_tribunais()}


def atualizar_texto_busca(p: Processo, sigla_tribunal: str | None = None) -> None:
    if sigla_tribunal is None and p.tribunal_codigo:
        sigla_tribunal = _SIGLAS.get(p.tribunal_codigo)
    partes = " ".join(pt.nome for pt in p.partes)
    assuntos = " ".join(str(a) for a in (p.assuntos or []))
    p.texto_busca = normalizar_texto(" ".join(filter(None, [
        p.numero_formatado, p.numero, sigla_tribunal, p.classe, assuntos, p.unidade, partes])))


def tribunais_por_codigo(db: Session) -> dict[str, Tribunal]:
    return {t.codigo: t for t in db.execute(select(Tribunal)).scalars()}


def por_numero(db: Session, escritorio_id: uuid.UUID, numero: str) -> Processo | None:
    n = analisar_cnj(numero)
    return db.execute(select(Processo).where(Processo.escritorio_id == escritorio_id,
                                             Processo.numero == n.digitos)).scalar()


def criar(db: Session, ator: auditoria.Ator, escritorio_id: uuid.UUID, *, numero: str,
          classe: str | None = None, assuntos: list[str] | None = None, unidade: str | None = None,
          status: str = "ativo", departamento_id: uuid.UUID | None = None, valor_causa: Decimal | None = None,
          data_distribuicao: date | None = None, observacoes: str | None = None,
          partes: list[dict] | None = None, origem: str = "manual", importacao_id: uuid.UUID | None = None,
          tribunais: dict[str, Tribunal] | None = None, auditar: bool = True) -> Processo:
    n = analisar_cnj(numero)  # NumeroInvalido
    if status not in STATUS_PROCESSO:
        raise ValueError("Situação inválida")
    existente = db.execute(select(Processo).where(Processo.escritorio_id == escritorio_id,
                                                  Processo.numero == n.digitos)).scalar()
    if existente:
        raise ProcessoDuplicado(existente)
    tribs = tribunais if tribunais is not None else tribunais_por_codigo(db)
    trib = tribs.get(n.codigo_tribunal)
    p = Processo(escritorio_id=escritorio_id, numero=n.digitos, numero_formatado=n.formatado,
                 tribunal_codigo=trib.codigo if trib else None, departamento_id=departamento_id,
                 classe=(classe or None), assuntos=[a for a in (assuntos or []) if a], unidade=(unidade or None),
                 status=status, valor_causa=valor_causa, data_distribuicao=data_distribuicao,
                 observacoes=observacoes or None, origem=origem, importacao_id=importacao_id)
    for pt in partes or []:
        p.partes.append(_nova_parte(escritorio_id, pt))
    atualizar_texto_busca(p, trib.sigla if trib else None)
    db.add(p)
    db.flush()
    if auditar:
        auditoria.registrar(db, ator, "processo.criar", entidade="processo", entidade_id=p.id, origem=origem,
                            alteracoes={"numero": p.numero_formatado, "partes": len(p.partes)})
    return p


def _nova_parte(escritorio_id: uuid.UUID, dados: dict) -> Parte:
    nome = " ".join(str(dados.get("nome") or "").split())
    if len(nome) < 2:
        raise ValueError("Nome da parte é obrigatório")
    polo = dados.get("polo") or "outro"
    if polo not in POLOS:
        raise ValueError("Polo inválido")
    return Parte(escritorio_id=escritorio_id, nome=nome, polo=polo, papel=dados.get("papel") or None,
                 cliente_id=dados.get("cliente_id"), representado=bool(dados.get("cliente_id")) or bool(dados.get("representado")))


def adicionar_parte(db: Session, ator: auditoria.Ator, p: Processo, dados: dict) -> Parte:
    parte = _nova_parte(p.escritorio_id, dados)
    p.partes.append(parte)
    atualizar_texto_busca(p)
    p.atualizado_em = datetime.now(timezone.utc)
    db.flush()
    auditoria.registrar(db, ator, "processo.parte.adicionar", entidade="processo", entidade_id=p.id,
                        alteracoes={"parte": parte.nome, "polo": parte.polo,
                                    "cliente_id": str(parte.cliente_id) if parte.cliente_id else None})
    return parte


def remover_parte(db: Session, ator: auditoria.Ator, p: Processo, parte_id: uuid.UUID) -> None:
    parte = next((x for x in p.partes if x.id == parte_id), None)
    if parte is None:
        raise LookupError("Parte não encontrada")
    p.partes.remove(parte)
    atualizar_texto_busca(p)
    p.atualizado_em = datetime.now(timezone.utc)
    db.flush()
    auditoria.registrar(db, ator, "processo.parte.remover", entidade="processo", entidade_id=p.id,
                        alteracoes={"parte": parte.nome, "polo": parte.polo})


CAMPOS_EDITAVEIS = ("classe", "assuntos", "unidade", "status", "departamento_id", "valor_causa",
                    "data_distribuicao", "observacoes")


def alterar(db: Session, ator: auditoria.Ator, p: Processo, dados: dict[str, Any], operacao: str = "processo.alterar") -> dict:
    antes, depois = {}, {}
    for campo, valor in dados.items():
        if campo not in CAMPOS_EDITAVEIS:
            continue
        if campo == "status" and valor not in STATUS_PROCESSO:
            raise ValueError("Situação inválida")
        atual = getattr(p, campo)
        if atual != valor:
            antes[campo], depois[campo] = atual, valor
            setattr(p, campo, valor)
    if depois:
        atualizar_texto_busca(p)
        p.atualizado_em = datetime.now(timezone.utc)
        db.flush()
        auditoria.registrar(db, ator, operacao, entidade="processo", entidade_id=p.id,
                            alteracoes={"antes": antes, "depois": depois})
    return depois


def registrar_movimentacao(db: Session, ator: auditoria.Ator, p: Processo, *, descricao: str, tipo: str = "anotacao",
                           ocorrido_em: datetime | None = None, origem: str = "manual", autor_id: uuid.UUID | None = None,
                           codigo_tpu: int | None = None) -> Movimentacao:
    descricao = (descricao or "").strip()
    if not descricao:
        raise ValueError("Descrição obrigatória")
    m = Movimentacao(escritorio_id=p.escritorio_id, processo_id=p.id, tipo=tipo, descricao=descricao,
                     ocorrido_em=ocorrido_em or datetime.now(timezone.utc), origem=origem, autor_id=autor_id,
                     codigo_tpu=codigo_tpu)
    db.add(m)
    if tipo == "movimentacao" and (p.ultima_movimentacao_em is None or m.ocorrido_em > p.ultima_movimentacao_em):
        p.ultima_movimentacao_em = m.ocorrido_em
    p.atualizado_em = datetime.now(timezone.utc)
    db.flush()
    auditoria.registrar(db, ator, f"processo.{tipo}.registrar", entidade="processo", entidade_id=p.id,
                        alteracoes={"movimentacao_id": str(m.id), "ocorrido_em": m.ocorrido_em})
    return m


def linha_do_tempo(db: Session, p: Processo, limite: int = 100, antes_de: datetime | None = None) -> list[dict]:
    """Movimentações, anotações e eventos de auditoria do processo, em ordem cronológica decrescente."""
    q = select(Movimentacao).where(Movimentacao.processo_id == p.id)
    if antes_de:
        q = q.where(Movimentacao.ocorrido_em < antes_de)
    movs = db.execute(q.order_by(Movimentacao.ocorrido_em.desc()).limit(limite)).scalars().all()
    qa = select(Auditoria).where(Auditoria.entidade == "processo", Auditoria.entidade_id == str(p.id),
                                 Auditoria.operacao.notlike("processo.%.registrar"))
    if antes_de:
        qa = qa.where(Auditoria.ocorrido_em < antes_de)
    auds = db.execute(qa.order_by(Auditoria.ocorrido_em.desc()).limit(limite)).scalars().all()
    itens = [{"tipo": m.tipo, "ocorrido_em": m.ocorrido_em, "descricao": m.descricao, "origem": m.origem,
              "codigo_tpu": m.codigo_tpu, "id": str(m.id)} for m in movs]
    itens += [{"tipo": "historico", "ocorrido_em": a.ocorrido_em, "descricao": _descrever(a), "origem": a.origem or "sistema",
               "autor": a.ator_nome, "id": f"a{a.id}"} for a in auds]
    qp = select(Publicacao).where(Publicacao.processo_id == p.id, Publicacao.situacao != "duplicada")
    pubs = db.execute(qp.order_by(Publicacao.capturado_em.desc()).limit(limite)).scalars().all()
    for pub in pubs:
        quando = (datetime.combine(pub.disponibilizado_em, time(12, 0), tzinfo=_FORTALEZA)
                  if pub.disponibilizado_em else pub.capturado_em)
        if antes_de and quando >= antes_de:
            continue
        resumo = (pub.classificacao or {}).get("resumo") or pub.texto[:200]
        itens.append({"tipo": "publicacao", "ocorrido_em": quando, "id": f"p{pub.id}", "origem": pub.fonte,
                      "descricao": f"{'[SIMULADO] ' if pub.simulado else ''}{resumo} — disponibilizada no "
                                   f"{pub.tribunal_sigla or 'diário'}", "publicacao_id": str(pub.id)})
    itens.sort(key=lambda x: x["ocorrido_em"], reverse=True)
    return itens[:limite]


_DESCRICOES = {
    "processo.criar": "Processo cadastrado", "processo.alterar": "Dados do processo alterados",
    "processo.lote": "Alterado por operação em lote", "processo.parte.adicionar": "Parte adicionada",
    "processo.parte.remover": "Parte removida", "processo.importar": "Processo importado",
}


def _descrever(a: Auditoria) -> str:
    base = _DESCRICOES.get(a.operacao, a.operacao)
    alt = a.alteracoes or {}
    if a.operacao in ("processo.alterar", "processo.lote") and isinstance(alt.get("depois"), dict):
        base += ": " + ", ".join(sorted(alt["depois"]))
    if a.operacao.startswith("processo.parte.") and alt.get("parte"):
        base += f": {alt['parte']} ({alt.get('polo')})"
    return base


def como_json(p: Processo, tribunais: dict[str, Tribunal] | None = None, departamentos: dict | None = None,
              completo: bool = False) -> dict[str, Any]:
    t = (tribunais or {}).get(p.tribunal_codigo) if p.tribunal_codigo else None
    d = (departamentos or {}).get(p.departamento_id) if p.departamento_id else None
    base = {
        "id": str(p.id), "numero": p.numero_formatado, "numero_digitos": p.numero,
        "tribunal": {"codigo": t.codigo, "sigla": t.sigla, "nome": t.nome} if t else None,
        "departamento": {"id": str(d.id), "nome": d.nome} if d else None,
        "classe": p.classe, "unidade": p.unidade, "status": p.status, "status_rotulo": ROTULO_STATUS[p.status],
        "origem": p.origem, "ultima_movimentacao_em": p.ultima_movimentacao_em, "atualizado_em": p.atualizado_em,
        "clientes": [{"id": str(pt.cliente_id), "nome": pt.nome} for pt in p.partes if pt.cliente_id],
    }
    if completo:
        base.update({
            "assuntos": p.assuntos, "portal_visivel": p.portal_visivel, "valor_causa": str(p.valor_causa) if p.valor_causa is not None else None,
            "data_distribuicao": p.data_distribuicao, "observacoes": p.observacoes, "criado_em": p.criado_em,
            "importacao_id": str(p.importacao_id) if p.importacao_id else None,
            "partes": [{"id": str(pt.id), "nome": pt.nome, "polo": pt.polo, "papel": pt.papel,
                        "cliente_id": str(pt.cliente_id) if pt.cliente_id else None,
                        "representado": pt.representado} for pt in p.partes],
        })
    return base


def filtrar(escritorio_id: uuid.UUID, *, q: str | None = None, status: str | None = None,
            tribunal: str | None = None, departamento_id: uuid.UUID | None = None,
            cliente_id: uuid.UUID | None = None, importacao_id: uuid.UUID | None = None):
    cond = [Processo.escritorio_id == escritorio_id]
    if status:
        cond.append(Processo.status == status)
    if tribunal:
        cond.append(Processo.tribunal_codigo == tribunal)
    if departamento_id:
        cond.append(Processo.departamento_id == departamento_id)
    if importacao_id:
        cond.append(Processo.importacao_id == importacao_id)
    if cliente_id:
        cond.append(Processo.id.in_(select(Parte.processo_id).where(Parte.cliente_id == cliente_id)))
    if q:
        cond.append(condicao_busca(q))
    return and_(*cond)


def condicao_busca(q: str):
    """Busca textual: dígitos do número (trigram), termos sem acento (tsvector por prefixo) ou trecho (trigram)."""
    digitos = "".join(c for c in q if c.isdigit())
    termos = [t for t in normalizar_texto(q).replace(".", " ").replace("-", " ").split() if t]
    alternativas = []
    if len(digitos) >= 7:
        alternativas.append(Processo.numero.contains(digitos))
    if termos:
        consulta = " & ".join(_lexema(t) + ":*" for t in termos)
        alternativas.append(Processo.busca.op("@@")(func.to_tsquery("simple", consulta)))
        alternativas.append(Processo.texto_busca.contains(normalizar_texto(q)))
    return or_(*alternativas) if alternativas else Processo.id.is_(None)


def _lexema(t: str) -> str:
    return "".join(c for c in t if c.isalnum()) or "_"


def resumo(db: Session, escritorio_id: uuid.UUID) -> dict[str, Any]:
    por_status = dict(db.execute(select(Processo.status, func.count()).where(Processo.escritorio_id == escritorio_id)
                                 .group_by(Processo.status)).all())
    por_tribunal = db.execute(select(Tribunal.sigla, func.count()).join(Processo, Processo.tribunal_codigo == Tribunal.codigo)
                              .where(Processo.escritorio_id == escritorio_id).group_by(Tribunal.sigla)
                              .order_by(func.count().desc()).limit(8)).all()
    por_dep = db.execute(select(Departamento.nome, func.count()).join(Processo, Processo.departamento_id == Departamento.id)
                         .where(Processo.escritorio_id == escritorio_id).group_by(Departamento.nome)
                         .order_by(func.count().desc()).limit(8)).all()
    return {"total": sum(por_status.values()), "por_status": por_status,
            "por_tribunal": [{"sigla": s, "total": n} for s, n in por_tribunal],
            "por_departamento": [{"nome": s, "total": n} for s, n in por_dep],
            "clientes": db.execute(select(func.count()).select_from(Cliente).where(Cliente.escritorio_id == escritorio_id)).scalar()}


__all__ = ["NumeroInvalido", "ProcessoDuplicado", "criar", "alterar", "adicionar_parte", "remover_parte",
           "registrar_movimentacao", "linha_do_tempo", "como_json", "filtrar", "condicao_busca", "resumo",
           "tribunais_por_codigo", "por_numero", "atualizar_texto_busca"]
